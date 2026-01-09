#!/usr/bin/env python3
"""
Large Files Cleanup Script
==========================
Removes large files to reduce directory size for zipping and GitHub upload.
"""

import os
import shutil
from pathlib import Path

def format_size(size_bytes):
    """Format size in human readable format"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f}{size_names[i]}"

def get_file_size(file_path):
    """Get file size in bytes"""
    try:
        return os.path.getsize(file_path)
    except:
        return 0

def cleanup_versions():
    """SKIP Versions directory - preserving version backups"""
    print("SKIPPING Versions/ directory - preserving version backups")
    print("  - Versions/ contains important version history")
    print("  - These are your backups and should be kept")
    return 0

def cleanup_database_wal():
    """Remove ONLY .db-wal files (database write-ahead logs) - SAFE"""
    wal_files = []
    
    # Find all .db-wal files
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith('.db-wal'):
                wal_files.append(Path(root) / file)
    
    total_freed = 0
    print(f"Found {len(wal_files)} .db-wal files")
    print("  - These are write-ahead logs (safe to remove)")
    print("  - Main database files (.db) are preserved")
    
    for wal_file in wal_files:
        size = get_file_size(wal_file)
        print(f"Removing: {wal_file} ({format_size(size)})")
        try:
            wal_file.unlink()
            total_freed += size
        except Exception as e:
            print(f"Error removing {wal_file}: {e}")
    
    return total_freed

def cleanup_logs():
    """SKIP log files - preserving important logs"""
    print("SKIPPING log files - preserving important logs")
    print("  - Log files contain valuable debugging information")
    print("  - Current logs are needed for troubleshooting")
    print("  - Only remove manually if you're sure you don't need them")
    return 0

def cleanup_cache():
    """Remove __pycache__ directories and .pyc files"""
    total_freed = 0
    
    # Remove __pycache__ directories
    for root, dirs, files in os.walk("."):
        if '__pycache__' in dirs:
            cache_dir = Path(root) / '__pycache__'
            size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
            print(f"Removing: {cache_dir} ({format_size(size)})")
            try:
                shutil.rmtree(cache_dir)
                total_freed += size
            except Exception as e:
                print(f"Error removing {cache_dir}: {e}")
    
    # Remove .pyc files
    pyc_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith('.pyc'):
                pyc_files.append(Path(root) / file)
    
    for pyc_file in pyc_files:
        size = get_file_size(pyc_file)
        print(f"Removing: {pyc_file} ({format_size(size)})")
        try:
            pyc_file.unlink()
            total_freed += size
        except Exception as e:
            print(f"Error removing {pyc_file}: {e}")
    
    return total_freed

def cleanup_other_large_files():
    """Remove ONLY safe large files - preserving important executables"""
    total_freed = 0
    
    # Only remove clearly safe files
    files_to_remove = [
        "$null.zip"  # This appears to be a corrupted/empty zip file
    ]
    
    # Files to preserve (important for bot operation)
    files_to_preserve = [
        "ngrok.exe",        # Needed for tunneling
        ".ngrok.exe.old"    # Backup of ngrok
    ]
    
    print("PRESERVING important files:")
    for file_name in files_to_preserve:
        file_path = Path(file_name)
        if file_path.exists():
            size = get_file_size(file_path)
            print(f"  - Keeping: {file_name} ({format_size(size)})")
    
    print("\nRemoving only clearly safe files:")
    for file_name in files_to_remove:
        file_path = Path(file_name)
        if file_path.exists():
            size = get_file_size(file_path)
            print(f"Removing: {file_name} ({format_size(size)})")
            try:
                file_path.unlink()
                total_freed += size
            except Exception as e:
                print(f"Error removing {file_name}: {e}")
    
    return total_freed

def create_gitignore():
    """Create .gitignore file"""
    gitignore_content = """# Large files and directories
*.zip
*.db-wal
*.log
*.log.*
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Data directories
data/
Versions/

# IDE files
.vscode/
.idea/
*.swp
*.swo
*~

# OS files
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    
    print("Created .gitignore file")

def main():
    """Main cleanup function - SAFE VERSION"""
    print("=" * 80)
    print("SAFE LARGE FILES CLEANUP")
    print("=" * 80)
    print("This script will ONLY remove safe files:")
    print("  - Database WAL files (write-ahead logs)")
    print("  - Python cache files (__pycache__)")
    print("  - Corrupted zip files ($null.zip)")
    print()
    print("PRESERVING important files:")
    print("  - Versions/ directory (your backups)")
    print("  - Log files (for debugging)")
    print("  - ngrok.exe (needed for tunneling)")
    print("  - Main database files (.db)")
    print("  - Source code files")
    print("=" * 80)
    
    total_freed = 0
    
    print("\n1. SKIPPING Versions/ directory (preserving backups)...")
    total_freed += cleanup_versions()
    
    print("\n2. Cleaning up database WAL files (SAFE)...")
    total_freed += cleanup_database_wal()
    
    print("\n3. SKIPPING log files (preserving for debugging)...")
    total_freed += cleanup_logs()
    
    print("\n4. Cleaning up cache files (SAFE)...")
    total_freed += cleanup_cache()
    
    print("\n5. Cleaning up other large files (SAFE ONLY)...")
    total_freed += cleanup_other_large_files()
    
    print("\n6. SKIPPING .gitignore creation (already updated)...")
    print("  - .gitignore already updated to prevent large files")
    
    print("\n" + "=" * 80)
    print(f"SAFE CLEANUP COMPLETE")
    print(f"Total space freed: {format_size(total_freed)}")
    print("=" * 80)
    
    print("\nWHAT WAS PRESERVED:")
    print("  - Versions/ directory (your version backups)")
    print("  - All log files (for debugging)")
    print("  - ngrok.exe (needed for tunneling)")
    print("  - Main database files (.db)")
    print("  - All source code files")
    print()
    print("WHAT WAS REMOVED:")
    print("  - Database WAL files (write-ahead logs)")
    print("  - Python cache files (__pycache__)")
    print("  - Corrupted zip files ($null.zip)")
    print()
    print("EXPECTED RESULT:")
    print(f"  - Directory size reduced by ~{format_size(total_freed)}")
    print("  - Bot functionality preserved")
    print("  - Safe for zipping and GitHub upload")

if __name__ == "__main__":
    main()
