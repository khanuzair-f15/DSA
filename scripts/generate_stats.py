#!/usr/bin/env python3
"""Scan LeetCode problem folders and regenerate the root README dashboard.

Offline. Standard library only. Never modifies per-problem files.

Layout (auto-discovered, never hardcoded):
  <id>-<slug>/            e.g. 125-valid-palindrome/
    README.md            LeetSync metadata (authoritative when present, read-only)
    Notes.md             ignored for metadata
    <slug>.<ext>         solution source (one file is the normal case)

Per-problem normalized record (in memory, nothing to maintain by hand):
  problem_id, title, leetcode_url, difficulty, language,
  source_file, time_complexity, space_complexity, complexity_confidence

Metadata priority (no internet lookups):
  1. <folder>/README.md parsed for title / URL / difficulty
  2. data/problem_meta.json cache (generated earlier, read-only fallback)
  3. folder-slug fallback (Title Case title, Unknown URL/difficulty)

Complexity: heuristic static analysis of the selected source file.
Unknown is preferred over a wrong guess (Low confidence -> Unknown).

Usage:
  python scripts/generate_stats.py [--root .] [--readme README.md]
                                   [--assets-dir assets/stats] [--no-charts]
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import math
import re
import struct
import sys
import zlib
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

# --------------------------------------------------------------------------
# Central configuration (extend here)
# --------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_ROOT = SCRIPT_PATH.parents[1]  # scripts/generate_stats.py -> repo root

PROBLEM_RE = re.compile(r"^(\d+)-(.+)$")

# Extension -> language. Add new languages here.
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".py": "Python",
    ".java": "Java",
    ".c": "C",
    ".js": "JavaScript",
    ".ts": "TypeScript",
}

# Files never treated as solution sources.
IGNORED_FILENAMES_LOWER = {"readme.md", "notes.md"}
IGNORED_EXTENSIONS = {
    ".md", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".lock",
}

# Lower priority: test / helper / benchmark files.
TEST_NAME_RES = [
    re.compile(r"^test$", re.IGNORECASE),
    re.compile(r"^tests$", re.IGNORECASE),
    re.compile(r"^benchmark$", re.IGNORECASE),
    re.compile(r".*_test$", re.IGNORECASE),
    re.compile(r"^test_.*", re.IGNORECASE),
]
# Common solution basenames, in preference order.
SOLUTION_BASENAMES = ["solution", "answer", "main"]

VALID_DIFFICULTIES = ("Easy", "Medium", "Hard")
TIME_ORDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "Unknown"]
SPACE_ORDER = ["O(1)", "O(n)", "O(n^2)", "Unknown"]

AUTO_START = "<!-- AUTO_STATS_START -->"
AUTO_END = "<!-- AUTO_STATS_END -->"
LEGACY_START = "<!-- STATS:START -->"
LEGACY_END = "<!-- STATS:END -->"

CHART_FILES = {
    # key: (svg file, png fallback). Radar is used for 3+ categories;
    # smaller sets fall back to compact bars inside the same files.
    "difficulty": ("difficulty-radar.svg", "difficulty-radar.png"),
    "languages": ("language-radar.svg", "language-radar.png"),
    "time": ("time-complexity-radar.svg", "time-complexity-radar.png"),
    "space": ("space-complexity-radar.svg", "space-complexity-radar.png"),
}
# Live LeetCode profile card (owned by scripts/generate_leetcode_card.py).
# write_charts() must never delete these.
LEETCODE_CARD_FILES = ("leetcode-profile.svg", "leetcode-profile.png")
CHART_TITLES = {
    "difficulty": "Difficulty",
    "languages": "Languages",
    "time": "Time complexity",
    "space": "Space complexity",
}
# Fixed axis order for radar charts (Unknown kept as an honest axis).
DIFF_AXES = ["Easy", "Medium", "Hard", "Unknown"]
TIME_AXES = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)",
             "O(n^2 log n)", "O(n^3)", "Unknown"]
SPACE_AXES = ["O(1)", "O(n)", "O(n^2)", "Unknown"]

warnings_log: list[str] = []


def warn(msg: str) -> None:
    warnings_log.append(msg)
    print(f"WARNING: {msg}")


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

def find_repo_root(cli_root: str | None) -> Path:
    if cli_root:
        return Path(cli_root).resolve()
    cand = DEFAULT_ROOT
    try:
        if (cand / "README.md").is_file() or any(
            p.is_dir() and PROBLEM_RE.match(p.name) for p in cand.iterdir()
        ):
            return cand.resolve()
    except OSError:
        pass
    return Path.cwd().resolve()


def is_problem_dir(p: Path) -> bool:
    return (
        p.is_dir()
        and not p.name.startswith(".")
        and p.name.lower() not in {"assets", "scripts", ".github", "data", "node_modules"}
        and PROBLEM_RE.match(p.name) is not None
    )


def list_problem_dirs(root: Path) -> list[Path]:
    try:
        entries = list(root.iterdir())
    except OSError as e:
        warn(f"cannot list repo root: {e}")
        return []
    return sorted(
        [p for p in entries if is_problem_dir(p)],
        key=lambda p: (int(PROBLEM_RE.match(p.name).group(1)), p.name.lower()),
    )


def split_folder(name: str) -> tuple[int | None, str, str]:
    """Return (problem_id or None, folder_slug, title_slug)."""
    m = PROBLEM_RE.match(name)
    if not m:
        return None, name, name
    return int(m.group(1)), name, m.group(2)


def fallback_title(title_slug: str) -> str:
    return " ".join(w.capitalize() for w in re.split(r"[-_]+", title_slug) if w)


# --------------------------------------------------------------------------
# LeetSync README parsing (read-only; tolerant)
# --------------------------------------------------------------------------

TITLE_RE = re.compile(
    r"<h2>\s*<a\s+href=\"([^\"]+)\"\s*>([^<]+)</a>\s*</h2>", re.IGNORECASE
)
MD_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
DIFF_RE = re.compile(r"Difficulty-(Easy|Medium|Hard)", re.IGNORECASE)
DIFF_ALT_RE = re.compile(r"Difficulty:\s*(Easy|Medium|Hard)", re.IGNORECASE)
URL_RE = re.compile(r"https?://leetcode\.com/problems/([A-Za-z0-9\-_]+)/?", re.IGNORECASE)


def parse_leetsync_readme(path: Path) -> tuple[str | None, str | None, str | None, list[str]]:
    """Return (title, url, difficulty, issues). None = not found."""
    issues: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return None, None, None, [f"unreadable: {e}"]
    title = url = diff = None
    m = TITLE_RE.search(text)
    if m:
        url = m.group(1).strip()
        title = re.sub(r"\s+", " ", m.group(2)).strip() or None
        if url and not URL_RE.search(url):
            issues.append("URL does not look like a LeetCode problem link")
    else:
        m2 = MD_TITLE_RE.search(text)
        if m2:
            title = m2.group(1).strip() or None
        u = URL_RE.search(text)
        if u:
            url = u.group(0)
    d = DIFF_RE.search(text) or DIFF_ALT_RE.search(text)
    if d:
        diff = d.group(1).capitalize()
    else:
        issues.append("difficulty not found")
    if title is None:
        issues.append("title not found")
    if url is None:
        issues.append("URL not found")
    return title, url, diff, issues


def load_meta_cache(root: Path) -> dict:
    """Read-only fallback: data/problem_meta.json ({slug: {difficulty, tags}})."""
    f = root / "data" / "problem_meta.json"
    if not f.is_file():
        return {}
    try:
        import json

        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        warn(f"ignoring corrupt data/problem_meta.json: {e}")
        return {}


# --------------------------------------------------------------------------
# Source file selection
# --------------------------------------------------------------------------

def is_test_like(stem: str) -> bool:
    return any(r.match(stem) for r in TEST_NAME_RES)


def select_source(problem_dir: Path, title_slug: str, folder_slug: str) -> tuple[Path | None, str, str]:
    """Return (path or None, language, note).

    note is '' on a clean pick, else a short reason (e.g. 'Multiple').
    Emits warnings for missing/ambiguous sources. Never modifies files.
    """
    try:
        files = [f for f in problem_dir.iterdir() if f.is_file()]
    except OSError as e:
        warn(f"cannot list {problem_dir.name}: {e}")
        return None, "Unknown", "unreadable"

    cands: list[Path] = []
    for f in files:
        if f.name.lower() in IGNORED_FILENAMES_LOWER:
            continue
        if f.suffix.lower() in IGNORED_EXTENSIONS:
            continue
        if f.suffix.lower() in SUPPORTED_EXTENSIONS:
            cands.append(f)
        # unknown extension: not a supported source; ignore silently

    if not cands:
        warn(f"no supported source file in {problem_dir.name}")
        return None, "Unknown", "missing"

    if len(cands) == 1:
        f = cands[0]
        return f, SUPPORTED_EXTENSIONS[f.suffix.lower()], ""

    # Multiple candidates: score them, never combine results.
    def score(f: Path) -> tuple:
        stem = f.stem
        slow = stem.lower()
        exact = 100 if slow == title_slug.lower() else 0
        folder = 90 if slow == folder_slug.lower() else 0
        sol = 0
        if slow in SOLUTION_BASENAMES:
            sol = 50 - SOLUTION_BASENAMES.index(slow)
        test_pen = -50 if is_test_like(stem) else 0
        closeness = difflib.SequenceMatcher(None, slow, title_slug.lower()).ratio()
        return (exact, folder, sol, test_pen, closeness)

    ranked = sorted(cands, key=score, reverse=True)
    top, second = score(ranked[0]), score(ranked[1])
    if top[0] > 0 and top[0] != second[0]:
        # unique exact problem-slug match wins outright
        f = ranked[0]
        return f, SUPPORTED_EXTENSIONS[f.suffix.lower()], ""
    skips_signal = lambda s: (s[0], s[1], s[2])  # exact, folder, solution-name
    if skips_signal(top) != skips_signal(second) and max(skips_signal(top)) > 0:
        # unique best by the priority signals above
        f = ranked[0]
        if is_test_like(f.stem):
            warn(f"only test-like sources in {problem_dir.name}; using {f.name}")
        return f, SUPPORTED_EXTENSIONS[f.suffix.lower()], ""
    if top[4] >= 0.6 and top[4] != second[4]:
        # decisive closest-filename match to the problem slug
        f = ranked[0]
        return f, SUPPORTED_EXTENSIONS[f.suffix.lower()], ""
    warn(f"Multiple possible solution files found in {problem_dir.name}")
    return None, "Unknown", "Multiple"


# --------------------------------------------------------------------------
# Complexity analyzer (heuristic, conservative)
# --------------------------------------------------------------------------

BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT_RE = re.compile(r"//[^\n]*")
PY_COMMENT_RE = re.compile(r"#[^\n]*")
STRING_RE = re.compile(
    r'"""(?:\\.|.)*?"""|\'\'\'(?:\\.|.)*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`',
    re.DOTALL,
)

LOOP_KW_RE = re.compile(r"\b(for|while|do)\b")
SORT_RES = [
    re.compile(r"\bsort\s*\("),
    re.compile(r"\bstable_sort\s*\("),
    re.compile(r"\bstd::sort\s*\("),
    re.compile(r"\.sort\s*\("),
    re.compile(r"\bsorted\s*\("),
    re.compile(r"\bnth_element\s*\("),
]
LOGBOUND_RES = [
    re.compile(r"\blower_bound\s*\("),
    re.compile(r"\bupper_bound\s*\("),
    re.compile(r"\bbinary_search\s*\("),
    re.compile(r"\bbisect\s*(\.|_)"),
]
HALVING_RES = [
    re.compile(r"\bmid\b"),
    re.compile(r">>\s*1"),
    re.compile(r"/\s*2"),
    re.compile(r"//\s*2"),
]
NARROW_RES = [
    re.compile(r"\b(low|high|left|right|lo|hi)\b"),
]
RECURSION_DEF_RES = [
    re.compile(r"\bdef\s+([A-Za-z_]\w*)\s*\("),  # python
    re.compile(r"\b([A-Za-z_]\w*)\s*\([^;{}()]*\)\s*(?:const\s*)?\{"),  # brace langs
]
ALLOC_2D_RES = [
    # bare `vector<vector<...>` type mentions (e.g. `& matrix` parameters are
    # input storage) must not count: require an allocation token `(`, `=`,
    # `{` before the declaration ends.
    re.compile(r"vector\s*<\s*vector\b[^;{}()]*[\(=\{]"),
    re.compile(r"new\s+[A-Za-z_:\w]+\s*(\[[^\]]+\]\s*){2,}"),
    re.compile(r"\[\s*\[.*?for\s+\w+\s+in\b", re.DOTALL),
]
ALLOC_N_RES = [
    re.compile(r"\bvector\s*<[^;{}]*\(\s*[^;{}]*\b(n\b|len\b|size\s*\(\s*\)|\.size|length\b)"),
    re.compile(r"new\s+[A-Za-z_:\w]+\s*\[[^\]]*\b(n\b|len|size|length)\b[^\]]*\]"),
    re.compile(r"\[\s*0\s*\]\s*\*\s*n\b"),
    re.compile(r"\[.+for\s+\w+\s+in\b", re.DOTALL),
    re.compile(r"\b(Counter|defaultdict|OrderedDict)\s*\("),
]
GROW_CALL_RE = re.compile(
    r"\.(push_back|push|emplace|emplace_back|append|add|insert|put)\s*\("
)
NLIKE_RE = re.compile(r"\b(n\b|len\b|size\s*\(\s*\)|\.size\b|length\b|nums\b|s\b|arr\b)")
CONST_BOUND_RES = [
    re.compile(r"range\s*\(\s*\d{1,4}\s*\)"),
    re.compile(r";\s*[A-Za-z_]\w*\s*<\s*\d{1,4}\s*;"),
    re.compile(r"<\s*\d{1,4}\s*\)"),
]


def strip_code(text: str, lang: str) -> str:
    """Remove comments and string contents (keeps structure) for analysis."""
    t = BLOCK_COMMENT_RE.sub(" ", text)
    if lang == "Python":
        t = PY_COMMENT_RE.sub(" ", t)
    else:
        t = LINE_COMMENT_RE.sub(" ", t)
    return STRING_RE.sub('""', t)


def match_paren(s: str, open_idx: int) -> int:
    """Index of matching ')' for '(' at open_idx, or -1."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def match_brace(s: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def header_is_const(header: str) -> bool:
    h = header
    if NLIKE_RE.search(h):
        return False
    return any(r.search(h) for r in CONST_BOUND_RES)


