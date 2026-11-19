"""NOVA — Production Release Packager (v1.0.0).

Generates a standalone, clean release distribution zip archive for Windows:
`dist/NOVA-v1.0.0-windows-x64.zip`
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

VERSION = "1.0.0"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
ARCHIVE_NAME = f"NOVA-v{VERSION}-windows-x64.zip"


def package_release():
    print("=" * 60)
    print(f"   NOVA v{VERSION} — Production Release Packager")
    print("=" * 60)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    target_zip = DIST_DIR / ARCHIVE_NAME

    include_dirs = [
        "backend",
        "desktop",
        "docs",
        "frontend/dist",
        "local_agent",
        "scripts",
    ]

    include_files = [
        "README.md",
        "requirements.txt",
        "pyproject.toml",
        ".env.example",
    ]

    # Exclude unwanted build artifacts or temporary files
    exclude_patterns = [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".pytest_cache",
        "node_modules",
        ".git",
        ".venv",
        "tests",
        "*.db",
        "*.log",
    ]

    print(f"\n[1/3] Gathering release assets from {PROJECT_ROOT}...")

    total_files = 0
    with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # Include top-level files
        for rel_file in include_files:
            file_path = PROJECT_ROOT / rel_file
            if file_path.exists():
                arcname = f"NOVA-v{VERSION}/{rel_file}"
                zf.write(file_path, arcname)
                total_files += 1

        # Include directories
        for rel_dir in include_dirs:
            dir_path = PROJECT_ROOT / rel_dir
            if not dir_path.exists():
                print(f"[WARNING] Directory not found: {rel_dir}")
                continue

            for root, dirs, files in os.walk(dir_path):
                # Filter out excluded directory names
                dirs[:] = [d for d in dirs if not any(d.startswith(p.rstrip("*")) for p in ["__pycache__", ".pytest_cache", "node_modules"])]

                for file in files:
                    if file.endswith((".pyc", ".pyo", ".log", ".tmp")):
                        continue
                    full_path = Path(root) / file
                    rel_to_proj = full_path.relative_to(PROJECT_ROOT)
                    arcname = f"NOVA-v{VERSION}/{rel_to_proj.as_posix()}"
                    zf.write(full_path, arcname)
                    total_files += 1

    archive_size_mb = round(target_zip.stat().st_size / (1024 * 1024), 2)
    print(f"[2/3] Archived {total_files} files successfully.")
    print(f"[3/3] Output generated: {target_zip} ({archive_size_mb} MB)")
    print("=" * 60)
    print("   Release distribution build complete!")
    print("=" * 60)


if __name__ == "__main__":
    package_release()
