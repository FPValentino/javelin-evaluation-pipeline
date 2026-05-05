import os
import subprocess

def find_source_dirs(project_path):
    """Return a list of directories to diff for source changes.

    Priority:
    1. Top-level src/ or source/  (Chart, Cli, Csv, Lang, JacksonCore, JacksonDatabind, Jsoup)
    2. ALL subdirectories that contain a src/  (Gson: gson/, extras/, codegen/, etc.)
    Returns None if neither is found — caller falls back to full directory.
    """
    # 1. Top-level src/ or source/ (Chart uses source/)
    top_src = os.path.join(project_path, "src")
    if os.path.exists(top_src):
        return [top_src]
    top_source = os.path.join(project_path, "source")
    if os.path.exists(top_source):
        return [top_source]

    # 2. All subdirectories containing src/ (multi-module projects like Gson)
    dirs_with_src = []
    try:
        for item in sorted(os.listdir(project_path)):
            if item.startswith('.'):
                continue
            subdir = os.path.join(project_path, item)
            if os.path.isdir(subdir) and os.path.exists(os.path.join(subdir, "src")):
                dirs_with_src.append(subdir)
    except OSError:
        pass

    return dirs_with_src if dirs_with_src else None


def generate_all_patches():
    print("🛠️  Javelin Patch Generator (Defects4J Only)")

    # Look for buggy/fixed folders in the same directory as this script
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    patch_dir = os.path.expanduser("~/javelin-workspaces/gitbug_patches")

    # Create the patches folder if it doesn't exist
    os.makedirs(patch_dir, exist_ok=True)

    # Find all folders that end with "-buggy" AND start with "Defects4J"
    buggy_folders = [f for f in os.listdir(workspace_dir) if f.endswith("-buggy") and f.startswith("Defects4J")]

    if not buggy_folders:
        print("⚠️ No Defects4J buggy folders found to compare.")
        return

    print(f"Found {len(buggy_folders)} Defects4J bugs. Generating patches...\n")

    for buggy_folder in buggy_folders:
        bug_id = buggy_folder.replace("-buggy", "")
        buggy_path = os.path.join(workspace_dir, buggy_folder)
        fixed_path = os.path.join(workspace_dir, f"{bug_id}-fixed")

        patch_file_path = os.path.join(patch_dir, f"{bug_id}.patch")

        if not os.path.exists(fixed_path):
            print(f" ⚠️ Skipping {bug_id}: Could not find matching '-fixed' folder.")
            continue

        if os.path.exists(patch_file_path):
            print(f" -> Skipping {bug_id}: patch already exists.")
            continue

        print(f" -> Creating patch for {bug_id}...")

        buggy_dirs = find_source_dirs(buggy_path)
        fixed_dirs = find_source_dirs(fixed_path)

        if buggy_dirs and fixed_dirs:
            with open(patch_file_path, 'w') as f:
                for buggy_src, fixed_src in zip(buggy_dirs, fixed_dirs):
                    cmd = f'git diff --no-index "{buggy_src}" "{fixed_src}"'
                    subprocess.run(cmd, shell=True, stdout=f)
        else:
            print(f"    ⚠️  No src/ found for {bug_id} — diffing full directory (may include noise).")
            with open(patch_file_path, 'w') as f:
                cmd = f'git diff --no-index "{buggy_path}" "{fixed_path}"'
                subprocess.run(cmd, shell=True, stdout=f)

    print(f"\n✅ All patches successfully saved to: {patch_dir}")
    print("You can now run your 'build_ground_truth.py' script!")

if __name__ == "__main__":
    generate_all_patches()