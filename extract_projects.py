import json
import re
from collections import defaultdict

with open("ground_truth.json", "r") as f:
    ground_truth = json.load(f)

# Parse each key into (project, number) and group
projects = defaultdict(list)
for bug_id in ground_truth:
    match = re.match(r"Defects4J-(\w+)-(\d+)", bug_id)
    if match:
        project = match.group(1)
        number = int(match.group(2))
        projects[project].append((number, bug_id))

# Sort projects alphabetically, bugs numerically within each project
sorted_projects = sorted(projects.keys())

output = {
    "summary": {
        "total_bugs": len(ground_truth),
        "total_projects": len(sorted_projects),
        "projects": sorted_projects,
    },
    "by_project": {},
    "ordered_bugs": [],
}

for project in sorted_projects:
    bugs = sorted(projects[project], key=lambda x: x[0])
    output["by_project"][project] = [
        {"bug_id": bug_id, "fault_locations": len(ground_truth[bug_id])}
        for _, bug_id in bugs
    ]
    for _, bug_id in bugs:
        output["ordered_bugs"].append(bug_id)

with open("projects_ordered.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"Written to projects_ordered.json — {len(ground_truth)} bugs across {len(sorted_projects)} projects")
