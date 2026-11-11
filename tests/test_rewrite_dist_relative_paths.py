"""Tests for scripts/rewrite_dist_relative_paths.py (postbuild path rewriting)."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rewrite_dist_relative_paths.py"
spec = importlib.util.spec_from_file_location("rewrite_dist_relative_paths", SCRIPT)
rewrite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rewrite)

PAGE = '<link rel="stylesheet" href="/_astro/app.css"><a href="/compare/">Compare</a>'


def write(path: Path, text: str = PAGE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestRewriteFile:
    def test_root_page_gets_dot_prefix(self, tmp_path):
        page = write(tmp_path / "index.html")
        assert rewrite.rewrite_file(page, tmp_path) is True
        assert 'href="./_astro/app.css"' in page.read_text(encoding="utf-8")

    def test_nested_page_gets_depth_prefix(self, tmp_path):
        page = write(tmp_path / "blog" / "post" / "index.html")
        rewrite.rewrite_file(page, tmp_path)
        assert 'href="../../_astro/app.css"' in page.read_text(encoding="utf-8")

    def test_root_404_keeps_root_absolute_paths(self, tmp_path):
        # A 404 is served at any URL depth, so a relative path would break it.
        page = write(tmp_path / "404.html")
        assert rewrite.rewrite_file(page, tmp_path) is False
        assert page.read_text(encoding="utf-8") == PAGE

    def test_nested_404_html_is_still_rewritten(self, tmp_path):
        # Only the root 404.html is special; a page that merely has that name is not.
        page = write(tmp_path / "docs" / "404.html")
        assert rewrite.rewrite_file(page, tmp_path) is True
        assert 'href="../_astro/app.css"' in page.read_text(encoding="utf-8")
