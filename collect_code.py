# =====================================
# collect_code.py
# Bundle a project into a single Markdown file for review
# No external dependencies. Python 3.8+
# =====================================
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from datetime import datetime
import zipfile
import sys
import textwrap

# ---------- Defaults ----------
DEFAULT_EXCLUDES = [
    ".git/**",
    ".hg/**",
    ".svn/**",
    ".idea/**",
    ".vscode/**",
    "venv/**",
    ".venv/**",
    "__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.pyd",
    "**/*.so",
    "**/*.dll",
    "**/*.dylib",
    "**/*.exe",
    "**/*.bin",
    "**/*.o",
    "**/*.obj",
    "**/*.class",
    "**/*.db",
    "**/*.sqlite*",
    "**/*.log",
    "**/*.tmp",
    "**/*.cache",
    "**/*.lock",
    # media/binaries
    "**/*.png",
    "**/*.jpg",
    "**/*.jpeg",
    "**/*.gif",
    "**/*.webp",
    "**/*.svg",
    "**/*.pdf",
    "**/*.mp3",
    "**/*.wav",
    "**/*.mp4",
    "**/*.mov",
    "**/*.zip",
    "**/*.7z",
    "**/*.tar",
    "**/*.gz",
    "**/*.bz2",
    "**/*.xz",
]

DEFAULT_INCLUDES = ["**/*"]

LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".ini": "",
    ".cfg": "",
    ".conf": "",
    ".md": "md",
    ".rst": "rst",
    ".txt": "",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".sh": "bash",
    ".ps1": "powershell",
    ".bat": "bat",
    ".dockerfile": "dockerfile",
    "Dockerfile": "dockerfile",
}


# ---------- Helpers ----------
def is_binary_bytes(sample: bytes) -> bool:
    if not sample:
        return False
    # Heuristic: if there's a NUL byte or high proportion of non-text
    if b"\x00" in sample:
        return True
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
    nontext = sample.translate(None, text_chars)
    return float(len(nontext)) / max(1, len(sample)) > 0.30


def detect_language(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in LANG_BY_EXT:
        return LANG_BY_EXT[ext]
    # Special-case Dockerfile
    if path.name.lower() == "dockerfile":
        return "dockerfile"
    return ""  # unknown


def sha1_of_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def matches_any(path: Path, patterns: Iterable[str], root: Path) -> bool:
    rel = path.relative_to(root).as_posix()
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def should_include(
    path: Path, includes: List[str], excludes: List[str], root: Path
) -> bool:
    # Include if it matches any include and does not match any exclude
    rel = path.relative_to(root).as_posix()
    inc_ok = any(fnmatch.fnmatch(rel, pat) for pat in includes)
    exc_bad = any(fnmatch.fnmatch(rel, pat) for pat in excludes)
    return inc_ok and not exc_bad


def read_text_safely(
    p: Path, max_kb: Optional[int]
) -> Tuple[Optional[str], Optional[str]]:
    try:
        raw = p.read_bytes()
    except Exception as e:
        return None, f"ERROR: could not read bytes ({e})"
    if max_kb is not None and len(raw) > max_kb * 1024:
        return (
            None,
            f"SKIPPED: file size {len(raw)/1024:.1f} KB exceeds --max-kb {max_kb}",
        )
    if is_binary_bytes(raw[:4096]):
        return None, "SKIPPED: appears to be binary"
    # Try UTF-8, then fallback
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc), None
        except Exception:
            continue
    return None, "ERROR: could not decode as text (utf-8/latin-1)"


def clamp_lines(s: str, max_lines: Optional[int]) -> Tuple[str, Optional[str]]:
    if max_lines is None:
        return s, None
    lines = s.splitlines()
    if len(lines) <= max_lines:
        return s, None
    # Show head+tail
    half = max_lines // 2
    head = lines[:half]
    tail = lines[-half:]
    snip = "\n".join(
        head + ["", f"... (snipped {len(lines) - 2*half} lines) ...", ""] + tail
    )
    return snip, f"NOTE: truncated to {max_lines} lines for brevity"


def make_toc(entries: List[Tuple[str, int]]) -> str:
    # entries: (relative_path, heading_index)
    out = []
    for rel, _ in entries:
        anchor = rel.lower().replace(" ", "-").replace("/", "-").replace("\\", "-")
        out.append(f"- [{rel}](#file--{anchor})")
    return "\n".join(out)


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


