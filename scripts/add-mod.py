#!/usr/bin/env python3
"""Append a mod entry to an environment's mods.yaml, by Workshop ID.

Usage: scripts/add-mod.py <testing|prod> [workshop_id]

Only looks up the title from the Steam Web API (fast, no Docker/SteamCMD
needed) and appends a workshop_id-only entry -- it does NOT resolve
mod_id/sub_mods. The public API doesn't expose those; only the item's own
mod.info does, and reading that means downloading the item somewhere.

Instead: deploy as-is (this entry just adds its workshop_id to
WorkshopItems=, contributing nothing to Mods= yet), let the server
download it normally, then run scripts/sync-submods.py to resolve
mod_id/sub_mods from what the server already downloaded -- fast, since it
reads the existing download instead of fetching it again.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
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


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_entry_text(workshop_id: str, name: str) -> str:
    lines = [f"  - workshop_id: {quote(workshop_id)}"]
    if name:
        lines.append(f"    name: {quote(name)}")
    return "\n".join(lines) + "\n"


def insert_entry(mods_file: Path, entry_text: str) -> None:
    content = mods_file.read_text()
    empty_pattern = re.compile(r"^mods:\s*\[\]\s*$", re.MULTILINE)
    if empty_pattern.search(content):
        new_content = empty_pattern.sub("mods:\n" + entry_text.rstrip("\n"), content, count=1)
    else:
        new_content = content.rstrip("\n") + "\n\n" + entry_text.rstrip("\n") + "\n"
    mods_file.write_text(new_content)


def fetch_title(workshop_id: str) -> str | None:
    data = urllib.parse.urlencode(
        {"itemcount": "1", "publishedfileids[0]": workshop_id}
    ).encode()
    req = urllib.request.Request(
        "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.load(resp)
    details = payload.get("response", {}).get("publishedfiledetails", [])
    if not details or details[0].get("result") != 1:
        return None
    return details[0].get("title")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    parser.add_argument("workshop_id", nargs="?")
    args = parser.parse_args()

    mods_file = REPO_ROOT / args.environment / "mods.yaml"
    if not mods_file.exists():
        sys.exit(f"{mods_file} not found")

    existing = yaml.safe_load(mods_file.read_text()) or {}
    existing_workshop_ids = {str(e.get("workshop_id")) for e in existing.get("mods") or []}

    workshop_id = (args.workshop_id or "").strip()
    while True:
        if not workshop_id:
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
                continue
        break

    print(f"Looking up workshop item {workshop_id} on Steam...")
    try:
        title = fetch_title(workshop_id)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"warning: Steam API lookup failed ({exc})", file=sys.stderr)
        title = prompt("Mod name (lookup failed, enter manually; optional)")
    else:
        if title is None:
            sys.exit(f"Workshop item {workshop_id} not found (deleted, private, or invalid ID)")
        print(f"Title: {title}")

    entry_text = build_entry_text(workshop_id, title)
    print("\nAdding:")
    print(entry_text)

    if not prompt_yes_no("Add this to mods.yaml?", True):
        print("Aborted, nothing written.")
        return

    insert_entry(mods_file, entry_text)
    print(f"Added to {mods_file}")
    print(f"\nNext: scripts/sync-mods.py {args.environment}, then deploy.")
    print(f"Once the server has downloaded it, run scripts/sync-submods.py {args.environment}")
    print("to resolve mod_id/sub_mods, then scripts/sync-mods.py again to apply them.")


if __name__ == "__main__":
    main()
