#!/usr/bin/env python3
"""Fetch live LeetCode profile data and render a single polished profile card.

Outputs (stdlib SVG is the source of truth):
  assets/stats/leetcode-profile.svg   preferred embed
  assets/stats/leetcode-profile.png   fallback embed (Pillow renderer)

Live data only: username, ranking, solved-by-difficulty, question totals,
and the 52-week submission calendar all come from LeetCode's public GraphQL
API. Nothing is hardcoded from any reference mockup.

Failure policy (per spec):
  - API failure + existing card  -> preserve the previous card, exit 0.
  - API failure + no card yet    -> emit a clear "data unavailable" card.
  - Repository stats keep working independently either way.

Usage:
  python scripts/generate_leetcode_card.py [--username NAME]
      [--assets-dir assets/stats] [--timeout 25] [--no-png]
      [--cache data/leetcode_cache.json]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_ROOT = SCRIPT_PATH.parents[1]

# ---------------------------------------------------------------------------
# Card geometry / palette (single source; PNG renderer mirrors these numbers)
# ---------------------------------------------------------------------------

W, H = 960, 440
BG = "#0d1117"
BORDER = "#30363d"
PRIMARY = "#f0f6fc"
SECONDARY = "#8b949e"
TRACK = "#21262d"
ACCENT = "#ffa116"  # LeetCode orange, total-solved ring
EASY_C = "#3fb950"
MEDIUM_C = "#d29922"
HARD_C = "#f85149"

# Heatmap intensity: empty + 4 greens (dark -> bright).
LEVEL_COLORS = ["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"]

CX, CY, R, RING_W = 130, 158, 58, 12
DIFF_X0, DIFF_X1, BAR_H = 272, 932, 8
DIFF_ROWS = (
    ("Easy", EASY_C, 102, 114),
    ("Medium", MEDIUM_C, 162, 174),
    ("Hard", HARD_C, 222, 234),
)
DIVIDER_Y = 262
HEAT_TITLE_Y = 288
GX, GY, CELL, PITCH = 28, 304, 13, 16
DATE_LABEL_Y = 432

FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, "
        "sans-serif")


def esc(s: object) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# LeetCode API (public GraphQL, no auth)
# ---------------------------------------------------------------------------

PROFILE_QUERY = """query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile { ranking }
    submitStatsGlobal {
      acSubmissionNum { difficulty count submissions }
    }
  }
  allQuestionsCount { difficulty count }
}"""

CALENDAR_QUERY = """query getCalendar($username: String!) {
  matchedUser(username: $username) {
    username
    userCalendar {
      activeYears
      streak
      totalActiveDays
      submissionCalendar
    }
  }
}"""


def gql(endpoint: str, query: str, username: str, timeout: int) -> dict:
    body = json.dumps(
        {"query": query, "variables": {"username": username}}).encode()
    req = urllib.request.Request(
        endpoint, data=body,
        headers={"Content-Type": "application/json",
                 "Referer": "https://leetcode.com",
                 "User-Agent": "Mozilla/5.0 (compatible; DSA-stats/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def fetch_leetcode(username: str, timeout: int) -> dict:
    endpoint = "https://leetcode.com/graphql"
    p = gql(endpoint, PROFILE_QUERY, username, timeout)
    c = gql(endpoint, CALENDAR_QUERY, username, timeout)

    mu = (p.get("data") or {}).get("matchedUser")
    if not mu:
        raise ValueError(f"LeetCode user not found: {username!r}")
    canon = mu.get("username") or username
    ranking = (mu.get("profile") or {}).get("ranking")

    solved = {"Easy": 0, "Medium": 0, "Hard": 0, "All": 0}
    for row in ((mu.get("submitStatsGlobal") or {})
                .get("acSubmissionNum") or []):
        d = row.get("difficulty")
        if d in solved:
            solved[d] = int(row.get("count") or 0)
    # Truth rule: total = Easy + Medium + Hard (API "All" must agree).
    total_solved = solved["Easy"] + solved["Medium"] + solved["Hard"]
    if solved["All"] != total_solved:
        total_solved = solved["All"] or total_solved

    totals = {"Easy": 0, "Medium": 0, "Hard": 0, "All": 0}
    for row in (p.get("data") or {}).get("allQuestionsCount") or []:
        d = row.get("difficulty")
        if d in totals:
            totals[d] = int(row.get("count") or 0)
    total_questions = totals["All"] or (
        totals["Easy"] + totals["Medium"] + totals["Hard"])

    cal = ((c.get("data") or {}).get("matchedUser") or {}).get("userCalendar") or {}
    raw_cal = cal.get("submissionCalendar") or "{}"
    try:
        entries = json.loads(raw_cal) if isinstance(raw_cal, str) else raw_cal
    except (ValueError, TypeError):
        entries = {}
    by_date: dict[str, int] = {}
    latest: datetime.date | None = None
    for ts, count in (entries.items() if isinstance(entries, dict) else []):
        try:
            day = datetime.datetime.fromtimestamp(
                int(ts), tz=datetime.timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            continue
        key = day.isoformat()
        by_date[key] = by_date.get(key, 0) + int(count or 0)
        if latest is None or day > latest:
            latest = day
    if latest is None:  # active account with no submissions in window
        latest = datetime.datetime.now(datetime.timezone.utc).date()

    return {
        "username": canon,
        "ranking": ranking if isinstance(ranking, int) else None,
        "solved": {"Easy": solved["Easy"], "Medium": solved["Medium"],
                   "Hard": solved["Hard"], "All": total_solved},
        "totals": totals,
        "total_questions": total_questions,
        "by_date": by_date,
        "latest": latest.isoformat(),
        "fetched_at": datetime.datetime.now(
            datetime.timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Heatmap model: 52-week window anchored on latest activity + quantile levels
# ---------------------------------------------------------------------------

def heat_levels(by_date: dict[str, int],
                start: datetime.date,
                end: datetime.date) -> list[int]:
    """Quantile thresholds [q1, q2, q3] over nonzero daily counts.

    Falls back to the familiar 1 / 2-3 / 4-6 / 7+ bands when there are too
    few distinct values for quantiles to be meaningful.
    """
    vals = sorted(v for k, v in by_date.items() if v > 0 and
                  start.isoformat() <= k <= end.isoformat())
    uniq = sorted(set(vals))
    if len(uniq) >= 4:
        def pct(q: float) -> float:
            if len(vals) == 1:
                return float(vals[0])
            pos = q * (len(vals) - 1)
            lo, hi = int(pos), min(int(pos) + 1, len(vals) - 1)
            frac = pos - lo
            return vals[lo] * (1 - frac) + vals[hi] * frac
        return [pct(0.25), pct(0.50), pct(0.75)]
    return [1.0, 3.0, 6.0]


def level_for(count: int, thresholds: list[int]) -> int:
    if count <= 0:
        return 0
    q1, q2, q3 = thresholds
    if count <= q1:
        return 1
    if count <= q2:
        return 2
    if count <= q3:
        return 3
    return 4


def week_grid(end: datetime.date):
    """Return (start, grid_start_sunday, grid_end_saturday, ncols).

    Display window is exactly 365 days (start..end inclusive, ~52 weeks);
    the drawn grid extends to week boundaries for clean 7-row alignment.
    """
    start = end - datetime.timedelta(days=364)
    # Row 0 = Sunday. Python weekday(): Mon=0..Sun=6 -> Sun-row = (wd+1)%7.
    grid_start = start - datetime.timedelta(days=(start.weekday() + 1) % 7)
    grid_end = end + datetime.timedelta(
        days=6 - ((end.weekday() + 1) % 7))
    ncols = ((grid_end - grid_start).days + 1) // 7
    return start, grid_start, grid_end, ncols


def fmt_dot(d: datetime.date) -> str:
    return f"{d.year}.{d.month}.{d.day}"


# ---------------------------------------------------------------------------
# SVG card
# ---------------------------------------------------------------------------

def build_svg(data: dict) -> str:
    username = data["username"]
    ranking = data.get("ranking")
    solved = data["solved"]
    totals = data["totals"]
    total_q = data.get("total_questions") or 0
    total_solved = solved["All"]

    end = datetime.date.fromisoformat(data["latest"])
    start, grid_start, grid_end, ncols = week_grid(end)
    thresholds = heat_levels(data.get("by_date") or {}, start, end)
    by_date = data.get("by_date") or {}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img">',
        f"<title>LeetCode profile for {esc(username)} \u2014 "
        f"{total_solved} solved</title>",
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="16" '
        f'fill="{BG}" stroke="{BORDER}"/>',
        # Header: brand icon + username .... rank.
        f'<rect x="28" y="24" width="32" height="32" rx="8" '
        f'fill="{ACCENT}" fill-opacity="0.15"/>',
        f'<text x="44" y="46" text-anchor="middle" font-family="{FONT}" '
        f'font-size="13" font-weight="700" fill="{ACCENT}">&lt;/&gt;</text>',
        f'<text x="72" y="49" font-family="{FONT}" font-size="20" '
        f'font-weight="700" fill="{PRIMARY}">{esc(username)}</text>',
    ]
    if ranking is not None:
        parts.append(
            f'<text x="932" y="49" text-anchor="end" font-family="{FONT}" '
            f'font-size="14" fill="{SECONDARY}">#{ranking}</text>')

    # Total-solved ring. Arc length is the honest solved/total fraction.
    import math
    circ = 2 * math.pi * R
    parts.append(
        f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" '
        f'stroke="{TRACK}" stroke-width="{RING_W}"/>')
    if total_q > 0 and total_solved > 0:
        frac = min(max(total_solved / total_q, 0.0), 1.0)
        dash = frac * circ
        parts.append(
            f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="none" '
            f'stroke="{ACCENT}" stroke-width="{RING_W}" '
            f'stroke-linecap="round" stroke-dasharray="{dash:.1f} {circ:.1f}" '
            f'transform="rotate(-90 {CX} {CY})"/>')
    parts += [
        f'<text x="{CX}" y="{CY + 4}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="34" font-weight="700" '
        f'fill="{PRIMARY}">{total_solved}</text>',
        f'<text x="{CX}" y="{CY + 24}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="12" fill="{SECONDARY}">Solved</text>',
    ]
    if total_q > 0:
        parts.append(
            f'<text x="{CX}" y="{CY + 40}" text-anchor="middle" '
            f'font-family="{FONT}" font-size="11" '
            f'fill="{SECONDARY}">of {total_q}</text>')

    # Difficulty rows with honest per-difficulty fractions.
    bar_w = DIFF_X1 - DIFF_X0
    for label, color, y_lab, y_bar in DIFF_ROWS:
        s = solved.get(label, 0)
        t = totals.get(label, 0)
        frac = (s / t) if t > 0 else 0.0
        fw = round(bar_w * min(max(frac, 0.0), 1.0), 1)
        parts += [
            f'<text x="{DIFF_X0}" y="{y_lab}" font-family="{FONT}" '
            f'font-size="14" font-weight="600" fill="{color}">{label}</text>',
            f'<text x="{DIFF_X1}" y="{y_lab}" text-anchor="end" '
            f'font-family="{FONT}" font-size="14" fill="{SECONDARY}">'
            f'<tspan font-weight="700" fill="{PRIMARY}">{s}</tspan>'
            f" / {t if t > 0 else '—'}</text>",
            f'<rect x="{DIFF_X0}" y="{y_bar}" width="{bar_w}" height="{BAR_H}" '
            f'rx="4" fill="{TRACK}"/>',
        ]
        if fw > 0:
            parts.append(
                f'<rect x="{DIFF_X0}" y="{y_bar}" width="{fw}" '
                f'height="{BAR_H}" rx="4" fill="{color}"/>')

    # Divider + heatmap.
    parts += [
        f'<line x1="28" y1="{DIVIDER_Y}" x2="932" y2="{DIVIDER_Y}" '
        f'stroke="{TRACK}"/>',
        f'<text x="28" y="{HEAT_TITLE_Y}" font-family="{FONT}" font-size="13" '
        f'fill="{SECONDARY}">Heatmap (Last 52 Weeks)</text>',
        f'<text x="830" y="{HEAT_TITLE_Y}" text-anchor="end" '
        f'font-family="{FONT}" font-size="11" '
        f'fill="{SECONDARY}">Less</text>',
    ]
    for i, color in enumerate(LEVEL_COLORS):
        lx = 838 + i * (10 + 3)
        parts.append(
            f'<rect x="{lx}" y="{HEAT_TITLE_Y - 9}" width="10" height="10" '
            f'rx="2" fill="{color}"/>')
    parts.append(
        f'<text x="912" y="{HEAT_TITLE_Y}" font-family="{FONT}" font-size="11" '
        f'fill="{SECONDARY}">More</text>')
    for col in range(ncols):
        for row in range(7):
            day = grid_start + datetime.timedelta(days=col * 7 + row)
            if day > grid_end:
                continue
            count = by_date.get(day.isoformat(), 0) if day <= end else 0
            lv = level_for(count, thresholds)
            color = LEVEL_COLORS[lv]
            opacity = ("" if day <= end or lv > 0
                       else ' fill-opacity="0.35"')
            x, y = GX + col * PITCH, GY + row * PITCH
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="3" fill="{color}"{opacity}/>')
    parts += [
        f'<text x="28" y="{DATE_LABEL_Y}" font-family="{FONT}" font-size="12" '
        f'fill="{SECONDARY}">{fmt_dot(start)}</text>',
        f'<text x="932" y="{DATE_LABEL_Y}" text-anchor="end" '
        f'font-family="{FONT}" font-size="12" '
        f'fill="{SECONDARY}">{fmt_dot(end)}</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def unavailable_svg(username: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img">\n'
        f"<title>LeetCode profile for {esc(username)} \u2014 "
        "data unavailable</title>\n"
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="16" '
        f'fill="{BG}" stroke="{BORDER}"/>\n'
        f'<rect x="28" y="24" width="32" height="32" rx="8" '
        f'fill="{ACCENT}" fill-opacity="0.15"/>\n'
        f'<text x="44" y="46" text-anchor="middle" font-family="{FONT}" '
        f'font-size="13" font-weight="700" '
        f'fill="{ACCENT}">&lt;/&gt;</text>\n'
        f'<text x="72" y="49" font-family="{FONT}" font-size="20" '
        f'font-weight="700" fill="{PRIMARY}">{esc(username)}</text>\n'
        f'<text x="480" y="200" text-anchor="middle" font-family="{FONT}" '
        f'font-size="20" font-weight="700" fill="{PRIMARY}">'
        "LeetCode data unavailable</text>\n"
        f'<text x="480" y="228" text-anchor="middle" font-family="{FONT}" '
        f'font-size="13" fill="{SECONDARY}">The profile API could not be '
        "reached \u2014 repository stats below are unaffected. "
        "Next scheduled run will retry.</text>\n"
        "</svg>\n"
    )


# ---------------------------------------------------------------------------
# PNG fallback (Pillow native render mirroring the SVG geometry)
# ---------------------------------------------------------------------------

def build_png(data: dict | None, username: str, path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("PNG skipped: Pillow not installed (SVG is still written)")
        return False

    def font(size: int):
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=16,
                        outline=BORDER, width=1)
    # Header.
    d.rounded_rectangle([28, 24, 60, 56], radius=8, fill="#312617")
    d.text((44, 40), "</>", fill=ACCENT, font=font(14), anchor="mm")
    d.text((72, 36), username, fill=PRIMARY, font=font(22))
    if data and data.get("ranking") is not None:
        d.text((932, 36), f"#{data['ranking']}", fill=SECONDARY,
               font=font(16), anchor="ra")

    if data is None:
        d.text((480, 190), "LeetCode data unavailable", fill=PRIMARY,
               font=font(24), anchor="mm")
        d.text((480, 220), "API unreachable - repo stats unaffected",
               fill=SECONDARY, font=font(15), anchor="mm")
    else:
        solved, totals = data["solved"], data["totals"]
        total_q = data.get("total_questions") or 0
        # Ring.
        d.arc([CX - R, CY - R, CX + R, CY + R], 0, 360,
              fill=TRACK, width=RING_W)
        if total_q > 0 and solved["All"] > 0:
            frac = min(max(solved["All"] / total_q, 0.0), 1.0)
            d.arc([CX - R, CY - R, CX + R, CY + R], -90,
                  -90 + 360 * frac, fill=ACCENT, width=RING_W)
        d.text((CX, CY - 8), str(solved["All"]), fill=PRIMARY,
               font=font(36), anchor="mm")
        d.text((CX, CY + 20), "Solved", fill=SECONDARY,
               font=font(14), anchor="mm")
        if total_q:
            d.text((CX, CY + 38), f"of {total_q}", fill=SECONDARY,
                   font=font(13), anchor="mm")
        # Difficulty rows.
        bar_w = DIFF_X1 - DIFF_X0
        for label, color, y_lab, y_bar in DIFF_ROWS:
            s, t = solved.get(label, 0), totals.get(label, 0)
            d.text((DIFF_X0, y_lab - 12), label, fill=color, font=font(16))
            d.text((DIFF_X1, y_lab - 12), f"{s} / {t if t else '--'}",
                   fill=PRIMARY, font=font(16), anchor="ra")
            d.rounded_rectangle([DIFF_X0, y_bar, DIFF_X1, y_bar + BAR_H],
                                radius=4, fill=TRACK)
            if t > 0 and s > 0:
                fw = max(4, round(bar_w * min(s / t, 1.0)))
                d.rounded_rectangle([DIFF_X0, y_bar, DIFF_X0 + fw,
                                     y_bar + BAR_H], radius=4, fill=color)
        # Heatmap.
        end = datetime.date.fromisoformat(data["latest"])
        start, grid_start, grid_end, ncols = week_grid(end)
        thresholds = heat_levels(data.get("by_date") or {}, start, end)
        by_date = data.get("by_date") or {}
        d.line([28, DIVIDER_Y, 932, DIVIDER_Y], fill=TRACK)
        d.text((28, HEAT_TITLE_Y - 12), "Heatmap (Last 52 Weeks)",
               fill=SECONDARY, font=font(15))
        d.text((830, HEAT_TITLE_Y - 12), "Less", fill=SECONDARY,
               font=font(12), anchor="ra")
        for i, color in enumerate(LEVEL_COLORS):
            lx = 838 + i * (10 + 3)
            d.rounded_rectangle([lx, HEAT_TITLE_Y - 9, lx + 10,
                                 HEAT_TITLE_Y + 1], radius=2, fill=color)
        d.text((912, HEAT_TITLE_Y - 12), "More", fill=SECONDARY,
               font=font(12))
        for col in range(ncols):
            for row in range(7):
                day = grid_start + datetime.timedelta(days=col * 7 + row)
                if day > grid_end:
                    continue
                count = (by_date.get(day.isoformat(), 0)
                         if day <= end else 0)
                d.rounded_rectangle(
                    [GX + col * PITCH, GY + row * PITCH,
                     GX + col * PITCH + CELL, GY + row * PITCH + CELL],
                    radius=3, fill=LEVEL_COLORS[level_for(count, thresholds)])
        d.text((28, DATE_LABEL_Y - 12), fmt_dot(start),
               fill=SECONDARY, font=font(14))
        d.text((932, DATE_LABEL_Y - 12), fmt_dot(end),
               fill=SECONDARY, font=font(14), anchor="ra")

    img.save(path)
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Generate LeetCode profile card.")
    ap.add_argument("--username",
                    default=os.environ.get("LEETCODE_USERNAME",
                                           "uzair_khan_work"))
    ap.add_argument("--root", default=None)
    ap.add_argument("--assets-dir", default=None)
    ap.add_argument("--cache", default=None)
    ap.add_argument("--timeout", type=int, default=25)
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else DEFAULT_ROOT
    assets = (Path(args.assets_dir).resolve() if args.assets_dir
              else root / "assets" / "stats")
    assets.mkdir(parents=True, exist_ok=True)
    cache_path = (Path(args.cache) if args.cache
                  else root / "data" / "leetcode_cache.json")
    svg_path = assets / "leetcode-profile.svg"
    png_path = assets / "leetcode-profile.png"

    try:
        data = fetch_leetcode(args.username, args.timeout)
    except Exception as e:
        print(f"LeetCode fetch failed: {e}")
        if svg_path.is_file():
            print(f"preserving previous card: {svg_path} "
                  "(repo stats continue independently)")
            return 0
        print("no previous card; writing 'unavailable' state")
        svg = unavailable_svg(args.username)
        ET.fromstring(svg)
        svg_path.write_text(svg, encoding="utf-8")
        if not args.no_png:
            build_png(None, args.username, png_path)
        return 0

    print(f"LeetCode live: {data['username']} rank={data['ranking']} "
          f"solved={data['solved']} totals={data['totals']} "
          f"active_days={len(data['by_date'])} latest={data['latest']}")

    svg = build_svg(data)
    ET.fromstring(svg)  # never commit broken XML
    svg_path.write_text(svg, encoding="utf-8")
    print(f"wrote {svg_path} ({len(svg)} bytes)")

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        print(f"cache write skipped: {e}")

    if not args.no_png:
        if build_png(data, data["username"], png_path):
            print(f"wrote {png_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
