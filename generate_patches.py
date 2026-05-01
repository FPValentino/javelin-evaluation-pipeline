import os
import subprocess

def generate_all_patches():
    print("🛠️  Javelin Patch Generator")
    
    # Dynamically ask for the WSL username to build the path
    wsl_user = input("Enter your WSL Ubuntu username (e.g., ferdinand): ").strip()
    workspace_dir = fr"\\wsl.localhost\Ubuntu\home\{wsl_user}\javelin-workspaces"
    patch_dir = os.path.join(workspace_dir, "gitbug_patches")
    
    # Create the patches folder if it doesn't exist
    os.makedirs(patch_dir, exist_ok=True)
    
    if not os.path.exists(workspace_dir):
        print(f"❌ Error: Could not find {workspace_dir}. Check your WSL connection and username.")
        return

    # Find all folders that end with "-buggy"
    buggy_folders = [f for f in os.listdir(workspace_dir) if f.endswith("-buggy")]
    
    if not buggy_folders:
        print("⚠️ No buggy folders found to compare.")
        return

    print(f"Found {len(buggy_folders)} bugs. Generating patches...\n")

    for buggy_folder in buggy_folders:
        bug_id = buggy_folder.replace("-buggy", "")
        buggy_path = os.path.join(workspace_dir, buggy_folder)
        fixed_path = os.path.join(workspace_dir, f"{bug_id}-fixed")
        
        patch_file_path = os.path.join(patch_dir, f"{bug_id}.patch")

        # Check if the matching fixed folder actually exists
        if os.path.exists(fixed_path):
            print(f" -> Creating patch for {bug_id}...")
            
            buggy_src = os.path.join(buggy_path, "src")
            fixed_src = os.path.join(fixed_path, "src")
            
            # Use quotes around paths to protect them during the Windows shell command
            if os.path.exists(buggy_src) and os.path.exists(fixed_src):
                cmd = f'git diff --no-index "{buggy_src}" "{fixed_src}" > "{patch_file_path}"'
            else:
                cmd = f'git diff --no-index "{buggy_path}" "{fixed_path}" > "{patch_file_path}"'

            subprocess.run(cmd, shell=True)
        else:
            print(f" ⚠️ Skipping {bug_id}: Could not find matching '-fixed' folder.")

    print(f"\n✅ All patches successfully saved to: {patch_dir}")
    print("You can now run your 'build_ground_truth.py' script!")

if __name__ == "__main__":
    generate_all_patches()
