#!/usr/bin/env python3
"""
Large Files and Directories Analyzer - Simple Version
=====================================================
Analyzes the codebase to identify large files and directories
for cleanup before zipping and GitHub upload.
"""

import os
import sys
from pathlib import Path
from collections import defaultdict

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

def analyze_directory(path, max_depth=3, current_depth=0):
    """Analyze directory structure and file sizes"""
    results = {
        'large_files': [],
        'directory_sizes': defaultdict(int),
        'total_size': 0,
        'file_count': 0
    }
    
    try:
        for item in Path(path).iterdir():
            if item.is_file():
                size = item.stat().st_size
                results['total_size'] += size
                results['file_count'] += 1
                
                # Track large files (>1MB)
                if size > 1024 * 1024:  # 1MB
                    results['large_files'].append({
                        'path': str(item),
                        'size': size,
                        'size_formatted': format_size(size)
                    })
                
                # Track directory sizes
                if current_depth < max_depth:
                    parent_dir = str(item.parent)
                    results['directory_sizes'][parent_dir] += size
                    
            elif item.is_dir() and current_depth < max_depth:
                # Recursively analyze subdirectories
                sub_results = analyze_directory(item, max_depth, current_depth + 1)
                results['total_size'] += sub_results['total_size']
                results['file_count'] += sub_results['file_count']
                results['large_files'].extend(sub_results['large_files'])
                
                # Merge directory sizes
                for dir_path, dir_size in sub_results['directory_sizes'].items():
                    results['directory_sizes'][dir_path] += dir_size
                    
    except PermissionError:
        print(f"Permission denied: {path}")
    except Exception as e:
        print(f"Error analyzing {path}: {e}")
    
    return results

def main():
    """Main analysis function"""
    print("=" * 80)
    print("LARGE FILES AND DIRECTORIES ANALYSIS")
    print("=" * 80)
    
    # Analyze current directory
    current_dir = Path.cwd()
    print(f"Analyzing: {current_dir}")
    print()
    
    results = analyze_directory(current_dir)
    
    # Sort large files by size
    results['large_files'].sort(key=lambda x: x['size'], reverse=True)
    
    # Sort directories by size
    sorted_dirs = sorted(results['directory_sizes'].items(), 
                        key=lambda x: x[1], reverse=True)
    
    print("SUMMARY")
    print("-" * 40)
    print(f"Total size: {format_size(results['total_size'])}")
    print(f"Total files: {results['file_count']}")
    print(f"Large files (>1MB): {len(results['large_files'])}")
    print()
    
    print("LARGEST DIRECTORIES")
    print("-" * 40)
    for i, (dir_path, size) in enumerate(sorted_dirs[:15]):
        rel_path = os.path.relpath(dir_path, current_dir)
        print(f"{i+1:2d}. {format_size(size):>10} - {rel_path}")
    print()
    
    print("LARGEST FILES")
    print("-" * 40)
    for i, file_info in enumerate(results['large_files'][:20]):
        rel_path = os.path.relpath(file_info['path'], current_dir)
        print(f"{i+1:2d}. {file_info['size_formatted']:>10} - {rel_path}")
    print()
    
    print("FILES TO CONSIDER REMOVING/IGNORING")
    print("-" * 40)
    
    # Identify files that should be removed or ignored
    removable_files = []
    for file_info in results['large_files']:
        file_path = file_info['path']
        file_name = os.path.basename(file_path)
        
        # Check for common large file patterns
        if any(pattern in file_name.lower() for pattern in [
            '.zip', '.db-wal', '.log', '.exe', '.dll', '.so', '.dylib',
            '__pycache__', '.pyc', '.pyd', '.egg-info'
        ]):
            removable_files.append(file_info)
    
    for file_info in removable_files:
        rel_path = os.path.relpath(file_info['path'], current_dir)
        print(f"* {file_info['size_formatted']:>10} - {rel_path}")
    
    print()
    print("RECOMMENDATIONS")
    print("-" * 40)
    print("1. Remove .zip files from Versions/ directory")
    print("2. Clean up .db-wal files (database write-ahead logs)")
    print("3. Remove old log files")
    print("4. Add .gitignore for:")
    print("   - *.zip")
    print("   - *.db-wal")
    print("   - *.log")
    print("   - __pycache__/")
    print("   - *.pyc")
    print("   - data/")
    print("   - Versions/")
    print("5. Consider using Git LFS for large files if needed")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
