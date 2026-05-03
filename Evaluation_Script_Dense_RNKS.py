import os
import sys
import pandas as pd
import json
from scipy.stats import wilcoxon
from tqdm import tqdm
from collections import defaultdict

# ── SENSITIVITY ANALYSIS CONFIGURATION ───────────────────────────────────────
# Each key is a scenario label shown in the Sensitivity Analysis sheet.
# Each value is a list of project prefixes to exclude from that scenario.
# Add, remove, or rename entries freely — all other sheets are unaffected.
# Minimum 15 paired bugs required for Wilcoxon to be computed per scenario.
SENSITIVITY_EXCLUDE_SETS = {
    "Without JacksonDatabind":  ["Defects4J-JacksonDatabind"],
    "Without JacksonCore":      ["Defects4J-JacksonCore"],
    "Without both Jackson":     ["Defects4J-JacksonCore", "Defects4J-JacksonDatabind"],
}
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_algorithm(algorithm_name, folder_path, bug_records):
    exam_scores_dict = {}
    best_ranks_dict = {}
    lines_inspected_dict = {}
    gt_coverage_dict = {}
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
            total_gt_lines = len(fault_list)
            for fault in fault_list:
                faulty_class, faulty_line = fault[0], fault[1]
                fault_row = data_frame[
                    (data_frame['FullyQualifiedClass'] == faulty_class) &
                    (data_frame['Line'] == faulty_line)
                ]
                if not fault_row.empty:
                    found_ranks.append(fault_row['Rank'].iloc[0])

            found_gt_lines = len(found_ranks)
            gt_coverage_dict[bug_id] = f"{found_gt_lines}/{total_gt_lines}"

            # Fix 3: no GT line found in ranking → worst-case EXAM
            if not found_ranks:
                exam_scores_dict[bug_id] = 1.0
                best_ranks_dict[bug_id] = None
                project_scores[project_name].append(1.0)
                project_ranks[project_name].append(None)
                if found_gt_lines < total_gt_lines:
                    tqdm.write(f"  ⚠ {bug_id}: Only {found_gt_lines}/{total_gt_lines} ground truth lines found in SBFL output (omission/interface bug?)")
                continue

            best_fault_rank = min(found_ranks)

            if found_gt_lines < total_gt_lines:
                tqdm.write(f"  ⚠ {bug_id}: Only {found_gt_lines}/{total_gt_lines} ground truth lines found in SBFL output (omission/interface bug?)")

            # Fix 1: count actual lines inspected under dense ranking
            lines_inspected = len(data_frame[data_frame['Rank'] <= best_fault_rank])
            exam_score = lines_inspected / total_elements

            exam_scores_dict[bug_id] = exam_score
            best_ranks_dict[bug_id] = best_fault_rank
            lines_inspected_dict[bug_id] = lines_inspected
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
        "lines_inspected": lines_inspected_dict,
        "gt_coverage": gt_coverage_dict,
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
    try:
        statistic, p_value = wilcoxon(paired_ochiai, paired_ms, alternative='greater')
    except ValueError as ve:
        print(f"Wilcoxon could not be computed: {ve}")
        print(f"==========================================\n")
        return None

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

