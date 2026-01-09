#!/usr/bin/env python3
"""
Setup Git Repository for TelegramMoneyBot v8.0
Initializes git repository and prepares for GitHub upload
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return success status"""
    print(f"🔄 {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode == 0:
            print(f"✅ {description} - Success")
            return True
        else:
            print(f"❌ {description} - Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - Error: {e}")
        return False

def setup_git_repository():
    """Setup git repository for GitHub upload"""
    print("🚀 Setting up Git Repository for TelegramMoneyBot v8.0")
    print("=" * 60)
    
    # Check if git is installed
    if not run_command("git --version", "Checking Git installation"):
        print("❌ Git is not installed. Please install Git first.")
        return False
    
    # Initialize git repository if not already initialized
    if not os.path.exists('.git'):
        if not run_command("git init", "Initializing Git repository"):
            return False
    else:
        print("ℹ️ Git repository already initialized")
    
    # Add all files (respecting .gitignore)
    if not run_command("git add .", "Adding files to Git (respecting .gitignore)"):
        return False
    
    # Check what will be committed
    print("\n📋 Files that will be committed:")
    run_command("git status --short", "Checking staged files")
    
    # Create initial commit
    if not run_command('git commit -m "Initial commit: TelegramMoneyBot v8.0 - Advanced AI Trading System"', "Creating initial commit"):
        return False
    
    print("\n✅ Git repository setup complete!")
    print("\n📋 Next steps to upload to GitHub:")
    print("1. Create a new repository on GitHub")
    print("2. Copy the repository URL")
    print("3. Run: git remote add origin <your-repo-url>")
    print("4. Run: git branch -M main")
    print("5. Run: git push -u origin main")
    
    print("\n🔍 To check what files will be uploaded, run:")
    print("python check_git_status.py")
    
    return True

if __name__ == "__main__":
    setup_git_repository()