def brace_loop_spans(code: str) -> tuple[list, dict]:
    """Collect loop body spans; info holds max scaling depth + flags."""
    spans: list[tuple[int, int, bool]] = []  # (start, end, const)
    headers: list[dict] = []
    block_stack: list[bool] = []  # True = loop block
    pending: dict | None = None
    chained: list[dict] = []  # braceless outer loops awaiting an inner body

    def record(s: int, e: int, c: bool) -> None:
        spans.append((s, e, c))
        # braceless chains (`for (..) for (..) x++;`): outers end where the
        # innermost body ends.
        for o in chained:
            spans.append((o["hstart"], e, o["const"] and c))
        chained.clear()

    def body_starts_with_loop(k: int) -> bool:
        m2 = LOOP_KW_RE.match(code, k)
        return bool(m2 and not (code[k - 1].isalnum() or code[k - 1] == "_")) \
            if k > 0 else bool(m2)
    i, n = 0, len(code)
    while i < n:
        m = LOOP_KW_RE.match(code, i)
        if m and (i == 0 or not (code[i - 1].isalnum() or code[i - 1] == "_")):
            kw = m.group(1)
            j = m.end()
            while j < n and code[j].isspace():
                j += 1
            if kw == "do":
                while j < n and code[j].isspace():
                    j += 1
                if j < n and code[j] == "{":
                    pending = {"const": False, "hstart": m.start()}
                    headers.append({"kw": kw, "const": False, "header": "do"})
                    i = j
                    continue
                semi = code.find(";", j)
                bend = semi if semi != -1 else min(n - 1, j + 200)
                record(m.start(), bend, False)
                headers.append({"kw": kw, "const": False, "header": "do"})
                i = bend + 1
                continue
            # for / while: expect '(' header
            if j < n and code[j] == "(":
                hend = match_paren(code, j)
                if hend == -1:
                    i = j + 1
                    continue
                const = header_is_const(code[j : hend + 1])
                k = hend + 1
                while k < n and code[k].isspace():
                    k += 1
                headers.append({"kw": kw, "const": const,
                                "header": code[m.start() : hend + 1]})
                if k < n and code[k] == "{":
                    pending = {"const": const, "hstart": m.start()}
                    i = k
                    continue
                if body_starts_with_loop(k):
                    # `for (..) for (..) ...`: outer ends with the inner body
                    chained.append({"hstart": m.start(), "const": const})
                    i = k
                    continue
                semi = code.find(";", k)
                bend = semi if semi != -1 else min(n - 1, k + 200)
                record(m.start(), bend, const)
                i = bend + 1
                continue
            i = m.end()
            continue
        if code[i] == "{":
            is_loop = pending is not None
            block_stack.append(is_loop)
            if is_loop:
                bend = match_brace(code, i)
                if bend == -1:
                    bend = n - 1
                record(pending["hstart"], bend, pending["const"])
                pending = None
            i += 1
            continue
        if code[i] == "}":
            if block_stack:
                block_stack.pop()
            pending = None
            chained.clear()
            i += 1
            continue
        i += 1
    scaling = [(s, e) for s, e, c in spans if not c]
    maxdepth = 0
    for s, e in scaling:
        depth = 1 + sum(
            1 for os, oe in scaling
            if (os, oe) != (s, e) and os <= s and e <= oe
        )
        maxdepth = max(maxdepth, depth)
    unclear = any(h["kw"] == "while" and not h["const"] for h in headers)
    info = {"nloops": len(scaling), "maxdepth": maxdepth,
            "unclear": unclear, "headers": headers}
    return spans, info


