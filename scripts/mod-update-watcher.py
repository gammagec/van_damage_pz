#!/usr/bin/env python3
"""Restart the PZ container whenever any subscribed mod is updated on Steam Workshop.

Reads enabled workshop IDs from mods.yaml, polls the Steam
GetPublishedFileDetails API every POLL_INTERVAL seconds, and restarts
the target container via the Docker socket when any item's time_updated
changes.  Sends in-game warnings via RCON before restarting.
After a restart it waits RESTART_COOLDOWN seconds (to let the
server finish its SteamCMD + boot cycle) before resuming normal polling.

Environment variables:
  MODS_YAML         Path to mods.yaml            (default: /mods.yaml)
  PZ_CONTAINER      Container name to restart     (default: pz)
  RCON_HOST         RCON hostname                 (default: PZ_CONTAINER)
  RCON_PORT         RCON port                     (default: 27015)
  PZ_RCON_PASSWORD  RCON password                 (warnings skipped if unset)
  POLL_INTERVAL     Seconds between polls         (default: 900  = 15 min)
  RESTART_COOLDOWN  Seconds to wait after restart (default: 1200 = 20 min)
"""
import http.client
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from pz_rcon import try_rcon  # noqa: E402

STEAM_API = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
STEAM_BATCH = 100  # max items per Steam API request


# ---------------------------------------------------------------------------
# mods.yaml parser (no PyYAML dependency)
# ---------------------------------------------------------------------------

def _load_workshop_ids(path: str) -> list[str]:
    """Return workshop IDs for all top-level-enabled entries in mods.yaml."""
    ids: list[str] = []
    current_id: str | None = None
    enabled = True

    for line in Path(path).read_text().splitlines():
        # New top-level mod entry: "  - workshop_id: ..."  (≤4-space indent)
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent <= 4 and stripped.startswith("- workshop_id:"):
            if current_id and enabled:
                ids.append(current_id)
            current_id = stripped.split(":", 1)[1].strip().strip("\"'")
            enabled = True
        # Top-level "enabled: false" has exactly 4-space indent.
        # Sub-mod "enabled: false" is 8+ spaces — startswith won't match.
        elif line.startswith("    enabled:") and "false" in line.lower():
            enabled = False

    if current_id and enabled:
        ids.append(current_id)

    return ids


# ---------------------------------------------------------------------------
# Steam API
# ---------------------------------------------------------------------------

def _fetch_update_times(ids: list[str]) -> dict[str, int]:
    """Return {workshop_id: time_updated} for all given IDs."""
    result: dict[str, int] = {}
    for i in range(0, len(ids), STEAM_BATCH):
        batch = ids[i : i + STEAM_BATCH]
        body = urllib.parse.urlencode(
            {"itemcount": len(batch), **{f"publishedfileids[{j}]": wid for j, wid in enumerate(batch)}}
        ).encode()
        req = urllib.request.Request(STEAM_API, data=body, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            print(f"[watcher] Steam API error: {exc}", flush=True)
            return {}
        for item in data.get("response", {}).get("publishedfiledetails", []):
            result[item["publishedfileid"]] = item.get("time_updated", 0)
    return result


# ---------------------------------------------------------------------------
# Docker socket client (no extra packages — plain Unix HTTP)
# ---------------------------------------------------------------------------

class _Docker:
    def __init__(self, sock: str = "/var/run/docker.sock"):
        self._sock = sock

    def _request(self, method: str, path: str) -> int:
        conn = http.client.HTTPConnection("localhost")
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.connect(self._sock)
        conn.request(method, path)
        status = conn.getresponse().status
        conn.close()
        return status

    def restart(self, container: str, stop_timeout: int = 30) -> bool:
        try:
            status = self._request("POST", f"/containers/{container}/restart?t={stop_timeout}")
            return status in (200, 204)
        except OSError as exc:
            print(f"[watcher] Docker socket error: {exc}", flush=True)
            return False


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _warn_and_restart(docker: _Docker, container: str, rcon_host: str,
                       rcon_port: int, rcon_pass: str, names: list[str],
                       cooldown: int) -> bool:
    noun = "mod" if len(names) == 1 else "mods"
    detail = ", ".join(names[:3]) + (" ..." if len(names) > 3 else "")

    if rcon_pass:
        print(f"[watcher] Sending 5-minute warning ...", flush=True)
        try_rcon(rcon_host, rcon_port, rcon_pass,
                 f'servermsg "Server restarting in 5 minutes — {len(names)} {noun} updated ({detail})."')
        time.sleep(4 * 60)

        print(f"[watcher] Sending 1-minute warning ...", flush=True)
        try_rcon(rcon_host, rcon_port, rcon_pass,
                 'servermsg "Server restarting in 1 minute!"')
        time.sleep(50)

        print(f"[watcher] Triggering server save ...", flush=True)
        try_rcon(rcon_host, rcon_port, rcon_pass, "save")
        time.sleep(10)
    else:
        print("[watcher] PZ_RCON_PASSWORD not set — skipping warnings.", flush=True)

    print(f"[watcher] Restarting {container} ...", flush=True)
    if docker.restart(container):
        print(f"[watcher] Restart triggered. Cooling down for {cooldown}s.", flush=True)
        time.sleep(cooldown)
        return True
    else:
        print(f"[watcher] Restart failed — will retry next poll.", flush=True)
        return False


def main() -> None:
    mods_yaml      = os.environ.get("MODS_YAML",         "/mods.yaml")
    container      = os.environ.get("PZ_CONTAINER",      "pz")
    rcon_host      = os.environ.get("RCON_HOST",          container)
    rcon_port      = int(os.environ.get("RCON_PORT",      "27015"))
    rcon_pass      = os.environ.get("PZ_RCON_PASSWORD",   "")
    poll_interval  = int(os.environ.get("POLL_INTERVAL",     "900"))
    cooldown       = int(os.environ.get("RESTART_COOLDOWN", "1200"))

    print(
        f"[watcher] container={container}  poll={poll_interval}s  cooldown={cooldown}s",
        flush=True,
    )

    ids = _load_workshop_ids(mods_yaml)
    print(f"[watcher] Watching {len(ids)} workshop items.", flush=True)

    docker = _Docker()

    # Establish baseline — retry once if the first attempt fails at startup.
    print("[watcher] Fetching initial mod timestamps ...", flush=True)
    known = _fetch_update_times(ids)
    if not known:
        print("[watcher] Steam API unreachable on startup, retrying in 60s.", flush=True)
        time.sleep(60)
        known = _fetch_update_times(ids)
    if not known:
        print("[watcher] Could not reach Steam API. Exiting.", flush=True)
        sys.exit(1)
    print(f"[watcher] Baseline set for {len(known)} items.", flush=True)

    while True:
        time.sleep(poll_interval)

        current = _fetch_update_times(ids)
        if not current:
            print("[watcher] Steam API unreachable — skipping poll.", flush=True)
            continue

        changed = [wid for wid, ts in current.items() if known.get(wid, 0) != ts]
        if not changed:
            continue

        print(f"[watcher] {len(changed)} updated workshop item(s): {', '.join(changed)}", flush=True)

        if _warn_and_restart(docker, container, rcon_host, rcon_port, rcon_pass, changed, cooldown):
            known.update(current)


if __name__ == "__main__":
    main()
