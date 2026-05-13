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

### 4. Search for existing bug and upstream fix
- Search Launchpad (`launchpad.net`) for existing bugs against the source package
- Search Debian BTS (`bugs.debian.org`) for existing reports
- Search upstream repository (GitHub, Codeberg, GitLab, srcbox, etc.) for related commits or issues
- Use web search to find patches (e.g. Linux From Scratch patches, Fedora fixes)
- If the package is unmaintained upstream, note this explicitly
- Cross-reference: check if the same failure pattern appears in other packages (shared root cause)

### 5. Write Bug Report / Summary
Produce a concise report with:
- **Summary**: One-line description of the failure
- **Build environment**: distro version, architecture, toolchain versions if known
- **Relevant log excerpt**: The smallest snippet showing the actual failure (≤50 lines)
- **Analysis**: Why it failed and what category it falls into
- **Existing bugs**: Links to any existing Launchpad/Debian/upstream bugs or commits found
- **Suggested fix**: Concrete next step (add dependency, patch code, sync from Debian, skip test, etc.)
- **Severity**: FTBFS (Fails To Build From Source) classification if applicable

### Common failure patterns in Ubuntu/Debian
Keep an eye out for these recurring systemic issues:
- **glibc 2.43 / ISO C23**: `strchr()`, `strrchr()`, `memchr()` now return `const` pointers. Look for `-Werror=discarded-qualifiers` errors.
- **GCC 15 / `-Wincompatible-pointer-types`**: Old K&R C function pointers `()` with no prototype now error when assigned to modern prototypes.
- **Packaging regressions**: Header files moved between binary packages (e.g. `gkrellm-visibility.h` moved from `gkrellmd` to `gkrellm`).
- **Missing dependencies**: Build-depends not declared, or transitions changed package names.
- **Test failures**: Root-required tests, flaky tests, tests depending on external services.

### Style Notes
- Be terse but precise. Distribution maintainers don't have time for essays.
- Never guess. If the root cause is unclear, say so and list the possibilities.
- Always include the exact error message, not a paraphrase.