def py_loop_info(lines: list[tuple[int, int, str]]) -> tuple[list, dict]:
    """Indent-based loop spans. lines: (lineno, indent, text)."""
    spans: list[tuple[int, int, bool]] = []
    headers: list[dict] = []
    stack: list[tuple[int, bool, bool]] = []  # (indent, is_loop, const)
    open_loop: dict | None = None  # {'indent', 'const', 'start'}
    for lineno, ind, text in lines:
        while len(stack) > 1 and ind <= stack[-1][0]:
            popped = stack.pop()
            if popped[1] and open_loop is not None and open_loop.get("indent") == popped[0]:
                spans.append((open_loop["start"], lineno - 1, open_loop["const"]))
                open_loop = None
        m = re.match(r"(for|while)\b(.*)", text)
        if m:
            kw, hdr = m.group(1), m.group(2)
            const = False
            if kw == "for":
                if re.search(r"range\s*\(\s*\d{1,4}\s*\)", hdr) and not NLIKE_RE.search(hdr):
                    const = True
            else:
                const = False
                if NLIKE_RE.search(hdr):
                    pass
            headers.append({"kw": kw, "const": const, "header": hdr.strip()[:120]})
            stack.append((ind, True, const))
            open_loop = {"indent": ind, "const": const, "start": lineno}
        else:
            # plain block (if/def/with/try): track indent for dedent logic
            if text.endswith(":"):
                stack.append((ind, False, False))
    #close any still-open loop at EOF
    last = lines[-1][0] if lines else 0
    if open_loop is not None:
        spans.append((open_loop["start"], last, open_loop["const"]))
    if len(stack) > 1:
        pass
    scaling = [(s, e) for s, e, c in spans if not c]
    maxdepth = 0
    for s, e in scaling:
        depth = 1 + sum(
            1 for os, oe in scaling
            if (os, oe) != (s, e) and os <= s and e <= oe
        )
        maxdepth = max(maxdepth, depth)
    unclear = any(h["kw"] == "while" for h in headers)
    info = {"nloops": len(scaling), "maxdepth": maxdepth,
            "unclear": unclear, "headers": headers}
    return spans, info


def depth_at(spans: list, pos: int) -> int:
    return sum(1 for s, e, c in spans if not c and s <= pos <= e)


def find_calls(code: str, patterns: list) -> list[int]:
    out: list[int] = []
    for r in patterns:
        out.extend(m.start() for m in r.finditer(code))
    return sorted(out)


def detect_recursion(code: str, lang: str) -> bool:
    """True only if a function/method calls itself inside its own body."""
    for r in RECURSION_DEF_RES:
        for m in r.finditer(code):
            # skip C++ operator overloads: `operator new(...)`, `operator delete`
            prefix = code[max(0, m.start(1) - 9) : m.start(1)]
            if prefix.rstrip().endswith("operator"):
                continue
            name = m.group(1)
            if name in {"if", "for", "while", "switch", "catch", "return",
                        "sizeof", "elif", "with", "delete", "new", "operator"}:
                continue
            body: str | None = None
            if lang == "Python":
                lineno = code.count("\n", 0, m.start()) + 1
                lines = code.splitlines()
                try:
                    base = len(lines[lineno - 1]) - len(lines[lineno - 1].lstrip(" "))
                except IndexError:
                    continue
                buf: list[str] = []
                for ln in lines[lineno:]:
                    if ln.strip() == "":
                        buf.append(ln)
                        continue
                    ind = len(ln) - len(ln.lstrip(" "))
                    if ind <= base:
                        break
                    buf.append(ln)
                body = "\n".join(buf)
            else:
                bopen = code.find("{", m.end())
                if bopen == -1:
                    continue
                bend = match_brace(code, bopen)
                if bend == -1:
                    continue
                body = code[bopen + 1 : bend]
            if body and re.search(r"\b" + re.escape(name) + r"\s*\(", body):
                return True
    return False


def file_looks_halving(code: str, info: dict) -> bool:
    if info.get("nloops", 0) != 1:
        return False
    if not any(r.search(code) for r in HALVING_RES):
        return False
    return any(r.search(code) for r in NARROW_RES) or bool(
        re.search(r"\bmid\b", code))


# Assignment that shrinks a variable by division, e.g. `temp = temp / 10`,
# `n /= 2`. Nested loops driven by such shrinking bounds are not polynomial
# (typically logarithmic digit/halving behavior per level); label Unknown.
SHRINK_DIV_RE = re.compile(r"(\b\w+\b)\s*=\s*[^;{]*\b\1\b\s*/|/\s*=")


