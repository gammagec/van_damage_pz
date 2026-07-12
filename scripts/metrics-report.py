#!/usr/bin/env python3
"""Generate an HTML usage report from the metrics collected by metrics-collector.py.

Reads the SQLite database produced by the metrics-collector sidecar and writes a
single self-contained HTML file with charts:

  * concurrent players over time
  * container CPU %
  * container memory usage
  * network + disk throughput
  * per-player session timeline (who was on, when)
  * summary statistics

Pure Python standard library (sqlite3 + hand-rolled inline SVG) — no third-party
packages required, so it runs on any Python 3.9+ without pip installs.

Usage:
  python3 scripts/metrics-report.py                       # last 7 days -> prod/metrics/report.html
  python3 scripts/metrics-report.py --days 30
  python3 scripts/metrics-report.py --all
  python3 scripts/metrics-report.py --db prod/metrics/metrics.db --out /tmp/report.html
"""
import argparse
import os
import sqlite3
import time
from datetime import datetime, timedelta
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "..", "prod", "metrics", "metrics.db")
DEFAULT_OUT = os.path.join(HERE, "..", "prod", "metrics", "report.html")

# A player is considered to have left if we see no sample of them for longer
# than this. Sized generously relative to the 60s poll interval to absorb the
# occasional missed poll without splitting one session into many.
SESSION_GAP = 5 * 60  # seconds

PALETTE = ["#4f9dff", "#ff6b6b", "#51cf66", "#ffd43b", "#cc5de8",
           "#20c997", "#ff922b", "#f06595", "#94d82d", "#22b8cf"]


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def load(db_path, since_ts):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    samples = conn.execute(
        "SELECT * FROM samples WHERE ts >= ? ORDER BY ts", (since_ts,)
    ).fetchall()
    presence = conn.execute(
        "SELECT ts, player FROM presence WHERE ts >= ? ORDER BY ts", (since_ts,)
    ).fetchall()
    conn.close()
    return samples, presence


def build_sessions(presence):
    """Collapse per-sample presence rows into (player, start_ts, end_ts) sessions."""
    by_player = {}
    for row in presence:
        by_player.setdefault(row["player"], []).append(row["ts"])
    sessions = []
    for player, times in by_player.items():
        times.sort()
        start = prev = times[0]
        for t in times[1:]:
            if t - prev > SESSION_GAP:
                sessions.append((player, start, prev))
                start = t
            prev = t
        sessions.append((player, start, prev))
    return sessions


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def fmt_bytes(n):
    if n is None:
        return "—"
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


def fmt_dur(secs):
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def local_dt(ts):
    return datetime.fromtimestamp(ts)


