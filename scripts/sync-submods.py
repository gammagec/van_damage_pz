#!/usr/bin/env python3
"""Resolve mod_id/sub_mods in mods.yaml from already-downloaded Workshop content.

Usage: scripts/sync-submods.py <testing|prod> [--force]

scripts/add-mod.py only adds a workshop_id + title (fast, no download). The
PZ server itself downloads each WorkshopItems= entry the first time it's
deployed with it set, landing under
pzserver/steamapps/workshop/content/108600/<id>/mods/*/mod.info inside the
environment's volume. This script reads mod.info straight out of that
volume (no SteamCMD call of its own -- fast) and fills in each unresolved
entry's mod_id (single mod) or sub_mods (multiple bundled mods, each
individually enable/disable-able).

Entries that already have mod_id/sub_mods are left alone unless --force is
given, in which case they're re-resolved -- existing per-sub-mod enabled
flags are preserved for ids that still exist, new ones default enabled.

Workflow: add-mod.py -> sync-mods.py -> deploy -> sync-submods.py ->
sync-mods.py -> deploy again.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PZ_APP_ID = "108600"  # Project Zomboid (base game) -- where the dedicated
# server itself downloads Workshop content, NOT 380870 (the server appid).


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yamlize(value: str) -> str:
    if value == "" or re.search(r"^\s|\s$|[:#]", value):
        return quote(value)
    return value


def parse_mod_info(text: str) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            info[key.strip().lower()] = value.strip()
    return info


def find_mods_in_volume(volume: str, workshop_id: str) -> list[tuple[str, str]]:
    """Read mod.info(s) for workshop_id directly out of the named volume."""
    content_path = f"/dest/pzserver/steamapps/workshop/content/{PZ_APP_ID}/{workshop_id}"
    script = f"""
    set -e
    results=$(find '{content_path}/mods' -mindepth 2 -maxdepth 2 -iname mod.info 2>/dev/null || true)
    if [ -z "$results" ]; then
      results=$(find '{content_path}' -maxdepth 1 -iname mod.info 2>/dev/null || true)
    fi
    printf '%s\\n' "$results" | while IFS= read -r f; do
      [ -n "$f" ] || continue
      echo '===MODINFO==='
      cat "$f"
    done
    """
    result = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{volume}:/dest:ro", "alpine", "sh", "-c", script],
        capture_output=True,
        text=True,
    )
    blocks = result.stdout.split("===MODINFO===")[1:]
    mods = []
    for block in blocks:
        info = parse_mod_info(block)
        if info.get("id"):
            mods.append((info["id"], info.get("name", info["id"])))
    return mods


def build_resolution_lines(mod_id: str, sub_mods: list[tuple[str, str, bool]]) -> list[str]:
    lines = []
    if sub_mods:
        lines.append("    sub_mods:")
        for sub_id, sub_name, enabled in sub_mods:
            lines.append(f"      - id: {yamlize(sub_id)}")
            if sub_name:
                lines.append(f"        name: {quote(sub_name)}")
            if not enabled:
                lines.append("        enabled: false")
    elif mod_id:
        lines.append(f"    mod_id: {yamlize(mod_id)}")
    return lines


def update_entry_in_text(content: str, workshop_id: str, mod_id: str, sub_mods: list[tuple[str, str, bool]]) -> str | None:
    """Insert/replace mod_id/sub_mods lines for one entry, touching nothing else in the file."""
    head_pattern = re.compile(rf'^  - workshop_id: {re.escape(quote(workshop_id))}\n', re.MULTILINE)
    head_match = head_pattern.search(content)
    if not head_match:
        return None
    block_pattern = re.compile(r'(?:(?!^  - workshop_id:)[^\n]*\n?)*', re.MULTILINE)
    block_match = block_pattern.match(content, head_match.end())
    block_end = block_match.end()
    block = content[head_match.end():block_end]

    # Strip any existing mod_id/sub_mods lines from the block before reinserting.
    block = re.sub(r'^    mod_id:.*\n', '', block, flags=re.MULTILINE)
    block = re.sub(r'^    sub_mods:\n(?:      .*\n)*', '', block, flags=re.MULTILINE)

    name_match = re.match(r'(    name: .*\n)', block)
    insertion = "\n".join(build_resolution_lines(mod_id, sub_mods))
    insertion = (insertion + "\n") if insertion else ""
    if name_match:
        new_block = name_match.group(1) + insertion + block[name_match.end():]
    else:
        new_block = insertion + block

    return content[:head_match.end()] + new_block + content[block_end:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    parser.add_argument("--force", action="store_true", help="re-resolve entries that already have mod_id/sub_mods")
    args = parser.parse_args()

    mods_file = REPO_ROOT / args.environment / "mods.yaml"
    if not mods_file.exists():
        sys.exit(f"{mods_file} not found")

    volume = f"pz_{args.environment}_data"
    content = mods_file.read_text()
    entries = (yaml.safe_load(content) or {}).get("mods") or []

    updated = 0
    pending = 0
    for entry in entries:
        workshop_id = str(entry.get("workshop_id", "")).strip()
        if not workshop_id:
            continue
        already_resolved = "mod_id" in entry or "sub_mods" in entry
        if already_resolved and not args.force:
            continue

        label = entry.get("name") or workshop_id
        print(f"Checking {label} ({workshop_id})...")
        mods_found = find_mods_in_volume(volume, workshop_id)
        if not mods_found:
            print("  not downloaded yet -- deploy first, then rerun this script.")
            pending += 1
            continue

        if len(mods_found) == 1:
            mod_id, mod_name = mods_found[0]
            print(f"  resolved: mod_id={mod_id} ({mod_name})")
            new_content = update_entry_in_text(content, workshop_id, mod_id, [])
        else:
            existing_enabled = {sm.get("id"): sm.get("enabled", True) for sm in entry.get("sub_mods") or []}
            print(f"  resolved {len(mods_found)} sub-mods:")
            sub_mods = []
            for sub_id, sub_name in mods_found:
                enabled = existing_enabled.get(sub_id, True)
                print(f"    - {sub_name} (id: {sub_id}, enabled: {enabled})")
                sub_mods.append((sub_id, sub_name, enabled))
            new_content = update_entry_in_text(content, workshop_id, "", sub_mods)

        if new_content is None:
            print(f"  warning: couldn't locate this entry's text in {mods_file}, skipping", file=sys.stderr)
            continue
        content = new_content
        updated += 1

    if updated:
        mods_file.write_text(content)
        plural = "y" if updated == 1 else "ies"
        print(f"\nUpdated {updated} entr{plural} in {mods_file}")
        print(f"Next: scripts/sync-mods.py {args.environment}, then redeploy.")
    else:
        print("\nNo entries updated.")
    if pending:
        plural = "y" if pending == 1 else "ies"
        print(f"{pending} entr{plural} still pending download.")


if __name__ == "__main__":
    main()
