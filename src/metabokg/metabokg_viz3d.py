#!/usr/bin/env python3
"""
metabokg_viz3d.py — CLI launcher for the MetaboKG 3-D PyVista visualiser.

Usage::

    metabokg-viz3d [--db PATH] [--layout allium|cake]
                 [--width WIDTH] [--height HEIGHT]
                 [--export-html PATH]

Examples::

    # Open interactive window with Allium layout (default)
    metabokg-viz3d --db data/hsa_pathways/.metabokg/hsa.sqlite

    # Layer-cake layout showing metabolic relationships
    metabokg-viz3d --layout cake

    # Export to HTML without opening a window
    metabokg-viz3d --export-html metabolic_graph.html

Author: Eric G. Suchanek, PhD
2026-02-28 20:45:30
"""

from __future__ import annotations

from pathlib import Path


def main(
    db: str | None = None,
    lancedb: str | None = None,
    layout: str = "allium",
    width: int = 1400,
    height: int = 900,
    export_html: str | None = None,
    export_png: str | None = None,
) -> None:
    """Launch the 3-D knowledge-graph visualiser."""
    from metabokg.cli.options import resolve_db, resolve_lancedb

    db_str = resolve_db(db)
    lancedb_str = resolve_lancedb(lancedb)

    db_path = Path(db_str)
    if not db_path.exists():
        raise SystemExit(
            f"Database not found: {db_path}\n"
            "Run 'metabokg-build' first to build your metabolic knowledge graph."
        )

    from metabokg.viz3d import launch

    launch(
        db_path=str(db_path),
        lancedb_dir=lancedb_str,
        layout_name=layout,
        width=width,
        height=height,
        export_html=export_html,
        export_png=export_png,
    )


if __name__ == "__main__":
    main()