# --------------------------------------------------------------------------- #
# SVG chart primitives
# --------------------------------------------------------------------------- #
class Chart:
    """A minimal time-series SVG line/area chart with a time X axis."""

    W, H = 1000, 260
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 16, 34

    def __init__(self, t0, t1, ymax, y_fmt=lambda v: f"{v:g}", ymin=0.0):
        self.t0, self.t1 = t0, max(t1, t0 + 1)
        self.ymin = ymin
        self.ymax = ymax if ymax > ymin else ymin + 1
        self.y_fmt = y_fmt
        self.parts = []

    def _x(self, ts):
        frac = (ts - self.t0) / (self.t1 - self.t0)
        return self.PAD_L + frac * (self.W - self.PAD_L - self.PAD_R)

    def _y(self, v):
        frac = (v - self.ymin) / (self.ymax - self.ymin)
        return self.H - self.PAD_B - frac * (self.H - self.PAD_T - self.PAD_B)

    def _grid(self):
        # Horizontal grid + Y labels (5 ticks).
        for i in range(6):
            v = self.ymin + (self.ymax - self.ymin) * i / 5
            y = self._y(v)
            self.parts.append(
                f'<line x1="{self.PAD_L}" y1="{y:.1f}" x2="{self.W - self.PAD_R}" '
                f'y2="{y:.1f}" class="grid"/>'
            )
            self.parts.append(
                f'<text x="{self.PAD_L - 8}" y="{y + 4:.1f}" class="ylab">'
                f'{escape(self.y_fmt(v))}</text>'
            )
        # Vertical time ticks (up to 7).
        span = self.t1 - self.t0
        n = 6
        for i in range(n + 1):
            ts = self.t0 + span * i / n
            x = self._x(ts)
            self.parts.append(
                f'<line x1="{x:.1f}" y1="{self.PAD_T}" x2="{x:.1f}" '
                f'y2="{self.H - self.PAD_B}" class="grid"/>'
            )
            dt = local_dt(ts)
            lab = dt.strftime("%m-%d") if span > 2 * 86400 else dt.strftime("%m-%d %H:%M")
            self.parts.append(
                f'<text x="{x:.1f}" y="{self.H - self.PAD_B + 20:.1f}" '
                f'class="xlab">{lab}</text>'
            )

    def add_series(self, points, color, fill=False, step=False):
        """points: list of (ts, value); None value breaks the line (gap)."""
        segs, cur = [], []
        for ts, v in points:
            if v is None:
                if cur:
                    segs.append(cur)
                    cur = []
                continue
            cur.append((self._x(ts), self._y(v)))
        if cur:
            segs.append(cur)
        for seg in segs:
            if len(seg) == 1:
                x, y = seg[0]
                self.parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="{color}"/>')
                continue
            d = []
            for j, (x, y) in enumerate(seg):
                if j == 0:
                    d.append(f"M{x:.1f},{y:.1f}")
                elif step:
                    d.append(f"H{x:.1f}V{y:.1f}")
                else:
                    d.append(f"L{x:.1f},{y:.1f}")
            path = " ".join(d)
            if fill:
                base = self._y(self.ymin)
                x_last = seg[-1][0]
                x_first = seg[0][0]
                self.parts.append(
                    f'<path d="{path} L{x_last:.1f},{base:.1f} '
                    f'L{x_first:.1f},{base:.1f} Z" fill="{color}" fill-opacity="0.15"/>'
                )
            self.parts.append(
                f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.8"/>'
            )

    def svg(self):
        self._grid()
        body = "\n".join(self.parts)
        return (
            f'<svg viewBox="0 0 {self.W} {self.H}" class="chart" '
            f'preserveAspectRatio="xMidYMid meet">\n'
            f'<rect x="{self.PAD_L}" y="{self.PAD_T}" '
            f'width="{self.W - self.PAD_L - self.PAD_R}" '
            f'height="{self.H - self.PAD_T - self.PAD_B}" class="plot-bg"/>\n'
            f"{body}\n</svg>"
        )


def gantt_svg(sessions, t0, t1):
    """Horizontal session bars, one row per player."""
    players = sorted({s[0] for s in sessions})
    if not players:
        return '<p class="empty">No player sessions in this window.</p>'
    color = {p: PALETTE[i % len(PALETTE)] for i, p in enumerate(players)}
    row_h = 26
    pad_l, pad_r, pad_t, pad_b = 130, 20, 10, 34
    W = 1000
    H = pad_t + pad_b + row_h * len(players)
    t1 = max(t1, t0 + 1)

    def x(ts):
        return pad_l + (ts - t0) / (t1 - t0) * (W - pad_l - pad_r)

    parts = []
    # time gridlines
    for i in range(7):
        ts = t0 + (t1 - t0) * i / 6
        xx = x(ts)
        parts.append(f'<line x1="{xx:.1f}" y1="{pad_t}" x2="{xx:.1f}" y2="{H - pad_b}" class="grid"/>')
        dt = local_dt(ts)
        lab = dt.strftime("%m-%d") if (t1 - t0) > 2 * 86400 else dt.strftime("%m-%d %H:%M")
        parts.append(f'<text x="{xx:.1f}" y="{H - pad_b + 20:.1f}" class="xlab">{lab}</text>')
    for i, p in enumerate(players):
        cy = pad_t + i * row_h
        parts.append(f'<text x="{pad_l - 10}" y="{cy + row_h/2 + 4:.1f}" class="rowlab">{escape(p)}</text>')
        parts.append(f'<line x1="{pad_l}" y1="{cy + row_h:.1f}" x2="{W - pad_r}" y2="{cy + row_h:.1f}" class="grid"/>')
    for player, s, e in sessions:
        i = players.index(player)
        cy = pad_t + i * row_h + 5
        x0, x1 = x(s), x(max(e, s + 30))
        w = max(2.0, x1 - x0)
        dur = fmt_dur(e - s)
        parts.append(
            f'<rect x="{x0:.1f}" y="{cy:.1f}" width="{w:.1f}" height="{row_h - 10}" '
            f'rx="3" fill="{color[player]}" fill-opacity="0.85">'
            f'<title>{escape(player)}: {local_dt(s):%Y-%m-%d %H:%M} → '
            f'{local_dt(e):%H:%M} ({dur})</title></rect>'
        )
    body = "\n".join(parts)
    return (
        f'<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet">\n'
        f"{body}\n</svg>"
    )


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #
def stat_card(label, value, sub=""):
    sub_html = f'<div class="stat-sub">{escape(sub)}</div>' if sub else ""
    return (
        f'<div class="card"><div class="stat-val">{escape(str(value))}</div>'
        f'<div class="stat-label">{escape(label)}</div>{sub_html}</div>'
    )


