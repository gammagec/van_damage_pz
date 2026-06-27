#!/usr/bin/env python3
"""Send in-game warnings then restart the PZ container.

Called by crond in the scheduler sidecar at 01:00 America/Los_Angeles daily.
Sends a 5-minute and 1-minute server message via RCON, triggers a server save,
then restarts the container via the Docker socket.  If RCON is unavailable the
warnings are skipped but the restart still proceeds.

Environment variables:
  PZ_CONTAINER     Docker container name to restart  (default: pz)
  RCON_HOST        Hostname/IP for RCON              (default: same as PZ_CONTAINER)
  RCON_PORT        RCON TCP port                     (default: 27015)
  PZ_RCON_PASSWORD RCON password set in the ini      (required for warnings)
"""
import http.client
import os
import socket
import sys
import time

# Allow importing pz_rcon from the same scripts directory.
sys.path.insert(0, os.path.dirname(__file__))
from pz_rcon import try_rcon  # noqa: E402

CONTAINER = os.environ.get("PZ_CONTAINER", "pz")
RCON_HOST = os.environ.get("RCON_HOST", CONTAINER)
RCON_PORT = int(os.environ.get("RCON_PORT", "27015"))
RCON_PASS = os.environ.get("PZ_RCON_PASSWORD", "")


def _log(msg: str) -> None:
    print(f"[restart] {msg}", flush=True)


def _docker_restart(container: str, stop_timeout: int = 30) -> bool:
    try:
        conn = http.client.HTTPConnection("localhost")
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.connect("/var/run/docker.sock")
        conn.request("POST", f"/containers/{container}/restart?t={stop_timeout}")
        status = conn.getresponse().status
        conn.close()
        return status in (200, 204)
    except OSError as exc:
        _log(f"Docker socket error: {exc}")
        return False


def _rcon(command: str) -> None:
    if RCON_PASS:
        try_rcon(RCON_HOST, RCON_PORT, RCON_PASS, command)
    else:
        _log("PZ_RCON_PASSWORD not set — skipping RCON command")


def main() -> None:
    _log(f"Starting graceful restart of {CONTAINER!r}")

    _log("Sending 5-minute warning ...")
    _rcon('servermsg "Server restarting in 5 minutes for scheduled maintenance."')

    time.sleep(4 * 60)

    _log("Sending 1-minute warning ...")
    _rcon('servermsg "Server restarting in 1 minute!"')

    time.sleep(50)

    _log("Triggering server save ...")
    _rcon("save")

    time.sleep(10)

    _log(f"Restarting {CONTAINER!r} ...")
    if _docker_restart(CONTAINER):
        _log("Restart triggered successfully.")
    else:
        _log("Restart failed — check Docker socket.")
        sys.exit(1)


if __name__ == "__main__":
    main()
