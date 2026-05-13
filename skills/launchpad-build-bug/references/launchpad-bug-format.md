# Launchpad bug format for Ubuntu FTBFS reports

This document defines the **Title** and **Description** format the
`launchpad-build-bug` skill emits. Triagers in Launchpad scan bug lists by
title and grep descriptions for exact error strings, so the format
optimizes for both: a recognizable title shape and verbatim error lines in
the body.

## Title format

```
<source-package> <version> FTBFS in <series>: <one-line cause>
```

- **FTBFS** is the conventional acronym ("Fails to Build From Source") used
  across Debian and Ubuntu. Keep it uppercase.
- **`<series>`** is the Ubuntu release codename from the buildlog summary
  (`Distribution:` field), e.g. `resolute`, `noble`, `oracular`.
- **`<one-line cause>`** is the shortest accurate handle on what broke.
  Aim for under ~60 characters here so the whole title stays under ~100.
  Prefer concrete signals (test name, missing symbol, command) over vague
  ones ("test failure", "build error").

**Examples:**

| Input                                          | Title |
|---|---|
| acl 2.3.2-2 test/misc.test fails 4 commands    | `acl 2.3.2-2 FTBFS in resolute: test/misc.test fails 4 ACL commands` |
| mysql-8.4 validate_json.pl fails 2 tests       | `mysql-8.4 8.4.8-0ubuntu1 FTBFS in resolute: validate_json.pl fails 2 mysql-test cases` |
| linker can't find -lsodium                     | `<pkg> <ver> FTBFS in <series>: ld can't find -lsodium during link` |
| gcc-16 error on `foo.cc:42`                    | `<pkg> <ver> FTBFS in <series>: gcc-16 error in foo.cc (warning-as-error)` |

## Description format

Always use exactly this markdown skeleton. Headings (`##`) and the bullet
list under "Build details" are fixed; the body content adapts to the
failure.

```markdown
**Package:** <source-package> <version>
**Series / arch:** <series> / <architecture>
**Fail stage:** <fail_stage>
**Build:** <build_url>
**Buildlog:** <buildlog_filename>

## Failure

<1-3 sentences naming the failing component (test, compile unit, link
step) and what specifically went wrong. Quote the operative error line
verbatim — Launchpad triagers grep for these. Use a fenced code block
for any multi-line excerpt.>

## Likely cause

<1-3 sentences with your best inference, clearly labelled as a guess
("likely", "appears to be") rather than asserted as fact. If the evidence
is thin, say so. If there's no obvious cause, write "Cause unclear from
the buildlog excerpt — see the linked buildlog for the full output."
Avoid speculating about fixes unless they're obvious from the error.>
```

### Section guidance

- **Package / Build details** — straight from the JSON metadata. Keep the
  bullet list exactly as shown.
- **Failure** — this is the highest-value section. Lead with the
  *concrete* failure (test name, file:line, undefined symbol). Quote the
  exact error line in a fenced code block when it's short; for multi-line
  errors, use a fenced block. Don't paraphrase error messages — copy them.
- **Likely cause** — earn this section. If the failure is "tests fail and
  I don't know why," say so plainly. A weak guess labelled as fact is
  worse than no guess.

### Why no "Build chain" section

The JSON extract carries a `build_chain` field with the `make[N]: ***`
cascade and the final `dpkg-buildpackage: error` line. We deliberately
*don't* surface that as its own section in the report. In practice it's
always one of three boilerplate shapes (dh_auto_configure / dh_auto_build
/ dh_auto_test failed, then standard make cascade, then dpkg-buildpackage
error) and the **Failure** section already names which step broke. The
cascade is still useful internally — if it points at a specific
`debian/rules` target the failure section didn't already name, fold that
detail into **Failure** rather than adding a section for it.

## What to avoid

- **Don't invent details.** If the architecture, version, or series isn't
  in the JSON, write "unknown" — don't guess from filenames or the URL.
- **Don't summarize away the error string.** A line like `error: 256,
  status: 1, errno: 2` is exactly what a triager will grep for. Keep it.
- **Don't add a "Fix" or "Reproducer" section.** Those belong in
  follow-up comments after triage, not the initial report.
- **Don't editorialize about whose bug it is.** ("This is clearly an
  upstream issue" is unhelpful in a triage bug.)
- **Don't include the cleanup/summary trailer** from the buildlog (the
  `+----- Summary -----+` block). The metadata header already captures
  what's needed from it.

## Worked example (acl)

Given the JSON extract:
```json
{
  "source_package": "acl",
  "version": "2.3.2-2",
  "series": "resolute",
  "architecture": "amd64",
  "fail_stage": "build",
  "build_url": "https://launchpad.net/ubuntu/+archive/test-rebuild-20260320-resolute/+build/32388755",
  "buildlog_filename": "buildlog_ubuntu-resolute-amd64.acl_2.3.2-2_BUILDING.txt",
  "build_chain": [
    "make[5]: *** [Makefile:2072: test-suite.log] Error 1",
    "make[4]: *** [Makefile:2207: check-TESTS] Error 2",
    "make[2]: *** [Makefile:1958: check-recursive] Error 1",
    "dh_auto_test: error: make -j4 check ... returned exit code 2",
    "dpkg-buildpackage.pl: error: debian/rules binary subprocess failed with exit status 2"
  ]
}
```

A good output is:

```
TITLE
-----
acl 2.3.2-2 FTBFS in resolute: test/misc.test fails 4 ACL commands

DESCRIPTION
-----------
**Package:** acl 2.3.2-2
**Series / arch:** resolute / amd64
**Fail stage:** build
**Build:** https://launchpad.net/ubuntu/+archive/test-rebuild-20260320-resolute/+build/32388755
**Buildlog:** buildlog_ubuntu-resolute-amd64.acl_2.3.2-2_BUILDING.txt

## Failure

`test/misc.test` reports 4 failed commands out of 17 during
`make check`. The testsuite logs show ACL `getfacl` / `ls -dl` output
differing from expected — `other::r-x` where the expected value is
`other::---`, and similar mask/default-ACL discrepancies. Final testsuite
summary:

```
# TOTAL: 15
# PASS:  8
# SKIP:  4
# XFAIL: 2
# FAIL:  1
```

## Likely cause

The diffs look like a change in default umask / inherited-ACL behavior
between the build environment and what the testsuite expects. Possibly a
glibc, util-linux, or kernel-side ACL change in resolute. The test itself
hasn't moved; this is most likely environmental.
```
