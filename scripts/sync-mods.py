#!/usr/bin/env python3
"""Write Mods=/WorkshopItems= into an environment's server .ini from its mods.yaml.

Usage: scripts/sync-mods.py <testing|prod> [--dry-run]

See <env>/mods.yaml for the schema (workshop items, optional sub_mods with
per-sub-mod enabled flags, optional per-entry enabled flag).
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_server_name(env_dir: Path) -> str:
    env_file = env_dir / ".env"
    for line in env_file.read_text().splitlines():
        if line.startswith("PZ_SERVER_NAME="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"PZ_SERVER_NAME not set in {env_file}")


def resolve_mods(entries: list) -> tuple[list[str], list[str]]:
    workshop_items: list[str] = []
    mod_ids: list[str] = []
    seen_workshop_items: set[str] = set()
    seen_mod_ids: set[str] = set()

    for i, entry in enumerate(entries):
        label = entry.get("name") or entry.get("workshop_id") or f"entry #{i}"

        if "workshop_id" not in entry:
            sys.exit(f"mods.yaml: {label}: missing required 'workshop_id'")
        if not entry.get("enabled", True):
            continue

        has_mod_id = "mod_id" in entry
        has_sub_mods = "sub_mods" in entry
        if has_mod_id and has_sub_mods:
            sys.exit(f"mods.yaml: {label}: specify 'mod_id' or 'sub_mods', not both")

        if has_mod_id:
            entry_mod_ids = [entry["mod_id"]]
        elif has_sub_mods:
            entry_mod_ids = [sm["id"] for sm in entry["sub_mods"] if sm.get("enabled", True)]
        else:
            # workshop_id-only entry: subscribes/downloads it (e.g. a map or
            # asset pack) without adding anything to Mods=.
            entry_mod_ids = []

        workshop_id = str(entry["workshop_id"])
        if workshop_id in seen_workshop_items:
            print(f"warning: duplicate workshop_id {workshop_id} ({label})", file=sys.stderr)
        else:
            seen_workshop_items.add(workshop_id)
            workshop_items.append(workshop_id)

        for mod_id in entry_mod_ids:
            if mod_id in seen_mod_ids:
                print(f"warning: duplicate mod_id {mod_id} ({label})", file=sys.stderr)
                continue
            seen_mod_ids.add(mod_id)
            mod_ids.append(mod_id)

    return workshop_items, mod_ids


def set_ini_value(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    if not pattern.search(content):
        sys.exit(f"'{key}=' line not found in ini file; bootstrap the server first")
    return pattern.sub(f"{key}={value}", content, count=1)


def get_ini_value(content: str, key: str) -> str:
    match = re.search(rf"^{key}=(.*)$", content, re.MULTILINE)
    return match.group(1) if match else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    parser.add_argument("--dry-run", action="store_true", help="show changes without writing")
    args = parser.parse_args()

    env_dir = REPO_ROOT / args.environment
    mods_file = env_dir / "mods.yaml"
    if not mods_file.exists():
        sys.exit(f"{mods_file} not found")

    data = yaml.safe_load(mods_file.read_text()) or {}
    entries = data.get("mods") or []
    workshop_items, mod_ids = resolve_mods(entries)

    server_name = load_server_name(env_dir)
    ini_file = env_dir / "config" / f"{server_name}.ini"
    if not ini_file.exists():
        sys.exit(
            f"{ini_file} not found. Bootstrap the server first (see "
            f"{args.environment}/config/README.md), then rerun this script."
        )

    content = ini_file.read_text()
    old_workshop_items = get_ini_value(content, "WorkshopItems")
    old_mods = get_ini_value(content, "Mods")

    new_workshop_items = ";".join(workshop_items)
    new_mods = ";".join(mod_ids)

    print(f"WorkshopItems: {old_workshop_items!r} -> {new_workshop_items!r}")
    print(f"Mods:          {old_mods!r} -> {new_mods!r}")

    if old_workshop_items == new_workshop_items and old_mods == new_mods:
        print("No changes.")
        return

    if args.dry_run:
        print("(dry run, not writing)")
        return

    content = set_ini_value(content, "WorkshopItems", new_workshop_items)
    content = set_ini_value(content, "Mods", new_mods)
    ini_file.write_text(content)
    print(f"Wrote {ini_file}")


if __name__ == "__main__":
    main()
