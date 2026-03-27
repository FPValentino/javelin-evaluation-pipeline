import os
import shutil  # NEW: Library for high-level file operations
import pandas as pd
import numpy as np
import json
import random

def clear_and_recreate_folder(folder_path):
    """Deletes the folder and all its contents if it exists, then creates a fresh one."""
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
    os.makedirs(folder_path, exist_ok=True)

def create_mock_csv(folder, bug_id, faulty_class, faulty_line, fault_rank, total_lines):
    # Create a dataframe with varying file lengths (Complexity)
    data = {
        'FullyQualifiedClass': ['org.example.TargetClass'] * total_lines,
        'LineNumber': np.arange(1, total_lines + 1),
        'Rank': np.arange(1, total_lines + 1),
        'Score': np.linspace(1.0, 0.0, total_lines)
    }
    df = pd.DataFrame(data)
    
    # Inject the fault
    df.loc[fault_rank - 1, 'FullyQualifiedClass'] = faulty_class
    df.loc[fault_rank - 1, 'LineNumber'] = faulty_line
    
    filepath = os.path.join(folder, f"{bug_id}.csv")
    df.to_csv(filepath, index=False)

print("Wiping old data and generating mock bugs with varying complexity...")

# 1. WIPE THE FOLDERS CLEAN FIRST
clear_and_recreate_folder("ochiai_results")
clear_and_recreate_folder("ochiai_ms_results")

# 2. START GENERATION
NUM_BUGS = 70
ground_truth = {}

for i in range(1, NUM_BUGS + 1):
    bug_id = f"bug_{i:04d}"
    faulty_class = f"org.example.Class{i}"
    faulty_line = random.randint(10, 40) 
    total_lines = random.randint(50, 5000) 
    
    # Standard Ochiai baseline
    ochiai_rank = random.randint(1, min(150, total_lines))
    
    # The new, highly realistic distribution
    chance = random.random()
    
    if chance < 0.65:
        # 65% of the time: Algorithms perform almost identically (+/- 2 ranks)
        ms_rank = max(1, ochiai_rank + random.randint(-2, 2))
        
    elif chance < 0.90:
        # 25% of the time: Ochiai-MS successfully mitigates CC! (Improves by 5 to 25 ranks)
        ms_rank = max(1, ochiai_rank - random.randint(5, 25))
        
    else:
        # 10% of the time: Mutation noise causes Ochiai-MS to lose slightly (Drops 1 to 5 ranks)
        ms_rank = min(total_lines, ochiai_rank + random.randint(1, 5))
        
    create_mock_csv("ochiai_results", bug_id, faulty_class, faulty_line, ochiai_rank, total_lines)
    create_mock_csv("ochiai_ms_results", bug_id, faulty_class, faulty_line, ms_rank, total_lines)
    
    ground_truth[bug_id] = [[faulty_class, faulty_line]]

# Save ground truth to a clean JSON file
with open("ground_truth.json", "w") as f:
    json.dump(ground_truth, f, indent=4)

print(f"Success! Generated {NUM_BUGS} bugs. Ground truth saved to 'ground_truth.json'.")