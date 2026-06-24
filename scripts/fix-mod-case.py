#!/usr/bin/env python3
"""Create lowercase symlinks for mod folders in the Workshop content volume.

Windows-authored mods often reference their own folder in lowercase in their
Lua scripts (e.g. require("lifestyle/...")) but ship with a mixed-case folder
name (e.g. mods/Lifestyle/). Linux's case-sensitive filesystem rejects those
references. This script creates a lowercase symlink alongside each such folder
so both spellings resolve correctly.

Safe to rerun -- symlinks that already exist are silently skipped.
Only touches mods/ subdirectories inside Workshop content, never save data.

Usage: scripts/fix-mod-case.py <testing|prod>
"""
import argparse
import subprocess
import sys

PZ_APP_ID = "108600"

SCRIPT = r"""
set -e
CONTENT_BASE="/dest/pzserver/steamapps/workshop/content/108600"
if [ ! -d "$CONTENT_BASE" ]; then
    echo "No workshop content found -- deploy the server first and let it download mods."
    exit 0
fi
fixed=0
skipped=0
for item_dir in "$CONTENT_BASE"/*/; do
    [ -d "$item_dir" ] || continue
    mods_dir="${item_dir}mods"
    [ -d "$mods_dir" ] || continue
    for mod_dir in "$mods_dir"/*/; do
        [ -d "$mod_dir" ] || continue
        folder=$(basename "$mod_dir")
        lower=$(echo "$folder" | tr '[:upper:]' '[:lower:]')
        if [ "$folder" = "$lower" ]; then
            continue
        fi
        symlink="${mods_dir}/${lower}"
        if [ -e "$symlink" ] || [ -L "$symlink" ]; then
            skipped=$((skipped + 1))
            continue
        fi
        echo "  ${mods_dir#/dest/}/${lower} -> ${folder}"
        ln -s "$folder" "$symlink"
        fixed=$((fixed + 1))
    done
done
echo ""
echo "Created ${fixed} symlink(s), skipped ${skipped} already-existing."
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    args = parser.parse_args()

    volume = f"pz_{args.environment}_data"
    print(f"Fixing mod case in volume: {volume}")
    print("Starting container (may take a moment)...")

    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{volume}:/dest", "alpine", "sh", "-c", SCRIPT],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stderr or "(no error output)", file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
