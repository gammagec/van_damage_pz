#!/usr/bin/env python3
"""Collect Project Zomboid server usage metrics into a SQLite database.

Runs as a sidecar container on the same Docker network as the PZ server
(see docker-compose.yml). Every POLL_INTERVAL seconds it records one sample:

  * whether the server answered RCON        (server_up)
  * concurrent players and their names      (players)
  * container CPU / memory / net / block IO (from the Docker socket)

Data is written to SQLITE_PATH (default /data/metrics.db) which is bind-mounted
back to the host so scripts/metrics-report.py can read it directly.

Environment variables:
  RCON_HOST         Hostname/IP for RCON               (default: pz-prod)
  RCON_PORT         RCON TCP port                       (default: 27015)
  PZ_RCON_PASSWORD  RCON password set in the ini        (required)
  PZ_CONTAINER      Container name to read stats for     (default: pz-prod)
  DOCKER_SOCK       Path to the Docker socket            (default: /var/run/docker.sock)
  SQLITE_PATH       Where to write the database          (default: /data/metrics.db)
  POLL_INTERVAL     Seconds between samples              (default: 60)
"""
import http.client
import json
import os
import re
import socket
import sqlite3
import sys
import time

# Allow importing pz_rcon from the same scripts directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pz_rcon import Rcon  # noqa: E402

RCON_HOST = os.environ.get("RCON_HOST", "pz-prod")
RCON_PORT = int(os.environ.get("RCON_PORT", "27015"))
RCON_PASS = os.environ.get("PZ_RCON_PASSWORD", "")
CONTAINER = os.environ.get("PZ_CONTAINER", "pz-prod")
DOCKER_SOCK = os.environ.get("DOCKER_SOCK", "/var/run/docker.sock")
SQLITE_PATH = os.environ.get("SQLITE_PATH", "/data/metrics.db")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))

_PLAYERS_RE = re.compile(r"Players connected\s*\((\d+)\)", re.IGNORECASE)


def _log(msg: str) -> None:
    print(f"[metrics] {msg}", flush=True)