def analyze_time(code: str, lang: str) -> tuple[str, str]:
    """Return (complexity, confidence). Low confidence callers map to Unknown."""
    if lang == "Python":
        raw_lines = code.splitlines()
        lines: list[tuple[int, int, str]] = []
        for idx, ln in enumerate(raw_lines, 1):
            stripped = ln.strip()
            if not stripped:
                continue
            indent = len(ln) - len(ln.lstrip(" "))
            lines.append((idx, indent, stripped))
        spans, info = py_loop_info(lines)
        positions = []
        for r in SORT_RES:
            for m in r.finditer(code):
                lineno = code.count("\n", 0, m.start()) + 1
                positions.append(("sort", lineno))
        for r in LOGBOUND_RES:
            for m in r.finditer(code):
                lineno = code.count("\n", 0, m.start()) + 1
                positions.append(("log", lineno))

        def pdepth(lineno: int) -> int:
            return sum(1 for s, e, c in spans if not c and s <= lineno <= e)

        sort_in = sum(1 for k, p in positions if k == "sort" and pdepth(p) >= 1)
        sort_out = sum(1 for k, p in positions if k == "sort" and pdepth(p) == 0)
        log_in = sum(1 for k, p in positions if k == "log" and pdepth(p) >= 1)
        log_out = sum(1 for k, p in positions if k == "log" and pdepth(p) == 0)
        rec = detect_recursion(code, lang)
        halving = file_looks_halving(code, info)
        depth, unclear = info["maxdepth"], info["unclear"]
    else:
        spans, info = brace_loop_spans(code)
        sort_pos = find_calls(code, SORT_RES)
        log_pos = find_calls(code, LOGBOUND_RES)
        sort_in = sum(1 for p in sort_pos if depth_at(spans, p) >= 1)
        sort_out = sum(1 for p in sort_pos if depth_at(spans, p) == 0)
        log_in = sum(1 for p in log_pos if depth_at(spans, p) >= 1)
        log_out = sum(1 for p in log_pos if depth_at(spans, p) == 0)
        rec = detect_recursion(code, lang)
        halving = file_looks_halving(code, info)
        depth, unclear = info["maxdepth"], info["unclear"]

    def conf(level: str) -> str:
        if unclear and level == "High":
            return "Medium"
        return level

    if rec:
        return "Unknown", "Low"
    if depth >= 2 and SHRINK_DIV_RE.search(code):
        # e.g. digit-extraction loops (x = x / 10): not polynomial
        return "Unknown", "Low"
    if depth == 0 and not sort_in and not sort_out and not log_in and not log_out:
        return "O(1)", "High"
    if halving and not sort_in and not sort_out and depth <= 1:
        return "O(log n)", "High" if not unclear else "Medium"
    if (depth == 1 and info.get("nloops", 0) == 1 and not sort_in
            and not sort_out and not log_in and SHRINK_DIV_RE.search(code)):
        # e.g. `while (x > 0) { ... x = x / 10; }`: digit-shrinking loop
        return "O(log n)", "Medium"
    if depth == 0 and (sort_out or sort_in) and not log_in and not log_out:
        return "O(n log n)", "High"
    if depth == 0 and (log_out or log_in) and not (sort_out or sort_in):
        return "O(log n)", "Medium"
    if depth == 1 and not sort_in and not sort_out and not log_in:
        return "O(n)", conf("High")
    if depth == 1 and not sort_in and log_in and not sort_out:
        return "O(n log n)", "Medium"
    if depth == 1 and sort_in and not log_in:
        # loop containing a sort over n: n * (n log n)
        return "O(n^2 log n)", "Medium"
    if depth == 1 and sort_out and not sort_in and not log_in:
        return "O(n log n)", "Medium"  # sort dominates the linear pass
    if depth == 2 and not sort_in and not log_in:
        return "O(n^2)", conf("Medium")
    if depth == 3 and not sort_in and not log_in:
        return "O(n^3)", "Medium"
    return "Unknown", "Low"


def var_grows(code: str, var: str) -> bool:
    """Evidence that `var` is a string/container (not a scalar counter)."""
    v = re.escape(var)
    if re.search(r"(?:std::string|string|StringBuilder|StringBuffer)\s+" + v + r"\b", code):
        return True
    if re.search(v + r"\s*=\s*(\"\"\"|\"|'|\[|list\s*\(|set\s*\(|dict\s*\(|str\s*\(|StringBuilder\s*\()", code):
        return True
    return False


def analyze_space(code: str, lang: str, spans: list) -> tuple[str, str]:
    if any(r.search(code) for r in ALLOC_2D_RES):
        return "O(n^2)", "High"
    if any(r.search(code) for r in ALLOC_N_RES):
        return "O(n)", "High"
    nloops_scaling = sum(1 for _, _, c in spans if not c)
    if nloops_scaling >= 1:
        if lang == "Python":
            def pdepth(lineno: int) -> int:
                return sum(1 for s, e, c in spans if not c and s <= lineno <= e)

            def at_depth(pat: re.Pattern[str]) -> list:
                out = []
                for m in pat.finditer(code):
                    out.append((m, pdepth(code.count("\n", 0, m.start()) + 1)))
                return out
        else:
            def at_depth(pat: re.Pattern[str]) -> list:
                return [(m, depth_at(spans, m.start())) for m in pat.finditer(code)]
        # containers grown inside a scaling loop (e.g. push_back / append)
        if any(d >= 1 for _, d in at_depth(GROW_CALL_RE)):
            return "O(n)", "Medium"
        # `x += ...` grows only when x is a string/container, not a scalar
        for m, d in at_depth(re.compile(r"(\w+)\s*\+=")):
            if d >= 1 and var_grows(code, m.group(1)):
                return "O(n)", "Medium"
    if detect_recursion(code, lang):
        return "O(n)", "Medium"  # recursion stack
    if re.search(r"\b(unordered_map|unordered_set|map\s*<|set\s*<|dict\s*\(|set\s*\(|Counter\s*\()", code):
        return "O(n)", "Medium" if nloops_scaling >= 1 else "Low"
    return "O(1)", "High"


