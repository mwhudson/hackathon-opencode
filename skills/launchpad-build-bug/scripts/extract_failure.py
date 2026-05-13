#!/usr/bin/env python3
"""Extract the failure-relevant slice of a Launchpad buildlog.

Launchpad buildlogs run tens of thousands of lines (the mysql-8.4 sample in
this repo is 18,761). The model only needs:
  - identifying metadata (package, version, series, arch, build URL)
  - the build-chain cascade (`make[N]: *** [...] Error N` lines and the
    `dpkg-buildpackage.pl` error line)
  - the failure tail: the ~200 lines immediately before that cascade, where
    the actual test/compile error usually lives

This script reads a buildlog and prints that compact view as JSON on stdout.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys

TAIL_CONTEXT_LINES = 250
CASCADE_LOOKBACK = 60
EXCERPT_BEFORE = 3
EXCERPT_AFTER = 30
MAX_EXCERPT_LINES = 400
NOISE_PREFIXES = (
    "PROCESS MEMORY HOGS",
    "SUMMARY: host:",
    "SUMMARY: swap",
)

# High-signal failure markers that can appear anywhere in the log. Test
# failures often happen thousands of lines before the build-chain cascade
# (e.g. mysql-test-run runs hundreds of passing tests after a failure), so
# we grep for these and capture a window of context around each.
FAILURE_MARKERS = (
    re.compile(r"\[ fail \]"),
    re.compile(r"\[ retry-fail \]"),
    re.compile(r"^FAIL: "),
    re.compile(r"\*\*\* ERROR"),
    re.compile(r"^FATAL:"),
    re.compile(r":\s+error:"),  # gcc/clang style: foo.c:42: error: ...
    re.compile(r"undefined reference to"),
    re.compile(r"cannot find -l"),
)


def parse_filename(path: pathlib.Path) -> dict:
    # buildlog_ubuntu-<series>-<arch>.<source>_<version>_BUILDING.txt
    m = re.match(
        r"buildlog_ubuntu-(?P<series>[^-]+)-(?P<arch>[^.]+)\."
        r"(?P<source>.+)_(?P<version>[^_]+)_BUILDING(?:\.txt)?$",
        path.name,
    )
    if not m:
        return {}
    return {
        "series": m.group("series"),
        "architecture": m.group("arch"),
        "source_package": m.group("source"),
        "version": m.group("version"),
    }


def find_build_url(lines: list[str]) -> str | None:
    for line in lines[:20]:
        m = re.search(r"https://launchpad\.net/\S+/\+build/\d+", line)
        if m:
            return m.group(0)
    return None


def parse_summary_block(lines: list[str]) -> dict:
    """Pull Key: Value pairs from the trailing '| Summary' banner block."""
    summary: dict[str, str] = {}
    # Find the line that contains "| Summary" — the banner. The block ends at
    # the next "----..." separator.
    start = None
    for i, line in enumerate(lines):
        if "| Summary" in line:
            start = i
    if start is None:
        return summary
    for line in lines[start + 1 :]:
        if re.match(r"^-{10,}$", line.strip()):
            break
        m = re.match(r"^([A-Za-z][A-Za-z -]+):\s+(.+)$", line)
        if m:
            summary[m.group(1).strip()] = m.group(2).strip()
    return summary


def find_failure_cascade(lines: list[str]) -> tuple[int, list[str]]:
    """Return (start_index, cascade_lines) for the final build-failure chain.

    The cascade is the cluster of `make[N]: *** [...] Error N` lines plus the
    `dpkg-buildpackage.pl: error` / `dh_auto_*: error` lines that immediately
    follow the actual failure. We anchor on the last `dpkg-buildpackage.pl:
    error` line in the file, then walk back collecting consecutive cascade-
    looking lines, stopping when we hit a gap of unrelated output.
    """
    anchor = None
    for i in range(len(lines) - 1, -1, -1):
        if "dpkg-buildpackage" in lines[i] and "error" in lines[i].lower():
            anchor = i
            break
    if anchor is None:
        # Fall back to the last make error.
        for i in range(len(lines) - 1, -1, -1):
            if re.match(r"^make(\[\d+\])?:\s+\*\*\*", lines[i]):
                anchor = i
                break
    if anchor is None:
        return len(lines), []

    cascade_patterns = (
        re.compile(r"^make(\[\d+\])?:\s+\*\*\*"),
        re.compile(r"^make(\[\d+\])?:\s+Leaving directory"),
        re.compile(r"^dh_\w+:\s+error"),
        re.compile(r"^dpkg-buildpackage"),
        re.compile(r"^E:\s+Build failure"),
    )

    start = anchor
    gap = 0
    for i in range(anchor, max(-1, anchor - CASCADE_LOOKBACK), -1):
        if any(p.match(lines[i]) for p in cascade_patterns):
            start = i
            gap = 0
        else:
            gap += 1
            if gap > 3:
                break
    return start, lines[start : anchor + 1]


def find_failure_excerpts(lines: list[str], cascade_start: int) -> list[str]:
    """Capture context around failure markers that appear far above the cascade.

    Returns a flat list of lines with `--- line N ---` separators between
    excerpts. Only looks above `cascade_start` (the cascade tail is already
    captured in `failure_tail`). Overlapping windows are merged.
    """
    if cascade_start <= 0:
        return []

    # Collect (start, end) inclusive ranges where we have a marker hit.
    ranges: list[tuple[int, int]] = []
    for i in range(min(cascade_start, len(lines))):
        if any(p.search(lines[i]) for p in FAILURE_MARKERS):
            start = max(0, i - EXCERPT_BEFORE)
            end = min(cascade_start - 1, i + EXCERPT_AFTER)
            if ranges and start <= ranges[-1][1] + 1:
                ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
            else:
                ranges.append((start, end))

    if not ranges:
        return []

    # If there are too many excerpts, prefer the ones nearest the cascade —
    # those are most likely to be the proximate cause. Walk from the end.
    selected: list[tuple[int, int]] = []
    total = 0
    for r in reversed(ranges):
        size = r[1] - r[0] + 1
        if total + size > MAX_EXCERPT_LINES and selected:
            break
        selected.append(r)
        total += size
    selected.reverse()

    out: list[str] = []
    for idx, (start, end) in enumerate(selected):
        if idx > 0:
            out.append(f"--- (skipped {selected[idx][0] - selected[idx-1][1] - 1} lines) ---")
        out.append(f"--- buildlog line {start + 1} ---")
        out.extend(lines[start : end + 1])
    return out


def trim_tail(lines: list[str]) -> list[str]:
    """Drop the noisy 'PROCESS MEMORY HOGS' and SUMMARY block tails."""
    out = []
    for line in lines:
        stripped = line.rstrip()
        if any(stripped.startswith(p) for p in NOISE_PREFIXES):
            continue
        if stripped.startswith("  ") and (
            "/usr/libexec/gcc" in stripped or "/usr/bin/ld" in stripped
        ):
            # Continuation of the memory-hog block — multi-GB cc1/ld lines.
            continue
        out.append(line)
    return out


def extract(path: pathlib.Path) -> dict:
    with path.open("r", errors="replace") as f:
        lines = f.read().splitlines()

    from_filename = parse_filename(path)
    summary = parse_summary_block(lines)
    build_url = find_build_url(lines)
    cascade_start, cascade = find_failure_cascade(lines)

    tail_start = max(0, cascade_start - TAIL_CONTEXT_LINES)
    tail = trim_tail(lines[tail_start:cascade_start])
    excerpts = find_failure_excerpts(lines, tail_start)

    package = (
        summary.get("Package")
        or from_filename.get("source_package")
        or "unknown"
    )
    version = (
        summary.get("Source-Version")
        or summary.get("Version")
        or from_filename.get("version")
        or "unknown"
    )
    series = (
        summary.get("Distribution") or from_filename.get("series") or "unknown"
    )
    arch = (
        from_filename.get("architecture")
        or summary.get("Host Architecture")
        or summary.get("Build Architecture")
        or "unknown"
    )

    return {
        "source_package": package,
        "version": version,
        "series": series,
        "architecture": arch,
        "fail_stage": summary.get("Fail-Stage", "unknown"),
        "build_url": build_url,
        "buildlog_filename": path.name,
        "build_chain": cascade,
        "failure_excerpts": excerpts,
        "failure_tail": tail,
        "tail_lines": len(tail),
        "excerpt_lines": len(excerpts),
        "total_lines": len(lines),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <buildlog-path>", file=sys.stderr)
        return 2
    path = pathlib.Path(sys.argv[1])
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 2
    data = extract(path)
    json.dump(data, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
