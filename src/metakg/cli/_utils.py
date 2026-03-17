"""
_utils.py — Shared helpers for MetaKG CLI commands.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click


def _timestamped_filename(basename: str = "metakg-analysis", ext: str = ".md") -> str:
    """Return a timestamped filename, e.g. ``metakg-analysis-2026-03-01-143022.md``."""
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return f"{basename}-{ts}{ext}"


def _parse_conc_args(conc_args: tuple[str, ...] | list[str]) -> dict[str, float]:
    """Parse ``ID:VALUE`` strings into a dict.  Last colon-separated token is the value."""
    result: dict[str, float] = {}
    for item in conc_args:
        parts = item.rsplit(":", 1)
        if len(parts) == 2:
            try:
                result[parts[0]] = float(parts[1])
            except ValueError:
                click.echo(f"WARNING: ignoring bad --conc value: {item!r}", err=True)
    return result


def _parse_factor_args(factor_args: tuple[str, ...] | list[str]) -> dict[str, float]:
    """Parse ``ENZ_ID:FACTOR`` strings.  Last colon-separated token is the factor."""
    return _parse_conc_args(factor_args)


def _write_output(text: str, output: str | None, basename: str) -> None:
    """Write *text* to *output* path (or a timestamped default) and report to stderr."""
    out_path = Path(output or _timestamped_filename(basename))
    out_path.write_text(text, encoding="utf-8")
    click.echo(f"Report written to {out_path}", err=True)
