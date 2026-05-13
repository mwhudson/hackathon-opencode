# Build failure taxonomy reference

This document catalogues the common failure categories found in
Launchpad FTBFS bug reports. Each section describes the failure
pattern, the typical error signature, and which packages tend to
be affected.

The `categorize_bugs.py` script uses regex patterns derived from
this taxonomy to classify bug reports automatically.

## Category index

### Toolchain / compiler

| Category | Pattern | Examples |
|---|---|---|
| **cmake-minimum-required** | `cmake_minimum_required` with version below 3.5 rejected by CMake 4.x | `liblaxjson`, `nitrokey-app`, `openbabel`, `q4wine`, `soapyplutosdr`, `emoslib`, `libfm-qt5`, `plasma-wallpaper-dynamic` |
| **cmake-policy** | CMake 4.x drops backward-compat for OLD policy (e.g. CMP0059) | `kreport` |
| **c23-keyword** | C23 makes `bool`, `nullptr`, `true`, `false` reserved keywords | `softether-vpn` (typedef bool), `golang-1.23` (nullptr) |
| **gcc-warnings-as-errors** | Newer gcc emits warnings that are fatal under `-Werror` | `faketime`, `pam-python`, `gnome-screensaver`, `erlang-ranch`, `isc-dhcp`, `ruby-eb` |
| **empty-function-prototype** | C23 treats `()` in function pointer declarations as zero-arg, not unspecified-arg | `isc-dhcp`, `ruby-eb`, `ruby-rpatricia`, `eta` |

### Header / type system

| Category | Pattern | Examples |
|---|---|---|
| **header-type-conflict** | Two system headers define the same type/macro incompatibly | `android-platform-system-extras` (__le64), `qt6-webengine` (SYS_SECCOMP vs signal.h), `r-cran-later` (pthread_once_t) |
| **incomplete-type** | `sizeof` applied to struct with no definition visible | `libexplain` (struct termio) |
| **cxx-std-compat** | C++ standard too old for library headers requiring C++14/17 | `librecad`, `r-bioc-ebseq` (Boost type_traits) |

### Build system

| Category | Pattern | Examples |
|---|---|---|
| **missing-dependency** | Package, library, or build-system include file not found | `libdbd-mysql-perl`, `lua-cqueues`, `lua-luaossl`, `lua-sec`, `gnome-system-tools`, `gnome-commander`, `libcrypt-util-perl`, `dataquay`, `kde-config-whoopsie`, `r-cran-rlinsolve` |
| **parallel-build-race** | LTO merge reads object file before parallel compile finishes | `python-psutil` |
| **fakeroot-chown** | chown fails in fakeroot/build sandbox | `brother-lpr-drivers-mfc9420cn` |

### Library API changes

| Category | Pattern | Examples |
|---|---|---|
| **api-removed** | Function removed from shared library in newer release | `erlang-ranch` (ssl:ssl_accept/2, ssl:cipher_suites/0) |
| **abstract-class** | Pure virtual function added to base class, making subclass abstract | `vdr-plugin-remote` (cThread::Action pure virtual) |
| **rust-ffi-mismatch** | Rust binding crate references FFI symbol not in -sys crate | `rust-gdk4` (glib::String missing), `rust-libphosh` (phosh_status_icon_get_priority missing) |

### Test failures

| Category | Pattern | Examples |
|---|---|---|
| **test-failure** | Specific test case or test suite fails at runtime | `rust-expectrl`, `haskell-cryptonite`, `libdbd-odbc-perl`, `php-sabre-vobject`, `python-pyscss`, `ruby-mysql2`, `rust-asn1-rs`, `ocaml-process`, `haskell-arithmoi`, `golang-github-traefik-yaegi` |

### Environment / sandbox

| Category | Pattern | Examples |
|---|---|---|
| **network-build** | Build or test attempts external network access | `ruby-chef-utils` (fauxhai-ng → raw.githubusercontent.com) |
| **dpkg-file-conflict** | Two packages claim the same file path during dep install | `libcrypt-twofish-perl` (sha3sum conflict with coreutils-from-uutils) |
| **arch-specific** | 32-bit data-size mismatch or architecture-specific layout issue | `texlive-bin` (aleph fmt undump on armhf) |

### Language-specific

| Category | Pattern | Examples |
|---|---|---|
| **typescript-error** | tsc type error in dependency declaration file | `node-y-codemirror` |
| **module-not-found** | Python/Ruby module import fails due to removed/renamed module | `python-urwid-utils` |
| **golang-linker-panic** | Go linker panics during dead-code or relocation pass | `golang-github-puzpuzpuz-xsync` |

## Interpreting the output

A single bug report can match **multiple** categories. For example:

- `golang-1.23` → **test-failure** (dh_auto_test fails) + **c23-keyword** (nullptr the root cause)
- `erlang-ranch` → **api-removed** (ssl functions gone) + **gcc-warnings-as-errors** (erlc -Werror)
- `isc-dhcp` → **empty-function-prototype** (the structural issue) + **gcc-warnings-as-errors** (-Wincompatible-pointer-types fatal)

This means you should read the categories as **facets** of the failure, not
as mutually exclusive bins.

## Top patterns (by frequency in resolute test-rebuild 2026-03-20)

From 56 bug reports:

| Rank | Category | Count | % of total |
|---|---|---|---|
| 1 | test-failure | 12 | 21.4% |
| 2 | missing-dependency | 10 | 17.9% |
| 3 | cmake-minimum-required | 8 | 14.3% |
| 4 | gcc-warnings-as-errors | 6 | 10.7% |
| 5 | empty-function-prototype | 4 | 7.1% |
| 6 | header-type-conflict | 4 | 7.1% |

The top three patterns alone account for over 53% of all failures.
