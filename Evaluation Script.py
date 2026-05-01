import os
import sys
import pandas as pd
import json
from scipy.stats import wilcoxon
from tqdm import tqdm
from collections import defaultdict

def evaluate_algorithm(algorithm_name, folder_path, bug_records):
    exam_scores_dict = {}
    best_ranks_dict = {}
    project_scores = defaultdict(list)
    project_ranks = defaultdict(list)
    project_hits = defaultdict(lambda: {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0})
    global_hits = {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0}

    print(f"\n==========================================")
    print(f" Analyzing {algorithm_name} (STATEMENT-Level) ")
    print(f"==========================================")

    bug_ids = list(bug_records.keys())

    for bug_id in tqdm(bug_ids, desc=f"Processing {algorithm_name}", unit="bug"):
        filename = f"{bug_id}.csv"
        filepath = os.path.join(folder_path, filename)

        project_name = "-".join(bug_id.split("-")[:-1])

        # Fix 3: if file missing, record worst-case instead of silently skipping
        if not os.path.exists(filepath):
            exam_scores_dict[bug_id] = 1.0
            best_ranks_dict[bug_id] = None
            project_scores[project_name].append(1.0)
            project_ranks[project_name].append(None)
            continue

        fault_list = bug_records[bug_id]

        try:
            data_frame = pd.read_csv(filepath)
            total_elements = len(data_frame)

            found_ranks = []
            for fault in fault_list:
                faulty_class, faulty_line = fault[0], fault[1]
                fault_row = data_frame[
                    (data_frame['FullyQualifiedClass'] == faulty_class) &
                    (data_frame['Line'] == faulty_line)
                ]
                if not fault_row.empty:
                    found_ranks.append(fault_row['Rank'].iloc[0])

            # Fix 3: no GT line found in ranking → worst-case EXAM
            if not found_ranks:
                exam_scores_dict[bug_id] = 1.0
                best_ranks_dict[bug_id] = None
                project_scores[project_name].append(1.0)
                project_ranks[project_name].append(None)
                continue

            best_fault_rank = min(found_ranks)

            # Fix 1: count actual lines inspected under dense ranking
            lines_inspected = len(data_frame[data_frame['Rank'] <= best_fault_rank])
            exam_score = lines_inspected / total_elements

            exam_scores_dict[bug_id] = exam_score
            best_ranks_dict[bug_id] = best_fault_rank
            project_scores[project_name].append(exam_score)
            project_ranks[project_name].append(best_fault_rank)

            # Fix 2: Top-N based on lines inspected, not raw dense rank
            if lines_inspected <= 1:
                global_hits["Top-1"] += 1
                project_hits[project_name]["Top-1"] += 1
            if lines_inspected <= 3:
                global_hits["Top-3"] += 1
                project_hits[project_name]["Top-3"] += 1
            if lines_inspected <= 5:
                global_hits["Top-5"] += 1
                project_hits[project_name]["Top-5"] += 1
            if lines_inspected <= 10:
                global_hits["Top-10"] += 1
                project_hits[project_name]["Top-10"] += 1

        except Exception as e:
            exam_scores_dict[bug_id] = 1.0
            best_ranks_dict[bug_id] = None
            project_scores[project_name].append(1.0)
            project_ranks[project_name].append(None)

    total_evaluated = len(exam_scores_dict)
    global_avg_exam = 0
    global_avg_rank = 0

    if total_evaluated > 0:
        print(f"\n--- PROJECT REPORT CARDS ---")
        for proj in project_scores.keys():
            proj_avg_exam = sum(project_scores[proj]) / len(project_scores[proj])
            valid_ranks = [r for r in project_ranks[proj] if r is not None]
            proj_avg_rank = sum(valid_ranks) / len(valid_ranks) if valid_ranks else None
            print(f"[{proj}] (Bugs: {len(project_scores[proj])})")
            print(f"  Avg EXAM:  {proj_avg_exam:.4f} ({proj_avg_exam * 100:.2f}%)")
            if proj_avg_rank is not None:
                print(f"  Avg Rank:  {proj_avg_rank:.2f}")
            print(f"  Hits: Top-1: {project_hits[proj]['Top-1']} | Top-3: {project_hits[proj]['Top-3']} | Top-5: {project_hits[proj]['Top-5']} | Top-10: {project_hits[proj]['Top-10']}\n")

        global_avg_exam = sum(exam_scores_dict.values()) / total_evaluated
        valid_all_ranks = [r for r in best_ranks_dict.values() if r is not None]
        global_avg_rank = sum(valid_all_ranks) / len(valid_all_ranks) if valid_all_ranks else 0

        print(f"--- GLOBAL SUMMARY ---")
        print(f"Total Bugs Evaluated: {total_evaluated}")
        print(f"Global Avg EXAM:      {global_avg_exam:.4f} ({global_avg_exam * 100:.2f}%)")
        print(f"Global Avg Best Rank: {global_avg_rank:.2f}")
        print("Global Top-N Accuracy (by lines inspected):")
        for k, v in global_hits.items():
            print(f"  {k}: {v} hits")

    return {
        "bug_scores": exam_scores_dict,
        "bug_ranks": best_ranks_dict,
        "project_scores": project_scores,
        "project_ranks": project_ranks,
        "project_hits": project_hits,
        "global_avg_exam": global_avg_exam,
        "global_avg_rank": global_avg_rank,
        "global_hits": global_hits,
        "total_evaluated": total_evaluated,
    }

