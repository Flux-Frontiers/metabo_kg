#!/usr/bin/env python3
"""
Generate GitHub Wiki pages for the metabo_kg repository.

This script creates wiki pages by processing markdown files from docs/,
article/, and README.md, structuring them appropriately for the GitHub wiki.
All content is sourced from living markdown files — no hardcoded content strings.

Usage:
    python scripts/generate_wiki.py
    python scripts/generate_wiki.py --dry-run
    python scripts/generate_wiki.py --repo Flux-Frontiers/metabo_kg

Author: Eric G. Suchanek, PhD
Last Revision: 2026-08-01
"""

import argparse
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def extract_section(
    content: str,
    heading: str,
    stop_at_next_h2: bool = True,
) -> str | None:
    """
    Extract a section from markdown content by its heading text.

    Matches headings with or without emoji prefixes (e.g. ``## Installation``
    and ``## 🚀 Installation`` both match ``heading="Installation"``).
    The search is case-insensitive.

    :param content: Full markdown document string.
    :param heading: Heading text to search for (without ``#`` markers).
    :param stop_at_next_h2: When ``True``, stop extraction at the next ``##``
        heading.  When ``False``, return from the match to the end of the
        document.
    :return: Extracted section text including the heading line, or ``None``
        if the heading is not found.
    """
    # Build a pattern that tolerates optional emoji / decoration before the
    # heading text and is case-insensitive.
    pattern = re.compile(
        r"^##\s+.*?" + re.escape(heading) + r".*?$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(content)
    if match is None:
        return None

    start = match.start()

    if stop_at_next_h2:
        # Find the next ## heading after the matched one.
        next_h2 = re.search(r"^\s*##\s+", content[match.end() :], re.MULTILINE)
        end = match.end() + next_h2.start() if next_h2 else len(content)
    else:
        end = len(content)

    return content[start:end]


# Repo documents that become wiki pages. A link to one of these should point at
# the wiki page, not back out to GitHub.
_DOC_TO_WIKI_PAGE = {
    "docs/INSTALL.md": "Installation",
    "docs/CHEATSHEET.md": "CLI-Reference",
    "docs/CAPABILITIES.md": "Architecture",
    "docs/MCP.md": "MCP-Integration",
    "README.md": "Home",
}

DEFAULT_REPO = "Flux-Frontiers/metabo_kg"


def rewrite_repo_links(
    content: str,
    *,
    base: str = "",
    repo: str = DEFAULT_REPO,
    branch: str = "main",
) -> str:
    """
    Make a source document's relative links work on the wiki.

    Wiki pages are flat and served from a different host, so a repo-relative
    link like ``docs/INSTALL.md`` resolves to nothing. Each such link is
    rewritten to the corresponding wiki page where one exists, and otherwise to
    an absolute ``blob`` URL on GitHub.

    Absolute URLs, ``mailto:``, and pure in-page anchors are left alone, as is
    anything inside a fenced code block — those are samples, not navigation.

    :param content: Markdown source.
    :param base: Directory of the source document relative to the repo root
        (``""`` for README.md, ``"docs"`` for files under docs/).
    :param repo: ``owner/name`` slug used to build absolute URLs.
    :param branch: Branch the absolute URLs should point at.
    :return: Content with its relative links rewritten.
    """
    link_re = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")

    def rewrite(match: re.Match) -> str:
        text, target = match.group(1), match.group(2)
        if target.startswith(("http://", "https://", "mailto:", "#")):
            return match.group(0)

        path, _, anchor = target.partition("#")
        if not path:
            return match.group(0)

        # normpath already drops a leading "./"; lstrip("./") would also eat the
        # leading dot of a dotfile path such as ".claude/skills/...".
        resolved = posixpath.normpath(posixpath.join(base, path))
        page = _DOC_TO_WIKI_PAGE.get(resolved)
        if page:
            # Anchors are dropped: the wiki page's headings are not guaranteed
            # to match the source document's once sections are composed.
            return f"[{text}]({page})"

        url = f"https://github.com/{repo}/blob/{branch}/{resolved}"
        return f"[{text}]({url}{'#' + anchor if anchor else ''})"

    out, fence = [], False
    for line in content.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fence = not fence
            out.append(line)
            continue
        out.append(line if fence else link_re.sub(rewrite, line))
    return "".join(out)


def strip_image_refs(content: str) -> str:
    """
    Remove image references from markdown content.

    Handles both Markdown syntax (``![alt](url)``) and HTML ``<img>`` tags so
    that wiki pages, which cannot resolve local repository image paths, render
    cleanly without broken image placeholders.

    :param content: Markdown string that may contain image references.
    :return: Content with all image references removed.
    """
    # Remove HTML <img ...> tags (single-line; wiki pages rarely have
    # multi-line img tags, and the centered <p><img/></p> wrappers should also
    # go away).
    content = re.sub(r"<img\s[^>]*/?>", "", content, flags=re.IGNORECASE)

    # Remove Markdown image syntax: ![alt text](url)
    content = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", content)

    # Clean up <p align="center"> wrappers that become empty after stripping
    # the img tag.  Match optional whitespace between tags.
    content = re.sub(
        r"<p[^>]*>\s*</p>",
        "",
        content,
        flags=re.IGNORECASE,
    )

    return content


# ---------------------------------------------------------------------------
# Page generators — each returns a complete wiki page string
# ---------------------------------------------------------------------------


def generate_home_page(readme_path: Path, logo_path: Path | None = None) -> str:
    """
    Generate Home.md from README.md with optional logo.

    Strips local image references and prepends a wiki navigation header with logo.

    :param readme_path: Path to README.md.
    :param logo_path: Optional path to logo image file.
    :return: Wiki-formatted home page content.
    """
    with open(readme_path, encoding="utf-8") as f:
        content = f.read()

    content = rewrite_repo_links(strip_image_refs(content), base="")

    logo_section = ""
    if logo_path and logo_path.exists():
        logo_section = f"![MetaboKG Logo]({logo_path.name})\n\n"

    wiki_header = f"""{logo_section}# MetaboKG Wiki

**Quick Navigation:**
- [Installation](Installation) — requirements, pip/Poetry, extras, first build
- [CLI Reference](CLI-Reference) — all subcommands and flags
- [Architecture](Architecture) — layers, data model, schema, dependencies
- [MCP Integration](MCP-Integration) — configure AI agents
- [Python API](Python-API) — programmatic usage

---

"""
    return wiki_header + content


def _promote_title(content: str, title: str) -> str:
    """
    Replace a document's leading ``#`` title with *title*.

    Wiki pages take their name from the filename, so the in-page H1 should say
    what the page is rather than repeat the source document's own title.

    :param content: Full markdown document.
    :param title: Replacement H1 text (without the ``#``).
    :return: Content with its first H1 replaced, or *title* prepended when the
        document has no H1.
    """
    if re.search(r"^#\s+.+$", content, re.MULTILINE):
        return re.sub(r"^#\s+.+$", f"# {title}", content, count=1, flags=re.MULTILINE)
    return f"# {title}\n\n{content}"


def _compose(docs_dir: Path, source: str, title: str, headings: tuple[str, ...]) -> str | None:
    """
    Build a page from named ``##`` sections of a source document.

    :param docs_dir: Path to the docs/ directory.
    :param source: Filename within *docs_dir* to read.
    :param title: H1 for the composed page.
    :param headings: Section headings to extract, in output order. Headings
        that are absent are skipped rather than failing the build.
    :return: Composed page, or ``None`` when the source is missing or none of
        the headings matched.
    """
    path = docs_dir / source
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        content = f.read()

    sections = [sec for h in headings if (sec := extract_section(content, h))]
    if not sections:
        return None

    # Source headings carry the numbering of their own document ("## 13. Database
    # Schema"), which reads as a gap once only a few sections are pulled out.
    sections = [re.sub(r"^##\s+\d+\.\s+", "## ", sec, count=1) for sec in sections]

    # A lone section whose heading restates the page title would render twice.
    if len(sections) == 1 and sections[0].startswith(f"## {title}"):
        body = sections[0].split("\n", 1)[1].lstrip("\n")
        return f"# {title}\n\n{body}"

    return f"# {title}\n\n" + "\n".join(sections)


def generate_installation_page(docs_dir: Path) -> str:
    """
    Return docs/INSTALL.md as the Installation wiki page.

    MetaboKG keeps its installation guide in ``docs/INSTALL.md`` rather than a
    README section, so the page is the whole document with its title promoted.

    :param docs_dir: Path to the docs/ directory.
    :return: Installation wiki page content.
    """
    install_path = docs_dir / "INSTALL.md"
    if not install_path.exists():
        return (
            "# Installation\n\n"
            "See [docs/INSTALL.md](https://github.com/Flux-Frontiers/metabo_kg/blob/main/docs/INSTALL.md) "
            "for installation instructions."
        )

    with open(install_path, encoding="utf-8") as f:
        content = f.read()

    page = strip_image_refs(_promote_title(content, "Installation Guide"))
    return rewrite_repo_links(page, base="docs")


def generate_cli_reference_page(docs_dir: Path) -> str:
    """
    Return docs/CHEATSHEET.md as the CLI Reference wiki page.

    The cheatsheet is the canonical per-command flag reference; the narrower
    ``## 11. CLI Reference`` section of CAPABILITIES.md is a summary of it.

    :param docs_dir: Path to the docs/ directory.
    :return: CLI Reference wiki page content.
    """
    cheatsheet_path = docs_dir / "CHEATSHEET.md"
    if not cheatsheet_path.exists():
        return (
            "# CLI Reference\n\n"
            "See [docs/CHEATSHEET.md](https://github.com/Flux-Frontiers/metabo_kg/blob/main/docs/CHEATSHEET.md) "
            "for CLI documentation."
        )

    with open(cheatsheet_path, encoding="utf-8") as f:
        content = f.read()

    page = strip_image_refs(_promote_title(content, "CLI Reference"))
    return rewrite_repo_links(page, base="docs")


def generate_architecture_page(docs_dir: Path) -> str:
    """
    Compose the Architecture wiki page from CAPABILITIES.md.

    MetaboKG has no standalone ``docs/Architecture.md``; the architectural
    material lives in numbered sections of the capabilities reference.

    :param docs_dir: Path to the docs/ directory.
    :return: Architecture wiki page content.
    """
    page = _compose(
        docs_dir,
        "CAPABILITIES.md",
        "Architecture",
        ("Architecture Overview", "Data Model", "Database Schema", "Dependencies & Extras"),
    )
    if page is None:
        return (
            "# Architecture\n\n"
            "See [docs/CAPABILITIES.md](https://github.com/Flux-Frontiers/metabo_kg/blob/main/docs/CAPABILITIES.md) "
            "for architecture details."
        )
    return rewrite_repo_links(strip_image_refs(page), base="docs")


def generate_mcp_integration_page(docs_dir: Path) -> str:
    """
    Return the full MCP.md document as the MCP Integration wiki page.

    :param docs_dir: Path to the docs/ directory.
    :return: MCP Integration wiki page content.
    """
    mcp_path = docs_dir / "MCP.md"
    if not mcp_path.exists():
        return (
            "# MCP Integration\n\nSee `docs/MCP.md` in the repository for MCP integration details."
        )

    with open(mcp_path, encoding="utf-8") as f:
        content = f.read()

    return rewrite_repo_links(content, base="docs")


def generate_python_api_page(docs_dir: Path) -> str:
    """
    Compose the Python API wiki page from CAPABILITIES.md.

    :param docs_dir: Path to the docs/ directory.
    :return: Python API wiki page content.
    """
    page = _compose(
        docs_dir,
        "CAPABILITIES.md",
        "Python API Reference",
        ("Python API Reference",),
    )
    if page is None:
        return (
            "# Python API Reference\n\n"
            "See [docs/CAPABILITIES.md](https://github.com/Flux-Frontiers/metabo_kg/blob/main/docs/CAPABILITIES.md) "
            "for the Python API reference."
        )
    return rewrite_repo_links(strip_image_refs(page), base="docs")


def generate_sidebar_page() -> str:
    """
    Generate the GitHub wiki sidebar with navigation.

    :return: Sidebar page content.
    """
    sidebar = """## Documentation

- [Home](Home)
- [Installation](Installation)
- [CLI Reference](CLI-Reference)
- [Architecture](Architecture)
- [MCP Integration](MCP-Integration)
- [Python API](Python-API)

## Resources

- [GitHub Repository](https://github.com/Flux-Frontiers/metabo_kg)
"""
    return sidebar


# ---------------------------------------------------------------------------
# Wiki I/O helpers
# ---------------------------------------------------------------------------


def clone_wiki(repo_url: str, temp_dir: str) -> None:
    """
    Clone the wiki repository into a temporary directory.

    Authenticates via the ``gh`` CLI when available, falling back to
    ``GITHUB_TOKEN`` / ``GITHUB_PERSONAL_ACCESS_TOKEN`` environment variables,
    and finally to an unauthenticated HTTPS clone.

    :param repo_url: GitHub repository slug (e.g. ``'Flux-Frontiers/metabo_kg'``).
    :param temp_dir: Destination directory for the wiki clone.
    """
    github_token: str | None = None

    # Prefer the gh CLI — it always has the right scopes.
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        github_token = result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get(
            "GITHUB_PERSONAL_ACCESS_TOKEN"
        )

    if github_token:
        wiki_url = f"https://x-access-token:{github_token}@github.com/{repo_url}.wiki.git"
    else:
        wiki_url = f"https://github.com/{repo_url}.wiki.git"

    print(f"Cloning wiki from https://github.com/{repo_url}.wiki.git...")
    subprocess.run(["git", "clone", wiki_url, temp_dir], check=True)


def write_wiki_pages(wiki_dir: Path, pages: dict[str, str], logo_path: Path | None = None) -> None:
    """
    Write generated wiki pages to the cloned wiki directory.

    :param wiki_dir: Path to the local wiki clone.
    :param pages: Mapping of ``{page_name: content}`` where ``page_name`` is
        the filename without the ``.md`` extension (e.g. ``"Home"``).
    :param logo_path: Optional path to a logo file to copy to the wiki directory.
    """
    for filename, content in pages.items():
        if not filename.endswith(".md"):
            filename += ".md"

        filepath = wiki_dir / filename
        print(f"Writing {filepath}...")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    if logo_path and logo_path.exists():
        dest_path = wiki_dir / logo_path.name
        print(f"Copying logo to {dest_path}...")
        shutil.copy2(logo_path, dest_path)


def commit_and_push(wiki_dir: Path) -> None:
    """
    Stage, commit, and push any changes in the wiki directory.

    Pushes to ``origin master`` (GitHub wiki default branch).
    If there are no staged changes the function prints a notice and returns
    without error.

    :param wiki_dir: Path to the local wiki clone (must be a git repository).
    """
    os.chdir(wiki_dir)

    subprocess.run(["git", "add", "."], check=True)

    result = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        print("Committing changes...")
        subprocess.run(
            ["git", "commit", "-m", "Auto-generated wiki update from docs/"],
            check=True,
        )
        print("Pushing to remote...")
        subprocess.run(["git", "push", "origin", "master"], check=True)
        print("Wiki updated successfully.")
    else:
        print("No changes to commit.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate GitHub wiki pages from docs/ and README.md"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without cloning or committing",
    )
    parser.add_argument(
        "--repo",
        default="Flux-Frontiers/metabo_kg",
        help="GitHub repository slug (default: Flux-Frontiers/metabo_kg)",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    readme_path = project_root / "README.md"
    docs_dir = project_root / "docs"
    assets_dir = project_root / "assets"
    logo_path = assets_dir / "logo-md-256x256.png"

    print("Generating wiki pages...")

    pages: dict[str, str] = {
        "Home": generate_home_page(readme_path, logo_path),
        "Installation": generate_installation_page(docs_dir),
        "CLI-Reference": generate_cli_reference_page(docs_dir),
        "Architecture": generate_architecture_page(docs_dir),
        "MCP-Integration": generate_mcp_integration_page(docs_dir),
        "Python-API": generate_python_api_page(docs_dir),
        "_Sidebar": generate_sidebar_page(),
    }

    if args.dry_run:
        print("\nDry run - would generate the following pages:")
        for name, content in pages.items():
            print(f"  - {name}.md  ({len(content)} chars)")
        print("\nPreview of Home.md (first 500 chars):")
        print(pages["Home"][:500] + "...\n")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        wiki_path = Path(temp_dir)

        try:
            clone_wiki(args.repo, str(wiki_path))
        except subprocess.CalledProcessError as e:
            print(f"Error cloning wiki: {e}")
            print(
                "\nNote: the wiki must be initialised first by creating at least one "
                "page manually through the GitHub UI."
            )
            return

        write_wiki_pages(wiki_path, pages, logo_path)

        try:
            commit_and_push(wiki_path)
        except subprocess.CalledProcessError as e:
            print(f"Error committing/pushing: {e}")
            return


if __name__ == "__main__":
    main()
