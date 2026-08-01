"""Tests for scripts/generate_wiki.py — the GitHub Wiki page generator.

Every page generator has a graceful fallback: if its source document is
missing, it returns a two-line "see the repo" stub instead of raising. That is
good behaviour for a missing optional page and terrible behaviour for a
*mis-pointed* one, because the script then reports success and publishes a wiki
made of stubs.

That is exactly what had happened. The generator was carried over from the
retired `code_kg` repo and still looked for `README ## Installation`,
`README ## CLI Usage`, `docs/Architecture.md` and `docs/deployment.md` — none
of which exist here — so five of eight pages were content-free while the script
exited 0.

So the load-bearing assertion is not "does it run" but **"is any page a
stub?"**.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "generate_wiki.py"
_DOCS = pathlib.Path(__file__).resolve().parents[1] / "docs"
_README = pathlib.Path(__file__).resolve().parents[1] / "README.md"


def _load():
    spec = importlib.util.spec_from_file_location("generate_wiki", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gw = _load()

# Text that appears only in a generator's missing-source fallback.
_STUB_MARKERS = ("in the repository for", "for installation instructions", "for CLI documentation")

# Every real page and the generator that builds it.
CONTENT_PAGES = {
    "Installation": lambda: gw.generate_installation_page(_DOCS),
    "CLI-Reference": lambda: gw.generate_cli_reference_page(_DOCS),
    "Architecture": lambda: gw.generate_architecture_page(_DOCS),
    "MCP-Integration": lambda: gw.generate_mcp_integration_page(_DOCS),
    "Python-API": lambda: gw.generate_python_api_page(_DOCS),
}


def _headings(body: str) -> list[str]:
    """Markdown headings only — anything inside a fenced block is code."""
    out, fence = [], False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence and line.startswith("#"):
            out.append(line)
    return out


class TestNoPageIsAStub:
    """The regression: five pages rendered as ~90-char placeholders."""

    @pytest.mark.parametrize("name", sorted(CONTENT_PAGES))
    def test_page_has_real_content(self, name):
        body = CONTENT_PAGES[name]()
        assert len(body) > 2000, f"{name} is {len(body)} chars — almost certainly a stub"

    @pytest.mark.parametrize("name", sorted(CONTENT_PAGES))
    def test_page_is_not_the_missing_source_fallback(self, name):
        body = CONTENT_PAGES[name]()
        for marker in _STUB_MARKERS:
            assert marker not in body, f"{name} fell back to its missing-source stub"

    @pytest.mark.parametrize("name", sorted(CONTENT_PAGES))
    def test_page_has_sections(self, name):
        """Any subsection depth counts: Python-API's title is de-duplicated, so
        its own sections sit at H3."""
        body = CONTENT_PAGES[name]()
        subs = [h for h in _headings(body) if h.startswith(("## ", "### "))]
        assert subs, f"{name} has no sections"


class TestPageStructure:
    @pytest.mark.parametrize("name", sorted(CONTENT_PAGES))
    def test_exactly_one_top_level_heading(self, name):
        """Two H1s render as two page titles; zero leaves the page unlabelled."""
        h1 = [h for h in _headings(CONTENT_PAGES[name]()) if h.startswith("# ")]
        assert len(h1) == 1, f"{name}: {h1}"

    @pytest.mark.parametrize("name", sorted(CONTENT_PAGES))
    def test_no_image_references(self, name):
        """Wiki pages cannot resolve repo-local image paths.

        Vacuous today — none of the four content sources currently embed an
        image — but it is the invariant that must hold if one is ever added.
        The Home page below is where this is actually exercised.
        """
        body = CONTENT_PAGES[name]()
        assert "![" not in body
        assert "<img" not in body.lower()

    def test_home_page_strips_the_readme_images(self):
        """README carries images; the Home page must come back with none."""
        assert "![" in _README.read_text(), "fixture assumption: README embeds images"
        home = gw.generate_home_page(_README)
        assert "![" not in home
        assert "<img" not in home.lower()

    def test_composed_pages_drop_source_numbering(self):
        """ "## 13. Database Schema" reads as a gap on a four-section page."""
        body = gw.generate_architecture_page(_DOCS)
        numbered = [
            h for h in _headings(body) if h.startswith("## ") and h[3:5].strip(". ").isdigit()
        ]
        assert not numbered, numbered

    def test_single_section_page_does_not_repeat_its_title(self):
        body = gw.generate_python_api_page(_DOCS)
        assert body.startswith("# Python API Reference")
        assert "## Python API Reference" not in body


class TestSourcesExist:
    """The generators point at documents this repo actually ships."""

    @pytest.mark.parametrize("source", ["INSTALL.md", "CHEATSHEET.md", "CAPABILITIES.md", "MCP.md"])
    def test_source_document_present(self, source):
        assert (_DOCS / source).is_file(), f"docs/{source} is a wiki source and must exist"


class TestNavigationIsConsistent:
    """Sidebar and home nav must name pages the generator actually writes."""

    def _linked(self, body: str) -> set[str]:
        import re

        return set(re.findall(r"\]\((?!http)([A-Za-z-]+)\)", body))

    def test_sidebar_links_only_to_generated_pages(self):
        generated = set(CONTENT_PAGES) | {"Home"}
        missing = self._linked(gw.generate_sidebar_page()) - generated
        assert not missing, f"sidebar links to non-existent pages: {sorted(missing)}"

    def test_home_nav_links_only_to_generated_pages(self):
        """Scoped to the generated nav header — everything after the first rule
        is README passthrough, whose repo-relative links are not wiki pages."""
        generated = set(CONTENT_PAGES) | {"Home"}
        nav = gw.generate_home_page(_README).split("\n---\n", 1)[0]
        missing = self._linked(nav) - generated
        assert not missing, f"home nav links to non-existent pages: {sorted(missing)}"

    def test_deployment_page_is_gone(self):
        """MetaboKG is local-first; there is no deployment story to publish."""
        assert not hasattr(gw, "generate_deployment_page")


class TestExtractSection:
    def test_matches_a_numbered_heading(self):
        content = "## 1. Architecture Overview\nbody\n\n## 2. Next\nother\n"
        assert "body" in gw.extract_section(content, "Architecture Overview")

    def test_stops_at_the_next_h2(self):
        content = "## One\nfirst\n\n## Two\nsecond\n"
        section = gw.extract_section(content, "One")
        assert "first" in section
        assert "second" not in section

    def test_returns_none_when_absent(self):
        assert gw.extract_section("## Something\n", "Nothing") is None


class TestPromoteTitle:
    def test_replaces_the_existing_h1(self):
        assert gw._promote_title("# Old\n\nbody\n", "New").startswith("# New")

    def test_leaves_the_body_intact(self):
        assert "body" in gw._promote_title("# Old\n\nbody\n", "New")

    def test_prepends_when_there_is_no_h1(self):
        out = gw._promote_title("just text\n", "Title")
        assert out.startswith("# Title")
        assert "just text" in out

    def test_does_not_touch_later_headings(self):
        out = gw._promote_title("# Old\n\n# Second\n", "New")
        assert out.count("# Second") == 1


class TestComposeFallback:
    def test_returns_none_for_a_missing_source(self, tmp_path):
        assert gw._compose(tmp_path, "absent.md", "T", ("Anything",)) is None

    def test_returns_none_when_no_heading_matches(self, tmp_path):
        (tmp_path / "doc.md").write_text("## Unrelated\ntext\n")
        assert gw._compose(tmp_path, "doc.md", "T", ("Missing",)) is None

    def test_skips_absent_headings_without_failing(self, tmp_path):
        (tmp_path / "doc.md").write_text("## Present\nkept\n")
        page = gw._compose(tmp_path, "doc.md", "T", ("Present", "Absent"))
        assert "kept" in page


class TestStripImageRefs:
    """Directly exercised, because the page-level guards are vacuous today."""

    def test_removes_markdown_images(self):
        assert gw.strip_image_refs("before ![alt](x.png) after") == "before  after"

    def test_removes_html_img_tags(self):
        assert "<img" not in gw.strip_image_refs('a <img src="x.png"/> b').lower()

    def test_removes_emptied_center_wrappers(self):
        out = gw.strip_image_refs('<p align="center"><img src="logo.png"/></p>')
        assert out.strip() == ""

    def test_leaves_ordinary_links_alone(self):
        text = "see [the docs](INSTALL.md)"
        assert gw.strip_image_refs(text) == text
