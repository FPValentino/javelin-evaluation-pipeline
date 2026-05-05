import os
import re
import json
from unidiff import PatchSet


def _is_executable(line_text):
    """Return True if a Java source line would be instrumented by JaCoCo."""
    stripped = line_text.strip()
    if not stripped:
        return False
    if stripped in ('{', '}', '};', '{}'):
        return False
    if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*') or stripped.startswith('*/'):
        return False
    if re.match(r'^@\w+(\(.*\))?\s*$', stripped):
        return False
    return True


def _is_interface_file(patched_file, hunk):
    """Heuristic: check if the file is a Java interface by looking for a
    top-level interface declaration (e.g. 'public interface Foo')."""
    for line in hunk:
        text = line.value if hasattr(line, 'value') else ''
        if re.match(r'^(public\s+)?interface\s+\w+', text.strip()):
            return True
    return False

def extract_faulty_lines(patch_folder):
    """
    Reads a folder of patch files and automatically generates the 
    ground_truth.json file for the Javelin evaluation script.
    """
    print(f"Scanning Defects4J patches in: {patch_folder}...\n")
    ground_truth = {}
    warnings = []

    for filename in os.listdir(patch_folder):
        # Skip anything that isn't a Defects4J patch
        if not filename.startswith("Defects4J"):
            continue
            
        if not filename.endswith(".patch") and not filename.endswith(".diff"):
            continue
            
        bug_id = filename.replace(".patch", "").replace(".diff", "")
        filepath = os.path.join(patch_folder, filename)
        
        try:
            # 1. Read the raw text, ignoring encoding errors
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                raw_lines = f.readlines()
                
            # 2. PRE-FILTER: Strip out binary garbage and non-java files
            cleaned_lines = []
            keep_file = True 
            
            for line in raw_lines:
                # Detect when the diff moves to a new file
                if line.startswith("diff ") or line.startswith("--- a/") or line.startswith("+++ b/"):
                    keep_file = ".java" in line
                    
                if keep_file:
                    # Unidiff strictly crashes on this git marker, so we delete it
                    if line.startswith("\\ No newline"):
                        continue
                    cleaned_lines.append(line)
            
            patch_string = "".join(cleaned_lines)
            
            # If there were no .java files changed in this patch, skip it
            if not patch_string.strip():
                continue

            # 3. Parse the cleaned, Java-only string
            patch = PatchSet.from_string(patch_string)
            faults_for_this_bug = []
            
            for patched_file in patch:
                # Strip quotes and normalize slashes
                clean_path = patched_file.path.replace('"', '').replace("'", "").replace('\\', '/')

                # Skip test files
                lower_path = clean_path.lower()
                filename_no_ext = lower_path.split("/")[-1].replace(".java", "")
                is_test_path = ("src/test" in lower_path or "/test/" in lower_path
                                or "/tests/" in lower_path or "focused-test" in lower_path)
                is_test_file = (filename_no_ext.startswith("test") or filename_no_ext.endswith("test")
                                or filename_no_ext.endswith("tests"))
                if is_test_path or is_test_file or not clean_path.endswith(".java"):
                    continue

                if clean_path.startswith("a/") or clean_path.startswith("b/"):
                    clean_path = clean_path[2:]

                source_roots = [
                    "src/main/java/", "src/test/java/", "src/java/",
                    "source/main/java/", "src/", "source/"
                ]

                class_name = clean_path
                for root in source_roots:
                    if root in clean_path:
                        class_name = clean_path.split(root)[-1]
                        break

                class_name = class_name.replace('/', '.').replace('.java', '')

                for hunk in patched_file:
                    # Skip interface files — JaCoCo cannot instrument them
                    if _is_interface_file(patched_file, hunk):
                        warnings.append(f"  ⚠ {bug_id}: Skipping interface hunk in {class_name} (not instrumentable by JaCoCo)")
                        continue

                    hunk_has_removals = any(line.is_removed for line in hunk)

                    if hunk_has_removals:
                        # Removal/modification bug: collect removed lines directly
                        for line in hunk:
                            if line.is_removed:
                                faults_for_this_bug.append([class_name, line.source_line_no])
                    else:
                        # Omission bug: use first executable line after the insertion point
                        pre_context = []
                        post_context = []
                        seen_addition = False
                        for line in hunk:
                            if line.is_added:
                                seen_addition = True
                                continue
                            if line.is_context and line.source_line_no is not None:
                                if seen_addition:
                                    post_context.append((line.source_line_no, line.value))
                                else:
                                    pre_context.append((line.source_line_no, line.value))

                        fault_line = None
                        # Prefer first executable line after the insertion
                        for line_no, line_text in post_context:
                            if _is_executable(line_text):
                                fault_line = line_no
                                break
                        # Fallback: last executable line before the insertion
                        if fault_line is None:
                            for line_no, line_text in reversed(pre_context):
                                if _is_executable(line_text):
                                    fault_line = line_no
                                    break
                        # Ultimate fallback: last context line or hunk start
                        if fault_line is None:
                            if pre_context:
                                fault_line = pre_context[-1][0]
                            elif post_context:
                                fault_line = post_context[0][0]
                            else:
                                fault_line = max(1, hunk.source_start)

                        faults_for_this_bug.append([class_name, fault_line])
            
            # Remove duplicates and add to dictionary
            if faults_for_this_bug:
                unique_faults = [list(x) for x in set(tuple(x) for x in faults_for_this_bug)]
                ground_truth[bug_id] = unique_faults
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Save exactly what the Evaluation Script expects
    output_file = "ground_truth.json"
    with open(output_file, "w") as f:
        json.dump(ground_truth, f, indent=4)
        
    print(f"\n✅ Extracted {len(ground_truth)} Defects4J bugs.")
    print(f"✅ Ground truth saved securely to '{output_file}'.")
    if warnings:
        print(f"\n⚠ Warnings ({len(warnings)}):")
        for w in warnings:
            print(w)
    print("\nYou may now run the Evaluation Script!")

if __name__ == "__main__":
    wsl_user = input("Enter your WSL Ubuntu username (e.g., ferdinand): ").strip()
    patch_dir = fr"\\wsl.localhost\Ubuntu\home\{wsl_user}\javelin-workspaces\gitbug_patches"
    
    if not os.path.exists(patch_dir):
        print(f"❌ Error: Could not find patches folder at {patch_dir}")
    else:
        extract_faulty_lines(patch_dir)