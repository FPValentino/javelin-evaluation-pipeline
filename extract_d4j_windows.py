import os
import shutil
import subprocess
import sys

def install_dependencies():
    """Checks for and automatically installs missing required libraries."""
    required_packages = ["pandas", "scipy", "tqdm", "unidiff", "openpyxl", "questionary"]
    print("🔍 Checking system dependencies...")

    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            print(f"📦 Installing missing package: {package}...")
            # Added --break-system-packages to bypass modern Linux PEP 668 restrictions
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--break-system-packages", "--quiet"])

    print("✅ All dependencies are installed and ready!\n")

# Run dependency check BEFORE importing third-party libraries
install_dependencies()

import questionary

def run_command(cmd):
    """Runs a command securely and captures output."""
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"❌ Error executing: {cmd}")
        print(result.stderr)
        return False
    return True

def parse_bug_ids(input_str):
    """Parses a string like '1, 2, 5-7' into a sorted list of integers [1, 2, 5, 6, 7]."""
    bug_ids = set()
    parts = [p.strip() for p in input_str.split(',')]
    for part in parts:
        if not part:
            continue
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                bug_ids.update(range(start, end + 1))
            except ValueError:
                print(f"⚠️ Invalid range: {part}")
        else:
            try:
                bug_ids.add(int(part))
            except ValueError:
                print(f"⚠️ Invalid number: {part}")
    return sorted(list(bug_ids))