def analyze_file(path: Path, lang: str) -> tuple[str, str, str, str]:
    """Return (time, time_conf, space, space_conf). Never raises."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "Unknown", "Low", "Unknown", "Low"
    if not text.strip():
        return "Unknown", "Low", "Unknown", "Low"
    code = strip_code(text, lang)
    try:
        t, tc = analyze_time(code, lang)
    except Exception:
        t, tc = "Unknown", "Low"
    try:
        if lang == "Python":
            raw = [(i + 1, len(l) - len(l.lstrip(" ")), l.strip())
                   for i, l in enumerate(code.splitlines()) if l.strip()]
            spans, info = py_loop_info(raw)
        else:
            spans, info = brace_loop_spans(code)
        s, sc = analyze_space(code, lang, spans)
    except Exception:
        s, sc = "Unknown", "Low"
    return t, tc, s, sc
# --------------------------------------------------------------------------
# SVG charts (standard library only; render natively on GitHub)
# --------------------------------------------------------------------------

PALETTE = [
    "#4caf50", "#2196f3", "#ff9800", "#9c27b0", "#f44336",
    "#00bcd4", "#8bc34a", "#ffc107", "#795548", "#607d8b",
]
GRAY = "#9e9e9e"


def esc_xml(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


# Theme-neutral SVG: transparent background, muted text that adapts via
# prefers-color-scheme (works in browsers for <img>-embedded SVG).
SVG_STYLE = (
    "<defs><style>"
    ".t{fill:#57606a;font-family:sans-serif}"
    ".g{stroke:#8b949e;stroke-opacity:.35;fill:none}"
    "@media (prefers-color-scheme: dark){.t{fill:#c9d1d9}.g{stroke:#8b949e}"
    "</style></defs>"
)

RADAR_COLORS = {
    "difficulty": "#1f6feb",
    "languages": "#1a7f37",
    "time": "#8250df",
    "space": "#cf222e",
}


def radar_geometry(n: int, cx: float, cy: float, radius: float,
                   fracs: list[float]) -> list[list[tuple[float, float]]]:
    """Polygons for each ring fraction; ring[-1] is the outer ring."""
    rings: list[list[tuple[float, float]]] = []
    for f in fracs:
        ring = []
        for i in range(n):
            ang = -math.pi / 2 + 2 * math.pi * i / n
            ring.append((cx + radius * f * math.cos(ang),
                         cy + radius * f * math.sin(ang)))
        rings.append(ring)
    return rings


def ordered_axes(counts: dict[str, int], order: list[str] | None) -> list[tuple[str, int]]:
    if order is None:
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    items = [(k, counts.get(k, 0)) for k in order]
    extra = sorted(((k, v) for k, v in counts.items() if k not in order),
                   key=lambda kv: (-kv[1], kv[0].lower()))
    # drop trailing all-zero fixed axes? keep honest zeros on radar axes,
    # but drop a fully-empty chart to a "No data" state in the caller.
    return [(k, v) for k, v in items if v > 0 or k == "Unknown"] + extra


def svg_radar_chart(key: str, title: str, items: list[tuple[str, int]]) -> str:
    """Spider chart. items may include zero counts (drawn at the center)."""
    n = max(len(items), 1)
    W, H = 560, 430
    cx, cy, R = W / 2, H / 2 + 8, 148
    color = RADAR_COLORS.get(key, "#1f6feb")
    total = sum(v for _, v in items) or 1
    maxv = max([v for _, v in items] + [1])
    rings = radar_geometry(n, cx, cy, R, [0.25, 0.5, 0.75, 1.0])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img">',
        f"<title>{esc_xml(title)}</title>",
        SVG_STYLE,
        f'<text class="t" x="{W / 2}" y="28" text-anchor="middle" '
        f'font-size="16" font-weight="bold">{esc_xml(title)}</text>',
    ]
    if not items or total == 0 and all(v == 0 for _, v in items):
        parts.append(f'<text class="t" x="{cx}" y="{cy}" text-anchor="middle" '
                     'font-size="13">No data</text>')
    for ring in rings:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in ring)
        parts.append(f'<polygon class="g" stroke-width="1" points="{pts}"/>')
    if n == 1:
        parts.append(f'<line class="g" x1="{cx}" y1="{cy}" '
                     f'x2="{cx}" y2="{cy - R}"/>')
    else:
        for x, y in rings[-1]:
            parts.append(f'<line class="g" x1="{cx:.1f}" y1="{cy:.1f}" '
                         f'x2="{x:.1f}" y2="{y:.1f}"/>')
    if items and maxv > 0:
        data = [(cx + R * (v / maxv) * math.cos(-math.pi / 2 + 2 * math.pi * i / n),
                 cy + R * (v / maxv) * math.sin(-math.pi / 2 + 2 * math.pi * i / n))
                for i, (_, v) in enumerate(items)]
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in data)
        parts.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="0.25" '
                     f'stroke="{color}" stroke-width="2"/>')
        for x, y in data:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
    for i, (label, count) in enumerate(items):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        lx, ly = cx + (R + 30) * math.cos(ang), cy + (R + 30) * math.sin(ang)
        anchor = "middle"
        if abs(math.cos(ang)) > 0.35:
            anchor = "start" if math.cos(ang) > 0 else "end"
        parts.append(
            f'<text class="t" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="12">{esc_xml(label)} · {count}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def svg_bars_chart(key: str, title: str, items: list[tuple[str, int]]) -> str:
    """Compact horizontal bars; used when a radar would be degenerate (<3 axes)."""
    items = sorted(items, key=lambda kv: (-kv[1], kv[0].lower()))
    items = [(k, v) for k, v in items if v > 0]
    total = sum(v for _, v in items) or 1
    color = RADAR_COLORS.get(key, "#1f6feb")
    row_h, top, left, bar_max, W = 34, 48, 170, 300, 560
    H = top + max(len(items), 1) * row_h + 14
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img">',
        f"<title>{esc_xml(title)}</title>",
        SVG_STYLE,
        f'<text class="t" x="16" y="28" font-size="16" font-weight="bold">'
        f"{esc_xml(title)}</text>",
    ]
    if not items:
        parts.append('<text class="t" x="16" y="64" font-size="13">No data</text>')
    biggest = max([v for _, v in items] + [1])
    for i, (label, count) in enumerate(items):
        y = top + i * row_h
        w = max(3, round(bar_max * count / biggest))
        pct = 100.0 * count / total
        parts.append(f'<text class="t" x="16" y="{y + 20}" font-size="13">'
                     f"{esc_xml(label)}</text>")
        parts.append(f'<rect x="{left}" y="{y}" width="{w}" height="20" rx="5" '
                     f'fill="{color}" fill-opacity="0.75"/>')
        parts.append(f'<text class="t" x="{left + w + 8}" y="{y + 16}" font-size="12">'
                     f"{count} ({pct:.0f}%)</text>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------
# PNG fallback (pure stdlib: rasterizer + 5x7 bitmap font + zlib encoder)
# --------------------------------------------------------------------------

# 5x7 bitmap font, rows as 5-char strings. Uppercase + digits + symbols;
# labels are uppercased before rendering, unknown chars become '?'.


def _build_font() -> dict[str, tuple[str, ...]]:
    glyphs = {
        "A": ("..#..", ".#.#.", "#...#", "#####", "#...#", "#...#", "#...#"),
        "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
        "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
        "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
        "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
        "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
        "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
        "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
        "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
        "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
        "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
        "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
        "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
        "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
        "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
        "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
        "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
        "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
        "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
        "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
        "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
        "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
        "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
        "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
        "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
        "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
        "0": (".###.", "#..##", "#.#.#", "#.#.#", "##..#", "#...#", ".###."),
        "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
        "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
        "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
        "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
        "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
        "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
        "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
        "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
        "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
        " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
        "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
        "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
        ".": (".....", ".....", ".....", ".....", ".....", "..#..", "....."),
        "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
        "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
        ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
        "^": ("..#..", ".#.#.", "#...#", ".....", ".....", ".....", "....."),
        "%": ("##..#", "##.#.", "...#.", "..#..", ".#...", ".#.##", "#..##"),
        "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
        ":": (".....", "..#..", ".....", ".....", ".....", "..#..", "....."),
        ",": (".....", ".....", ".....", ".....", "..#..", "..#..", ".#..."),
    }
    return glyphs


FONT = _build_font()


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class Raster:
    """Tiny RGBA canvas: lines, circles, filled polygons, bitmap text."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 4)

    def blend(self, x: int, y: int, rgb: tuple[int, int, int], a: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            o = (y * self.w + x) * 4
            inv = 255 - a
            self.px[o] = (rgb[0] * a + self.px[o] * inv) // 255
            self.px[o + 1] = (rgb[1] * a + self.px[o + 1] * inv) // 255
            self.px[o + 2] = (rgb[2] * a + self.px[o + 2] * inv) // 255
            self.px[o + 3] = max(self.px[o + 3], a)

    def line(self, x0: float, y0: float, x1: float, y1: float,
             rgb: tuple[int, int, int], a: int = 255, w: int = 1) -> None:
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            for ox in range(-w // 2, w // 2 + 1):
                for oy in range(-w // 2, w // 2 + 1):
                    self.blend(x0 + ox, y0 + oy, rgb, a)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx: float, cy: float, r: int,
               rgb: tuple[int, int, int], a: int = 255, fill: bool = True) -> None:
        cx, cy = int(round(cx)), int(round(cy))
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                d = (x - cx) ** 2 + (y - cy) ** 2
                if fill and d <= r * r:
                    self.blend(x, y, rgb, a)
                elif not fill and abs(d - r * r) <= r:
                    self.blend(x, y, rgb, a)

    def fill_poly(self, pts: list[tuple[float, float]],
                  rgb: tuple[int, int, int], a: int) -> None:
        if len(pts) < 3:
            return
        ys = [int(math.floor(y)) for _, y in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            m = len(pts)
            for i in range(m):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % m]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    xs.append(x)
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(max(0, int(math.ceil(xs[k]))),
                                min(self.w, int(math.floor(xs[k + 1])) + 1)):
                    self.blend(x, y, rgb, a)

    def polyline(self, pts: list[tuple[float, float]],
                 rgb: tuple[int, int, int], a: int = 255, w: int = 1,
                 close: bool = False) -> None:
        seq = pts + ([pts[0]] if close and len(pts) > 2 else [])
        for i in range(len(seq) - 1):
            self.line(seq[i][0], seq[i][1], seq[i + 1][0], seq[i + 1][1], rgb, a, w)

    def text(self, x: int, y: int, s: str,
             rgb: tuple[int, int, int] = (155, 160, 165), scale: int = 2) -> int:
        """Uppercase bitmap text. Returns advance width in pixels."""
        s = s.upper()
        cx = x
        for ch in s:
            glyph = FONT.get(ch, FONT["?"])
            for r, row in enumerate(glyph):
                for c, bit in enumerate(row):
                    if bit == "#":
                        for dy in range(scale):
                            for dx in range(scale):
                                self.blend(cx + c * scale + dx, y + r * scale + dy,
                                           rgb, 255)
            cx += 6 * scale
        return cx - x

    def text_centered(self, cx: float, y: int, s: str,
                      rgb: tuple[int, int, int] = (155, 160, 165),
                      scale: int = 2) -> None:
        w = len(s.upper()) * 6 * scale - scale
        self.text(int(round(cx - w / 2)), y, s, rgb, scale)


def encode_png(w: int, h: int, px: bytes) -> bytes:
    def chunk(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + px[y * w * 4:(y + 1) * w * 4] for y in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


PNG_TEXT = (155, 160, 165)  # theme-neutral gray, visible on light and dark
PNG_GRID = (139, 148, 158)


def png_radar(key: str, title: str, items: list[tuple[str, int]],
              w: int = 560, h: int = 430) -> bytes:
    n = max(len(items), 1)
    cx, cy, R = w / 2, h / 2 + 8, 148
    color = _hex_to_rgb(RADAR_COLORS.get(key, "#1f6feb"))
    img = Raster(w, h)
    maxv = max([v for _, v in items] + [1])
    rings = radar_geometry(n, cx, cy, R, [0.25, 0.5, 0.75, 1.0])
    for ring in rings:
        img.polyline(ring, PNG_GRID, 90, 1, close=True)
    if n == 1:
        img.line(cx, cy, cx, cy - R, PNG_GRID, 90)
    else:
        for x, y in rings[-1]:
            img.line(cx, cy, x, y, PNG_GRID, 70)
    if items and maxv > 0:
        data = [(cx + R * (v / maxv) * math.cos(-math.pi / 2 + 2 * math.pi * i / n),
                 cy + R * (v / maxv) * math.sin(-math.pi / 2 + 2 * math.pi * i / n))
                for i, (_, v) in enumerate(items)]
        img.fill_poly(data, color, 70)
        img.polyline(data, color, 255, 2, close=True)
        for x, y in data:
            img.circle(x, y, 4, color, 255)
    img.text_centered(cx, 14, title.upper(), PNG_TEXT, 2)
    for i, (label, count) in enumerate(items):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        lx, ly = cx + (R + 12) * math.cos(ang), cy + (R + 12) * math.sin(ang)
        img.text_centered(lx, int(round(ly - 7)), f"{label} {count}", PNG_TEXT, 1)
    return encode_png(w, h, bytes(img.px))


def png_bars(key: str, title: str, items: list[tuple[str, int]],
             w: int = 560) -> bytes:
    items = sorted(items, key=lambda kv: (-kv[1], kv[0].lower()))
    items = [(k, v) for k, v in items if v > 0]
    color = _hex_to_rgb(RADAR_COLORS.get(key, "#1f6feb"))
    row_h, top, left, bar_max = 30, 52, 190, 280
    h = top + max(len(items), 1) * row_h + 12
    img = Raster(w, h)
    img.text(16, 14, title.upper(), PNG_TEXT, 2)
    biggest = max([v for _, v in items] + [1])
    for i, (label, count) in enumerate(items):
        y = top + i * row_h
        bw = max(3, round(bar_max * count / biggest))
        img.text(16, y + 3, label.upper(), PNG_TEXT, 1)
        for yy in range(y + 2, y + 20):
            for xx in range(left, left + bw):
                img.blend(xx, yy, color, 200)
        img.text(left + bw + 8, y + 3, str(count), PNG_TEXT, 1)
    return encode_png(w, h, bytes(img.px))


def _chart_items(counts: dict[str, int], order: list[str] | None,
                 keep_zeros: bool) -> list[tuple[str, int]]:
    if order is None:
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        return [(k, v) for k, v in items if v > 0]
    items = [(k, counts.get(k, 0)) for k in order]
    extra = sorted(((k, v) for k, v in counts.items() if k not in order and v > 0),
                   key=lambda kv: (-kv[1], kv[0].lower()))
    items = items + extra
    return items if keep_zeros else [(k, v) for k, v in items if v > 0]


def write_charts(assets_dir: Path, stats: dict) -> dict[str, dict[str, bool]]:
    """Write SVG + PNG charts, clean stale assets. Returns availability map.

    Only files inside assets_dir are ever removed (stale chart filenames and
    nothing else; `.gitkeep` is preserved).
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    specs = {
        "difficulty": (stats["difficulty_counts"], DIFF_AXES, True),
        "languages": (stats["language_counts"], None, False),
        "time": (stats["time_complexity_counts"], TIME_AXES, True),
        "space": (stats["space_complexity_counts"], SPACE_AXES, True),
    }
    avail: dict[str, dict[str, bool]] = {}
    expected: set[str] = set(LEETCODE_CARD_FILES)
    for key, (svg_name, png_name) in CHART_FILES.items():
        counts, order, keep_zeros = specs[key]
        title = f"{CHART_TITLES[key]} distribution"
        items = _chart_items(counts, order, keep_zeros)
        use_radar = len(items) >= 3
        expected.update({svg_name, png_name})
        ok = {"svg": False, "png": False}
        try:
            svg = (svg_radar_chart(key, title, items) if use_radar
                   else svg_bars_chart(key, title, items))
            ET.fromstring(svg)  # never commit broken XML
            (assets_dir / svg_name).write_text(svg, encoding="utf-8")
            ok["svg"] = True
        except Exception as e:
            warn(f"chart {svg_name} SVG failed, PNG-only fallback: {e}")
        try:
            png = (png_radar(key, title, items) if use_radar
                   else png_bars(key, title, items))
            if len(png) < 100 or png[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError("bad PNG bytes")
            (assets_dir / png_name).write_bytes(png)
            ok["png"] = True
        except Exception as e:
            warn(f"chart {png_name} PNG failed, SVG-only fallback: {e}")
        if not ok["svg"] and not ok["png"]:
            warn(f"chart {key}: both SVG and PNG failed, showing table only")
        avail[key] = ok
    # cleanup: only inside assets_dir, never touching anything else
    try:
        for f in assets_dir.iterdir():
            if f.is_file() and f.name not in expected and f.name != ".gitkeep":
                f.unlink()
                print(f"removed stale chart asset: {f.name}")
    except OSError as e:
        warn(f"chart cleanup failed: {e}")
    return avail


def chart_embed(assets_rel: str, key: str, alt: str, width: int,
                avail: dict[str, dict[str, bool]]) -> str:
    """SVG-preferred embed with PNG fallback.

    Uses <picture> (supported by GitHub READMEs); degrades to a single image
    when only one format exists, or to "" when both failed (caller then shows
    the data table, which is always present anyway).
    """
    svg_name, png_name = CHART_FILES[key]
    ok = avail.get(key, {"svg": False, "png": False})
    if ok.get("svg") and ok.get("png"):
        return (
            f"<picture>\n"
            f'  <source srcset="{assets_rel}/{svg_name}" type="image/svg+xml">\n'
            f'  <img src="{assets_rel}/{png_name}" alt="{alt}" width="{width}">\n'
            f"</picture>"
        )
    if ok.get("svg"):
        return f"![{alt}]({assets_rel}/{svg_name})"
    if ok.get("png"):
        return f"![{alt}]({assets_rel}/{png_name})"
    return ""


# --------------------------------------------------------------------------
# Records + README rendering
# --------------------------------------------------------------------------

def build_record(root: Path, pdir: Path, meta_cache: dict) -> dict:
    folder = pdir.name
    pid, folder_slug, title_slug = split_folder(folder)

    title: str | None = None
    url: str | None = None
    diff: str | None = None
    readme = pdir / "README.md"
    if readme.is_file():
        t, u, d, issues = parse_leetsync_readme(readme)
        for issue in issues:
            # missing difficulty/URL/title are routine; keep messages short
            warn(f"{folder}: README {issue}")
        title, url, diff = t, u, d
    else:
        warn(f"LeetSync README missing in {folder}/")

    if diff not in VALID_DIFFICULTIES:
        entry = meta_cache.get(title_slug, {})
        if isinstance(entry, dict) and entry.get("difficulty") in VALID_DIFFICULTIES:
            diff = entry["difficulty"]
        else:
            entry2 = meta_cache.get(folder, {})
            if isinstance(entry2, dict) and entry2.get("difficulty") in VALID_DIFFICULTIES:
                diff = entry2["difficulty"]
    if diff not in VALID_DIFFICULTIES:
        if readme.is_file() and title is not None:
            pass  # warning already emitted
        diff = "Unknown"
    if not title:
        title = fallback_title(title_slug)
    if not url:
        # Deterministic LeetCode URL shape needs no network; unknown only if
        # we cannot trust the slug (non-standard folder). Title slugs from
        # LeetSync-style folders map 1:1 to problem URLs.
        url = f"https://leetcode.com/problems/{title_slug}/"

    src_path, lang, src_note = select_source(pdir, title_slug, folder)
    if src_path is None:
        if src_note == "Multiple":
            time_c, space_c, conf = "Unknown", "Unknown", "Low"
            rel = "Multiple"
        else:
            time_c, space_c, conf = "Unknown", "Unknown", "Low"
            rel = ""
    else:
        rel = src_path.relative_to(root).as_posix()
        t_raw, tc, s_raw, sc = analyze_file(src_path, lang)
        # Low confidence -> display Unknown (never invent a result)
        time_c = t_raw if tc in ("High", "Medium") else "Unknown"
        space_c = s_raw if sc in ("High", "Medium") else "Unknown"
        # overall confidence: lowest of the two
        rank = {"High": 2, "Medium": 1, "Low": 0}
        inv = {2: "High", 1: "Medium", 0: "Low"}
        conf = inv[min(rank[tc], rank[sc])]
        if time_c == "Unknown" and t_raw != "Unknown":
            warn(f"Could not determine time complexity for {folder} "
                 f"(low confidence, file kept as Unknown)")
        if space_c == "Unknown" and s_raw != "Unknown":
            warn(f"Could not determine space complexity for {folder} "
                 f"(low confidence, file kept as Unknown)")

    return {
        "problem_id": pid if pid is not None else 10**9,
        "folder": folder,
        "title": title,
        "leetcode_url": url,
        "difficulty": diff,
        "language": lang,
        "source_file": rel,
        "time_complexity": time_c,
        "space_complexity": space_c,
        "complexity_confidence": conf,
    }


def md_link(title: str, url: str) -> str:
    safe = title.replace("|", "\\|")
    if url and url != "Unknown":
        return f"[{safe}]({url})"
    return safe


DIFF_BADGE = {"Easy": "🟢 Easy", "Medium": "🟠 Medium", "Hard": "🔴 Hard",
              "Unknown": "⚪ Unknown"}


def render_dashboard(records: list[dict], today: str,
                     avail: dict[str, dict[str, bool]],
                     leet_embed: str = "",
                     leet_caption: str = "") -> tuple[str, dict]:
    total = len(records)
    diff_c = Counter(r["difficulty"] for r in records)
    lang_c = Counter(r["language"] for r in records)
    time_c = Counter(r["time_complexity"] for r in records)
    space_c = Counter(r["space_complexity"] for r in records)
    known_t = sum(v for k, v in time_c.items() if k != "Unknown")
    known_s = sum(v for k, v in space_c.items() if k != "Unknown")
    both = sum(1 for r in records
               if r["time_complexity"] != "Unknown" and r["space_complexity"] != "Unknown")
    most_lang, most_lang_n = (lang_c.most_common(1)[0] if lang_c else ("Unknown", 0))
    top_time = next((k for k in TIME_AXES if time_c.get(k, 0)), "Unknown")
    top_space = next((k for k in SPACE_AXES if space_c.get(k, 0)), "Unknown")

    def pct(n: int) -> str:
        return f"{100.0 * n / total:.0f}%" if total else "N/A"

    L: list[str] = []
    A = L.append
    # Hero: dynamic numbers only, no hardcoded counts. This section describes
    # the GitHub repository only; live LeetCode data has its own card below.
    A('<div align="center">')
    A("")
    A("## LeetCode Journey")
    A("")
    A(f"**{total} solutions tracked in this repository** — difficulty, "
      "languages and complexity, tracked automatically.")
    A("")
    A("</div>")
    A("")
    # Live LeetCode profile card (single self-contained SVG owned by
    # scripts/generate_leetcode_card.py). Detailed numbers live in the card;
    # they are intentionally not duplicated in a second table here.
    A("## 🧑‍💻 LeetCode — Live Profile")
    A("")
    if leet_embed:
        A(leet_embed)
        A("")
    else:
        A("_Live LeetCode card pending — run "
          "`python scripts/generate_leetcode_card.py` to generate it._")
        A("")
    if leet_caption:
        A(leet_caption)
        A("")
    A("## 📊 Repository Stats")
    A("")
    A("_GitHub repository data — independent of the live profile above. A "
      "solution missing here is not necessarily unsolved on LeetCode._")
    A("")
    # Stat cards (plain HTML table: theme-friendly, no JS, mobile-safe).
    A("<table>")
    A("<tr>")
    A(f'<td align="center">🧠<br/><b>{total}</b><br/>Solved</td>')
    A(f'<td align="center">🟢<br/><b>{diff_c.get("Easy", 0)}</b><br/>Easy</td>')
    A(f'<td align="center">🟠<br/><b>{diff_c.get("Medium", 0)}</b><br/>Medium</td>')
    A(f'<td align="center">🔴<br/><b>{diff_c.get("Hard", 0)}</b><br/>Hard</td>')
    A("</tr>")
    A("<tr>")
    A(f'<td align="center">💻<br/><b>{len(lang_c)}</b><br/>Languages</td>')
    A(f'<td align="center">⭐<br/><b>{esc_xml(most_lang)}</b><br/>Most used</td>')
    A(f'<td align="center">⚡<br/><b>{pct(known_t)}</b><br/>Time analyzed</td>')
    A(f'<td align="center">💾<br/><b>{pct(known_s)}</b><br/>Space analyzed</td>')
    A("</tr>")
    A("</table>")
    A("")
    A("---")
    A("")
    A("## 🎯 Progress")
    A("")
    A(f"**{total}** solutions in this repository")
    A("")
    A(f"🟢 Easy — **{diff_c.get('Easy', 0)}**<br>")
    A(f"🟠 Medium — **{diff_c.get('Medium', 0)}**<br>")
    A(f"🔴 Hard — **{diff_c.get('Hard', 0)}**")
    if diff_c.get("Unknown", 0):
        A(f"⚪ Unknown — **{diff_c.get('Unknown', 0)}**")
    A("")
    emb = chart_embed("assets/stats", "difficulty", "Difficulty distribution",
                      460, avail)
    if emb:
        A(emb)
        A("")
    A("---")
    A("")
    A("## 📊 Performance")
    A("")
    A("Difficulty mix at a glance — the radar scales with the numbers above, "
      "so it stays truthful as new problems land.")
    A("")
    A("---")
    A("")
    A("## 💻 Language Profile")
    A("")
    for lang, n in sorted(lang_c.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        A(f"{esc_xml(lang)} — **{n}**<br>")
    A("")
    emb = chart_embed("assets/stats", "languages", "Language distribution",
                      460, avail)
    if emb:
        A(emb)
        A("")
    A("_Fewer than three languages today renders as compact bars; the radar "
      "takes over automatically once more languages appear._")
    A("")
    A("---")
    A("")
    A("## ⚡ Complexity Profile")
    A("")
    A("<table>")
    A("<tr>")
    A(f"<td align=\"center\"><b>Time</b><br/>{chart_embed('assets/stats', 'time', 'Time complexity distribution', 300, avail)}</td>")
    A(f"<td align=\"center\"><b>Space</b><br/>{chart_embed('assets/stats', 'space', 'Space complexity distribution', 300, avail)}</td>")
    A("</tr>")
    A("</table>")
    A("")
    A(f"Most common time: **{top_time}** · Most common space: **{top_space}**")
    A("")
    A(f"Time analyzed: **{known_t}/{total}** · "
      f"Space analyzed: **{known_s}/{total}**")
    A("")
    A("_Unknown means the analyzer was not confident enough — intentional, "
      "and preferred over a wrong guess._")
    A("")
    A("---")
    A("")
    A("## 🧩 All Problems")
    A("")
    A("| # | Problem | Difficulty | Language | Time | Space |")
    A("|---:|---|:---:|:---:|:---:|:---:|")
    for r in records:
        pid = "" if r["problem_id"] == 10**9 else str(r["problem_id"])
        A(f"| {pid} | {md_link(r['title'], r['leetcode_url'])} "
          f"| {DIFF_BADGE.get(r['difficulty'], r['difficulty'])} "
          f"| {r['language']} | {r['time_complexity']} | {r['space_complexity']} |")
    A("")
    A("---")
    A("")
    A("## 💓 Repository Pulse")
    A("")
    A(f"Problems solved: **{total}** · Languages: **{len(lang_c)}** · "
      f"Complexity analyzed: **{pct(both)}** · Last updated: **{today}**")
    A("")
    A("---")
    A("")
    A("_Generated automatically from this repository._")
    A("")
    stats = {
        "difficulty_counts": dict(diff_c),
        "language_counts": dict(lang_c),
        "time_complexity_counts": dict(time_c),
        "space_complexity_counts": dict(space_c),
    }
    return "\n".join(L), stats
# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def update_readme(readme_path: Path, dashboard: str) -> bool:
    """Replace content between AUTO markers (migrating legacy markers).

    Returns True if the file changed. Custom content outside markers is kept.
    """
    try:
        original = readme_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        original = "# LeetCode Journey\n"
    except OSError as e:
        warn(f"cannot read {readme_path}: {e}")
        return False
    if AUTO_START in original and AUTO_END in original:
        pre, rest = original.split(AUTO_START, 1)
        _, post = rest.split(AUTO_END, 1)
        updated = pre + AUTO_START + "\n\n" + dashboard.strip() + "\n\n" + AUTO_END + post
    elif LEGACY_START in original and LEGACY_END in original:
        pre, rest = original.split(LEGACY_START, 1)
        _, post = rest.split(LEGACY_END, 1)
        updated = pre + AUTO_START + "\n\n" + dashboard.strip() + "\n\n" + AUTO_END + post
    else:
        updated = original.rstrip() + "\n\n" + AUTO_START + "\n\n" + dashboard.strip() + "\n\n" + AUTO_END + "\n"
    if updated != original:
        try:
            readme_path.write_text(updated, encoding="utf-8")
        except OSError as e:
            warn(f"cannot write {readme_path}: {e}")
            return False
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate LeetCode README dashboard.")
    ap.add_argument("--root", default=None, help="Repo root (default: auto-detect).")
    ap.add_argument("--readme", default=None, help="Root README (default: <root>/README.md).")
    ap.add_argument("--assets-dir", default=None,
                    help="Chart dir (default: <root>/assets/stats).")
    ap.add_argument("--no-charts", action="store_true", help="Skip SVG chart files.")
    args = ap.parse_args()

    root = find_repo_root(args.root)
    readme_path = Path(args.readme).resolve() if args.readme else (root / "README.md")
    assets_dir = (Path(args.assets_dir).resolve() if args.assets_dir
                  else (root / "assets" / "stats"))

    problems = list_problem_dirs(root)
    meta_cache = load_meta_cache(root)

    records: list[dict] = []
    for pdir in problems:
        try:
            records.append(build_record(root, pdir, meta_cache))
        except Exception as e:  # one bad folder must never stop the run
            warn(f"skipping {pdir.name}: {e}")
    records.sort(key=lambda r: (r["problem_id"], r["folder"].lower()))

    # Charts first: render_dashboard embeds whatever formats survived, and the
    # data tables always carry the same numbers as a no-JS fallback.
    today = datetime.date.today().isoformat()
    _dc = Counter(r["difficulty"] for r in records)
    _lc = Counter(r["language"] for r in records)
    _tc = Counter(r["time_complexity"] for r in records)
    _sc = Counter(r["space_complexity"] for r in records)
    prelim_stats = {
        "difficulty_counts": dict(_dc),
        "language_counts": dict(_lc),
        "time_complexity_counts": dict(_tc),
        "space_complexity_counts": dict(_sc),
    }
    avail: dict[str, dict[str, bool]] = {}
    if not args.no_charts:
        try:
            avail = write_charts(assets_dir, prelim_stats)
        except OSError as e:
            warn(f"chart output failed: {e}")
    else:
        warn("charts skipped (--no-charts); showing tables only")

    # Live LeetCode card embed (owned by generate_leetcode_card.py, which runs
    # before this script in the workflow). Never hardcoded numbers here; the
    # card itself carries the live statistics.
    leet_svg = assets_dir / LEETCODE_CARD_FILES[0]
    leet_png = assets_dir / LEETCODE_CARD_FILES[1]
    has_svg, has_png = leet_svg.is_file(), leet_png.is_file()
    if has_svg and has_png:
        leet_embed = (
            "<picture>\n"
            f'  <source srcset="assets/stats/{LEETCODE_CARD_FILES[0]}" '
            'type="image/svg+xml">\n'
            f'  <img src="assets/stats/{LEETCODE_CARD_FILES[1]}" '
            'alt="LeetCode Profile" width="960">\n'
            "</picture>"
        )
    elif has_svg:
        leet_embed = (f"![LeetCode Profile]"
                      f"(assets/stats/{LEETCODE_CARD_FILES[0]})")
    elif has_png:
        leet_embed = (f"![LeetCode Profile]"
                      f"(assets/stats/{LEETCODE_CARD_FILES[1]})")
    else:
        leet_embed = ""
        warn("live LeetCode card not found; run "
             "scripts/generate_leetcode_card.py first")
    leet_caption = ""
    try:
        import json as _json
        cache = _json.loads(
            (root / "data" / "leetcode_cache.json").read_text(
                encoding="utf-8"))
        _user = esc_xml(str(cache.get("username", "leetcode.com")))
        _when = str(cache.get("fetched_at", ""))[:10]
        if _when:
            leet_caption = (
                f"_Live LeetCode data for **{_user}**, synced {_when} — "
                "independent of the repository count below._")
        else:
            leet_caption = (
                f"_Live LeetCode data for **{_user}** — independent of the "
                "repository count below._")
    except (OSError, ValueError):
        if has_svg or has_png:
            leet_caption = ("_Live LeetCode data — independent of the "
                            "repository count below._")

    dashboard, stats = render_dashboard(records, today, avail,
                                        leet_embed, leet_caption)

    changed = update_readme(readme_path, dashboard)

    total = len(records)
    dc = Counter(r["difficulty"] for r in records)
    lc = Counter(r["language"] for r in records)
    tc = Counter(r["time_complexity"] for r in records)
    sc = Counter(r["space_complexity"] for r in records)
    print(f"Problems: {total} | Easy {dc.get('Easy', 0)} "
          f"Med {dc.get('Medium', 0)} Hard {dc.get('Hard', 0)} "
          f"Unknown-diff {dc.get('Unknown', 0)}")
    print(f"Languages: {dict(sorted(lc.items()))}")
    print(f"Time: {dict(sorted(tc.items()))}")
    print(f"Space: {dict(sorted(sc.items()))}")
    print(f"Charts: {avail} | README {'updated' if changed else 'unchanged'} "
          f"| warnings {len(warnings_log)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())