def build_html(samples, presence, sessions, since_ts, now_ts):
    t0 = samples[0]["ts"] if samples else since_ts
    t1 = samples[-1]["ts"] if samples else now_ts

    # ---- summary stats -----------------------------------------------------
    up = [s for s in samples if s["server_up"]]
    counts = [s["player_count"] for s in up if s["player_count"] is not None]
    cpus = [s["cpu_pct"] for s in up if s["cpu_pct"] is not None]
    mems = [s["mem_used"] for s in up if s["mem_used"] is not None]
    mem_limit = next((s["mem_limit"] for s in reversed(up) if s["mem_limit"]), None)
    unique_players = sorted({r["player"] for r in presence})
    peak_players = max(counts) if counts else 0
    peak_ts = up[counts.index(peak_players)]["ts"] if counts else None
    uptime_pct = 100.0 * len(up) / len(samples) if samples else 0.0

    # total player-hours from sessions
    player_seconds = sum(e - s for _, s, e in sessions)

    # busiest hour-of-day (by average concurrent players)
    hour_sum, hour_n = [0.0] * 24, [0] * 24
    for s in up:
        if s["player_count"] is not None:
            h = local_dt(s["ts"]).hour
            hour_sum[h] += s["player_count"]
            hour_n[h] += 1
    hour_avg = [(hour_sum[h] / hour_n[h]) if hour_n[h] else 0 for h in range(24)]
    busiest_hour = max(range(24), key=lambda h: hour_avg[h]) if any(hour_n) else None

    cards = [
        stat_card("Unique players", len(unique_players)),
        stat_card("Peak concurrent", peak_players,
                  f"at {local_dt(peak_ts):%m-%d %H:%M}" if peak_ts else ""),
        stat_card("Total play time", fmt_dur(player_seconds), "summed across players"),
        stat_card("Avg CPU", f"{(sum(cpus)/len(cpus)):.0f}%" if cpus else "—",
                  f"peak {max(cpus):.0f}%" if cpus else ""),
        stat_card("Avg memory", fmt_bytes(sum(mems)/len(mems)) if mems else "—",
                  f"peak {fmt_bytes(max(mems))}" if mems else ""),
        stat_card("Uptime", f"{uptime_pct:.1f}%",
                  f"{len(samples)} samples"),
    ]
    if busiest_hour is not None:
        cards.append(stat_card("Busiest hour", f"{busiest_hour:02d}:00",
                               f"~{hour_avg[busiest_hour]:.1f} players avg"))
    cards_html = "\n".join(cards)

    # ---- charts ------------------------------------------------------------
    # Players (step area). Downtime shown as gaps (None).
    pts_players = [(s["ts"], s["player_count"] if s["server_up"] else None) for s in samples]
    ymax_p = max([2] + counts)
    ch_players = Chart(t0, t1, ymax_p, y_fmt=lambda v: f"{v:.0f}")
    ch_players.add_series(pts_players, PALETTE[0], fill=True, step=True)

    # CPU
    pts_cpu = [(s["ts"], s["cpu_pct"] if s["server_up"] else None) for s in samples]
    ymax_c = max([10] + cpus) * 1.1 if cpus else 100
    ch_cpu = Chart(t0, t1, ymax_c, y_fmt=lambda v: f"{v:.0f}%")
    ch_cpu.add_series(pts_cpu, PALETTE[1], fill=True)

    # Memory (GiB)
    pts_mem = [(s["ts"], (s["mem_used"] / 2**30) if (s["server_up"] and s["mem_used"] is not None) else None)
               for s in samples]
    ymax_m = (mem_limit / 2**30) if mem_limit else (max(mems) / 2**30 if mems else 1)
    ch_mem = Chart(t0, t1, ymax_m, y_fmt=lambda v: f"{v:.1f}G")
    ch_mem.add_series(pts_mem, PALETTE[5], fill=True)
    if mem_limit:  # limit line
        lim = mem_limit / 2**30
        y = ch_mem._y(lim)
        ch_mem.parts.append(
            f'<line x1="{ch_mem.PAD_L}" y1="{y:.1f}" x2="{ch_mem.W - ch_mem.PAD_R}" '
            f'y2="{y:.1f}" stroke="{PALETTE[1]}" stroke-dasharray="4 3" stroke-width="1"/>'
        )

    # Throughput (per-second, derived from cumulative counters)
    def rate_series(field):
        pts, prev = [], None
        for s in samples:
            v = s[field] if s["server_up"] else None
            if v is None or prev is None or prev[1] is None:
                pts.append((s["ts"], None if v is None else 0))
            else:
                dt = s["ts"] - prev[0]
                dv = v - prev[1]
                pts.append((s["ts"], max(0, dv / dt) if dt > 0 else 0))
            prev = (s["ts"], v)
        return pts
    net_rx = rate_series("net_rx")
    net_tx = rate_series("net_tx")
    io_vals = [v for _, v in net_rx + net_tx if v]
    ymax_io = max(io_vals) * 1.1 if io_vals else 1024
    ch_io = Chart(t0, t1, ymax_io, y_fmt=lambda v: fmt_bytes(v) + "/s")
    ch_io.add_series(net_rx, PALETTE[2])
    ch_io.add_series(net_tx, PALETTE[3])

    gantt = gantt_svg(sessions, t0, t1)

    # ---- roster table ------------------------------------------------------
    roster = {}
    for player, s, e in sessions:
        r = roster.setdefault(player, {"sessions": 0, "secs": 0, "last": 0})
        r["sessions"] += 1
        r["secs"] += e - s
        r["last"] = max(r["last"], e)
    rows = "".join(
        f"<tr><td>{escape(p)}</td><td>{d['sessions']}</td>"
        f"<td>{fmt_dur(d['secs'])}</td><td>{local_dt(d['last']):%Y-%m-%d %H:%M}</td></tr>"
        for p, d in sorted(roster.items(), key=lambda kv: -kv[1]["secs"])
    ) or '<tr><td colspan="4" class="empty">No players recorded</td></tr>'

    generated = local_dt(now_ts).strftime("%Y-%m-%d %H:%M:%S")
    window = f"{local_dt(t0):%Y-%m-%d %H:%M} → {local_dt(t1):%Y-%m-%d %H:%M}"

    return TEMPLATE.format(
        generated=generated, window=window, cards=cards_html,
        players_svg=ch_players.svg(), cpu_svg=ch_cpu.svg(),
        mem_svg=ch_mem.svg(), io_svg=ch_io.svg(), gantt_svg=gantt,
        roster_rows=rows,
        io_legend=(f'<span class="key"><i style="background:{PALETTE[2]}"></i>net in</span>'
                   f'<span class="key"><i style="background:{PALETTE[3]}"></i>net out</span>'),
        n_samples=len(samples),
    )


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Project Zomboid — Server Usage Report</title>
<style>
  :root {{
    --bg:#0f1115; --panel:#181b22; --border:#262b36; --fg:#e6e9ef;
    --muted:#8b93a3; --grid:#262b36;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg:#f5f6f8; --panel:#fff; --border:#e2e5ea; --fg:#1a1d24;
             --muted:#6b7280; --grid:#eceef2; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
    font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:28px 20px 60px; }}
  h1 {{ font-size:22px; margin:0 0 2px; }}
  .sub {{ color:var(--muted); font-size:13px; margin-bottom:22px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
    gap:12px; margin-bottom:28px; }}
  .card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px;
    padding:14px 16px; }}
  .stat-val {{ font-size:26px; font-weight:650; letter-spacing:-0.5px; }}
  .stat-label {{ color:var(--muted); font-size:12px; text-transform:uppercase;
    letter-spacing:.4px; margin-top:2px; }}
  .stat-sub {{ color:var(--muted); font-size:12px; margin-top:4px; }}
  section {{ background:var(--panel); border:1px solid var(--border); border-radius:12px;
    padding:16px 18px; margin-bottom:20px; }}
  section h2 {{ font-size:15px; margin:0 0 10px; display:flex; gap:12px; align-items:center; }}
  .chart {{ width:100%; height:auto; display:block; }}
  .plot-bg {{ fill:transparent; }}
  .grid {{ stroke:var(--grid); stroke-width:1; }}
  .ylab {{ fill:var(--muted); font-size:11px; text-anchor:end; }}
  .xlab {{ fill:var(--muted); font-size:11px; text-anchor:middle; }}
  .rowlab {{ fill:var(--fg); font-size:12px; text-anchor:end; }}
  .key {{ font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:5px; }}
  .key i {{ width:11px; height:11px; border-radius:2px; display:inline-block; }}
  table {{ width:100%; border-collapse:collapse; font-size:14px; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--border); }}
  th {{ color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; }}
  .empty {{ color:var(--muted); font-style:italic; padding:14px; }}
  footer {{ color:var(--muted); font-size:12px; text-align:center; margin-top:30px; }}
