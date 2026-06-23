#!/usr/bin/env python3
"""Interactively append a mod entry to an environment's mods.yaml.

Usage: scripts/add-mod.py <testing|prod>

Asks for the Steam Workshop ID, then either a single mod_id or a list of
sub_mods (for workshop items that bundle several mods, each individually
enable/disable-able). Run scripts/sync-mods.py afterward to apply the
change to the server ini.
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def prompt_yes_no(text: str, default: bool) -> bool:
    default_label = "Y/n" if default else "y/N"
    value = input(f"{text} [{default_label}]: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def yamlize(value: str) -> str:
    if value == "" or re.search(r"^\s|\s$|[:#]", value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_entry_text(workshop_id: str, name: str, mod_id: str, sub_mods: list[tuple[str, bool]]) -> str:
    lines = [f'  - workshop_id: {quote(workshop_id)}']
    if name:
        lines.append(f'    name: {yamlize(name)}')
    if sub_mods:
        lines.append('    sub_mods:')
        for sub_id, enabled in sub_mods:
            lines.append(f'      - id: {yamlize(sub_id)}')
            if not enabled:
                lines.append('        enabled: false')
    elif mod_id:
        lines.append(f'    mod_id: {yamlize(mod_id)}')
    return "\n".join(lines) + "\n"


def insert_entry(mods_file: Path, entry_text: str) -> None:
    content = mods_file.read_text()
    empty_pattern = re.compile(r"^mods:\s*\[\]\s*$", re.MULTILINE)
    if empty_pattern.search(content):
        new_content = empty_pattern.sub("mods:\n" + entry_text.rstrip("\n"), content, count=1)
    else:
        new_content = content.rstrip("\n") + "\n\n" + entry_text.rstrip("\n") + "\n"
    mods_file.write_text(new_content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    args = parser.parse_args()

    mods_file = REPO_ROOT / args.environment / "mods.yaml"
    if not mods_file.exists():
        sys.exit(f"{mods_file} not found")

    existing = yaml.safe_load(mods_file.read_text()) or {}
    existing_workshop_ids = {str(e.get("workshop_id")) for e in existing.get("mods") or []}

    workshop_id = ""
    while not workshop_id:
        workshop_id = prompt("Steam Workshop ID").strip()
        if not workshop_id:
            print("Workshop ID is required.", file=sys.stderr)
            continue
        if not workshop_id.isdigit():
            if not prompt_yes_no(f"'{workshop_id}' doesn't look numeric, use it anyway?", False):
                workshop_id = ""
                continue
        if workshop_id in existing_workshop_ids:
            if not prompt_yes_no(f"workshop_id {workshop_id} is already in mods.yaml, add another entry for it anyway?", False):
                workshop_id = ""

    name = prompt("Mod name (optional, for your own reference)")

    mod_id = ""
    sub_mods: list[tuple[str, bool]] = []
    if prompt_yes_no("Does this workshop item bundle multiple sub-mods?", False):
        print("Enter each sub-mod ID, blank to finish.")
        while True:
            sub_id = prompt("  Sub-mod ID")
            if not sub_id:
                break
            enabled = prompt_yes_no(f"  Enable '{sub_id}'?", True)
            sub_mods.append((sub_id, enabled))
        if not sub_mods:
            print("No sub-mods entered; treating as a workshop-id-only entry.")
    else:
        mod_id = prompt("Mod ID (the 'Mods=' id from mod.info; leave blank for a map/asset-only item)")

    entry_text = build_entry_text(workshop_id, name, mod_id, sub_mods)
    print("\nAdding:")
    print(entry_text)

    if not prompt_yes_no("Add this to mods.yaml?", True):
        print("Aborted, nothing written.")
        return

    insert_entry(mods_file, entry_text)
    print(f"Added to {mods_file}")
    print(f"\nNext: scripts/sync-mods.py {args.environment}")


if __name__ == "__main__":
    main()
