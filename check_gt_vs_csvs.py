import os
import json

# ── CONFIG ────────────────────────────────────────────────────────────────────
GROUND_TRUTH_FILE = "ground_truth_merged.json"   # change to any ground_truth_*.json
CSV_FOLDER        = "ochiai_results"              # or "ochiai_ms_results" — either works
OUTPUT_FILTERED   = "ground_truth_filtered.json"  # saved only if you confirm
# ─────────────────────────────────────────────────────────────────────────────

# Load ground truth
with open(GROUND_TRUTH_FILE, "r") as f:
    ground_truth = json.load(f)

# Collect CSV names (strip .csv extension)
csv_files = {
    os.path.splitext(fname)[0]
    for fname in os.listdir(CSV_FOLDER)
    if fname.endswith(".csv")
}

# Cross-check
has_csv    = {}   # GT entries WITH a matching CSV
no_csv     = {}   # GT entries WITHOUT a matching CSV

for bug_id, entries in ground_truth.items():
    if bug_id in csv_files:
        has_csv[bug_id] = entries
    else:
        no_csv[bug_id] = entries

# ── REPORT ────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  Ground Truth File : {GROUND_TRUTH_FILE}")
print(f"  CSV Folder        : {CSV_FOLDER}/")
print(f"{'='*60}")
print(f"\n  Total GT entries  : {len(ground_truth)}")
print(f"  Has matching CSV  : {len(has_csv)}")
print(f"  NO matching CSV   : {len(no_csv)}")

if no_csv:
    print(f"\n{'─'*60}")
    print(f"  ⚠  ENTRIES WITH NO CSV (not tested — safe to remove):")
    print(f"{'─'*60}")
    for bug_id in sorted(no_csv.keys()):
        print(f"    {bug_id}")
else:
    print("\n  ✓  All GT entries have a matching CSV. Nothing to remove.")

if has_csv:
    print(f"\n{'─'*60}")
    print(f"  ✓  ENTRIES WITH CSV (tested — will be kept):")
    print(f"{'─'*60}")
    for bug_id in sorted(has_csv.keys()):
        print(f"    {bug_id}")

# ── OPTIONAL: SAVE FILTERED VERSION ──────────────────────────────────────────
if no_csv:
    print(f"\n{'='*60}")
    answer = input(
        f"  Save filtered ground truth (only entries WITH CSVs)\n"
        f"  → {OUTPUT_FILTERED}? [y/n]: "
    ).strip().lower()

    if answer == "y":
        with open(OUTPUT_FILTERED, "w") as f:
            json.dump(has_csv, f, indent=2)
        print(f"\n  ✓  Saved {len(has_csv)} entries to '{OUTPUT_FILTERED}'.")
        print(f"     Removed {len(no_csv)} entries with no matching CSV.")
    else:
        print("\n  Skipped. No file written.")

print()