def compute_filtered_results(ochiai_data, ms_data):
    """Compute EXAM scores and Wilcoxon on bugs where ALL ground truth lines
    were found in the SBFL output (fully detectable bugs only)."""

    # A bug is fully detectable if GT Found == total for BOTH algorithms
    def is_fully_detectable(bug_id):
        for data in (ochiai_data, ms_data):
            cov = data['gt_coverage'].get(bug_id, "0/1")
            if '/' in cov:
                found, total = cov.split('/')
                if found != total:
                    return False
        return True

    all_bugs = set(ochiai_data['bug_scores'].keys()).union(set(ms_data['bug_scores'].keys()))
    detectable = sorted([b for b in all_bugs if is_fully_detectable(b)])
    excluded  = sorted([b for b in all_bugs if not is_fully_detectable(b)])

    def filtered_stats(data):
        scores = {b: data['bug_scores'][b] for b in detectable if b in data['bug_scores']}
        avg_exam = sum(scores.values()) / len(scores) if scores else None
        hits = {"Top-1": 0, "Top-3": 0, "Top-5": 0, "Top-10": 0}
        for bug_id in detectable:
            lines = data['lines_inspected'].get(bug_id)
            if lines is None:
                continue
            if lines <= 1:  hits["Top-1"] += 1
            if lines <= 3:  hits["Top-3"] += 1
            if lines <= 5:  hits["Top-5"] += 1
            if lines <= 10: hits["Top-10"] += 1
        return scores, avg_exam, hits

    o_scores, o_avg, o_hits = filtered_stats(ochiai_data)
    ms_scores, ms_avg, ms_hits = filtered_stats(ms_data)

    # Second Wilcoxon on the filtered set
    wilcox_filtered = None
    common = set(o_scores.keys()).intersection(set(ms_scores.keys()))
    if len(common) >= 15:
        from scipy.stats import wilcoxon as _wilcoxon
        paired_o  = [o_scores[b]  for b in common]
        paired_ms = [ms_scores[b] for b in common]
        stat, pval = _wilcoxon(paired_o, paired_ms, alternative='greater')
        wilcox_filtered = {
            "n_samples": len(common),
            "statistic": stat,
            "p_value": pval,
            "significant": pval < 0.05,
        }

    return {
        "detectable_bugs": detectable,
        "excluded_bugs": excluded,
        "ochiai_scores": o_scores,
        "ms_scores": ms_scores,
        "ochiai_avg_exam": o_avg,
        "ms_avg_exam": ms_avg,
        "ochiai_hits": o_hits,
        "ms_hits": ms_hits,
        "wilcoxon": wilcox_filtered,
    }


def compute_sensitivity_analysis(ochiai_data, ms_data):
    """Recompute Wilcoxon + summary stats for each scenario in SENSITIVITY_EXCLUDE_SETS,
    plus an 'All Projects (Baseline)' row for direct comparison."""

    def get_project(bug_id):
        return "-".join(bug_id.split("-")[:-1])

    all_common = sorted(
        set(ochiai_data['bug_scores'].keys()).intersection(ms_data['bug_scores'].keys())
    )

    scenarios = {"All Projects (Baseline)": []}
    scenarios.update(SENSITIVITY_EXCLUDE_SETS)

    rows = []
    for scenario_name, excluded_projects in scenarios.items():
        subset = [b for b in all_common if get_project(b) not in excluded_projects]
        if not subset:
            continue

        o_scores  = [ochiai_data['bug_scores'][b] for b in subset]
        ms_scores = [ms_data['bug_scores'][b] for b in subset]

        o_avg  = sum(o_scores)  / len(o_scores)
        ms_avg = sum(ms_scores) / len(ms_scores)

        n_better = n_worse = n_tied = 0
        for o, m in zip(o_scores, ms_scores):
            d = o - m
            if abs(d) < 1e-10:
                n_tied += 1
            elif d > 0:
                n_better += 1
            else:
                n_worse += 1

        o_top10  = sum(1 for b in subset
                       if ochiai_data['lines_inspected'].get(b) is not None
                       and ochiai_data['lines_inspected'][b] <= 10)
        ms_top10 = sum(1 for b in subset
                       if ms_data['lines_inspected'].get(b) is not None
                       and ms_data['lines_inspected'][b] <= 10)

        n = len(subset)
        w_stat = p_val = sig = "N/A"
        if n >= 15:
            try:
                stat, pval = wilcoxon(o_scores, ms_scores, alternative='greater')
                w_stat = stat
                p_val  = round(pval, 10)
                sig    = "YES" if pval < 0.05 else "NO"
            except ValueError as ve:
                w_stat = f"Error: {ve}"
                sig    = "N/A"
        else:
            sig = f"Too few bugs (N={n}, need >=15)"

        rows.append({
            "Scenario":              scenario_name,
            "Excluded Projects":     ", ".join(excluded_projects) if excluded_projects else "(none — full dataset)",
            "N Bugs":                n,
            "Ochiai Avg EXAM":       o_avg,
            "Ochiai-MS Avg EXAM":    ms_avg,
            "MS Better":             n_better,
            "MS Worse":              n_worse,
            "Tied":                  n_tied,
            "Ochiai Top-10":         o_top10,
            "Ochiai-MS Top-10":      ms_top10,
            "Wilcoxon W":            w_stat,
            "P-Value":               p_val,
            "Significant (p<0.05)?": sig,
        })

    return rows


