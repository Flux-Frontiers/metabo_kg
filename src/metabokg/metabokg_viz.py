#!/usr/bin/env python3
"""
metabokg_viz.py — CLI launcher for the MetaKG Streamlit visualizer.

Usage:
    metabokg-viz [--db PATH] [--lancedb PATH] [--port PORT] [--no-browser]

Launches ``streamlit run`` against the bundled app.py in the package directory.
Works both from the source tree and when installed from a wheel.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main(
    db: str | None = None,
    lancedb: str | None = None,
    port: str = "8500",
    no_browser: bool = False,
) -> None:
    """
    Launch the MetaKG Streamlit visualizer as a subprocess.

    Locates the bundled ``app.py`` in the package directory, builds the
    ``streamlit run`` command with the requested database path and port, then
    hands off execution to the subprocess.

    :param db: Path to the SQLite database (overrides env/default).
    :param lancedb: Path to the LanceDB directory (overrides env/default).
    :param port: Streamlit server port.
    :param no_browser: If True, suppress automatic browser launch.
    """
    import os

    db = db or os.environ.get("METABOKG_DB", ".metabokg/hsa.sqlite")
    lancedb = lancedb or os.environ.get("METABOKG_LANCEDB", ".metabokg/lancedb")

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
        str(port),
    ]
    if no_browser:
        cmd += ["--server.headless", "true"]

    env = os.environ.copy()
    env["METABOKG_DB"] = db
    env["METABOKG_LANCEDB"] = lancedb

    print(f"Launching MetaKG Explorer on http://localhost:{port}")
    print(f"  app    : {app_path}")
    print(f"  db     : {db}")
    print(f"  lancedb: {lancedb}")
    print("  Press Ctrl+C to stop.\n")

    try:
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
