#!/usr/bin/env python3
"""
viz3d.py — 3D visualization of metabolic knowledge graphs using PyVista + Qt.

Provides an interactive Qt MainWindow with:
- Left control panel (pathway filter, visibility toggles, stats, render button)
- Centre PyVista 3D viewer (BackgroundPlotter embedded in Qt)
- Staged rendering: checkboxes change internal state only; the "Render Graph"
  button applies all toggles in a single re-render pass to prevent stalling on
  large metabolic networks.

Supports two layout strategies:
- AlliumLayout: each pathway rendered as a Giant Allium plant.
- LayerCakeLayout: nodes stratified by kind across Z layers using a Fibonacci
  disk packing.

Author: Eric G. Suchanek, PhD
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np

# ---------------------------------------------------------------------------
# VizState — internal UI state (no immediate re-render on change)
# ---------------------------------------------------------------------------


@dataclass
class VizState:
    """
    Holds all UI toggle state for the 3D visualizer.

    Checkboxes write to this object; the renderer reads it only when the
    "Render Graph" button is pressed.

    :param show_edges: Whether to render edges between nodes.
    :param show_isolated: Whether to include nodes with no positioned edges.
    :param show_labels: Whether to add text labels to each node.
    :param selected_pathway: ID of the currently selected pathway filter,
        or ``"(All Pathways)"`` to show the full graph.
    :param selected_layout: Active layout strategy — ``"allium"`` or ``"cake"``.
    """

    show_edges: bool = True
    show_isolated: bool = True
    show_labels: bool = False
    selected_pathway: str = "(All Pathways)"
    selected_layout: str = "cake"

    # Populated once after data load; used by the stats panel.
    pathway_names: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Qt MainWindow
# ---------------------------------------------------------------------------


def _build_qt_window(
    state: VizState,
    layout_nodes: list[Any],
    layout_edges: list[Any],
    positions: dict[str, Any],
    layout_name: str,
    width: int,
    height: int,
) -> None:
    """
    Build and show the Qt MainWindow containing the PyVista BackgroundPlotter.

    :param state: Shared :class:`VizState` instance.
    :param layout_nodes: Pre-converted :class:`~metakg.layout3d.LayoutNode` list.
    :param layout_edges: Pre-converted :class:`~metakg.layout3d.LayoutEdge` list.
    :param positions: Position mapping from the chosen layout engine.  This dict
        is replaced in-place when the user switches layouts via the sidebar.
    :param layout_name: Display name of the active layout (``"allium"`` or ``"cake"``).
    :param width: Total window width in pixels.
    :param height: Total window height in pixels.
    """
    import sys

    import pyvista as pv
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDockWidget,
        QFrame,
        QLabel,
        QMainWindow,
        QPushButton,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )
    from pyvistaqt import BackgroundPlotter
    from vtkmodules.vtkInteractionStyle import vtkInteractorStyleImage

    from metakg.layout3d import AlliumLayout, LayerCakeLayout
    from metakg.primitives import (
        KIND_COMPOUND,
        KIND_ENZYME,
        KIND_PATHWAY,
        KIND_REACTION,
    )

    kind_to_color = {
        KIND_PATHWAY: "blue",
        KIND_REACTION: "red",
        KIND_COMPOUND: "green",
        KIND_ENZYME: "orange",
    }

    # Build a lookup from pathway ID to display name for the combo box.
    pathway_nodes = [n for n in layout_nodes if n.kind == KIND_PATHWAY]
    pathway_id_to_name: dict[str, str] = {n.id: n.name for n in pathway_nodes}

    # Build CONTAINS adjacency for pathway subgraph filtering.
    # pathway_id → set of all descendant node IDs (direct + transitive)
    children_map: dict[str, list[str]] = {}
    for e in layout_edges:
        if e.rel == "CONTAINS":
            children_map.setdefault(e.src, []).append(e.dst)

    # Filter pathways: only keep those with member nodes
    pathways_with_nodes: dict[str, str] = {}
    for pw_id, pw_name in pathway_id_to_name.items():
        # Get all member nodes of this pathway (BFS via CONTAINS)
        member_nodes = {pw_id}
        queue = list(children_map.get(pw_id, []))
        while queue:
            nid = queue.pop()
            if nid not in member_nodes:
                member_nodes.add(nid)
                queue.extend(children_map.get(nid, []))

        # Only include if pathway has member nodes (more than just itself)
        if len(member_nodes) > 1:
            pathways_with_nodes[pw_id] = pw_name

    pathway_id_to_name = pathways_with_nodes
    pathway_names_sorted = sorted(pathway_id_to_name.values())

    # Build reverse map: display name → node ID
    name_to_id: dict[str, str] = {v: k for k, v in pathway_id_to_name.items()}

    # Load KEGG reaction names for enzyme display.
    # These map bare KEGG accessions (e.g. "R00710") to human-readable enzyme
    # function names (e.g. "Acetaldehyde:NAD+ oxidoreductase").
    kegg_reaction_names: dict[str, str] = {}
    tsv_path = Path(__file__).parent.parent.parent / "data" / "kegg_reaction_names.tsv"
    if tsv_path.exists():
        try:
            import csv

            with tsv_path.open(encoding="utf-8") as fh:
                reader = csv.reader(fh, delimiter="\t")
                for row in reader:
                    if len(row) >= 2:
                        rxn_id = row[0].strip()
                        # Take first synonym only
                        fn_name = row[1].split(";")[0].strip()
                        if rxn_id and fn_name:
                            kegg_reaction_names[rxn_id] = fn_name
        except Exception:
            pass  # If loading fails, just skip—enzyme display will still work

    # Mutable positions holder so the layout combo can replace the dict
    # without breaking the _render closure.
    pos_holder: list[dict[str, Any]] = [positions]

    def _pathway_member_ids(pathway_id: str) -> set[str]:
        """BFS to collect all nodes reachable from a pathway via CONTAINS."""
        visited: set[str] = {pathway_id}
        queue = list(children_map.get(pathway_id, []))
        while queue:
            nid = queue.pop()
            if nid not in visited:
                visited.add(nid)
                queue.extend(children_map.get(nid, []))
        return visited

    def _on_pick(picked_mesh: Any) -> None:
        """
        Callback when a node mesh is picked. Find closest node and display properties.
        """
        if picked_mesh is None or not hasattr(plotter, "picked_point"):
            node_label.setText("Click on a node to select")
            return

        picked_point = plotter.picked_point
        if picked_point is None:
            return

        # Find closest node to the picked point
        closest_node = None
        min_distance = float("inf")

        for node_data in mesh_to_node.values():
            mesh = node_data["mesh"]
            mesh_center = mesh.center
            distance = (
                (mesh_center[0] - picked_point[0]) ** 2
                + (mesh_center[1] - picked_point[1]) ** 2
                + (mesh_center[2] - picked_point[2]) ** 2
            ) ** 0.5
            if distance < min_distance:
                min_distance = distance
                closest_node = node_data

        if closest_node:
            node_id = closest_node["id"]
            node_name = closest_node["name"]
            node_kind = closest_node["kind"]

            # Build context-dependent property text with descriptors
            props = [f"KEGG ID: {node_id}", f"Type: {node_kind.capitalize()}", ""]

            if node_kind == KIND_COMPOUND:
                props.append(f"Name: {node_name}")
                # Count connected reactions
                conn_rxns = [
                    e.dst for e in layout_edges if e.src == node_id and e.rel == "participates_in"
                ]
                if conn_rxns:
                    props.append("")
                    props.append(f"Participates in: {len(conn_rxns)} reactions")

            elif node_kind == KIND_REACTION:
                props.append(f"Name: {node_name}")
                # Count substrates & products
                substrates = [
                    e.src for e in layout_edges if e.dst == node_id and e.rel == "substrate"
                ]
                products = [e.dst for e in layout_edges if e.src == node_id and e.rel == "product"]
                if substrates or products:
                    props.append("")
                    props.append(f"Substrates: {len(substrates)}")
                    props.append(f"Products: {len(products)}")

            elif node_kind == KIND_ENZYME:
                # Extract first gene name as enzyme label
                gene_list = (
                    [n.strip() for n in node_name.split(",")] if "," in node_name else [node_name]
                )
                props.append(f"Gene symbol: {gene_list[0]}")
                if len(gene_list) > 1:
                    props.append(f"Other symbols: {', '.join(gene_list[:2])}")
                    if len(gene_list) > 2:
                        props.append(f"                +{len(gene_list) - 2} more")
                # Show catalyzed reactions with their KEGG function names
                props.append("")
                catalyzes = [
                    e.dst for e in layout_edges if e.src == node_id and e.rel == "catalyzes"
                ]
                if catalyzes:
                    props.append(f"Catalyzes ({len(catalyzes)} reactions):")
                    # Show first 2 reactions with their KEGG function names (if available)
                    for rxn_id in catalyzes[:2]:
                        # Extract bare KEGG accession (e.g., "R00710" from "rxn:kegg:R00710")
                        rxn_accession = rxn_id.split(":")[-1] if ":" in rxn_id else rxn_id
                        fn_name = kegg_reaction_names.get(rxn_accession, "")
                        if fn_name:
                            fn_display = fn_name[:50] + "..." if len(fn_name) > 50 else fn_name
                            props.append(f"  • {fn_display}")
                        else:
                            props.append(f"  • {rxn_accession}")
                    if len(catalyzes) > 2:
                        props.append(f"  ... +{len(catalyzes) - 2} more")

            elif node_kind == KIND_PATHWAY:
                props.append(f"Name: {node_name}")

            # Update label with name + properties
            # Handle comma-separated gene names (KEGG enzymes often have multiple)
            if "," in node_name:
                names = [n.strip() for n in node_name.split(",")]
                display_name = names[0]
                if len(names) > 1:
                    display_name += f" (+{len(names) - 1})"
            else:
                display_name = node_name[:40] + "..." if len(node_name) > 40 else node_name
            text = f"<b>{display_name}</b>\n" + "\n".join(props)
            node_label.setText(text)

    def _node_display_name(node: Any) -> str:
        """
        Return a human-readable label for *node*.

        Reactions and compounds often carry bare KEGG IDs as their ``name``
        (e.g. "R00710", "pj1662").  When the name looks like a raw identifier
        (all alphanumerics, 8 chars or fewer) and the node has a different
        ``id``, we fall back to the last segment of the node's ID so at least
        the accession is shown clearly.

        :param node: :class:`~metakg.layout3d.LayoutNode` instance.
        :return: Display label string (truncated to 28 characters).
        """
        name = node.name.strip()
        # If the name is non-trivial (contains spaces or is longer than a
        # typical accession), use it directly.
        if " " in name or len(name) > 12:
            return name[:28]
        # Fall back to ID's last segment if name == last ID segment (no enrichment)
        last_seg = node.id.split(":")[-1]
        if name == last_seg or name == node.id:
            return last_seg[:28]
        return name[:28]

    # Mapping from mesh to node data for picking
    mesh_to_node: dict[Any, dict[str, Any]] = {}

    def _render(plotter: BackgroundPlotter) -> None:
        """
        Re-render the graph from scratch using the current :class:`VizState`.

        This is the single render entry point; all UI controls converge here
        when the user presses "Render Graph".
        """
        cur_positions = pos_holder[0]
        mesh_to_node.clear()

        plotter.clear()
        plotter.remove_all_lights()
        plotter.enable_anti_aliasing("msaa")

        # Restore lighting after clear
        plotter.add_light(pv.Light(position=(0, 0, 100), color="white", light_type="scene light"))
        plotter.add_light(pv.Light(position=(0, 100, 0), color="white", light_type="scene light"))
        plotter.add_light(pv.Light(position=(0, 0, -100), color="white", light_type="scene light"))

        # Determine the active node/edge set based on pathway filter.
        selected = state.selected_pathway
        if selected == "(All Pathways)":
            active_node_ids: set[str] | None = None  # no filter
        else:
            pw_id = name_to_id.get(selected)
            if pw_id:
                # Get CONTAINS members first
                pathway_members = _pathway_member_ids(pw_id)
                # Also include compounds/enzymes connected to pathway nodes
                connected_ids = set(pathway_members)
                for e in layout_edges:
                    if e.src in pathway_members and e.rel != "CONTAINS":
                        connected_ids.add(e.dst)
                    if e.dst in pathway_members and e.rel != "CONTAINS":
                        connected_ids.add(e.src)
                active_node_ids = connected_ids
            else:
                active_node_ids = None

        # Filter to nodes that have a position.
        if active_node_ids is None:
            candidate_nodes = [n for n in layout_nodes if cur_positions.get(n.id) is not None]
        else:
            candidate_nodes = [
                n
                for n in layout_nodes
                if cur_positions.get(n.id) is not None and n.id in active_node_ids
            ]

        candidate_ids = {n.id for n in candidate_nodes}

        # Optionally filter isolated nodes (no edge connecting to another visible node).
        if not state.show_isolated:
            connected_node_ids: set[str] = set()
            for e in layout_edges:
                if e.src in candidate_ids and e.dst in candidate_ids:
                    connected_node_ids.add(e.src)
                    connected_node_ids.add(e.dst)
            candidate_nodes = [n for n in candidate_nodes if n.id in connected_node_ids]
            candidate_ids = {n.id for n in candidate_nodes}

        # Filter edges to those connecting visible nodes.
        candidate_edges = [
            e
            for e in layout_edges
            if (
                cur_positions.get(e.src) is not None
                and cur_positions.get(e.dst) is not None
                and e.src in candidate_ids
                and e.dst in candidate_ids
            )
        ]

        n_nodes = len(candidate_nodes)
        n_edges = len(candidate_edges)

        # Adaptive geometry: cubes for large graphs (faster rendering).
        use_cubes = n_nodes > 500
        node_size = 0.3 if use_cubes else 0.5

        # Build MultiBlock groups per kind for a single draw call per color.
        node_blocks: dict[str, Any] = {
            kind: pv.MultiBlock()
            for kind in [KIND_PATHWAY, KIND_REACTION, KIND_COMPOUND, KIND_ENZYME]
        }

        # Geometry hierarchy by kind
        def _get_node_mesh(node: Any, pos: Any, size: float) -> Any:
            """Create mesh based on node kind (geometric hierarchy)."""
            if node.kind == KIND_COMPOUND:
                return pv.Cube(center=pos, x_length=size, y_length=size, z_length=size)
            elif node.kind == KIND_REACTION:
                return pv.Dodecahedron(radius=size, center=pos)
            elif node.kind == KIND_ENZYME:
                return pv.Icosahedron(radius=size, center=pos)
            else:  # pathways, etc
                return pv.Cube(center=pos, x_length=size, y_length=size, z_length=size)

        for node in candidate_nodes:
            pos = cur_positions[node.id]
            mesh = _get_node_mesh(node, pos, node_size)
            if node.kind in node_blocks:
                mesh_to_node[id(mesh)] = {
                    "id": node.id,
                    "name": node.name,
                    "description": getattr(node, "description", None),
                    "kind": node.kind,
                    "mesh": mesh,
                }
                node_blocks[node.kind].append(mesh)

        for kind, block in node_blocks.items():
            if block.n_blocks > 0:
                color = kind_to_color.get(kind, "gray")
                plotter.add_mesh(
                    block,
                    color=color,
                    opacity=1.0,
                    smooth_shading=False,
                    show_edges=False,
                    name=f"nodes_{kind}",
                )

        # Edges — only when toggled on and graph is not extremely dense.
        render_edges = state.show_edges and n_edges < 5000
        if render_edges:
            edge_block = pv.MultiBlock()
            edge_radius = 0.075  # Small radius for low-poly appearance (25% smaller)
            for edge in candidate_edges:
                p1 = cur_positions[edge.src]
                p2 = cur_positions[edge.dst]
                center = (p1 + p2) / 2
                direction = p2 - p1
                height = np.linalg.norm(direction)
                if height > 0:
                    direction = direction / height  # normalize
                    cyl = pv.Cylinder(
                        center=center,
                        direction=direction,
                        radius=edge_radius,
                        height=float(height),
                        resolution=4,
                    )
                    edge_block.append(cyl)
            if edge_block.n_blocks > 0:
                plotter.add_mesh(
                    edge_block,
                    color="gray",
                    opacity=0.4,
                    name="edges",
                )

        # Labels — batch render all at once (not individually)
        if state.show_labels:
            label_positions = []
            label_texts = []
            for node in candidate_nodes[:50]:  # Limit to first 50 to avoid clutter
                pos = cur_positions[node.id]
                label_positions.append(pos)
                label_texts.append(_node_display_name(node))
            if label_positions:
                plotter.add_point_labels(
                    label_positions,
                    label_texts,
                    font_size=12,
                    text_color="white",
                )

        plotter.reset_camera()
        plotter.view_isometric()

        # Update stats label.
        n_compounds = sum(1 for n in candidate_nodes if n.kind == KIND_COMPOUND)
        n_reactions = sum(1 for n in candidate_nodes if n.kind == KIND_REACTION)
        active_layout_label = state.selected_layout.capitalize()
        stats_text = (
            f"Layout: {active_layout_label}\n"
            f"Nodes: {n_nodes}  |  Edges: {n_edges}\n"
            f"Compounds: {n_compounds}  |  Reactions: {n_reactions}"
        )
        stats_label.setText(stats_text)

    # -----------------------------------------------------------------------
    # Build Qt UI
    # -----------------------------------------------------------------------
    app = QApplication.instance() or QApplication(sys.argv)

    # Handle Ctrl+C gracefully
    import signal

    def signal_handler(_sig, _frame):  # pylint: disable=unused-argument
        window.close()
        app.quit()

    signal.signal(signal.SIGINT, signal_handler)

    # Get version for window title
    try:
        import importlib.metadata

        version = importlib.metadata.version("metakg")
    except Exception:
        version = "dev"

    window = QMainWindow()
    window.setWindowTitle(f"MetaKG 3D Explorer v{version} — {layout_name.capitalize()} Layout")
    window.resize(width, height)

    # Centre widget: PyVista BackgroundPlotter embedded in Qt.
    pv.set_plot_theme("dark")
    plotter = cast(Any, BackgroundPlotter(show=False, window_size=(width - 280, height)))
    window.setCentralWidget(plotter.app_window)

    # Disable trackball—use image/pan interaction instead
    plotter.iren.interactor.SetInteractorStyle(vtkInteractorStyleImage())

    # Enable mesh picking with callback
    plotter.enable_mesh_picking(
        callback=_on_pick,
        show=False,
        show_actors=False,
        show_message=False,
        left_clicking=False,
        use_actor=True,
    )

    # -----------------------------------------------------------------------
    # Left control panel (QDockWidget)
    # -----------------------------------------------------------------------
    dock = QDockWidget("Controls", window)
    dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)  # type: ignore[attr-defined]
    dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)

    panel = QWidget()
    panel.setMinimumWidth(240)
    panel.setMaximumWidth(300)
    layout = QVBoxLayout(panel)
    layout.setAlignment(Qt.AlignTop)  # type: ignore[attr-defined]
    layout.setSpacing(10)
    layout.setContentsMargins(10, 12, 10, 12)

    # -- Layout selector ------------------------------------------------------
    layout_label = QLabel("Layout")
    layout_label.setStyleSheet("font-weight: bold;")
    layout.addWidget(layout_label)

    _LAYOUT_DISPLAY = {
        "allium": "Allium (Hub-Spoke)",
        "cake": "LayerCake (Rings)",
    }
    _DISPLAY_TO_KEY = {v: k for k, v in _LAYOUT_DISPLAY.items()}

    layout_combo = QComboBox()
    for display_name in _LAYOUT_DISPLAY.values():
        layout_combo.addItem(display_name)
    # Pre-select the layout passed in from CLI / caller.
    initial_display = _LAYOUT_DISPLAY.get(state.selected_layout, _LAYOUT_DISPLAY["allium"])
    layout_combo.setCurrentText(initial_display)
    layout_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _on_layout_changed(display_text: str) -> None:
        """Recompute layout positions and update state; render is deferred to button."""
        chosen = _DISPLAY_TO_KEY.get(display_text, "allium")
        state.selected_layout = chosen
        print(
            f"Recomputing {chosen.capitalize()} layout positions...",
            end="",
            flush=True,
        )
        new_layout = AlliumLayout() if chosen == "allium" else LayerCakeLayout()
        new_positions = new_layout.compute(layout_nodes, layout_edges)
        pos_holder[0] = new_positions
        print(" done")
        window.setWindowTitle(f"MetaKG 3D Explorer — {chosen.capitalize()} Layout")

    # Connect signal after setCurrentText so the initial selection does not
    # trigger a redundant recompute (positions were already computed by launch()).
    layout_combo.currentTextChanged.connect(_on_layout_changed)
    layout.addWidget(layout_combo)

    # -- Separator ------------------------------------------------------------
    sep_layout = QFrame()
    sep_layout.setFrameShape(QFrame.HLine)
    sep_layout.setFrameShadow(QFrame.Sunken)
    layout.addWidget(sep_layout)

    # -- Pathway filter -------------------------------------------------------
    pathway_label = QLabel("Pathway Filter")
    pathway_label.setStyleSheet("font-weight: bold;")
    layout.addWidget(pathway_label)

    pathway_combo = QComboBox()
    pathway_combo.addItem("(All Pathways)")
    for name in pathway_names_sorted:
        pathway_combo.addItem(name)
    pathway_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _on_pathway_changed(text: str) -> None:
        state.selected_pathway = text

    pathway_combo.currentTextChanged.connect(_on_pathway_changed)
    layout.addWidget(pathway_combo)

    # -- Separator ------------------------------------------------------------
    sep1 = QFrame()
    sep1.setFrameShape(QFrame.HLine)
    sep1.setFrameShadow(QFrame.Sunken)
    layout.addWidget(sep1)

    # -- Visibility checkboxes ------------------------------------------------
    toggles_label = QLabel("Visibility")
    toggles_label.setStyleSheet("font-weight: bold;")
    layout.addWidget(toggles_label)

    chk_edges = QCheckBox("Show Edges")
    chk_edges.setChecked(state.show_edges)

    def _on_edges(checked: bool) -> None:
        state.show_edges = checked

    chk_edges.stateChanged.connect(lambda s: _on_edges(bool(s)))
    layout.addWidget(chk_edges)

    chk_isolated = QCheckBox("Show Isolated Nodes")
    chk_isolated.setChecked(state.show_isolated)

    def _on_isolated(checked: bool) -> None:
        state.show_isolated = checked

    chk_isolated.stateChanged.connect(lambda s: _on_isolated(bool(s)))
    layout.addWidget(chk_isolated)

    chk_labels = QCheckBox("Show Labels")
    chk_labels.setChecked(state.show_labels)

    def _on_labels(checked: bool) -> None:
        state.show_labels = checked

    chk_labels.stateChanged.connect(lambda s: _on_labels(bool(s)))
    layout.addWidget(chk_labels)

    # -- Separator ------------------------------------------------------------
    sep2 = QFrame()
    sep2.setFrameShape(QFrame.HLine)
    sep2.setFrameShadow(QFrame.Sunken)
    layout.addWidget(sep2)

    # -- Render button --------------------------------------------------------
    render_btn = QPushButton("Render Graph")
    render_btn.setStyleSheet(
        "QPushButton { background-color: #2a6496; color: white; "
        "padding: 6px; border-radius: 4px; font-weight: bold; }"
        "QPushButton:hover { background-color: #3a7abc; }"
        "QPushButton:pressed { background-color: #1a4a76; }"
    )
    render_btn.clicked.connect(lambda: _render(plotter))
    layout.addWidget(render_btn)

    # -- Separator ------------------------------------------------------------
    sep3 = QFrame()
    sep3.setFrameShape(QFrame.HLine)
    sep3.setFrameShadow(QFrame.Sunken)
    layout.addWidget(sep3)

    # -- Selected node panel --------------------------------------------------
    node_title = QLabel("Selected Node")
    node_title.setStyleSheet("font-weight: bold;")
    layout.addWidget(node_title)

    node_label = QLabel("Click on a node to select")
    node_label.setWordWrap(True)
    node_label.setStyleSheet("color: #cccccc; font-size: 11px;")
    layout.addWidget(node_label)

    # -- Stats panel ----------------------------------------------------------
    stats_title = QLabel("Statistics")
    stats_title.setStyleSheet("font-weight: bold;")
    layout.addWidget(stats_title)

    stats_label = QLabel("Select pathway & click 'Render Graph'")
    stats_label.setWordWrap(True)
    stats_label.setStyleSheet("color: #cccccc; font-size: 11px;")
    layout.addWidget(stats_label)

    # -- Legend panel ----------------------------------------------------------
    legend_title = QLabel("Legend")
    legend_title.setStyleSheet("font-weight: bold;")
    layout.addWidget(legend_title)

    legend_text = QLabel(
        "<b>Colors:</b><br/>"
        "🔵 Blue = Pathway<br/>"
        "🔴 Red = Reaction<br/>"
        "🟢 Green = Compound<br/>"
        "🟠 Orange = Enzyme<br/>"
        "<br/>"
        "<b>Shapes:</b><br/>"
        "▮ Cube = Compound<br/>"
        "◇ Dodeca = Reaction<br/>"
        "◆ Icosa = Enzyme"
    )
    legend_text.setWordWrap(True)
    legend_text.setStyleSheet("color: #aaaaaa; font-size: 10px; line-height: 1.4;")
    layout.addWidget(legend_text)

    # Stretch filler at bottom so controls stay top-aligned.
    layout.addStretch(1)

    panel.setLayout(layout)
    dock.setWidget(panel)
    window.addDockWidget(Qt.LeftDockWidgetArea, dock)  # type: ignore[attr-defined]

    # Don't render on startup for large graphs—let user filter first.
    # Window shows immediately; user clicks "Render Graph" to load.
    window.show()
    app.exec_()


# ---------------------------------------------------------------------------
# Public launch() — called by CLI and tests
# ---------------------------------------------------------------------------


def launch(
    db_path: str,
    lancedb_dir: str | None = None,
    layout_name: str = "cake",
    width: int = 1400,
    height: int = 900,
    export_html: str | None = None,
    export_png: str | None = None,
) -> None:
    """
    Launch the 3D metabolic knowledge graph visualizer.

    When neither ``export_html`` nor ``export_png`` is specified, opens a Qt
    MainWindow with an embedded PyVista :class:`~pyvistaqt.BackgroundPlotter`
    and a left control panel for staged rendering.

    Optimized for large graphs using:

    - MultiBlock batching for efficient rendering.
    - Adaptive geometry (cubes for 500+ nodes).
    - Efficient edge rendering (skipped for 5000+ edges).
    - Staged rendering (re-render only on "Render Graph" button press).

    :param db_path: Path to the MetaKG SQLite database.
    :param lancedb_dir: Path to the LanceDB directory (optional, unused in rendering).
    :param layout_name: Layout strategy: ``"allium"`` (default) or ``"cake"``.
    :param width: Window width in pixels (default: 1400).
    :param height: Window height in pixels (default: 900).
    :param export_html: If provided, export to HTML file instead of launching GUI.
    :param export_png: If provided, export to PNG file instead of launching GUI.
    """
    try:
        import pyvista as pv

        from metakg.store import GraphStore
    except ImportError:
        import sys

        print(
            "ERROR: PyVista and related dependencies not installed.\n"
            "Install visualization support with: poetry install --extras viz3d",
            file=sys.stderr,
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Database not found: {db}")

    store = GraphStore(str(db))

    try:
        print("Loading nodes...", end="", flush=True)
        nodes_data = store.query_nodes()
        print(f" {len(nodes_data)} loaded")

        print("Loading edges...", end="", flush=True)
        edges_data = store.query_edges()
        print(f" {len(edges_data)} loaded")

        if not nodes_data:
            print("WARNING: No nodes found in the database")
            store.close()
            return

        from metakg.layout3d import LayoutEdge, LayoutNode

        print("Converting to layout format...", end="", flush=True)
        layout_nodes = [LayoutNode.from_dict(n) for n in nodes_data]
        layout_edges = [LayoutEdge.from_dict(e) for e in edges_data]
        print(" done")

        # ------------------------------------------------------------------
        # Compute layout positions
        # ------------------------------------------------------------------
        from metakg.layout3d import AlliumLayout, LayerCakeLayout, Layout3D

        layout: Layout3D
        if layout_name == "cake":
            layout = LayerCakeLayout()
        else:
            layout = AlliumLayout()

        print(
            f"Computing {layout_name.capitalize()} layout positions...",
            end="",
            flush=True,
        )
        positions = layout.compute(layout_nodes, layout_edges)
        print(" done")

        # ------------------------------------------------------------------
        # Export path (no Qt window)
        # ------------------------------------------------------------------
        if export_html or export_png:
            _run_export(
                layout_nodes=layout_nodes,
                layout_edges=layout_edges,
                positions=positions,
                layout_name=layout_name,
                width=width,
                height=height,
                export_html=export_html,
                export_png=export_png,
                pv=pv,
            )
            return

        # ------------------------------------------------------------------
        # Interactive Qt window
        # ------------------------------------------------------------------
        try:
            from PyQt5.QtWidgets import QApplication  # noqa: F401
            from pyvistaqt import BackgroundPlotter  # noqa: F401
        except ImportError:
            import sys

            print(
                "ERROR: PyQt5 and pyvistaqt are required for the interactive viewer.\n"
                "Install with: poetry install --extras viz3d",
                file=sys.stderr,
            )
            sys.exit(1)

        state = VizState(selected_layout=layout_name)
        print("Launching Qt window...")
        _build_qt_window(
            state=state,
            layout_nodes=layout_nodes,
            layout_edges=layout_edges,
            positions=positions,
            layout_name=layout_name,
            width=width,
            height=height,
        )

    finally:
        store.close()


# ---------------------------------------------------------------------------
# Export helper (HTML / PNG without Qt)
# ---------------------------------------------------------------------------


def _run_export(
    layout_nodes: list[Any],
    layout_edges: list[Any],
    positions: dict[str, Any],
    layout_name: str,
    width: int,
    height: int,
    export_html: str | None,
    export_png: str | None,
    pv: Any,
) -> None:
    """
    Render the graph off-screen and write to an HTML or PNG file.

    :param layout_nodes: Positioned :class:`~metakg.layout3d.LayoutNode` list.
    :param layout_edges: :class:`~metakg.layout3d.LayoutEdge` list.
    :param positions: Position mapping ``{node_id: np.ndarray}``.
    :param layout_name: Display name of the layout strategy.
    :param width: Render width in pixels.
    :param height: Render height in pixels.
    :param export_html: Target HTML file path, or ``None``.
    :param export_png: Target PNG file path, or ``None``.
    :param pv: Already-imported ``pyvista`` module reference.
    """
    from metakg.primitives import (
        KIND_COMPOUND,
        KIND_ENZYME,
        KIND_PATHWAY,
        KIND_REACTION,
    )

    kind_to_color = {
        KIND_PATHWAY: "blue",
        KIND_REACTION: "red",
        KIND_COMPOUND: "green",
        KIND_ENZYME: "orange",
    }

    print("Creating visualization for export...")
    pl = cast(Any, pv.Plotter(window_size=[width, height], off_screen=True))
    pl.set_background("black")
    pl.remove_all_lights()
    pl.enable_anti_aliasing("msaa")
    pl.add_light(pv.Light(position=(0, 0, 100), color="white", light_type="scene light"))
    pl.add_light(pv.Light(position=(0, 100, 0), color="white", light_type="scene light"))
    pl.add_light(pv.Light(position=(0, 0, -100), color="white", light_type="scene light"))

    positioned_nodes = [n for n in layout_nodes if positions.get(n.id) is not None]
    positioned_edges = [
        e
        for e in layout_edges
        if positions.get(e.src) is not None and positions.get(e.dst) is not None
    ]

    n_nodes = len(positioned_nodes)
    n_edges = len(positioned_edges)
    use_cubes = n_nodes > 500
    node_size = 0.3 if use_cubes else 0.5

    node_blocks: dict[str, Any] = {
        kind: pv.MultiBlock() for kind in [KIND_PATHWAY, KIND_REACTION, KIND_COMPOUND, KIND_ENZYME]
    }

    # Geometry hierarchy by kind (same as interactive viewer)
    def _get_export_mesh(node: Any, pos: Any, size: float) -> Any:
        """Create mesh based on node kind."""
        if node.kind == KIND_COMPOUND:
            return pv.Cube(center=pos, x_length=size, y_length=size, z_length=size)
        elif node.kind == KIND_REACTION:
            return pv.Dodecahedron(radius=size, center=pos)
        elif node.kind == KIND_ENZYME:
            return pv.Icosahedron(radius=size, center=pos)
        else:
            return pv.Cube(center=pos, x_length=size, y_length=size, z_length=size)

    for node in positioned_nodes:
        pos = positions[node.id]
        mesh = _get_export_mesh(node, pos, node_size)
        if node.kind in node_blocks:
            node_blocks[node.kind].append(mesh)

    for kind, block in node_blocks.items():
        if block.n_blocks > 0:
            color = kind_to_color.get(kind, "gray")
            pl.add_mesh(
                block,
                color=color,
                opacity=1.0,
                smooth_shading=not use_cubes,
                show_edges=False,
                name=f"nodes_{kind}",
            )

    if n_edges < 5000:
        edge_block = pv.MultiBlock()
        for edge in positioned_edges:
            edge_block.append(pv.Line(positions[edge.src], positions[edge.dst]))
        if edge_block.n_blocks > 0:
            pl.add_mesh(edge_block, color="gray", opacity=0.4, line_width=1, name="edges")

    pl.reset_camera()
    pl.view_isometric()
    pl.add_title(f"MetaKG 3D Explorer — {layout_name.capitalize()} Layout")

    if export_html:
        print(f"Exporting to HTML: {export_html}...", end="", flush=True)
        pl.export_html(str(export_html))
        print(" done")
    elif export_png:
        print(f"Exporting to PNG: {export_png}...", end="", flush=True)
        pl.screenshot(str(export_png))
        print(" done")