def export_results(ochiai_data, ms_data, wilcox_data):
    print("\n[Export] Generating Data Report...")

    # Compute filtered results before building rows
    filtered = compute_filtered_results(ochiai_data, ms_data)
    detectable_set = set(filtered['detectable_bugs'])

    # Bug-level data
    bug_rows = []
    all_bugs = set(ochiai_data['bug_scores'].keys()).union(set(ms_data['bug_scores'].keys()))
    for bug in sorted(list(all_bugs)):
        o_score = ochiai_data['bug_scores'].get(bug, None)
        ms_score = ms_data['bug_scores'].get(bug, None)
        o_rank = ochiai_data['bug_ranks'].get(bug, None)
        ms_rank = ms_data['bug_ranks'].get(bug, None)
        o_gt_cov = ochiai_data['gt_coverage'].get(bug, "N/A")
        ms_gt_cov = ms_data['gt_coverage'].get(bug, "N/A")
        fully_detectable = "Yes" if bug in detectable_set else "No"
        bug_rows.append({
            "Bug ID": bug,
            "Ochiai EXAM": o_score,
            "Ochiai-MS EXAM": ms_score,
            "Ochiai Best Rank": o_rank,
            "Ochiai-MS Best Rank": ms_rank,
            "Ochiai GT Found": o_gt_cov,
            "Ochiai-MS GT Found": ms_gt_cov,
            "Fully Detectable": fully_detectable,
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

    # Filtered Analysis sheet data
    n_excluded = len(filtered['excluded_bugs'])
    n_detectable = len(filtered['detectable_bugs'])
    filtered_rows = [
        {"Metric": "--- FILTERED EXAM SCORES (detectable bugs only) ---", "Value": ""},
        {"Metric": "Ochiai Avg EXAM (filtered)", "Value": filtered['ochiai_avg_exam']},
        {"Metric": "Ochiai-MS Avg EXAM (filtered)", "Value": filtered['ms_avg_exam']},
        {"Metric": "", "Value": ""},
        {"Metric": "--- FILTERED TOP-N HITS ---", "Value": ""},
        {"Metric": "Ochiai Top-1 (filtered)", "Value": filtered['ochiai_hits']['Top-1']},
        {"Metric": "Ochiai-MS Top-1 (filtered)", "Value": filtered['ms_hits']['Top-1']},
        {"Metric": "Ochiai Top-3 (filtered)", "Value": filtered['ochiai_hits']['Top-3']},
        {"Metric": "Ochiai-MS Top-3 (filtered)", "Value": filtered['ms_hits']['Top-3']},
        {"Metric": "Ochiai Top-5 (filtered)", "Value": filtered['ochiai_hits']['Top-5']},
        {"Metric": "Ochiai-MS Top-5 (filtered)", "Value": filtered['ms_hits']['Top-5']},
        {"Metric": "Ochiai Top-10 (filtered)", "Value": filtered['ochiai_hits']['Top-10']},
        {"Metric": "Ochiai-MS Top-10 (filtered)", "Value": filtered['ms_hits']['Top-10']},
    ]
    wf = filtered['wilcoxon']
    if wf:
        filtered_rows += [
            {"Metric": "", "Value": ""},
            {"Metric": "--- WILCOXON (filtered set) ---", "Value": ""},
            {"Metric": "Total Paired Samples", "Value": wf['n_samples']},
            {"Metric": "Test Statistic", "Value": wf['statistic']},
            {"Metric": "P-Value", "Value": wf['p_value']},
            {"Metric": "Statistically Significant (<0.05)?", "Value": "YES" if wf['significant'] else "NO"},
        ]
    else:
        filtered_rows.append({"Metric": "Wilcoxon (filtered)", "Value": f"Not computed — fewer than 15 paired samples (N={n_detectable})"})

    filtered_rows += [
        {"Metric": "", "Value": ""},
        {"Metric": "--- EXCLUSION SUMMARY ---", "Value": ""},
        {"Metric": "NOTE", "Value": f"{n_excluded} bug(s) excluded — not all ground truth lines appear in SBFL output (omission/interface components)."},
        {"Metric": "Detectable Bugs (N)", "Value": n_detectable},
        {"Metric": "Excluded Bugs (N)", "Value": n_excluded},
    ]
    for bug_id in filtered['excluded_bugs']:
        filtered_rows.append({"Metric": "Excluded Bug ID", "Value": bug_id})

    # --- Per-project Wilcoxon ---
    all_common = set(ochiai_data['bug_scores'].keys()).intersection(set(ms_data['bug_scores'].keys()))
    per_proj_bugs = defaultdict(list)
    for bug in all_common:
        per_proj_bugs["-".join(bug.split("-")[:-1])].append(bug)

    proj_wilcoxon_rows = []
    for proj in sorted(per_proj_bugs.keys()):
        bugs = sorted(per_proj_bugs[proj])
        p_o  = [ochiai_data['bug_scores'][b] for b in bugs]
        p_ms = [ms_data['bug_scores'][b] for b in bugs]
        n = len(bugs)
        if n < 6:
            proj_wilcoxon_rows.append({
                "Project": proj, "N (paired bugs)": n,
                "Test Statistic": "N/A", "P-Value": "N/A",
                "Significant (p<0.05)?": "Too few samples (min 6)",
            })
        else:
            try:
                stat, pval = wilcoxon(p_o, p_ms, alternative='greater')
                proj_wilcoxon_rows.append({
                    "Project": proj, "N (paired bugs)": n,
                    "Test Statistic": stat, "P-Value": pval,
                    "Significant (p<0.05)?": "YES" if pval < 0.05 else "NO",
                })
            except ValueError as ve:
                proj_wilcoxon_rows.append({
                    "Project": proj, "N (paired bugs)": n,
                    "Test Statistic": "N/A", "P-Value": "N/A",
                    "Significant (p<0.05)?": str(ve),
                })

    # --- Sensitivity Analysis ---
    sensitivity_rows = compute_sensitivity_analysis(ochiai_data, ms_data)

    # --- Explanatory sheet data ---
    explanatory_rows = [
        {"Topic": "REPORT OVERVIEW", "Description": "Compares Standard Ochiai vs Ochiai-MS spectrum-based fault localization (SBFL). This report uses dense ranking to resolve tied suspiciousness scores."},
        {"Topic": "", "Description": ""},
        {"Topic": "--- KEY METRICS ---", "Description": ""},
        {"Topic": "", "Description": ""},
        {"Topic": "EXAM Score", "Description": "EXAM = (lines inspected up to and including rank of first faulty line) / (total executable statements). Fraction of code inspected before reaching the first fault."},
        {"Topic": "  Range", "Description": "0.0 to 1.0. LOWER is better. EXAM = 0.05 means only 5% of code needs to be inspected to find the fault."},
        {"Topic": "  Calculation", "Description": "1) Rank all statements by suspiciousness descending (dense). 2) Find dense rank of highest-ranked GT line. 3) Count all lines at or above that rank. 4) Divide by total statements."},
        {"Topic": "  Worst Case", "Description": "EXAM = 1.0 is assigned when: result CSV is missing, no GT lines found in SBFL output, or an error occurs during processing."},
        {"Topic": "", "Description": ""},
        {"Topic": "Best Rank", "Description": "Dense rank position of the highest-ranked (most suspicious) ground truth faulty line. LOWER is better. Rank 1 = most suspicious line."},
        {"Topic": "  Ranking Method (Dense)", "Description": "Tied suspiciousness scores all receive the same rank, and the next distinct score gets the next integer rank (no gaps). Lines inspected = count of all lines at or above that dense rank."},
        {"Topic": "", "Description": ""},
        {"Topic": "Top-N Accuracy", "Description": "Count of bugs where the first faulty line was found within the first N lines inspected (N = 1, 3, 5, 10). HIGHER is better."},
        {"Topic": "  Calculation", "Description": "A bug is a Top-N hit if lines_inspected (count of lines at or above the best fault dense rank) is <= N."},
        {"Topic": "", "Description": ""},
        {"Topic": "GT Coverage", "Description": "Format: found/total. Number of known faulty ground truth lines that appear in the SBFL ranking output."},
        {"Topic": "  Interpretation", "Description": "found < total = omission or interface bugs: some faulty lines are not in the executed/instrumented code and cannot be ranked by SBFL."},
        {"Topic": "", "Description": ""},
        {"Topic": "Fully Detectable", "Description": "'Yes' = all GT lines found in SBFL output for BOTH algorithms. 'No' = one or more lines missing — excluded from Filtered Analysis."},
        {"Topic": "", "Description": ""},
        {"Topic": "--- STATISTICAL TESTING ---", "Description": ""},
        {"Topic": "", "Description": ""},
        {"Topic": "Wilcoxon Signed-Rank Test", "Description": "Non-parametric paired test. Does not assume normal distribution. Tests whether the median difference between two paired score distributions is zero."},
        {"Topic": "  Null Hypothesis (H0)", "Description": "No difference between Ochiai and Ochiai-MS EXAM scores. Median of (Ochiai - Ochiai-MS) differences = 0."},
        {"Topic": "  Alt. Hypothesis (H1)", "Description": "Ochiai EXAM > Ochiai-MS EXAM (one-sided). Ochiai-MS produces lower (better) EXAM scores."},
        {"Topic": "  P-Value", "Description": "Probability of observing results this extreme under H0. p < 0.05 = statistically significant at 95% confidence, reject H0."},
        {"Topic": "  Test Statistic (W)", "Description": "Sum of positive signed ranks of pairwise differences (Ochiai - Ochiai-MS). Larger W supports H1."},
        {"Topic": "  Calculation", "Description": "1) d = Ochiai_EXAM - OchiaiMS_EXAM per paired bug. 2) Drop pairs where d = 0. 3) Rank |d| ascending (average-rank for ties). 4) Restore the sign of each rank. 5) W = sum of positive signed ranks. 6) Compare W against its null distribution (exact for small N, normal approximation for large N) to get p-value."},
        {"Topic": "  Interpretation", "Description": "p < 0.05 = Ochiai-MS produces significantly lower EXAM scores = Ochiai-MS localizes faults more effectively than Standard Ochiai."},
        {"Topic": "  Minimum Sample Size", "Description": "Global test: >= 15 paired bugs required. Per-project test: >= 6 paired bugs. Below threshold results are not reported."},
        {"Topic": "", "Description": ""},
        {"Topic": "Per-Project Wilcoxon", "Description": "Same Wilcoxon test applied per Defects4J project (Cli, Gson, Lang). Reveals whether improvement is consistent across projects or concentrated in a subset."},
        {"Topic": "", "Description": ""},
        {"Topic": "--- SHEET DESCRIPTIONS ---", "Description": ""},
        {"Topic": "", "Description": ""},
        {"Topic": "Guide (this sheet)", "Description": "Explains all metrics, statistical tests, and how to interpret results across all sheets in this workbook."},
        {"Topic": "Bug-Level Scores", "Description": "Per-bug EXAM scores, best ranks, and GT coverage for both algorithms. Use to compare per-bug performance and identify outliers."},
        {"Topic": "Project Summaries", "Description": "Aggregated metrics (avg EXAM, avg rank, Top-N hits) per Defects4J project."},
        {"Topic": "Global & Statistics", "Description": "Overall aggregated performance and global Wilcoxon signed-rank test results across all bugs."},
        {"Topic": "Filtered Analysis", "Description": "Same metrics but restricted to fully detectable bugs only (GT coverage = 100% for both). Fair head-to-head without interference from omission/interface bugs."},
        {"Topic": "Per-Project Wilcoxon", "Description": "Wilcoxon test results for each project individually — shows where Ochiai-MS improvement is statistically significant."},
        {"Topic": "Sensitivity Analysis", "Description": "Wilcoxon and key metrics recomputed after excluding specific projects. Edit SENSITIVITY_EXCLUDE_SETS at the top of this script to configure exclusion scenarios."},
    ]

    try:
        with pd.ExcelWriter('Javelin_Evaluation_Report_dense.xlsx', engine='openpyxl') as writer:
            # Sheet 1: Guide (explanatory — always first)
            pd.DataFrame(explanatory_rows).to_excel(writer, sheet_name="Guide", index=False)

            df_bugs     = pd.DataFrame(bug_rows)
            df_proj     = pd.DataFrame(proj_rows)
            df_global   = pd.DataFrame(global_rows)
            df_filtered = pd.DataFrame(filtered_rows)
            df_pw       = pd.DataFrame(proj_wilcoxon_rows)

            df_bugs.to_excel(writer,     sheet_name="Bug-Level Scores",     index=False, startrow=3)
            df_proj.to_excel(writer,     sheet_name="Project Summaries",    index=False, startrow=3)
            df_global.to_excel(writer,   sheet_name="Global & Statistics",  index=False, startrow=3)
            df_filtered.to_excel(writer, sheet_name="Filtered Analysis",    index=False, startrow=3)
            df_pw.to_excel(writer,       sheet_name="Per-Project Wilcoxon", index=False, startrow=3)
            pd.DataFrame(sensitivity_rows).to_excel(writer, sheet_name="Sensitivity Analysis", index=False, startrow=3)

            ws1 = writer.sheets["Bug-Level Scores"]
            ws1.cell(row=1, column=1, value="METRIC EXPLANATION: EXAM = (lines inspected before first fault found) / (total statements). LOWER is better.")
            ws1.cell(row=2, column=1, value="'Fully Detectable' = Yes means all ground truth lines were found in SBFL output. No = omission/interface bug components present.")
            ws1.cell(row=3, column=1, value="EXAM = 1.0 with blank Best Rank means: CSV file was missing (check GT Found = N/A) OR no ground truth lines were found in the SBFL output (check GT Found = 0/N). Both are worst-case penalties.")

            ws2 = writer.sheets["Project Summaries"]
            ws2.cell(row=1, column=1, value="METRIC EXPLANATION: Top-N = bugs where fault was within the first N statements inspected (ties handled via dense ranking).")
            ws2.cell(row=2, column=1, value="Avg Best Rank = mean dense rank of first faulty line across all bugs. LOWER is better for both EXAM and Avg Rank.")

            ws3 = writer.sheets["Global & Statistics"]
            ws3.cell(row=1, column=1, value="METRIC EXPLANATION: Overall aggregated performance and non-parametric statistical testing.")
            ws3.cell(row=2, column=1, value="Wilcoxon H1: Ochiai EXAM > Ochiai-MS EXAM (one-sided). P-Value < 0.05 means Ochiai-MS is significantly better.")

            ws4 = writer.sheets["Filtered Analysis"]
            ws4.cell(row=1, column=1, value="FILTERED ANALYSIS: Metrics computed only on bugs where ALL ground truth lines were found in SBFL output.")
            ws4.cell(row=2, column=1, value="Bugs with omission or interface components (partial GT coverage) are excluded. See 'Fully Detectable' column in Bug-Level Scores.")

            ws5 = writer.sheets["Per-Project Wilcoxon"]
            ws5.cell(row=1, column=1, value="PER-PROJECT WILCOXON: Signed-rank test (H1: Ochiai EXAM > Ochiai-MS EXAM) applied individually per Defects4J project.")
            ws5.cell(row=2, column=1, value="Minimum 6 paired bugs required. Shows whether Ochiai-MS improvement is statistically significant within each project.")

            ws6 = writer.sheets["Sensitivity Analysis"]
            ws6.cell(row=1, column=1, value="SENSITIVITY ANALYSIS: Global Wilcoxon and summary metrics recomputed after excluding specific projects from the dataset.")
            ws6.cell(row=2, column=1, value="Edit SENSITIVITY_EXCLUDE_SETS at the top of this script to add or modify exclusion scenarios. All other sheets always use the full dataset.")

        print(" Success: Generated 'Javelin_Evaluation_Report_dense.xlsx'.")
    except ImportError:
        print(" Note: 'openpyxl' not found. Falling back to CSV...")
        pd.DataFrame(bug_rows).to_csv('Javelin_Report_1_BugScores.csv', index=False)
        pd.DataFrame(proj_rows).to_csv('Javelin_Report_2_ProjectSummaries.csv', index=False)
        pd.DataFrame(global_rows).to_csv('Javelin_Report_3_GlobalStats.csv', index=False)
        pd.DataFrame(filtered_rows).to_csv('Javelin_Report_4_FilteredAnalysis.csv', index=False)
        pd.DataFrame(proj_wilcoxon_rows).to_csv('Javelin_Report_5_PerProjectWilcoxon.csv', index=False)
        print(" Success: Generated CSV report files.")

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
