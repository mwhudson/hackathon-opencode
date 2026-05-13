---
name: launchpad-build-bug
description: Turn a Launchpad build-failure URL into a ready-to-file bug report (Title + Description). Use this skill whenever the user shares a Launchpad build URL (either a `+build` page like `https://launchpad.net/.../+build/<id>` or a direct `buildlog_*_BUILDING.txt.gz` link) and wants to summarize, triage, or file the failure as a Launchpad bug — including phrasings like "make a bug for this build", "summarize this FTBFS", "write up this build failure", or just sharing the URL with no explicit ask when the context is filing a bug.
---

# Launchpad build-failure bug report

This skill takes a URL pointing at a Launchpad build failure and produces a
**Title** and **Description** suitable for pasting straight into Launchpad's
bug-filing form. The heavy lifting (downloading the buildlog, finding the
failure, structuring metadata) is done by bundled Python scripts. The
write-up is delegated to a Sonnet 4.6 subagent for consistent output
quality regardless of the orchestrating model.

## Workflow

All paths below are relative to this skill directory.

### Step 1 — Download the buildlog

Run the fetcher with the URL the user gave you:

```bash
python3 scripts/fetch_buildlog.py <url>
```

The script accepts both shapes:
- A Launchpad `+build` page (e.g. `https://launchpad.net/ubuntu/+archive/.../+build/32388755`).
  The script scrapes the page for the `*_BUILDING.txt.gz` link and follows it.
- A direct buildlog URL (`*.txt` or `*.txt.gz` on `launchpadlibrarian.net` or
  `launchpad.net`).

It writes the decompressed log to `/tmp/launchpad-build-bug/<basename>.txt`
and prints that path on stdout. Capture stdout.

If the script fails (network, page format change), tell the user and ask
for either a direct buildlog URL or the file on disk — don't fall back to
`WebFetch` and try to parse HTML yourself; the script is the source of
truth for what counts as a buildlog.

### Step 2 — Extract the failure-relevant slice

Run the extractor against the downloaded log:

```bash
python3 scripts/extract_failure.py <local-log-path>
```

This emits a JSON object on stdout with the package metadata, the
build-chain cascade, and two complementary log slices (`failure_excerpts`
around any failure markers, and `failure_tail` immediately before the
cascade).

**Don't `Read` the raw buildlog yourself.** Launchpad logs run tens of
thousands of lines — the mysql sample in the repo's hackathon directory
is 18,761. The extractor is designed to give the writer subagent
everything it needs in well under 1000 lines.

### Step 3 — Delegate the write-up to a subagent

Read `agents/bug-writer.md`. Then construct the prompt:

1. The full contents of `agents/bug-writer.md`
2. Two blank lines
3. `## Input`
4. The JSON from step 2
5. A blank line
6. `Build URL: <the original URL the user pasted>`

Delegate the write-up using the appropriate tool for your environment:

**Claude Code** — invoke the `Agent` tool:

- **`subagent_type`**: `"general-purpose"`
- **`model`**: `"sonnet"` (pins the write-up to Sonnet 4.6 for consistent
  quality regardless of the orchestrating model)
- **`prompt`**: the prompt constructed above

**opencode** — invoke the `Task` tool:

- **`subagent_type`**: `"general"`
- **`description`**: `"Draft Launchpad bug from buildlog"`
- **`prompt`**: the full contents of `agents/bug-writer.md`, followed by
  two blank lines, then `## Input`, then the JSON from step 2, then a
  blank line, then `Build URL: <the original URL the user pasted>`

The subagent returns the formatted `TITLE` / `DESCRIPTION` block as its
final message.

### Step 4 — Save the output to a file

Write the subagent's output to `./<source_package>_<version>-bug.md` in
the current working directory, where `<source_package>` and `<version>`
come from the JSON extract in step 2. Use the `Write` tool — no need to
shell out. If the file already exists (e.g. the user is re-running on
the same build), overwrite it.

### Step 5 — Surface the result

Show the subagent's output to the user **verbatim**, then on a final
line tell them where it was saved (e.g. "Saved to
`./fprintd_1.94.5-4-bug.md`."). Don't reformat the report, don't add a
summary, don't append "let me know if you want changes." If the user
asks for revisions, run the subagent again with the revision request
appended to the prompt and overwrite the file.

## Why the subagent

Three reasons:
1. **Model pinning.** The orchestrator may be running Opus, Haiku, or a
   non-Anthropic model (e.g. when this repo is used with opencode +
   OpenRouter). A dedicated subagent gives a known, appropriate quality
   floor for the write-up step. Claude Code users get Sonnet 4.6; opencode
   users configure the model in `.opencode/agents/bug-writer.md`.
2. **Context isolation.** The subagent only sees the JSON extract, not
   the orchestrator's full conversation. Cleaner input → more reliable
   output, and the orchestrator's context isn't bloated with log data.
3. **Cost shape.** Sonnet handles the inference comfortably; Opus would
   be more expensive with no quality lift on templated summarization,
   and Haiku tends to over-claim root causes on log data. For open-weight
   models via OpenRouter, pick the best model your budget allows — the
   subagent config makes this easy to adjust.

## Reference

See `references/launchpad-bug-format.md` for the full title/description
template and a worked example. The subagent prompt already encodes
this — don't re-read the reference yourself unless the user asks
about the format directly.
