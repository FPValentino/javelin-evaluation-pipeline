import json
import glob
import os
import sys

DIRECTORY = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(DIRECTORY, "ground_truth_merged.json")

def merge_ground_truths():
    pattern = os.path.join(DIRECTORY, "ground_truth_*.json")
    files = sorted(glob.glob(pattern))

    if not files:
        print("No ground_truth_*.json files found (expected ground_truth_1.json, ground_truth_2.json, etc.)")
        sys.exit(1)

    print(f"Found {len(files)} file(s) to merge:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    print()

    merged = {}
    skipped_count = 0
    added_count = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"Processing {filename} ({len(data)} projects)...")

        for project_name, entries in data.items():
            if project_name in merged:
                print(f"  '{project_name}' already exists, skipping.")
                skipped_count += 1
            else:
                merged[project_name] = entries
                added_count += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=4)

    print(f"\nDone. Added: {added_count}, Skipped (duplicates): {skipped_count}")
    print(f"Merged output saved to: {os.path.basename(OUTPUT_FILE)}")

if __name__ == "__main__":
    merge_ground_truths()
