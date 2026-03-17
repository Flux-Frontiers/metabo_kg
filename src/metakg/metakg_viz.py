#!/usr/bin/env python3
"""
metakg_viz.py — CLI launcher for the MetaKG Streamlit visualizer.

Usage:
    metakg-viz [--db PATH] [--lancedb PATH] [--port PORT] [--no-browser]

Launches ``streamlit run`` against the bundled app.py in the package directory.
Works both from the source tree and when installed from a wheel.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """
    Parse arguments and launch the MetaKG Streamlit visualizer as a subprocess.

    Locates the bundled ``app.py`` in the package directory, builds the
    ``streamlit run`` command with the requested database path and port, then
    hands off execution to the subprocess.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Launch the MetaKG Streamlit visualizer.")
    parser.add_argument(
        "--db",
        default=".metakg/meta.sqlite",
        help="Path to the SQLite database (default: .metakg/meta.sqlite)",
    )
    parser.add_argument(
        "--lancedb",
        default=".metakg/lancedb",
        help="Path to the LanceDB directory (default: .metakg/lancedb)",
    )
    parser.add_argument(
        "--port",
        default="8500",
        help="Streamlit server port (default: 8500)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window automatically",
    )
    args = parser.parse_args()

    # app.py is bundled alongside this module in the package directory
    app_path = Path(__file__).parent / "app.py"

    if not app_path.exists():
        print(
            f"ERROR: Could not find app.py at {app_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(args.port),
        "--",
        "--db",
        args.db,
        "--lancedb",
        args.lancedb,
    ]
    if args.no_browser:
        cmd[5:5] = ["--server.headless", "true"]

    print(f"Launching MetaKG Explorer on http://localhost:{args.port}")
    print(f"  app    : {app_path}")
    print(f"  db     : {args.db}")
    print(f"  lancedb: {args.lancedb}")
    print("  Press Ctrl+C to stop.\n")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
