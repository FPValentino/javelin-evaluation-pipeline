import os
import pandas as pd
import json
from scipy.stats import wilcoxon
from tqdm import tqdm  # The progress bar library

def evaluate_algorithm(algorithm_name, folder_path, bug_records):
    exam_scores_dict = {}
    top_n_counts = {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0}
    
    print(f"\n==========================================")
    print(f" Analyzing {algorithm_name} Results ")
    print(f"==========================================")
    
    # NEW LOGIC: Only count the exact bugs listed in our ground truth JSON
    bug_ids = list(bug_records.keys())
    
    # The progress bar now uses exactly the number of bugs in the JSON
    for bug_id in tqdm(bug_ids, desc=f"Processing {algorithm_name}", unit="bug"):
        
        filename = f"{bug_id}.csv"
        filepath = os.path.join(folder_path, filename)
        
        # Skip if the CSV doesn't exist yet
        if not os.path.exists(filepath):
            continue

        fault_list = bug_records[bug_id]

        try:
            data_frame = pd.read_csv(filepath)
            total_statements = len(data_frame)
            found_ranks = []
            
            for fault in fault_list:
                faulty_class, faulty_line = fault[0], fault[1]
                fault_row = data_frame[(data_frame['FullyQualifiedClass'] == faulty_class) & 
                                       (data_frame['LineNumber'] == faulty_line)]
                if not fault_row.empty:
                    found_ranks.append(fault_row['Rank'].iloc[0])
            
            if not found_ranks:
                continue
                
            best_fault_rank = min(found_ranks)
            exam_score = best_fault_rank / total_statements
            exam_scores_dict[bug_id] = exam_score
            
            if best_fault_rank <= 1: top_n_counts["Top-1"] += 1
            if best_fault_rank <= 3: top_n_counts["Top-3"] += 1
            if best_fault_rank <= 5: top_n_counts["Top-5"] += 1
            if best_fault_rank <= 10: top_n_counts["Top-10"] += 1

        except Exception as e:
            pass

    total_evaluated = len(exam_scores_dict)
    if total_evaluated > 0:
        avg_exam = sum(exam_scores_dict.values()) / total_evaluated
        print(f"\nTotal Bugs Evaluated: {total_evaluated}")
        print(f"Average EXAM Score:   {avg_exam:.4f} ({avg_exam * 100:.2f}%)")
        print("Top-N Accuracy:")
        for k, v in top_n_counts.items():
            print(f"  {k}: {v} hits")
    
    return exam_scores_dict

def run_wilcoxon_test(ochiai_dict, ochiai_ms_dict):
    print(f"\n==========================================")
    print(f" WILCOXON SIGNED-RANK TEST ")
    print(f"==========================================")
    
    common_bugs = set(ochiai_dict.keys()).intersection(set(ochiai_ms_dict.keys()))
    
    if len(common_bugs) < 5:
        print("Error: Not enough paired samples.")
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

# ==========================================
# EXECUTION BLOCK
# ==========================================
if __name__ == "__main__":
    
    # Load the ground truth securely from the JSON file
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