</style></head>
<body><div class="wrap">
  <h1>Project Zomboid — Server Usage Report</h1>
  <div class="sub">Window: {window} · {n_samples} samples · generated {generated}</div>

  <div class="cards">{cards}</div>

  <section><h2>Concurrent players</h2>{players_svg}</section>
  <section><h2>Player sessions</h2>{gantt_svg}</section>
  <section><h2>CPU usage</h2>{cpu_svg}</section>
  <section><h2>Memory usage <span class="key">dashed = limit</span></h2>{mem_svg}</section>
  <section><h2>Network throughput {io_legend}</h2>{io_svg}</section>

  <section><h2>Player roster</h2>
    <table><thead><tr><th>Player</th><th>Sessions</th><th>Total time</th><th>Last seen</th></tr></thead>
    <tbody>{roster_rows}</tbody></table>
  </section>

  <footer>Generated by scripts/metrics-report.py</footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Generate a PZ server usage report.")
    ap.add_argument("--db", default=DEFAULT_DB, help="path to metrics.db")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output HTML path")
    ap.add_argument("--days", type=float, default=7, help="how many days back (default 7)")
    ap.add_argument("--all", action="store_true", help="include all data")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"database not found: {args.db}\n"
                         "Has the metrics-collector sidecar been running?")

    now_ts = int(time.time())
    since_ts = 0 if args.all else int(now_ts - args.days * 86400)
    samples, presence = load(args.db, since_ts)
    if not samples:
        raise SystemExit("No samples in the selected window yet — let the collector run a while.")

    sessions = build_sessions(presence)
    html = build_html(samples, presence, sessions, since_ts, now_ts)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write(html)
    print(f"Wrote {args.out}  ({len(samples)} samples, "
          f"{len({r['player'] for r in presence})} unique players)")


if __name__ == "__main__":
    main()
