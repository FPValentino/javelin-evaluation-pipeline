import os
import json
from unidiff import PatchSet

def extract_faulty_lines(patch_folder):
    """
    Reads a folder of patch files and automatically generates the 
    ground_truth.json file for the Javelin evaluation script.
    """
    print(f"Scanning patches in: {patch_folder}...\n")
    ground_truth = {}

    for filename in os.listdir(patch_folder):
        if not filename.endswith(".patch") and not filename.endswith(".diff"):
            continue
            
        bug_id = filename.replace(".patch", "").replace(".diff", "")
        filepath = os.path.join(patch_folder, filename)
        
        try:
            patch = PatchSet.from_filename(filepath)
            faults_for_this_bug = []
            
            for patched_file in patch:
                # Strip quotes and normalize slashes
                clean_path = patched_file.path.replace('"', '').replace("'", "").replace('\\', '/')
                
                # Skip test files (Expanded for older Defects4J folder structures)
                lower_path = clean_path.lower()
                if "src/test" in lower_path or "/test/" in lower_path or "/tests/" in lower_path or not clean_path.endswith(".java"):
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
                    hunk_has_removals = any(line.is_removed for line in hunk)
                    
                    # THE FIX: Keep a running tracker of the last valid original line number
                    last_source_line = max(1, hunk.source_start)
                    
                    for line in hunk:
                        # Update our tracker if this line actually existed in the original file
                        if line.source_line_no is not None:
                            last_source_line = line.source_line_no
                            
                        if line.is_removed:
                            # Standard bug: a line was changed or deleted
                            faults_for_this_bug.append([class_name, line.source_line_no])
                        elif not hunk_has_removals and line.is_added:
                            # Omission bug: code was only added. Use the tracker!
                            faults_for_this_bug.append([class_name, last_source_line])
            
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
        
    print(f"\n✅ Extracted {len(ground_truth)} bugs.")
    print(f"✅ Ground truth saved securely to '{output_file}'.")
    print("You may now run the Evaluation Script!")

if __name__ == "__main__":
    patch_dir = r"\\wsl.localhost\Ubuntu\home\paul\javelin-workspaces\gitbug_patches"
    
    if not os.path.exists(patch_dir):
        print(f"Error: Could not find patches folder at {patch_dir}")
    else:
        extract_faulty_lines(patch_dir)