def run_wilcoxon_test(ochiai_dict, ochiai_ms_dict):
    print(f"\n==========================================")
    print(f" WILCOXON SIGNED-RANK TEST ")
    print(f"==========================================")

    common_bugs = set(ochiai_dict.keys()).intersection(set(ochiai_ms_dict.keys()))

    if len(common_bugs) < 15:
        print(f"Error: Not enough paired samples (Found {len(common_bugs)}, need at least 15).")
        return None

    paired_ochiai = [ochiai_dict[bug] for bug in common_bugs]
    paired_ms = [ochiai_ms_dict[bug] for bug in common_bugs]

    # alternative='greater': tests H1 that Ochiai EXAM > Ochiai-MS EXAM
    # i.e., Ochiai-MS produces significantly lower (better) EXAM scores
    statistic, p_value = wilcoxon(paired_ochiai, paired_ms, alternative='greater')
    is_significant = p_value < 0.05

    print(f"Total Paired Samples: {len(common_bugs)}")
    print(f"Test Statistic:       {statistic}")
    print(f"P-Value:              {p_value:.10f}")
    print(f"------------------------------------------")

    if is_significant:
        print("CONCLUSION: SIGNIFICANT (Ochiai-MS is significantly better than Ochiai)")
    else:
        print("CONCLUSION: NOT SIGNIFICANT")
    print(f"==========================================\n")

    return {
        "n_samples": len(common_bugs),
        "statistic": statistic,
        "p_value": p_value,
        "significant": is_significant,
    }

