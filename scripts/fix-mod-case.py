#!/usr/bin/env python3
"""Create lowercase symlinks for mod folders in the Workshop content volume.

Windows-authored mods often reference their own folder in lowercase in their
Lua scripts (e.g. require("lifestyle/...")) but ship with a mixed-case folder
name (e.g. mods/Lifestyle/). Linux's case-sensitive filesystem rejects those
references. This script creates a lowercase symlink alongside each such folder
so both spellings resolve correctly.

Safe to rerun -- symlinks that already exist are silently skipped.
Only touches mods/ subdirectories inside Workshop content, never save data.

If the pz container is running it execs into it (avoids mounting the volume
a second time). If the server is stopped it falls back to a temporary alpine
container.

Usage: scripts/fix-mod-case.py <testing|prod>
"""
import argparse
import subprocess
import sys

# Path where the pz container mounts the volume (from docker-compose.yml).
PZ_MOUNT = "/home/ubuntu"
# Fallback mount point for a temporary alpine container (when pz is stopped).
ALPINE_MOUNT = "/mnt"

# The shell script runs inside whichever container we land in.
# MOD_BASE is set to the correct mount point before it's invoked.
SCRIPT = r"""
set -e
CONTENT_BASE="$MOD_BASE/pzserver/steamapps/workshop/content/108600"
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
        echo "  ${lower} -> ${folder}"
        ln -s "$folder" "$symlink"
        fixed=$((fixed + 1))
    done
done
echo ""
echo "Created ${fixed} symlink(s), skipped ${skipped} already-existing."
"""

CONTAINERS = {"testing": "pz-testing", "prod": "pz-prod"}
VOLUMES = {"testing": "pz_testing_data", "prod": "pz_prod_data"}


def is_running(container: str) -> bool:
    r = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", container],
        capture_output=True, text=True,
    )
    return r.stdout.strip() == "true"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    args = parser.parse_args()

    env = args.environment
    container = CONTAINERS[env]
    volume = VOLUMES[env]

    if is_running(container):
        print(f"Exec-ing into running container ({container})...")
        cmd = ["docker", "exec", "-e", f"MOD_BASE={PZ_MOUNT}", container, "sh", "-c", SCRIPT]
    else:
        print(f"pz container not running -- using temporary alpine container...")
        cmd = ["docker", "run", "--rm",
               "-e", f"MOD_BASE={ALPINE_MOUNT}",
               "-v", f"{volume}:{ALPINE_MOUNT}",
               "alpine", "sh", "-c", SCRIPT]

    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        print(result.stderr or "(no error output)", file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
