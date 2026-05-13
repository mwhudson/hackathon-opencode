# Build Failure Debugger

## Description

Specialized skill for debugging software build failures, particularly in Debian/Ubuntu packaging contexts. Provides systematic log analysis, root cause identification, and bug report generation.

## Instructions

When asked to debug a build failure, follow this workflow precisely:

### 1. Fetch Build Failure Log
- Accept input as: local file path, URL, or pasted log content
- If URL: use `webfetch` to retrieve the log
- If local file: read with `read` tool
- If pasted content: proceed directly to analysis

### 2. Extract Relevant Logs
- Identify the build system (debuild, dpkg-buildpackage, make, cmake, meson, etc.)
- Locate the actual error (not just warnings)
- Extract the last 200 lines leading to failure, or the specific error block
- Note: scroll up from the bottom; build systems often print "error" summaries after the real failure

### 3. Analyze Root Cause
Classify the failure into one of these categories:
- **Missing dependency**: `No such file or directory`, `package not found`, `cannot find -l<lib>`
- **Compiler error**: syntax errors, type mismatches, missing headers
- **Linker error**: undefined references, missing libraries
- **Test failure**: assertion failed, test suite non-zero exit
- **Architecture-specific**: asm constraints, endianness, 32/64-bit issues
- **Toolchain issue**: autopkgtest, cross-build, dpkg-shlibdeps warnings
- **Infrastructure**: out of disk space, OOM killed, network fetch failed

### 4. Search for existing bug in launchpad.net


### 5. Write Bug Report / Summary
Produce a concise report with:
- **Summary**: One-line description of the failure
- **Build environment**: distro version, architecture, toolchain versions if known
- **Relevant log excerpt**: The smallest snippet showing the actual failure (≤50 lines)
- **Analysis**: Why it failed and what category it falls into
- **Suggested fix**: Concrete next step (add dependency, patch code, skip test, etc.)
- **Severity**: FTBFS (Fails To Build From Source) classification if applicable

### Style Notes
- Be terse but precise. Distribution maintainers don't have time for essays.
- Never guess. If the root cause is unclear, say so and list the possibilities.
- Always include the exact error message, not a paraphrase.