def main():
    print("🎯 Defects4J Target Selector (Interactive Mode)")

    windows_dir = "/mnt/c/Users/Paul/Downloads/THESIS/Javelin"
    staging_dir = "/home/paul/defects4j/staging"
    os.makedirs(windows_dir, exist_ok=True)
    os.makedirs(staging_dir, exist_ok=True)

    projects = {
        "Chart (JFreeChart)": "Chart",
        "Cli (Apache Commons CLI)": "Cli",
        "Closure (Google Closure Compiler)": "Closure",
        "Codec (Apache Commons Codec)": "Codec",
        "Collections (Apache Commons Collections)": "Collections",
        "Compress (Apache Commons Compress)": "Compress",
        "Csv (Apache Commons CSV)": "Csv",
        "Gson (Google Gson)": "Gson",
        "JacksonCore (Jackson Core)": "JacksonCore",
        "JacksonDatabind (Jackson Databind)": "JacksonDatabind",
        "JacksonXml (Jackson XML format)": "JacksonXml",
        "Jsoup (Jsoup HTML parser)": "Jsoup",
        "JxPath (Apache Commons JXPath)": "JxPath",
        "Lang (Apache Commons Lang)": "Lang",
        "Math (Apache Commons Math)": "Math",
        "Mockito (Mockito Mocking framework)": "Mockito",
        "Time (Joda-Time)": "Time"
    }

    # 1. UI: Multi-select projects (checkbox)
    selected_project_labels = questionary.checkbox(
        "Select projects to extract (Space to toggle, Enter to confirm):",
        choices=list(projects.keys())
    ).ask()

    if not selected_project_labels:
        print("No projects selected. Operation cancelled.")
        sys.exit(0)

    # 2. UI: Ask for bug IDs per project
    extraction_queue = []
    for label in selected_project_labels:
        project_id = projects[label]
        bug_input = questionary.text(
            f"Bug IDs for {project_id} (e.g., '1-5,7-10' or 'all'):"
        ).ask()

        if not bug_input:
            print(f"   Skipping {project_id}.")
            continue

        if bug_input.strip().lower() == "all":
            result = subprocess.run(
                f"defects4j query -p {project_id} -q 'bug.id'",
                shell=True, text=True, capture_output=True
            )
            if result.returncode == 0 and result.stdout.strip():
                bug_ids = sorted(int(x) for x in result.stdout.strip().split('\n') if x.strip())
            else:
                print(f"   ⚠️ Could not query bug count for {project_id}. Skipping.")
                continue
        else:
            bug_ids = parse_bug_ids(bug_input)

        if bug_ids:
            extraction_queue.append((project_id, bug_ids))

    if not extraction_queue:
        print("Nothing to extract.")
        sys.exit(0)

    # 3. Show summary before starting
    total_bugs = sum(len(bugs) for _, bugs in extraction_queue)
    print(f"\n📋 Extraction Queue Summary:")
    print("-" * 40)
    for project_id, bug_ids in extraction_queue:
        print(f"   {project_id}: {len(bug_ids)} bugs ({bug_ids[0]}-{bug_ids[-1]})")
    print(f"   TOTAL: {total_bugs} bugs across {len(extraction_queue)} projects")
    print("-" * 40)

    confirm = questionary.confirm("Proceed with extraction?").ask()
    if not confirm:
        print("Operation cancelled.")
        sys.exit(0)

    print(f"\nStarting extraction...\n")

    success_count = 0
    extracted = []
    for selected_project, selected_bugs in extraction_queue:
        print(f"\n{'='*50}")
        print(f"📁 Project: {selected_project} ({len(selected_bugs)} bugs)")
        print(f"{'='*50}")

        for bug_num in selected_bugs:
            bug_id = f"Defects4J-{selected_project}-{bug_num}"
            buggy_staging = os.path.join(staging_dir, f"{bug_id}-buggy")
            fixed_staging = os.path.join(staging_dir, f"{bug_id}-fixed")
            buggy_final = os.path.join(windows_dir, f"{bug_id}-buggy")
            fixed_final = os.path.join(windows_dir, f"{bug_id}-fixed")

            print(f"📦 Processing {bug_id}...")

            # Step A: Safe Buggy Extraction
            if os.path.exists(buggy_final):
                print(f"   -> Buggy folder exists in destination. Skipping.")
            elif os.path.exists(buggy_staging):
                print(f"   -> Buggy folder exists in staging. Will copy to Windows.")
            else:
                print(f"   -> Pulling buggy environment...")
                cmd_buggy = f"defects4j checkout -p {selected_project} -v {bug_num}b -w {buggy_staging}"
                if not run_command(cmd_buggy):
                    continue

            # Step B: Safe Fixed Extraction
            if os.path.exists(fixed_final):
                print(f"   -> Fixed folder exists in destination. Skipping.")
            elif os.path.exists(fixed_staging):
                print(f"   -> Fixed folder exists in staging. Will copy to Windows.")
            else:
                print(f"   -> Pulling developer-fixed environment...")
                cmd_fixed = f"defects4j checkout -p {selected_project} -v {bug_num}f -w {fixed_staging}"
                if not run_command(cmd_fixed):
                    continue

            extracted.append(bug_id)
            success_count += 1

    # Move from fast Linux filesystem to Windows
    if extracted:
        print(f"\n📂 Copying {len(extracted)} bugs to Windows directory...")
        for bug_id in extracted:
            for suffix in ["-buggy", "-fixed"]:
                src = os.path.join(staging_dir, f"{bug_id}{suffix}")
                dst = os.path.join(windows_dir, f"{bug_id}{suffix}")
                if os.path.exists(src) and not os.path.exists(dst):
                    print(f"   -> Moving {bug_id}{suffix} to Windows...")
                    shutil.copytree(src, dst)
                    shutil.rmtree(src)
        print("✅ All files moved to Windows!")

    print(f"\n✅ All done! Successfully extracted {success_count}/{total_bugs} bugs to {windows_dir}")
    print("\n========================================================")
    print("NEXT STEPS:")
    print("1. Compile the buggy project (Ensure your terminal is running Java 8!):")
    print(f"   cd <project-folder>")
    print("   defects4j compile")
    print("   defects4j test")
    print("2. Run Javelin in IntelliJ to generate your .csv ranking.")
    print("3. Generate patches and run the Evaluation Script!")
    print("========================================================")

if __name__ == "__main__":
    main()
