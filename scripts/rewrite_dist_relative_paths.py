#!/usr/bin/env python3
"""Rewrite root-absolute internal URLs in dist HTML to depth-relative paths.

Production is served from two URL layouts with the same artifact:
- GitHub Pages: https://datum-cloud.github.io/awesome-alt-clouds/…
- Public proxy: https://www.alt-cloud.org/… (datumproxy strips the subpath)

Root-absolute paths like /_astro/app.css resolve from the domain root and break on
GitHub Pages. Depth-relative paths (../_astro/app.css) resolve correctly in both
layouts. Canonical/OG URLs use absolute https:// links and are not rewritten.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Root-absolute path immediately after an opening quote (not protocol-relative).
ROOT_ABS = re.compile(r'(?<=["\'])/(?!/)')


def depth_prefix(dist_root: Path, file_path: Path) -> str:
    rel = file_path.parent.relative_to(dist_root)
    depth = len(rel.parts)
    if depth == 0:
        return "./"
    return "../" * depth


def rewrite_file(path: Path, dist_root: Path) -> bool:
    prefix = depth_prefix(dist_root, path)
    original = path.read_text(encoding="utf-8")
    updated = ROOT_ABS.sub(prefix, original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    if not dist.is_dir():
        print(f"dist not found: {dist}", file=sys.stderr)
        return 1

    changed = 0
    for path in dist.rglob("*.html"):
        if rewrite_file(path, dist):
            changed += 1

    print(f"Rewrote root-absolute paths in {changed} HTML files under {dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
