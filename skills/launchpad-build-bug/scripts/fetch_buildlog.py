#!/usr/bin/env python3
"""Download a Launchpad build log.

Accepts either:
  - A Launchpad +build page URL (e.g. https://launchpad.net/ubuntu/+source/foo/1.0/+build/12345)
    -- the page is fetched and the BUILDING.txt.gz link is scraped from it.
  - A direct buildlog URL (.txt or .txt.gz on launchpadlibrarian.net or launchpad.net).

Writes the decompressed log to /tmp/launchpad-build-bug/<basename>.txt and
prints that path on stdout. Stderr carries progress/diagnostics.
"""

from __future__ import annotations

import gzip
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

OUT_DIR = pathlib.Path("/tmp/launchpad-build-bug")
USER_AGENT = "launchpad-build-bug-skill/1.0 (+https://launchpad.net)"


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def is_buildlog_url(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith(".txt") or path.endswith(".txt.gz")


def find_buildlog_link(build_page_html: str, base_url: str) -> str:
    # Launchpad +build pages link to the build log with text like
    # "buildlog" and an href pointing at a *_BUILDING.txt.gz under
    # launchpadlibrarian.net or the same host. Match the href directly.
    candidates = re.findall(
        r'href="([^"]+_BUILDING\.txt(?:\.gz)?)"', build_page_html
    )
    if not candidates:
        raise SystemExit(
            f"Could not find a buildlog link on {base_url}. "
            "Pass the direct buildlog URL instead."
        )
    # Prefer .gz (smaller, what Launchpad always serves).
    candidates.sort(key=lambda u: (not u.endswith(".gz"), u))
    link = candidates[0]
    if link.startswith("//"):
        link = "https:" + link
    elif link.startswith("/"):
        parsed = urllib.parse.urlparse(base_url)
        link = f"{parsed.scheme}://{parsed.netloc}{link}"
    return link


def download_buildlog(url: str) -> pathlib.Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if is_buildlog_url(url):
        log_url = url
    else:
        log(f"Fetching +build page: {url}")
        page = http_get(url).decode("utf-8", errors="replace")
        log_url = find_buildlog_link(page, url)
        log(f"Found buildlog link: {log_url}")

    log(f"Downloading: {log_url}")
    data = http_get(log_url)

    basename = os.path.basename(urllib.parse.urlparse(log_url).path)
    if basename.endswith(".gz"):
        data = gzip.decompress(data)
        basename = basename[:-3]
    if not basename.endswith(".txt"):
        basename += ".txt"

    out_path = OUT_DIR / basename
    out_path.write_bytes(data)
    log(f"Wrote {len(data)} bytes to {out_path}")
    return out_path


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <launchpad-url>", file=sys.stderr)
        return 2
    try:
        path = download_buildlog(sys.argv[1])
    except urllib.error.URLError as e:
        log(f"network error: {e}")
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