# ---------- Main bundler ----------
def bundle_project(
    root: Path,
    out_md: Path,
    includes: List[str],
    excludes: List[str],
    max_kb: Optional[int],
    max_lines: Optional[int],
    zip_sources: bool,
) -> None:
    root = root.resolve()
    files: List[Path] = []

    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if should_include(p, includes, excludes, root):
            files.append(p)

    files.sort(key=lambda p: p.relative_to(root).as_posix())

    md = io.StringIO()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md.write(f"# Project Bundle: {root.name}\n")
    md.write(f"_Generated on {now}_\n\n")

    # Summary
    total_bytes = 0
    for f in files:
        try:
            total_bytes += f.stat().st_size
        except Exception:
            pass
    md.write(f"- Root: `{root}`\n")
    md.write(f"- Files considered: **{len(files)}**\n")
    md.write(f"- Raw size (pre-filters): **{human_bytes(total_bytes)}**\n")
    if max_kb:
        md.write(f"- Max file size: **{max_kb} KB**\n")
    if max_lines:
        md.write(f"- Max lines per file: **{max_lines}**\n")
    md.write("\n---\n\n")

    # TOC
    toc_entries: List[Tuple[str, int]] = [
        (f.relative_to(root).as_posix(), i) for i, f in enumerate(files, 1)
    ]
    md.write("## Table of Contents\n\n")
    md.write(make_toc(toc_entries))
    md.write("\n\n---\n")

    # Per-file sections
    for f in files:
        rel = f.relative_to(root).as_posix()
        raw = None
        note = None
        raw, err = read_text_safely(f, max_kb=max_kb)
        sha = None
        lang = detect_language(f)

        if raw is not None:
            sha = sha1_of_bytes(raw.encode("utf-8", errors="ignore"))
            content, trunc_note = clamp_lines(raw, max_lines=max_lines)
            note = trunc_note
        else:
            content = ""
            note = err or "SKIPPED"

        anchor = rel.lower().replace(" ", "-").replace("/", "-").replace("\\", "-")
        md.write(f"\n\n## File — {rel}\n")
        md.write(f"<a id='file--{anchor}'></a>\n\n")
        if sha:
            md.write(f"- SHA1: `{sha}`\n")
        try:
            sz = human_bytes(f.stat().st_size)
            md.write(f"- Size: {sz}\n")
        except Exception:
            pass
        if note:
            md.write(f"- Note: {note}\n")
        md.write("\n")

        if content:
            fence = lang if lang else ""
            md.write(f"```{fence}\n{content}\n```\n")
        else:
            md.write("_(content omitted)_\n")

    out_md.write_text(md.getvalue(), encoding="utf-8")
    print(f"[OK] Wrote markdown bundle → {out_md}")

    if zip_sources:
        zip_path = out_md.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                # Include only text files we successfully read; skip known binaries by heuristic too
                try:
                    raw = f.read_bytes()
                except Exception:
                    continue
                if is_binary_bytes(raw[:4096]):
                    continue
                zf.write(f, arcname=f.relative_to(root).as_posix())
        print(f"[OK] Wrote source ZIP (text files only) → {zip_path}")


# ---------- CLI ----------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bundle a codebase into a single Markdown file with language-aware code fences."
    )
    p.add_argument(
        "--root", default=".", help="Project root (default: current directory)"
    )
    p.add_argument("--out", default="project_dump.md", help="Output markdown path")
    p.add_argument(
        "--include", nargs="*", default=DEFAULT_INCLUDES, help="Include glob(s)"
    )
    p.add_argument(
        "--exclude", nargs="*", default=DEFAULT_EXCLUDES, help="Exclude glob(s)"
    )
    p.add_argument(
        "--max-kb", type=int, default=None, help="Skip files larger than this (in KB)"
    )
    p.add_argument(
        "--max-lines",
        type=int,
        default=None,
        help="Truncate long text files to this many lines (head+tail)",
    )
    p.add_argument(
        "--zip", action="store_true", help="Also create a .zip of text sources"
    )
    return p.parse_args(argv)


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    out = Path(args.out)
    includes = list(args.include)
    excludes = list(args.exclude)
    # Normalize includes/excludes to POSIX-like matching
    includes = [i.replace("\\", "/") for i in includes]
    excludes = [e.replace("\\", "/") for e in excludes]
    bundle_project(
        root=root,
        out_md=out,
        includes=includes,
        excludes=excludes,
        max_kb=args.max_kb,
        max_lines=args.max_lines,
        zip_sources=args.zip,
    )


if __name__ == "__main__":
    main()
