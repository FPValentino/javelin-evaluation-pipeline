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
                # Skip test files, we only want source code faults
                if "src/test" in patched_file.path or not patched_file.path.endswith(".java"):
                    continue
                
                # ---------------------------------------------------------
                # BULLETPROOF FQCN EXTRACTION (For diverse project layouts)
                # ---------------------------------------------------------
                # Git diffs often start with 'a/' or 'b/', strip that first
                clean_path = patched_file.path
                if clean_path.startswith("a/") or clean_path.startswith("b/"):
                    clean_path = clean_path[2:]
                
                # List of common Java root directories we want to strip away
                source_roots = [
                    "src/main/java/", "src/test/java/", "src/java/", 
                    "source/main/java/", "src/", "source/"
                ]
                
                class_name = clean_path
                for root in source_roots:
                    if root in clean_path:
                        # Split by the root and keep everything after it
                        class_name = clean_path.split(root)[-1]
                        break # Stop at the first match
                
                # Convert the remaining path (e.g., org/jsoup/TextNode.java) into FQCN
                class_name = class_name.replace('/', '.').replace('\\', '.').replace('.java', '')
                # ---------------------------------------------------------
                
                for hunk in patched_file:
                    hunk_has_removals = any(line.is_removed for line in hunk)
                    
                    for line in hunk:
                        if line.is_removed:
                            # Standard bug: a line was changed or deleted
                            faults_for_this_bug.append([class_name, line.source_line_no])
                        elif not hunk_has_removals and line.is_added:
                            # Omission bug: code was only added. Grab the source line right above it.
                            fault_line = max(1, line.source_line_no - 1)
                            faults_for_this_bug.append([class_name, fault_line])
            
            # Remove duplicates and add to dictionary
            if faults_for_this_bug:
                # Convert to tuple for unique set, then back to list
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

# --- Run the extractor ---
# Note: You will need to extract the .patch files from GitBug-Java first.
# Uncomment the line below and point it to your patches folder when ready to run.
# extract_faulty_lines('./gitbug_patches')