"""Build Git Manager as a standalone .exe using PyInstaller.

File Name: build.py
Author: hang.shi
Time: 2026-05-04
Version: 2
Description: Build Git Manager standalone executable with PyInstaller
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Git Manager")
    parser.add_argument(
        "--mode",
        choices=["onedir", "onefile"],
        default="onedir",
        help="Packaging mode (default: onedir for faster startup).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"

    if not venv_python.exists():
        print("ERROR: .venv not found. Create it first:")
        print(f"  {sys.executable} -m venv .venv")
        sys.exit(1)

    # Ensure PyInstaller is installed
    print("Checking PyInstaller...")
    result = subprocess.run(
        [str(venv_python), "-m", "PyInstaller", "--version"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("Installing PyInstaller...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "pyinstaller"],
            check=True,
        )

    icon_path = project_root / "git_manager" / "git_manager.ico"
    if not icon_path.exists():
        print("ERROR: Icon not found. Run generate_icon.py first.")
        sys.exit(1)

    entry_point = project_root / "git_manager" / "main.py"
    sep = ";" if sys.platform == "win32" else ":"
    add_data = f"git_manager\\git_manager.ico{sep}."

    mode_flag = "--onedir" if args.mode == "onedir" else "--onefile"

    print(f"Building GitManager.exe (mode={args.mode})...")
    cmd = [
        str(venv_python), "-m", "PyInstaller",
        mode_flag,
        "--windowed",
        f"--icon={icon_path}",
        "--name", "GitManager",
        f"--add-data={add_data}",
        "--distpath", str(project_root / "dist"),
        "--workpath", str(project_root / "build"),
        "--specpath", str(project_root),
        "-y",
        "--exclude-module", "tkinter",
        "--exclude-module", "ttkbootstrap",
        "--exclude-module", "PIL",
        str(entry_point),
    ]
    print(f"  {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(project_root))

    if args.mode == "onedir":
        exe_path = project_root / "dist" / "GitManager" / "GitManager.exe"
    else:
        exe_path = project_root / "dist" / "GitManager.exe"

    if exe_path.exists():
        size = exe_path.stat().st_size / 1024 / 1024
        print(f"\nBuild complete: {exe_path}")
        print(f"  Size: {size:.1f} MB")
        if args.mode == "onedir":
            dist_dir = project_root / "dist" / "GitManager"
            total = sum(f.stat().st_size for f in dist_dir.rglob("*") if f.is_file())
            print(f"  Total dir size: {total / 1024 / 1024:.1f} MB")
    else:
        print("\nERROR: Build failed - GitManager.exe not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