def export_results(ochiai_data, ms_data, wilcox_data):
    print("\n[Export] Generating Data Report...")

    # Bug-level data
    bug_rows = []
    all_bugs = set(ochiai_data['bug_scores'].keys()).union(set(ms_data['bug_scores'].keys()))
    for bug in sorted(list(all_bugs)):
        o_score = ochiai_data['bug_scores'].get(bug, None)
        ms_score = ms_data['bug_scores'].get(bug, None)
        o_rank = ochiai_data['bug_ranks'].get(bug, None)
        ms_rank = ms_data['bug_ranks'].get(bug, None)
        bug_rows.append({
            "Bug ID": bug,
            "Ochiai EXAM": o_score,
            "Ochiai-MS EXAM": ms_score,
            "Ochiai Best Rank": o_rank,
            "Ochiai-MS Best Rank": ms_rank,
        })

    # Project-level data
    proj_rows = []
    for proj in ochiai_data['project_scores'].keys():
        o_proj_scores = ochiai_data['project_scores'].get(proj, [])
        ms_proj_scores = ms_data['project_scores'].get(proj, [])
        o_valid_ranks = [r for r in ochiai_data['project_ranks'].get(proj, []) if r is not None]
        ms_valid_ranks = [r for r in ms_data['project_ranks'].get(proj, []) if r is not None]
        proj_rows.append({
            "Project": proj,
            "Total Bugs Evaluated": len(o_proj_scores),
            "Ochiai Avg EXAM": sum(o_proj_scores) / len(o_proj_scores) if o_proj_scores else None,
            "Ochiai-MS Avg EXAM": sum(ms_proj_scores) / len(ms_proj_scores) if ms_proj_scores else None,
            "Ochiai Avg Best Rank": sum(o_valid_ranks) / len(o_valid_ranks) if o_valid_ranks else None,
            "Ochiai-MS Avg Best Rank": sum(ms_valid_ranks) / len(ms_valid_ranks) if ms_valid_ranks else None,
            "Ochiai Top-1": ochiai_data['project_hits'][proj]['Top-1'],
            "Ochiai-MS Top-1": ms_data['project_hits'].get(proj, {}).get('Top-1', 0),
            "Ochiai Top-5": ochiai_data['project_hits'][proj]['Top-5'],
            "Ochiai-MS Top-5": ms_data['project_hits'].get(proj, {}).get('Top-5', 0),
        })

    # Global & Wilcoxon data
    global_rows = [
        {"Metric": "Total Bugs Evaluated", "Standard Ochiai": ochiai_data['total_evaluated'], "Ochiai-MS": ms_data['total_evaluated']},
        {"Metric": "Global Avg EXAM Score", "Standard Ochiai": ochiai_data['global_avg_exam'], "Ochiai-MS": ms_data['global_avg_exam']},
        {"Metric": "Global Avg Best Rank", "Standard Ochiai": ochiai_data['global_avg_rank'], "Ochiai-MS": ms_data['global_avg_rank']},
        {"Metric": "Global Top-1 Hits", "Standard Ochiai": ochiai_data['global_hits']['Top-1'], "Ochiai-MS": ms_data['global_hits']['Top-1']},
        {"Metric": "Global Top-3 Hits", "Standard Ochiai": ochiai_data['global_hits']['Top-3'], "Ochiai-MS": ms_data['global_hits']['Top-3']},
        {"Metric": "Global Top-5 Hits", "Standard Ochiai": ochiai_data['global_hits']['Top-5'], "Ochiai-MS": ms_data['global_hits']['Top-5']},
        {"Metric": "Global Top-10 Hits", "Standard Ochiai": ochiai_data['global_hits']['Top-10'], "Ochiai-MS": ms_data['global_hits']['Top-10']},
    ]

    if wilcox_data:
        global_rows.extend([
            {"Metric": "--- WILCOXON SIGNED-RANK TEST ---", "Standard Ochiai": "", "Ochiai-MS": ""},
            {"Metric": "Total Paired Samples", "Standard Ochiai": wilcox_data['n_samples'], "Ochiai-MS": ""},
            {"Metric": "Test Statistic", "Standard Ochiai": wilcox_data['statistic'], "Ochiai-MS": ""},
            {"Metric": "P-Value", "Standard Ochiai": wilcox_data['p_value'], "Ochiai-MS": ""},
            {"Metric": "Statistically Significant (<0.05)?", "Standard Ochiai": "YES" if wilcox_data['significant'] else "NO", "Ochiai-MS": ""},
        ])

    try:
        with pd.ExcelWriter('Javelin_Evaluation_Report.xlsx', engine='openpyxl') as writer:
            df_bugs = pd.DataFrame(bug_rows)
            df_proj = pd.DataFrame(proj_rows)
            df_global = pd.DataFrame(global_rows)

            df_bugs.to_excel(writer, sheet_name="Bug-Level Scores", index=False, startrow=3)
            df_proj.to_excel(writer, sheet_name="Project Summaries", index=False, startrow=3)
            df_global.to_excel(writer, sheet_name="Global & Statistics", index=False, startrow=3)

            ws1 = writer.sheets["Bug-Level Scores"]
            ws1.cell(row=1, column=1, value="METRIC EXPLANATION: EXAM = (lines inspected before first fault found) / (total statements). LOWER is better.")
            ws1.cell(row=2, column=1, value="Best Rank = dense rank of the first faulty line found. Top-N uses lines inspected (not raw rank) to account for ties.")

            ws2 = writer.sheets["Project Summaries"]
            ws2.cell(row=1, column=1, value="METRIC EXPLANATION: Top-N = bugs where fault was within the first N statements inspected (ties accounted for).")
            ws2.cell(row=2, column=1, value="Avg Best Rank = mean dense rank of first faulty line across all bugs. LOWER is better for both EXAM and Avg Rank.")

            ws3 = writer.sheets["Global & Statistics"]
            ws3.cell(row=1, column=1, value="METRIC EXPLANATION: Overall aggregated performance and non-parametric statistical testing.")
            ws3.cell(row=2, column=1, value="Wilcoxon H1: Ochiai EXAM > Ochiai-MS EXAM. P-Value < 0.05 means Ochiai-MS is significantly better.")

        print(" Success: Generated 'Javelin_Evaluation_Report.xlsx'.")
    except ImportError:
        print(" Note: 'openpyxl' not found. Falling back to CSV...")
        pd.DataFrame(bug_rows).to_csv('Javelin_Report_1_BugScores.csv', index=False)
        pd.DataFrame(proj_rows).to_csv('Javelin_Report_2_ProjectSummaries.csv', index=False)
        pd.DataFrame(global_rows).to_csv('Javelin_Report_3_GlobalStats.csv', index=False)
        print(" Success: Generated 3 CSV report files.")

