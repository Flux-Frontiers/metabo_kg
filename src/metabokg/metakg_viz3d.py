#!/usr/bin/env python3
"""
metabokg_viz3d.py — CLI launcher for the MetaKG 3-D PyVista visualiser.

Usage::

    metabokg-viz3d [--db PATH] [--layout allium|cake]
                 [--width WIDTH] [--height HEIGHT]
                 [--export-html PATH]

Examples::

    # Open interactive window with Allium layout (default)
    metabokg-viz3d --db .metabokg/meta.sqlite

    # Layer-cake layout showing metabolic relationships
    metabokg-viz3d --layout cake

    # Export to HTML without opening a window
    metabokg-viz3d --export-html metabolic_graph.html

Author: Eric G. Suchanek, PhD
2026-02-28 20:45:30
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    """
    Parse CLI arguments and launch the 3-D knowledge-graph visualiser.

    Delegates to :func:`~metabokg.viz3d.launch` after resolving the layout
    strategy from the command-line arguments.
    """
    parser = argparse.ArgumentParser(
        prog="metabokg-viz3d",
        description="MetaKG 3D — interactive PyVista metabolic knowledge-graph explorer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db",
        default=".metabokg/meta.sqlite",
        metavar="PATH",
        help="Path to the SQLite database (default: .metabokg/meta.sqlite)",
    )
    parser.add_argument(
        "--lancedb",
        default=".metabokg/lancedb",
        metavar="PATH",
        help="Path to the LanceDB directory (default: .metabokg/lancedb)",
    )
    parser.add_argument(
        "--layout",
        choices=["allium", "cake"],
        default="allium",
        help=(
            "3-D layout strategy (default: allium). "
            "'allium' renders each pathway as a Giant Allium plant; "
            "'cake' stratifies nodes by kind across Z layers."
        ),
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1400,
        help="Window width in pixels (default: 1400)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=900,
        help="Window height in pixels (default: 900)",
    )
    parser.add_argument(
        "--export-html",
        metavar="PATH",
        help="Export to HTML file instead of opening interactive window",
    )
    parser.add_argument(
        "--export-png",
        metavar="PATH",
        help="Export to PNG file",
    )

    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        parser.error(
            f"Database not found: {db}\n"
            "Run 'metabokg-build' first to build your metabolic knowledge graph."
        )

    from metabokg.viz3d import launch

    launch(
        db_path=str(db),
        lancedb_dir=args.lancedb,
        layout_name=args.layout,
        width=args.width,
        height=args.height,
        export_html=args.export_html,
        export_png=args.export_png,
    )


if __name__ == "__main__":
    main()
