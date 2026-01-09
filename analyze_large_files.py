#!/usr/bin/env python3
"""
Analyze Large Files in TelegramMoneyBot v8.0 Codebase
Finds and reports the largest files in the project
"""

import os
import sys
from pathlib import Path
from collections import defaultdict

def get_file_size(file_path):
    """Get file size in bytes"""
    try:
        return os.path.getsize(file_path)
    except (OSError, FileNotFoundError):
        return 0

def format_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def analyze_large_files():
    """Analyze and report large files in the codebase"""
    print("🔍 Analyzing Large Files in TelegramMoneyBot v8.0")
    print("=" * 60)
    
    # Files to exclude from analysis
    exclude_patterns = [
        '.git',
        '__pycache__',
        '.vscode',
        '.idea',
        'node_modules',
        'venv',
        '.venv',
        'env',
        '.env'
    ]
    
    # File extensions to prioritize
    important_extensions = {
        '.py': 'Python Code',
        '.md': 'Documentation',
        '.txt': 'Text Files',
        '.json': 'JSON Config',
        '.yaml': 'YAML Config',
        '.yml': 'YAML Config',
        '.sql': 'SQL Files',
        '.db': 'Database Files',
        '.sqlite': 'SQLite Database',
        '.log': 'Log Files',
        '.zip': 'Archive Files',
        '.exe': 'Executable Files',
        '.dll': 'Dynamic Libraries',
        '.pdf': 'PDF Documents',
        '.docx': 'Word Documents',
        '.png': 'PNG Images',
        '.jpg': 'JPEG Images',
        '.jpeg': 'JPEG Images',
        '.gif': 'GIF Images',
        '.mp4': 'MP4 Videos',
        '.avi': 'AVI Videos',
        '.mov': 'MOV Videos'
    }
    
    file_sizes = []
    total_size = 0
    file_count = 0
    
    print("📊 Scanning files...")
    
    # Walk through all files
    for root, dirs, files in os.walk('.'):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not any(pattern in d for pattern in exclude_patterns)]
        
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, '.')
            
            # Skip if in excluded directory
            if any(pattern in relative_path for pattern in exclude_patterns):
                continue
            
            try:
                size = get_file_size(file_path)
                if size > 0:
                    file_sizes.append((relative_path, size))
                    total_size += size
                    file_count += 1
            except Exception as e:
                print(f"⚠️ Error reading {relative_path}: {e}")
    
    # Sort by size (largest first)
    file_sizes.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📈 Summary:")
    print(f"Total files: {file_count:,}")
    print(f"Total size: {format_size(total_size)}")
    print(f"Average file size: {format_size(total_size / file_count if file_count > 0 else 0)}")
    
    # Show top 20 largest files
    print(f"\n🏆 Top 20 Largest Files:")
    print("-" * 80)
    print(f"{'Rank':<4} {'Size':<10} {'Type':<15} {'File Path'}")
    print("-" * 80)
    
    for i, (file_path, size) in enumerate(file_sizes[:20], 1):
        file_ext = Path(file_path).suffix.lower()
        file_type = important_extensions.get(file_ext, 'Other')
        
        # Truncate long paths
        display_path = file_path if len(file_path) <= 50 else "..." + file_path[-47:]
        
        print(f"{i:<4} {format_size(size):<10} {file_type:<15} {display_path}")
    
    # Analyze by file type
    print(f"\n📊 Analysis by File Type:")
    print("-" * 60)
    
    type_stats = defaultdict(lambda: {'count': 0, 'size': 0})
    
    for file_path, size in file_sizes:
        file_ext = Path(file_path).suffix.lower()
        file_type = important_extensions.get(file_ext, 'Other')
        type_stats[file_type]['count'] += 1
        type_stats[file_type]['size'] += size
    
    # Sort by total size
    sorted_types = sorted(type_stats.items(), key=lambda x: x[1]['size'], reverse=True)
    
    print(f"{'Type':<15} {'Count':<8} {'Total Size':<12} {'Avg Size':<12}")
    print("-" * 60)
    
    for file_type, stats in sorted_types:
        avg_size = stats['size'] / stats['count'] if stats['count'] > 0 else 0
        print(f"{file_type:<15} {stats['count']:<8} {format_size(stats['size']):<12} {format_size(avg_size):<12}")
    
    # Show files larger than 1MB
    large_files = [(path, size) for path, size in file_sizes if size > 1024 * 1024]
    
    if large_files:
        print(f"\n🚨 Files Larger Than 1MB:")
        print("-" * 60)
        for file_path, size in large_files:
            print(f"{format_size(size):<10} {file_path}")
    else:
        print(f"\n✅ No files larger than 1MB found!")
    
    # Show database files specifically
    db_files = [(path, size) for path, size in file_sizes if any(ext in path.lower() for ext in ['.db', '.sqlite', '.sqlite3'])]
    
    if db_files:
        print(f"\n🗄️ Database Files:")
        print("-" * 60)
        for file_path, size in db_files:
            print(f"{format_size(size):<10} {file_path}")
    
    # Show log files
    log_files = [(path, size) for path, size in file_sizes if path.endswith('.log') or '.log.' in path]
    
    if log_files:
        print(f"\n📝 Log Files:")
        print("-" * 60)
        for file_path, size in log_files:
            print(f"{format_size(size):<10} {file_path}")
    
    # Show archive files
    archive_files = [(path, size) for path, size in file_sizes if any(ext in path.lower() for ext in ['.zip', '.tar.gz', '.rar', '.7z', '.gz'])]
    
    if archive_files:
        print(f"\n📦 Archive Files:")
        print("-" * 60)
        for file_path, size in archive_files:
            print(f"{format_size(size):<10} {file_path}")
    
    print(f"\n" + "=" * 60)
    print("✅ Analysis complete!")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if large_files:
        print("• Consider adding large files to .gitignore")
        print("• Database files should be excluded from git")
        print("• Log files should be excluded from git")
        print("• Archive files should be excluded from git")
    else:
        print("• Repository size looks good for GitHub upload")
        print("• No large files detected that would cause issues")

if __name__ == "__main__":
    analyze_large_files()