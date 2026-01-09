#!/usr/bin/env python3
"""
Check Git Status for TelegramMoneyBot v8.0
Shows what files will be included/excluded when uploading to GitHub
"""

import os
import subprocess
import sys
from pathlib import Path

def run_git_command(cmd):
    """Run a git command and return the output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())
        return result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return "", str(e)

def check_git_status():
    """Check what files will be tracked by git"""
    print("🔍 Checking Git Status for TelegramMoneyBot v8.0")
    print("=" * 60)
    
    # Check if this is a git repository
    stdout, stderr = run_git_command("git status --porcelain")
    if stderr and "not a git repository" in stderr:
        print("❌ This is not a git repository!")
        print("Run 'git init' first to initialize the repository.")
        return
    
    # Check git status
    print("\n📊 Git Status:")
    stdout, stderr = run_git_command("git status --short")
    if stdout:
        lines = stdout.split('\n')
        print(f"Found {len(lines)} files with changes:")
        for line in lines:
            if line.strip():
                status = line[:2]
                filename = line[3:]
                if status.startswith('??'):
                    print(f"  📄 {filename} (untracked)")
                elif status.startswith('A'):
                    print(f"  ✅ {filename} (added)")
                elif status.startswith('M'):
                    print(f"  📝 {filename} (modified)")
                elif status.startswith('D'):
                    print(f"  🗑️ {filename} (deleted)")
    else:
        print("No changes detected.")
    
    # Check ignored files
    print("\n🚫 Ignored Files (will NOT be uploaded):")
    stdout, stderr = run_git_command("git status --ignored --porcelain")
    if stdout:
        ignored_files = [line.split()[-1] for line in stdout.split('\n') if line.startswith('!!')]
        if ignored_files:
            print(f"Found {len(ignored_files)} ignored files:")
            for file in ignored_files[:20]:  # Show first 20
                print(f"  🚫 {file}")
            if len(ignored_files) > 20:
                print(f"  ... and {len(ignored_files) - 20} more ignored files")
        else:
            print("No ignored files found.")
    else:
        print("No ignored files found.")
    
    # Check repository size
    print("\n📏 Repository Size Analysis:")
    stdout, stderr = run_git_command("git ls-files | wc -l")
    if stdout:
        file_count = int(stdout.strip())
        print(f"Total tracked files: {file_count}")
    
    # Check for large files
    print("\n📦 Large Files Check:")
    stdout, stderr = run_git_command("git ls-files | xargs ls -la | awk '$5 > 1000000 {print $5, $9}' | sort -nr")
    if stdout:
        large_files = stdout.strip().split('\n')
        if large_files and large_files[0]:
            print("Large files (>1MB) that WILL be uploaded:")
            for line in large_files[:10]:  # Show top 10
                if line.strip():
                    size, filename = line.split(' ', 1)
                    size_mb = int(size) / (1024 * 1024)
                    print(f"  📦 {filename} ({size_mb:.1f}MB)")
        else:
            print("✅ No large files found in tracked files.")
    else:
        print("✅ No large files found in tracked files.")
    
    # Check .gitignore effectiveness
    print("\n🔒 .gitignore Effectiveness:")
    critical_dirs = ['data/', 'Versions/', 'backups/', 'logs/', 'archives/', 'temp/']
    for dir_name in critical_dirs:
        if os.path.exists(dir_name):
            stdout, stderr = run_git_command(f"git check-ignore {dir_name}")
            if stdout:
                print(f"  ✅ {dir_name} is properly ignored")
            else:
                print(f"  ⚠️ {dir_name} is NOT ignored (may be uploaded!)")
        else:
            print(f"  ℹ️ {dir_name} does not exist")
    
    print("\n" + "=" * 60)
    print("✅ Git status check complete!")
    print("\n💡 Next steps:")
    print("1. Review the files above")
    print("2. Run 'git add .' to stage files")
    print("3. Run 'git commit -m \"Initial commit\"' to commit")
    print("4. Run 'git remote add origin <your-repo-url>' to add remote")
    print("5. Run 'git push -u origin main' to upload to GitHub")

if __name__ == "__main__":
    check_git_status()
