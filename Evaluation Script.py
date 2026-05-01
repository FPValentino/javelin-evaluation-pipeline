import os
import sys
import pandas as pd
import json
from scipy.stats import wilcoxon
from tqdm import tqdm
from collections import defaultdict

def evaluate_algorithm(algorithm_name, folder_path, bug_records, granularity="method"):
    exam_scores_dict = {}
    project_scores = defaultdict(list)
    project_hits = defaultdict(lambda: {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0})
    global_hits = {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0}
    
    print(f"\n==========================================")
    print(f" Analyzing {algorithm_name} ({granularity.upper()}-Level) ")
    print(f"==========================================")
    
    bug_ids = list(bug_records.keys())
    
    for bug_id in tqdm(bug_ids, desc=f"Processing {algorithm_name}", unit="bug"):
        filename = f"{bug_id}.csv"
        filepath = os.path.join(folder_path, filename)
        
        if not os.path.exists(filepath):
            continue

        project_name = "-".join(bug_id.split("-")[:-1])
        fault_list = bug_records[bug_id]

        try:
            data_frame = pd.read_csv(filepath)
            total_elements = len(data_frame) # Total methods OR total statements
            
            found_ranks = []
            for fault in fault_list:
                faulty_class, faulty_line = fault[0], fault[1]
                
                # THE TOGGLE: Choose how to match the fault to the CSV
                if granularity == "method":
                    fault_row = data_frame[(data_frame['FullyQualifiedClass'] == faulty_class) & 
                                           (data_frame['FirstLine'] <= faulty_line) & 
                                           (data_frame['LastLine'] >= faulty_line)]
                elif granularity == "statement":
                    fault_row = data_frame[(data_frame['FullyQualifiedClass'] == faulty_class) & 
                                           (data_frame['LineNumber'] == faulty_line)]
                else:
                    raise ValueError("Granularity must be 'method' or 'statement'")
                
                if not fault_row.empty:
                    found_ranks.append(fault_row['Rank'].iloc[0])
            
            if not found_ranks:
                continue
                
            best_fault_rank = min(found_ranks)
            exam_score = best_fault_rank / total_elements
            
            exam_scores_dict[bug_id] = exam_score
            project_scores[project_name].append(exam_score)
            
            if best_fault_rank <= 1: global_hits["Top-1"] += 1; project_hits[project_name]["Top-1"] += 1
            if best_fault_rank <= 3: global_hits["Top-3"] += 1; project_hits[project_name]["Top-3"] += 1
            if best_fault_rank <= 5: global_hits["Top-5"] += 1; project_hits[project_name]["Top-5"] += 1
            if best_fault_rank <= 10: global_hits["Top-10"] += 1; project_hits[project_name]["Top-10"] += 1

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

def run_wilcoxon_test(ochiai_dict, ochiai_ms_dict, test_name="Comparison"):
    print(f"\n==========================================")
    print(f" WILCOXON SIGNED-RANK TEST: {test_name} ")
    print(f"==========================================")
    
    common_bugs = set(ochiai_dict.keys()).intersection(set(ochiai_ms_dict.keys()))
    
    # REQUIREMENT UPDATED TO 15
    if len(common_bugs) < 15:
        print(f"Error: Not enough paired samples (Found {len(common_bugs)}, need at least 15).")
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
    else:
        print("CONCLUSION: NOT SIGNIFICANT")
    print(f"==========================================\n")

def check_prerequisites(mode):
    """Verifies that all required files and folders exist before running."""
    print("\n[System Check] Verifying prerequisites...")
    
    if not os.path.exists("ground_truth.json"):
        print(" ❌ Error: 'ground_truth.json' not found. Please run the generation script first.")
        return False
        
    required_folders = []
    if mode in ["method", "both"]:
        required_folders.extend(["./ochiai_method_results", "./ochiai_ms_method_results"])
    if mode in ["statement", "both"]:
        required_folders.extend(["./ochiai_statement_results", "./ochiai_ms_statement_results"])
        
    missing_folders = [folder for folder in required_folders if not os.path.exists(folder)]
    
    if missing_folders:
        print(f" ❌ Error: Missing required result folders for {mode.upper()}-level analysis.")
        for folder in missing_folders:
            print(f"    -> {folder} is missing.")
        print(" Please ensure Javelin has generated the CSV files in the correct directories.")
        return False
        
    print(" ✅ All prerequisites met.")
    return True

def execute_analysis(mode):
    """Runs the selected analysis if prerequisites are met."""
    if not check_prerequisites(mode):
        input("\nPress Enter to return to the main menu...")
        return

    with open("ground_truth.json", "r") as f:
        bug_records = json.load(f)

    if mode in ["method", "both"]:
        print("\n\n>>> RUNNING METHOD-LEVEL EVALUATION <<<")
        ochiai_method = evaluate_algorithm("Standard Ochiai", "./ochiai_method_results", bug_records, granularity="method")
        ochiai_ms_method = evaluate_algorithm("Ochiai-MS", "./ochiai_ms_method_results", bug_records, granularity="method")
        if ochiai_method and ochiai_ms_method:
            run_wilcoxon_test(ochiai_method, ochiai_ms_method, "Method-Level: Ochiai vs Ochiai-MS")

    if mode in ["statement", "both"]:
        print("\n\n>>> RUNNING STATEMENT-LEVEL EVALUATION <<<")
        ochiai_statement = evaluate_algorithm("Standard Ochiai", "./ochiai_statement_results", bug_records, granularity="statement")
        ochiai_ms_statement = evaluate_algorithm("Ochiai-MS", "./ochiai_ms_statement_results", bug_records, granularity="statement")
        if ochiai_statement and ochiai_ms_statement:
            run_wilcoxon_test(ochiai_statement, ochiai_ms_statement, "Statement-Level: Ochiai vs Ochiai-MS")
            
    input("\nEvaluation complete! Press Enter to return to the main menu...")

def main_menu():
    """Interactive main menu for the evaluation suite."""
    while True:
        print("\n" + "="*50)
        print(" 🎯 JAVELIN EVALUATION SUITE ")
        print("="*50)
        print(" 1. Run Method-Level Analysis")
        print(" 2. Run Statement-Level Analysis")
        print(" 3. Run Both Analyses")
        print(" 4. Exit")
        print("="*50)
        
        choice = input("Select an option (1-4): ").strip()
        
        if choice == '1':
            execute_analysis("method")
        elif choice == '2':
            execute_analysis("statement")
        elif choice == '3':
            execute_analysis("both")
        elif choice == '4':
            print("\nExiting...")
            sys.exit(0)
        else:
            print("\n⚠️ Invalid choice. Please enter a number between 1 and 4.")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    main_menu()