def check_prerequisites():
    print("\n[System Check] Verifying prerequisites...")

    if not os.path.exists("ground_truth.json"):
        print(" Error: 'ground_truth.json' not found. Please run the generation script first.")
        return False

    required_folders = ["./ochiai_results", "./ochiai_ms_results"]
    missing_folders = [folder for folder in required_folders if not os.path.exists(folder)]

    if missing_folders:
        print(f" Error: Missing required result folders for analysis.")
        for folder in missing_folders:
            print(f"    -> {folder} is missing.")
        print(" Please ensure Javelin has generated the CSV files in the correct directories.")
        return False

    print(" All prerequisites met.")
    return True

def execute_analysis():
    if not check_prerequisites():
        input("\nPress Enter to return to the main menu...")
        return

    with open("ground_truth.json", "r") as f:
        bug_records = json.load(f)

    print("\n\n>>> RUNNING STATEMENT-LEVEL EVALUATION <<<")
    ochiai_data = evaluate_algorithm("Standard Ochiai", "./ochiai_results", bug_records)
    ochiai_ms_data = evaluate_algorithm("Ochiai-MS", "./ochiai_ms_results", bug_records)

    if ochiai_data and ochiai_ms_data:
        wilcox_data = run_wilcoxon_test(ochiai_data['bug_scores'], ochiai_ms_data['bug_scores'])
        export_results(ochiai_data, ochiai_ms_data, wilcox_data)

    input("\nEvaluation complete! Press Enter to return to the main menu...")

def main_menu():
    while True:
        print("\n" + "="*50)
        print(" JAVELIN EVALUATION SUITE ")
        print("="*50)
        print(" 1. Run Statement-Level Analysis & Export")
        print(" 2. Exit")
        print("="*50)

        choice = input("Select an option (1 or 2): ").strip()

        if choice == '1':
            execute_analysis()
        elif choice == '2':
            print("\nExiting Javelin Evaluation Suite. Goodbye!")
            sys.exit(0)
        else:
            print("\n Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    main_menu()
