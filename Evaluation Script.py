import os
import pandas as pd
import json
from scipy.stats import wilcoxon
from tqdm import tqdm
from collections import defaultdict

def evaluate_algorithm(algorithm_name, folder_path, bug_records):
    exam_scores_dict = {}
    
    # Trackers for Project-Level slicing
    project_scores = defaultdict(list)
    project_hits = defaultdict(lambda: {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0})
    
    # Trackers for Global slicing
    global_hits = {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0}
    
    print(f"\n==========================================")
    print(f" Analyzing {algorithm_name} Results ")
    print(f"==========================================")
    
    bug_ids = list(bug_records.keys())
    
    for bug_id in tqdm(bug_ids, desc=f"Processing {algorithm_name}", unit="bug"):
        filename = f"{bug_id}.csv"
        filepath = os.path.join(folder_path, filename)
        
        if not os.path.exists(filepath):
            continue

        # Dynamically extract project name (e.g., 'iipc-jwarc' from 'iipc-jwarc-a1b2')
        project_name = "-".join(bug_id.split("-")[:-1])
        fault_list = bug_records[bug_id]

        try:
            data_frame = pd.read_csv(filepath)
            total_statements = len(data_frame)
            
            # Strict Average Rank calculation for academic validity
            data_frame['AbsoluteRank'] = data_frame['OchiaiScore'].rank(method='average', ascending=False)
            
            found_ranks = []
            for fault in fault_list:
                faulty_class, faulty_line = fault[0], fault[1]
                fault_row = data_frame[(data_frame['FullyQualifiedClass'] == faulty_class) & 
                                       (data_frame['LineNumber'] == faulty_line)]
                if not fault_row.empty:
                    found_ranks.append(fault_row['AbsoluteRank'].iloc[0])
            
            if not found_ranks:
                continue
                
            best_fault_rank = min(found_ranks)
            exam_score = best_fault_rank / total_statements
            
            # Store scores for both Global and Project levels
            exam_scores_dict[bug_id] = exam_score
            project_scores[project_name].append(exam_score)
            
            # Record Global Hits
            if best_fault_rank <= 1: global_hits["Top-1"] += 1
            if best_fault_rank <= 3: global_hits["Top-3"] += 1
            if best_fault_rank <= 5: global_hits["Top-5"] += 1
            if best_fault_rank <= 10: global_hits["Top-10"] += 1
            
            # Record Project Hits
            if best_fault_rank <= 1: project_hits[project_name]["Top-1"] += 1
            if best_fault_rank <= 3: project_hits[project_name]["Top-3"] += 1
            if best_fault_rank <= 5: project_hits[project_name]["Top-5"] += 1
            if best_fault_rank <= 10: project_hits[project_name]["Top-10"] += 1

        except Exception as e:
            pass

    total_evaluated = len(exam_scores_dict)
    if total_evaluated > 0:
        
        print(f"\n--- 📊 PROJECT REPORT CARDS ---")
        for proj in project_scores.keys():
            proj_avg = sum(project_scores[proj]) / len(project_scores[proj])
            print(f"[{proj}] (Bugs: {len(project_scores[proj])})")
            print(f"  Avg EXAM: {proj_avg:.4f} ({proj_avg * 100:.2f}%)")
            print(f"  Hits: Top-1: {project_hits[proj]['Top-1']} | Top-3: {project_hits[proj]['Top-3']} | Top-5: {project_hits[proj]['Top-5']} | Top-10: {project_hits[proj]['Top-10']}\n")
        
        global_avg = sum(exam_scores_dict.values()) / total_evaluated
        print(f"--- 🌍 GLOBAL SUMMARY ---")
        print(f"Total Bugs Evaluated: {total_evaluated}")
        print(f"Global Avg EXAM:      {global_avg:.4f} ({global_avg * 100:.2f}%)")
        print("Global Top-N Accuracy:")
        for k, v in global_hits.items():
            print(f"  {k}: {v} hits")
    
    return exam_scores_dict

def run_wilcoxon_test(ochiai_dict, ochiai_ms_dict):
    print(f"\n==========================================")
    print(f" WILCOXON SIGNED-RANK TEST ")
    print(f"==========================================")
    
    common_bugs = set(ochiai_dict.keys()).intersection(set(ochiai_ms_dict.keys()))
    
    if len(common_bugs) < 5:
        print(f"Error: Not enough paired samples (Found {len(common_bugs)}, need at least 5).")
        return
        
    paired_ochiai = [ochiai_dict[bug] for bug in common_bugs]
    paired_ms = [ochiai_ms_dict[bug] for bug in common_bugs]
        
    statistic, p_value = wilcoxon(paired_ochiai, paired_ms, alternative='greater')
    
    print(f"Total Paired Samples: {len(common_bugs)}")
    print(f"Test Statistic:       {statistic}")
    print(f"P-Value:              {p_value:.10f}")
    print(f"------------------------------------------")
    
    if p_value < 0.05:
        print("CONCLUSION: SIGNIFICANT")
        print("Ochiai-MS provides a statistically significant improvement.")
    else:
        print("CONCLUSION: NOT SIGNIFICANT")
    print(f"==========================================\n")

if __name__ == "__main__":
    try:
        with open("ground_truth.json", "r") as f:
            gitbug_bug_records = json.load(f)
    except FileNotFoundError:
        print("Error: 'ground_truth.json' not found. Run the generator script first.")
        exit()

    ochiai_scores = evaluate_algorithm("Standard Ochiai", "./ochiai_results", gitbug_bug_records)
    ochiai_ms_scores = evaluate_algorithm("Ochiai-MS", "./ochiai_ms_results", gitbug_bug_records)

    if ochiai_scores and ochiai_ms_scores:
        run_wilcoxon_test(ochiai_scores, ochiai_ms_scores)