def init_db(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS samples (
            ts          INTEGER PRIMARY KEY,   -- unix seconds
            server_up   INTEGER NOT NULL,      -- 1 if RCON answered
            player_count INTEGER,              -- NULL when server down
            cpu_pct     REAL,                  -- container CPU %, may exceed 100 (multi-core)
            mem_used    INTEGER,               -- bytes
            mem_limit   INTEGER,               -- bytes
            net_rx      INTEGER,               -- cumulative bytes received
            net_tx      INTEGER,               -- cumulative bytes sent
            blk_r       INTEGER,               -- cumulative bytes read
            blk_w       INTEGER                -- cumulative bytes written
        );
        CREATE TABLE IF NOT EXISTS presence (
            ts     INTEGER NOT NULL,           -- matches samples.ts
            player TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_presence_ts     ON presence(ts);
        CREATE INDEX IF NOT EXISTS idx_presence_player ON presence(player);
        """
    )
    conn.commit()
    return conn


def poll_players():
    """Return (player_count, [names]) or (None, []) if the server is unreachable."""
    if not RCON_PASS:
        _log("PZ_RCON_PASSWORD not set — cannot poll players")
        return None, []
    try:
        with Rcon(RCON_HOST, RCON_PORT, RCON_PASS, timeout=8) as r:
            body = r.run("players")
    except Exception as exc:
        _log(f"RCON unavailable: {exc}")
        return None, []

    lines = body.splitlines()
    count = None
    if lines:
        m = _PLAYERS_RE.search(lines[0])
        if m:
            count = int(m.group(1))
    names = []
    for line in lines[1:]:
        name = line.strip().lstrip("-").strip()
        if name:
            names.append(name)
    # Trust the parsed name list for the count when the header is missing.
    if count is None:
        count = len(names)
    return count, names


def _docker_get(path: str):
    conn = http.client.HTTPConnection("localhost")
    conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.sock.connect(DOCKER_SOCK)
    conn.request("GET", path)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    if resp.status != 200:
        raise RuntimeError(f"docker API {path} -> {resp.status}")
    return json.loads(data)


def poll_stats():
    """Return a dict of container resource metrics, or {} on failure.

    Uses a single non-streaming stats snapshot, which carries both `precpu_stats`
    and `cpu_stats` so the CPU delta can be computed from one request.
    """
    try:
        s = _docker_get(f"/containers/{CONTAINER}/stats?stream=false")
    except Exception as exc:
        _log(f"docker stats unavailable: {exc}")
        return {}

    out = {"cpu_pct": None, "mem_used": None, "mem_limit": None,
           "net_rx": None, "net_tx": None, "blk_r": None, "blk_w": None}
    try:
        cpu = s["cpu_stats"]
        pre = s["precpu_stats"]
        cpu_delta = cpu["cpu_usage"]["total_usage"] - pre["cpu_usage"]["total_usage"]
        sys_delta = cpu.get("system_cpu_usage", 0) - pre.get("system_cpu_usage", 0)
        ncpu = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage") or []) or 1
        if sys_delta > 0 and cpu_delta >= 0:
            out["cpu_pct"] = (cpu_delta / sys_delta) * ncpu * 100.0
    except (KeyError, TypeError):
        pass

    try:
        mem = s["memory_stats"]
        used = mem.get("usage")
        # Match `docker stats`: subtract cache so the number reflects live working set.
        cache = (mem.get("stats") or {}).get("inactive_file")
        if used is not None and cache is not None:
            used = max(0, used - cache)
        out["mem_used"] = used
        out["mem_limit"] = mem.get("limit")
    except (KeyError, TypeError):
        pass

    try:
        rx = tx = 0
        for iface in (s.get("networks") or {}).values():
            rx += iface.get("rx_bytes", 0)
            tx += iface.get("tx_bytes", 0)
        out["net_rx"], out["net_tx"] = rx, tx
    except (KeyError, TypeError):
        pass

    try:
        r = w = 0
        for e in (s.get("blkio_stats") or {}).get("io_service_bytes_recursive") or []:
            if e.get("op", "").lower() == "read":
                r += e.get("value", 0)
            elif e.get("op", "").lower() == "write":
                w += e.get("value", 0)
        out["blk_r"], out["blk_w"] = r, w
    except (KeyError, TypeError):
        pass

    return out


def record(conn: sqlite3.Connection) -> None:
    ts = int(time.time())
    count, names = poll_players()
    server_up = 1 if count is not None else 0
    stats = poll_stats() if server_up else {}

    conn.execute(
        """INSERT OR REPLACE INTO samples
           (ts, server_up, player_count, cpu_pct, mem_used, mem_limit,
            net_rx, net_tx, blk_r, blk_w)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (ts, server_up, count,
         stats.get("cpu_pct"), stats.get("mem_used"), stats.get("mem_limit"),
         stats.get("net_rx"), stats.get("net_tx"),
         stats.get("blk_r"), stats.get("blk_w")),
    )
    if names:
        conn.executemany(
            "INSERT INTO presence (ts, player) VALUES (?, ?)",
            [(ts, n) for n in names],
        )
    conn.commit()

    if server_up:
        cpu = stats.get("cpu_pct")
        cpu_s = f"{cpu:.1f}%" if cpu is not None else "?"
        _log(f"players={count} cpu={cpu_s} names={names}")
    else:
        _log("server down / RCON unreachable — recorded downtime sample")


def main() -> None:
    _log(f"starting: interval={POLL_INTERVAL}s db={SQLITE_PATH} container={CONTAINER}")
    conn = init_db(SQLITE_PATH)
    while True:
        start = time.time()
        try:
            record(conn)
        except Exception as exc:  # never let one bad sample kill the collector
            _log(f"sample error: {exc}")
        elapsed = time.time() - start
        time.sleep(max(1.0, POLL_INTERVAL - elapsed))


if __name__ == "__main__":
    main()
