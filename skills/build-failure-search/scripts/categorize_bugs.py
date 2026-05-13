#!/usr/bin/env python3
"""Parse FTBFS bug report .md files and categorize them by failure cause.

Reads all *-bug.md files in a directory, extracts structured data from each,
assigns failure categories based on pattern matching, and returns JSON.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


CATEGORIES = [
    ("cmake-minimum-required", "CMake 4.x rejects old cmake_minimum_required version", [
        r"(?i)cmake_minimum_required.*compatibility.*removed",
        r"(?i)cmake.*< 3\.5.*removed",
        r"(?i)cmake_minimum_required.*version.*too.*old",
    ]),
    ("cmake-policy", "CMake policy OLD behavior no longer supported", [
        r"(?i)policy CMP\d+.*no longer supports?.*OLD",
        r"(?i)CMP\d+.*may not be set to OLD",
    ]),
    ("c23-keyword", "C23 keyword conflict (bool, nullptr, etc.)", [
        r"(?i)cannot be defined via.*typedef.*\bbool\b",
        r"(?i)\bbool\b.*is a keyword with.*C23",
        r"(?i)nullptr.*(?:\bkeyword\b|\breserved\b)",
    ]),
    ("gcc-warnings-as-errors", "gcc/newer compiler warnings promoted to errors (-Werror)", [
        r"(?i)-Werror=discarded-qualifiers",
        r"(?i)-Werror=incompatible-pointer-types",
        r"(?i)-Wincompatible-pointer-types",
        r"(?i)warnings being treated as errors",
        r"(?i)discards.*const.*qualifier.*-Werror",
    ]),
    ("empty-function-prototype", "Empty function pointer prototype `()` rejected as zero-arg", [
        r"(?i)empty.*prototype|too many arguments.*expected 0",
        r"(?i)void \(\*\)\(\)|void \(\*\)\(void\)",
        r"(?i)expected.*void \(\*\)\(void\).*but argument is of type",
        r"(?i)incompatible.*pointer.*?expected.*void \(\*\)\(void\)",
    ]),
    ("header-type-conflict", "Conflicting types/macros between system headers", [
        r"(?i)conflicting types for",
        r"(?i)previous declaration of.*type",
        r"(?i)#define.*\n.*error.*expected identifier.*before numeric constant",
        r"(?i)error: expected identifier.*before numeric constant.*\n.*#define",
        r"(?i)conflicts with.*signal\.h|conflicts with.*siginfo",
    ]),
    ("incomplete-type", "Incomplete/undefined struct or type", [
        r"(?i)sizeof.*incomplete type",
        r"(?i)invalid application of.*sizeof.*incomplete",
    ]),
    ("missing-dependency", "Missing build dependency (package, library, include file)", [
        r"(?i)cannot find -l",
        r"(?i)No such file or directory.*\.(?:mk|prf|pri)\b",
        r"(?i)not available.*architecture|not installable",
        r"(?i)unable to satisfy dependencies",
        r"(?i)library.*not defined",
        r"(?i)none of the choices are installable",
        r"(?i)no rule to make target",
        r"(?i)(?:shared or static|shared|static) library.*not found",
        r"(?i)Errors were encountered while processing",
    ]),
    ("api-removed", "Removed API/function in newer library version", [
        r"\w+:\w+/\d+ is removed; use \w+/\d+",
        r"(?i)warning:.*is removed.*use .*instead",
    ]),
    ("cxx-std-compat", "C++ standard/library compatibility issue", [
        r"(?i)has not been declared in.*std",
        r"(?i)type_traits.*(?:incompatible|undeclared)",
        r"(?i)std::.*not been declared",
    ]),
    ("test-failure", "Specific test suite or test case failure", [
        r"(?i)test.*panicked",
        r"(?i)assertion.*`left == right` failed",
        r"(?i)0 of 1 test suites.*0 of 1 test cases.*passed",
        r"(?i)panicked at.*tests?/",
        r"(?i)dh_auto_test.*fail|Test suite.*FAIL",
    ]),
    ("parallel-build-race", "Parallel build race condition or LTO issue", [
        r"(?i)file too short",
        r"(?i)lto1.*error.*file too short",
        r"(?i)race.*condition.*parallel",
    ]),
    ("arch-specific", "Architecture-specific data-size issue (32-bit, endianness)", [
        r"(?i)Could not undump.*byte item.*armhf",
        r"(?i)32.?bit.*format.*layout",
        r"(?i)data-size mismatch",
    ]),
    ("fakeroot-chown", "chown fails in fakeroot/build sandbox environment", [
        r"(?i)chown.*changing ownership.*Operation not permitted",
        r"(?i)fakeroot.*does not intercept.*chown",
    ]),
    ("rust-ffi-mismatch", "Rust crate FFI symbol mismatch with -sys or binding crate", [
        r"(?i)cannot find function.*in crate.*ffi",
        r"(?i)cannot find type.*in crate.*glib",
        r"(?i)similarly named.*defined here",  # Rust "similarly named struct" suggestion
    ]),
    ("abstract-class", "Pure virtual function makes class abstract, can't instantiate", [
        r"(?i)invalid new-expression of abstract class",
        r"(?i)= 0;.*class.*abstract",
        r"(?i)pure virtual.*= 0",
    ]),
    ("network-build", "Build attempts external network access in sandbox", [
        r"(?i)failed to open TCP connection.*raw\.githubusercontent",
        r"(?i)getaddrinfo.*Name or service not known",
        r"(?i)network.*access.*build.*sandbox",
    ]),
    ("typescript-error", "TypeScript type error during build", [
        r"(?i)error TS\d+",
        r"(?i)does not satisfy the constraint",
    ]),
    ("module-not-found", "Python/Ruby/Perl module import failure", [
        r"(?i)ModuleNotFoundError: No module named",
        r"(?i)ImportError:.*No module named",
        r"(?i)cannot import name",
    ]),
    ("dpkg-file-conflict", "dpkg file overwrite conflict between packages", [
        r"(?i)trying to overwrite.*which is also in package",
        r"(?i)dpkg.*error.*trying to overwrite",
    ]),
    ("golang-linker-panic", "Go linker panic during compilation/linking", [
        r"(?i)panic: R_USEIFACE",
        r"(?i)linker.*panic.*cmd/link",
        r"(?i)cmd/link/internal/ld",
    ]),
]


MATCH_ALL_PATTERNS = [
    # Broad patterns that match many bugs but are useful as secondary classifiers.
    # Only applied when no other category matched — prevents over-tagging.
    ("dh-auto-test-fail", "Build fails during dh_auto_test", [
        r"(?i)dh_auto_test: error",
    ]),
    ("dh-auto-build-fail", "Build fails during dh_auto_build", [
        r"(?i)dh_auto_build: error",
    ]),
]


def parse_bug_file(filepath: str) -> dict | None:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None

    result = {"file": os.path.basename(filepath), "title": "", "metadata": {}, "failure": "", "likely_cause": ""}

    title_m = re.search(r"^TITLE\s*\n-+\s*\n(.+)$", text, re.MULTILINE)
    if title_m:
        result["title"] = title_m.group(1).strip()

    metadata_m = re.findall(r"\*\*(.+?):\*\*\s*(.+)", text)
    for key, val in metadata_m:
        result["metadata"][key.strip()] = val.strip()

    failure_m = re.search(r"## Failure\s*\n(.+?)(?=\n## Likely cause|\n## |\Z)", text, re.DOTALL)
    if failure_m:
        result["failure"] = failure_m.group(1).strip()

    cause_m = re.search(r"## Likely cause\s*\n(.+?)(?=\n## |\Z)", text, re.DOTALL)
    if cause_m:
        result["likely_cause"] = cause_m.group(1).strip()

    return result


def categorize(parsed: dict) -> list[str]:
    haystack = " ".join([
        parsed.get("title", ""),
        parsed.get("failure", ""),
        parsed.get("likely_cause", ""),
    ])

    matched = []
    for label, _desc, patterns in CATEGORIES:
        for pat in patterns:
            if re.search(pat, haystack, re.MULTILINE):
                matched.append(label)
                break
    return matched


def main():
    ap = argparse.ArgumentParser(description="Categorize FTBFS bug report .md files")
    ap.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory containing *-bug.md files (default: .)",
    )
    ap.add_argument(
        "--summary",
        action="store_true",
        help="Print a human-readable category summary instead of full JSON",
    )
    args = ap.parse_args()

    bug_files = sorted(Path(args.directory).glob("*-bug.md"))
    if not bug_files:
        print(json.dumps({"error": f"No *-bug.md files found in {args.directory}"}))
        sys.exit(1)

    bugs = []
    for fp in bug_files:
        parsed = parse_bug_file(str(fp))
        if parsed is None:
            continue
        parsed["categories"] = categorize(parsed)
        bugs.append(parsed)

    for b in bugs:
        if not b["categories"]:
            b["categories"] = ["other"]

    if args.summary:
        cat_map: dict[str, list[str]] = {}
        for b in bugs:
            for cat in b["categories"]:
                cat_map.setdefault(cat, []).append(b["title"] or b["file"])

        # Print sorted by count descending
        for label, desc, _ in sorted(CATEGORIES, key=lambda c: len(cat_map.get(c[0], [])), reverse=True):
            bugs_in_cat = cat_map.get(label, [])
            if not bugs_in_cat:
                continue
            print(f"\n## {desc} ({len(bugs_in_cat)} bugs)")
            for t in bugs_in_cat:
                print(f"  - {t}")

        others = cat_map.get("other", [])
        if others:
            print(f"\n## Unclassified ({len(others)} bugs)")
            for t in others:
                print(f"  - {t}")

        classified = len(bugs) - len(others)
        print(f"\n---\nTotal: {len(bugs)} bug reports, {classified} classified, {len(others)} unclassified")
    else:
        cat_defs = {label: desc for label, desc, _ in CATEGORIES}
        print(json.dumps({"categories": cat_defs, "bugs": bugs}, indent=2))


if __name__ == "__main__":
    main()
