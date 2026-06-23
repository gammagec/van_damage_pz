#!/usr/bin/env python3
"""Append a mod entry to an environment's mods.yaml, looked up from Steam.

Usage: scripts/add-mod.py <testing|prod> [workshop_id] [--no-lookup]

Asks for the Steam Workshop ID (or takes it as an argument), fetches the
item's title from the Steam Web API, then downloads it anonymously via
SteamCMD (cached under .cache/steamcmd-scratch/ for faster repeat lookups)
to read its mod.info file(s) -- this is the only reliable source for the
actual Mods= id(s); the public API doesn't expose them. Workshop items
that bundle several mods get one mod.info per sub-mod, each individually
enable/disable-able. Run scripts/sync-mods.py afterward to apply the
change to the server ini.

Pass --no-lookup to skip Steam/Docker entirely and enter everything by
hand (useful with no internet/Docker access).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / ".cache" / "steamcmd-scratch"
PZ_APP_ID = "108600"  # Project Zomboid (base game) -- Workshop content lives
# under this appid, NOT 380870 (the dedicated server appid used elsewhere).


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


def yamlize(value: str) -> str:
    if value == "" or re.search(r"^\s|\s$|[:#]", value):
        return quote(value)
    return value


def build_entry_text(workshop_id: str, name: str, mod_id: str, sub_mods: list[tuple[str, str, bool]]) -> str:
    lines = [f"  - workshop_id: {quote(workshop_id)}"]
    if name:
        lines.append(f"    name: {quote(name)}")
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
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"warning: Steam API lookup failed: {exc}", file=sys.stderr)
        return None
    details = payload.get("response", {}).get("publishedfiledetails", [])
    if not details or details[0].get("result") != 1:
        return None
    return details[0].get("title")


def download_workshop_item(workshop_id: str) -> Path | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{CACHE_DIR}:/home/ubuntu",
        "--entrypoint", "steamcmd",
        "jthomastek/project-zomboid-server:latest",
        "+login", "anonymous",
        "+workshop_download_item", PZ_APP_ID, workshop_id,
        "+quit",
    ]
    output = ""
    for attempt in range(1, 4):
        result = subprocess.run(cmd, capture_output=True, text=True)
        output = result.stdout + result.stderr
        if f"Downloaded item {workshop_id}" in output:
            return CACHE_DIR / ".local/share/Steam/steamapps/workshop/content" / PZ_APP_ID / workshop_id
        print(f"steamcmd download attempt {attempt}/3 failed, retrying...", file=sys.stderr)
    print(f"warning: steamcmd workshop download failed after 3 attempts:\n{output}", file=sys.stderr)
    return None


def cleanup_workshop_item(workshop_id: str) -> None:
    subprocess.run(
        [
            "docker", "run", "--rm",
            "-v", f"{CACHE_DIR}:/home/ubuntu",
            "alpine", "sh", "-c",
            f"rm -rf '/home/ubuntu/.local/share/Steam/steamapps/workshop/content/{PZ_APP_ID}/{workshop_id}'",
        ],
        capture_output=True,
    )


def parse_mod_info(path: Path) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in path.read_text(errors="replace").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            info[key.strip().lower()] = value.strip()
    return info


def find_mods(content_dir: Path) -> list[tuple[str, str]]:
    """Return [(mod_id, mod_name), ...], one per sub-mod bundled in this item.

    The canonical declaration for each sub-mod is mods/<Folder>/mod.info --
    one level under "mods/". Version-specific override folders nested
    deeper (e.g. mods/<Folder>/42.17/mod.info) repeat the same id and are
    skipped. Falls back to a root-level mod.info for legacy items with no
    "mods/" wrapper.
    """
    mods_dir = content_dir / "mods"
    candidates: list[Path] = []
    if mods_dir.is_dir():
        candidates = [d for d in mods_dir.iterdir() if d.is_dir() and (d / "mod.info").exists()]
    if not candidates:
        if (content_dir / "mod.info").exists():
            candidates = [content_dir]
        elif content_dir.is_dir():
            candidates = [d for d in content_dir.iterdir() if d.is_dir() and (d / "mod.info").exists()]

    results = []
    for d in candidates:
        info = parse_mod_info(d / "mod.info")
        if info.get("id"):
            results.append((info["id"], info.get("name", d.name)))
    return results


def manual_entry() -> tuple[str, str, list[tuple[str, str, bool]]]:
    name = prompt("Mod name (optional, for your own reference)")
    mod_id = ""
    sub_mods: list[tuple[str, str, bool]] = []
    if prompt_yes_no("Does this workshop item bundle multiple sub-mods?", False):
        print("Enter each sub-mod ID, blank to finish.")
        while True:
            sub_id = prompt("  Sub-mod ID")
            if not sub_id:
                break
            enabled = prompt_yes_no(f"  Enable '{sub_id}'?", True)
            sub_mods.append((sub_id, "", enabled))
        if not sub_mods:
            print("No sub-mods entered; treating as a workshop-id-only entry.")
    else:
        mod_id = prompt("Mod ID (the 'Mods=' id from mod.info; leave blank for a map/asset-only item)")
    return name, mod_id, sub_mods


def looked_up_entry(workshop_id: str) -> tuple[str, str, list[tuple[str, str, bool]]]:
    print(f"Looking up workshop item {workshop_id} on Steam...")
    title = fetch_title(workshop_id)
    if title is None:
        sys.exit(f"Workshop item {workshop_id} not found (deleted, private, or invalid ID)")
    print(f"Title: {title}")

    if shutil.which("docker") is None:
        print("warning: docker not found, can't read mod.info -- falling back to manual entry.", file=sys.stderr)
        name, mod_id, sub_mods = manual_entry()
        return title or name, mod_id, sub_mods

    print("Downloading via SteamCMD to read mod.info (cached after the first run)...")
    content_dir = download_workshop_item(workshop_id)
    mods_found: list[tuple[str, str]] = []
    if content_dir is not None:
        try:
            mods_found = find_mods(content_dir)
        finally:
            cleanup_workshop_item(workshop_id)
    else:
        print("warning: download failed -- falling back to manual entry.", file=sys.stderr)
        name, mod_id, sub_mods = manual_entry()
        return title or name, mod_id, sub_mods

    if not mods_found:
        print("No mod.info found -- treating as a workshop-id-only entry (e.g. a map/asset pack).")
        return title, "", []

    if len(mods_found) == 1:
        mod_id, mod_name = mods_found[0]
        print(f"Detected mod id: {mod_id} (name: {mod_name})")
        return title, mod_id, []

    print(f"Detected {len(mods_found)} sub-mods bundled in this item:")
    sub_mods = []
    for sub_id, sub_name in mods_found:
        enabled = prompt_yes_no(f"  Enable '{sub_name}' (id: {sub_id})?", True)
        sub_mods.append((sub_id, sub_name, enabled))
    return title, "", sub_mods


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["testing", "prod"])
    parser.add_argument("workshop_id", nargs="?")
    parser.add_argument("--no-lookup", action="store_true", help="skip Steam/Docker lookup, enter everything manually")
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

    if args.no_lookup:
        name, mod_id, sub_mods = manual_entry()
    else:
        name, mod_id, sub_mods = looked_up_entry(workshop_id)

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
