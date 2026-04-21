#!/usr/bin/env python3
"""
app.py — MetaboKG Streamlit Metabolic Knowledge Graph Explorer

Interactive metabolic pathway explorer with:
  • Sidebar: configure database paths and query parameters
  • Graph tab: pyvis interactive graph of pathways, reactions, compounds, enzymes
  • Query tab: semantic and structural search with ranked results
  • Details tab: comprehensive node information

Run with:
    poetry run metabokg-viz

Author: Eric G. Suchanek, PhD
Last Revision: 2026-02-28 21:25:00

"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from pyvis.network import Network

from metabokg.simulate import FBAResult, MetabolicSimulator, ODEResult, SimulationConfig
from metabokg.store import GraphStore

# ---------------------------------------------------------------------------
# Constants — colours, shapes, and display strings
# ---------------------------------------------------------------------------

_KIND_COLOR: dict[str, str] = {
    "pathway": "#3498DB",  # blue
    "reaction": "#E74C3C",  # red
    "compound": "#27AE60",  # green
    "enzyme": "#F39C12",  # orange
}

# String truncation limits for different contexts
_DESCRIPTION_BRIEF_LEN = 80  # Node list view (expander)
_DESCRIPTION_HOVER_LEN = 150  # Hover title
_DESCRIPTION_CARD_LEN = 200  # Search result card
_LABEL_TRUNCATE_LEN = 30  # Bar chart labels
_LABEL_TRUNCATE_SUFFIX = "…"
_BARE_KEGG_ID = re.compile(r"^[RCG]\d{5}$")  # e.g. R00710, C00031, G00001

_KIND_SHAPE: dict[str, str] = {
    "pathway": "box",
    "reaction": "diamond",
    "compound": "dot",
    "enzyme": "triangle",
}

_REL_COLOR: dict[str, str] = {
    "CONTAINS": "#BDC3C7",  # grey
    "SUBSTRATE_OF": "#3498DB",  # blue
    "PRODUCT_OF": "#27AE60",  # green
    "CATALYZES": "#F39C12",  # orange
    "INHIBITS": "#E74C3C",  # red
    "ACTIVATES": "#F1C40F",  # yellow
    "XREF": "#95A5A6",  # dark grey
}

_DEFAULT_DB = os.environ.get("METABOKG_DB", "data/hsa_pathways/.metabokg/hsa.sqlite")
_DEFAULT_LANCEDB = os.environ.get("METABOKG_LANCEDB", "data/hsa_pathways/.metabokg/lancedb")

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MetaboKG Explorer",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Minimal CSS tweaks
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------


def _init_state() -> None:
    """
    Initialize Streamlit session state with default values.
    """
    defaults = {
        "db_path": _DEFAULT_DB,
        "lancedb_dir": _DEFAULT_LANCEDB,
        "store": None,
        "store_loaded_path": None,
        "query_result": None,
        "graph_nodes": None,
        "graph_edges": None,
        "selected_node_id": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner="Opening SQLite store…")
def _resolve_db_path(db_path: str) -> Path:
    """
    Resolve a db path: if it's a directory, look for a .sqlite file inside
    .metabokg/ or directly in the directory. Returns the resolved Path
    (may not exist — caller checks).
    """
    p = Path(db_path)
    if p.is_dir():
        metabokg_dir = p / ".metabokg"
        candidates = [p / ".metabokg" / "hsa.sqlite"]
        if metabokg_dir.is_dir():
            candidates += sorted(metabokg_dir.glob("*.sqlite"))
        candidates += sorted(p.glob("*.sqlite"))
        for candidate in candidates:
            if Path(candidate).exists():
                return Path(candidate)
    return p


@st.cache_resource(show_spinner="Loading MetaKG (embedding model)…")
def _load_kg(db_path: str, lancedb_dir: str) -> Any:
    """Load and cache a MetaKG instance (holds the embedding model in memory)."""
    from metabokg import MetaKG

    return MetaKG(db_path=db_path, lancedb_dir=lancedb_dir)


@st.cache_resource(show_spinner="Loading full graph…")
def _load_full_graph(db_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Cache-load the full node/edge lists for the Graph Browser tab.

    Keyed by ``db_path`` so the ~17K-row scan runs once per session (or when the
    user points at a different database), not on every Streamlit rerun.
    """
    resolved = _resolve_db_path(db_path)
    if not resolved.exists() or not resolved.is_file():
        return [], []
    store = GraphStore(str(resolved))
    try:
        return store.query_nodes(), store.query_edges()
    finally:
        try:
            store.close()
        except Exception:
            pass


def _load_store(db_path: str) -> GraphStore | None:
    """
    Load and cache a GraphStore from the given SQLite database path.

    :param db_path: Filesystem path to the SQLite database file or a directory
        containing one.
    :return: A connected ``GraphStore`` instance, or ``None`` if not found.
    """
    p = _resolve_db_path(db_path)
    if not p.exists() or not p.is_file():
        return None
    try:
        return GraphStore(str(p))
    except Exception:
        return None


def _get_store() -> GraphStore | None:
    """Retrieve the current GraphStore, loading it if the database path has changed."""
    current_path = str(st.session_state.get("db_path", _DEFAULT_DB))
    loaded_path = st.session_state.get("store_loaded_path")

    if current_path != loaded_path:
        resolved = str(_resolve_db_path(current_path))
        store = _load_store(current_path)
        st.session_state["store"] = store
        st.session_state["store_loaded_path"] = current_path
        if store is not None and resolved != current_path:
            st.session_state["db_path"] = resolved

    return st.session_state.get("store")


# ---------------------------------------------------------------------------
# UI: Legend
# ---------------------------------------------------------------------------


def _render_legend() -> None:
    """Display a legend of node kinds and edge relations."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Node Kinds:**")
        for kind, color in _KIND_COLOR.items():
            st.markdown(
                f'<span style="color:{color}">●</span> {kind.capitalize()}',
                unsafe_allow_html=True,
            )

    with col2:
        st.markdown("**Edge Relations:**")
        for rel, color in _REL_COLOR.items():
            st.markdown(
                f'<span style="color:{color}">→</span> {rel}',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Node display helpers
# ---------------------------------------------------------------------------


def _get_node_label(node: dict[str, Any] | None) -> str:
    """
    Extract a readable label for a node, preferring name over ID.

    :param node: Node dict from the store (or None).
    :return: Display-friendly label string.
    """
    if node is None:
        return "unknown"
    name = node.get("name", "").strip()
    node_id = node.get("id", "unknown")
    # Use name if present and not a bare KEGG accession (e.g. "R00710" / "C00031").
    # Enriched nodes carry human-readable names for all kinds.
    if name and not _BARE_KEGG_ID.match(name):
        return name
    # Fallback: last segment of the node URI (e.g. "R00710" from "rxn:kegg:R00710")
    return node_id.split(":")[-1]


def _build_node_label_map(node_ids: list[str], store: GraphStore) -> dict[str, str]:
    """
    Build a mapping of node IDs to display labels using batch query.

    :param node_ids: List of node IDs to fetch.
    :param store: GraphStore instance.
    :return: Dict mapping node_id → display label.
    """
    nodes = store.nodes(node_ids)
    return {nid: _get_node_label(nodes.get(nid)) for nid in node_ids}


def _build_node_title(node: dict[str, Any]) -> str:
    """
    Build minimal plain-text hover tooltip (for pyvis compatibility).

    :param node: Node dict from the store.
    :return: Plain-text hover title with newlines.
    """
    node_id = node.get("id", "unknown")
    name = node.get("name", "")
    description = node.get("description", "")
    kind = node.get("kind", "")

    parts = []

    # Name (or ID if no name)
    if name:
        parts.append(name)
    else:
        parts.append(node_id)

    # Description (if available)
    if description:
        parts.append(description[:_DESCRIPTION_HOVER_LEN])

    # Kind-specific metadata (formula/charge for compounds, EC for enzymes)
    if kind == "compound":
        formula = node.get("formula", "")
        charge = node.get("charge", "")
        advanced = []
        if formula:
            advanced.append(f"Formula: {formula}")
        if charge is not None and charge != "":
            advanced.append(f"Charge: {charge}")
        if advanced:
            parts.append(" | ".join(advanced))
    elif kind == "enzyme":
        ec_number = node.get("ec_number", "")
        if ec_number:
            parts.append(f"EC: {ec_number}")

    # KEGG ID (if not already the label)
    if name and "kegg" in node_id:
        kegg_id = node_id.split(":")[-1]
        parts.append(f"(KEGG: {kegg_id})")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Pyvis graph rendering
# ---------------------------------------------------------------------------


def _build_pyvis(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    height: str = "750px",
    physics_on: bool = False,
) -> str:
    """
    Build an interactive pyvis graph from nodes and edges.

    :param nodes: List of node dicts.
    :param edges: List of edge dicts.
    :param height: Height of the graph widget.
    :param physics_on: Whether to enable physics simulation.
    :return: HTML string for embedding in Streamlit.
    """
    net = Network(directed=True, height=height)

    for node in nodes:
        node_id = node["id"]
        kind = node.get("kind", "")
        label = _get_node_label(node)
        title = _build_node_title(node)
        color = _KIND_COLOR.get(kind, "#95A5A6")
        shape = _KIND_SHAPE.get(kind, "dot")
        net.add_node(node_id, label=label, color=color, shape=shape, title=title)

    for edge in edges:
        src = edge["src"]
        dst = edge["dst"]
        rel = edge["rel"]
        color = _REL_COLOR.get(rel, "#95A5A6")
        net.add_edge(src, dst, label=rel, color=color)

    net.toggle_physics(physics_on)
    temp_file = f"temp_{id(net)}.html"
    net.write_html(temp_file)
    with open(temp_file, encoding="utf-8") as f:
        html_content = f.read()
    os.remove(temp_file)
    return html_content


# ---------------------------------------------------------------------------
# UI: Sidebar configuration
# ---------------------------------------------------------------------------


def _render_sidebar() -> dict[str, Any]:
    """
    Render sidebar controls and return a configuration dict.

    :return: Dict with keys: ``db_path``, ``lancedb_dir``, ``max_nodes``,
             ``physics_on``, ``node_kinds_filter``, ``edge_rels_filter``.
    """
    st.sidebar.markdown("## Configuration")

    db_path = st.sidebar.text_input(
        "SQLite Database Path",
        value=st.session_state.get("db_path", _DEFAULT_DB),
        help="Path to the MetaboKG SQLite database",
    )
    st.session_state["db_path"] = db_path

    lancedb_dir = st.sidebar.text_input(
        "LanceDB Directory",
        value=st.session_state.get("lancedb_dir", _DEFAULT_LANCEDB),
        help="Path to the LanceDB vector database directory",
    )
    st.session_state["lancedb_dir"] = lancedb_dir

    max_nodes = st.sidebar.number_input(
        "Max nodes to display",
        min_value=10,
        max_value=1000,
        value=200,
        step=10,
    )

    physics_on = st.sidebar.checkbox(
        "Enable physics simulation",
        value=False,
        help="Slow down the graph but may provide better layout",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Filters")

    node_kinds_filter = st.sidebar.multiselect(
        "Filter by node kind",
        options=list(_KIND_COLOR.keys()),
        default=list(_KIND_COLOR.keys()),
    )

    edge_rels_filter = st.sidebar.multiselect(
        "Filter by edge relation",
        options=list(_REL_COLOR.keys()),
        default=list(_REL_COLOR.keys()),
    )

    return {
        "db_path": db_path,
        "lancedb_dir": lancedb_dir,
        "max_nodes": max_nodes,
        "physics_on": physics_on,
        "node_kinds_filter": node_kinds_filter,
        "edge_rels_filter": edge_rels_filter,
    }


# ---------------------------------------------------------------------------
# Tab: Graph Browser
# ---------------------------------------------------------------------------


def _tab_graph(cfg: dict[str, Any]) -> None:
    """Render the Graph Browser tab."""
    st.subheader("🗺️ Graph Browser")

    store = _get_store()
    if store is None:
        st.error(
            f"❌ Database not found at `{cfg['db_path']}`\n\n"
            "Please run `metabokg-build` to create the database first."
        )
        return

    try:
        all_nodes, all_edges = _load_full_graph(str(Path(cfg["db_path"]).resolve()))
    except Exception as e:
        st.error(f"Error loading graph: {e}")
        return

    # Filter by kind and relation
    filtered_nodes = [n for n in all_nodes if n.get("kind") in cfg["node_kinds_filter"]]
    filtered_edges = [
        e
        for e in all_edges
        if e.get("rel") in cfg["edge_rels_filter"]
        and e.get("src") in {n["id"] for n in filtered_nodes}
        and e.get("dst") in {n["id"] for n in filtered_nodes}
    ]

    # Limit nodes
    if len(filtered_nodes) > cfg["max_nodes"]:
        filtered_nodes = filtered_nodes[: cfg["max_nodes"]]
        node_ids = {n["id"] for n in filtered_nodes}
        filtered_edges = [
            e for e in filtered_edges if e.get("src") in node_ids and e.get("dst") in node_ids
        ]

    st.caption(f"Showing {len(filtered_nodes)} nodes and {len(filtered_edges)} edges")

    _render_legend()
    html = _build_pyvis(filtered_nodes, filtered_edges, physics_on=cfg["physics_on"])
    st.iframe(html, height=750)

    # Node list
    with st.expander(f"📋 Nodes ({len(filtered_nodes)})", expanded=False):
        ndf = pd.DataFrame(
            [
                {
                    "ID": n["id"],
                    "Kind": n.get("kind", ""),
                    "Name": n.get("name", ""),
                    "Description": (n.get("description", "") or "")[:_DESCRIPTION_BRIEF_LEN],
                }
                for n in filtered_nodes
            ]
        )
        st.dataframe(ndf, width="stretch", hide_index=True)

    # Edges list
    with st.expander(f"🔗 Edges ({len(filtered_edges)})", expanded=False):
        edf = pd.DataFrame(
            [
                {"Source": e["src"], "Relation": e["rel"], "Target": e["dst"]}
                for e in sorted(filtered_edges, key=lambda x: (x["rel"], x["src"]))
            ]
        )
        st.dataframe(edf, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Tab: Semantic Search
# ---------------------------------------------------------------------------


def _expand_hits(
    seeds: dict[str, dict[str, Any]],
    store: GraphStore,
    hops: int,
) -> dict[str, dict[str, Any]]:
    """
    Expand a seed hit map through *hops* of graph neighbours.

    Uses ``store.neighbours`` to build the frontier and a single batched
    ``store.nodes`` call per hop to fetch node payloads (avoids N+1 fetches).

    :param seeds: Mapping of seed node ID → node dict (mutated is not, returned fresh).
    :param store: GraphStore instance.
    :param hops: Number of hops to expand (must be ≥ 1).
    :return: Dict of node ID → node dict containing seeds plus expanded neighbours.
    """
    seen: dict[str, dict[str, Any]] = dict(seeds)
    frontier: set[str] = set(seen.keys())

    for _ in range(hops):
        next_ids: set[str] = set()
        for nid in frontier:
            for neigh in store.neighbours(nid):
                if neigh not in seen:
                    next_ids.add(neigh)
        if not next_ids:
            break
        fetched = store.nodes(list(next_ids))
        for nid, node in fetched.items():
            if node is not None:
                seen[nid] = node
        frontier = set(fetched.keys()) & set(seen.keys())
    return seen


def _tab_search(cfg: dict[str, Any]) -> None:
    """Render the Semantic Search tab."""
    st.subheader("🔍 Semantic Search")

    store = _get_store()
    if store is None:
        st.error(f"❌ Database not found at `{cfg['db_path']}`")
        return

    col_q, col_k, col_h = st.columns([4, 1, 1])
    with col_q:
        query_text = st.text_area(
            "Enter a query",
            placeholder="e.g., 'glucose metabolism' or 'ATP synthase'",
            height=80,
            key="search_query",
        )
    with col_k:
        k = st.number_input(
            "Results (k)",
            min_value=1,
            max_value=50,
            value=10,
            key="search_k",
            help="Number of seed hits from semantic/text search.",
        )
    with col_h:
        hops = st.number_input(
            "Hops",
            min_value=0,
            max_value=3,
            value=0,
            key="search_hops",
            help="Graph hops to expand from seeds (0 = seeds only).",
        )

    if st.button("🔍 Search", type="primary", key="search_run"):
        if not query_text.strip():
            st.warning("Enter a query first.")
        else:
            debug: dict[str, Any] = {
                "cwd": str(Path.cwd()),
                "db_path_cfg": cfg["db_path"],
                "lancedb_dir_cfg": cfg.get("lancedb_dir"),
            }
            with st.spinner("Searching…"):
                try:
                    lancedb_dir = cfg.get("lancedb_dir", _DEFAULT_LANCEDB)
                    # Normalise to absolute paths so cache_resource key is stable
                    # across reruns where _get_store() may resolve the relative path
                    abs_db = str(Path(cfg["db_path"]).resolve())
                    abs_ld = str(Path(lancedb_dir).resolve())
                    debug["lancedb_exists"] = Path(abs_ld).exists()
                    use_vector = Path(abs_ld).exists()
                    raw_hits: list[dict[str, Any]] = []
                    if use_vector:
                        kg = _load_kg(abs_db, abs_ld)
                        if kg is None:
                            raise RuntimeError(
                                f"Could not load MetaKG (db={abs_db}, "
                                f"lancedb={abs_ld}). Check that the index exists."
                            )
                        debug["kg_db"] = str(kg.db_path)
                        debug["kg_lancedb"] = str(kg.lancedb_dir)
                        debug["kg_model"] = kg.model_name
                        debug["kg_table"] = kg.table_name
                        query_results = kg.query(query_text, k=int(k))
                        raw_hits = query_results.hits
                        debug["raw_hits"] = len(raw_hits)
                    else:
                        raw_hits = store.query_text(query_text, k=int(k))
                        debug["raw_hits"] = len(raw_hits)

                    seed_ids = {h["id"] for h in raw_hits}
                    hits_by_id: dict[str, dict[str, Any]] = {h["id"]: {**h} for h in raw_hits}
                    expanded = int(hops) > 0
                    if expanded:
                        hits_by_id = _expand_hits(hits_by_id, store, int(hops))

                    all_edges = store.edges_within(set(hits_by_id.keys()))

                    st.session_state["search_hits"] = list(hits_by_id.values())
                    st.session_state["search_seed_ids"] = seed_ids
                    st.session_state["search_edges"] = all_edges
                    st.session_state["search_mode"] = "vector" if use_vector else "text"
                    st.session_state["search_hops_used"] = int(hops)
                    st.session_state["search_debug"] = debug
                except Exception as exc:
                    debug["exception"] = f"{type(exc).__name__}: {exc}"
                    st.error(f"Query failed: {exc}")
                    st.session_state["search_hits"] = []
                    st.session_state["search_seed_ids"] = set()
                    st.session_state["search_edges"] = []
                    st.session_state["search_hops_used"] = 0
                    st.session_state["search_debug"] = debug

    hits: list[dict[str, Any]] | None = st.session_state.get("search_hits")
    debug_info = st.session_state.get("search_debug")
    if hits is None:
        st.info("Enter a query above and click **🔍 Search**.")
        return
    if not hits:
        st.warning("No results found.")
        if debug_info:
            with st.expander("🐞 Debug — what the search saw", expanded=True):
                st.json(debug_info)
        return

    all_edges = st.session_state.get("search_edges", [])
    mode = st.session_state.get("search_mode", "")
    hops_used = int(st.session_state.get("search_hops_used", 0))
    seed_ids = set(st.session_state.get("search_seed_ids", set()))
    kinds_filter: list[str] = cfg["node_kinds_filter"]
    rels_filter: list[str] = cfg["edge_rels_filter"]

    visible = [h for h in hits if h.get("kind") in kinds_filter]
    visible_ids = {h["id"] for h in visible}

    result_edges = [
        e
        for e in all_edges
        if e["src"] in visible_ids and e["dst"] in visible_ids and e.get("rel") in rels_filter
    ]

    seed_count = len(seed_ids) if seed_ids else len(hits)
    hop_note = f", +{len(hits) - seed_count} via {hops_used}-hop expansion" if hops_used else ""
    st.success(
        f"Found {seed_count} seed{'s' if seed_count != 1 else ''} ({mode} search){hop_note}"
        + (f" — {len(visible)} shown after filters" if len(visible) != len(hits) else "")
    )

    tab_graph, tab_list = st.tabs(["🗺️ Graph", "📋 Results"])

    with tab_graph:
        if result_edges:
            _render_legend()
            html = _build_pyvis(visible, result_edges, height="500px")
            st.iframe(html, height=500)
        else:
            st.info("No edges connect these result nodes — try a broader query or more results.")

    with tab_list:
        for i, result in enumerate(visible, 1):
            nid = result.get("id")
            kind = result.get("kind", "")
            name = result.get("name", "")
            description = result.get("description", "")
            score = result.get("score")
            score_str = f"  score={score:.3f}" if isinstance(score, float) else ""
            color = _KIND_COLOR.get(kind, "#95A5A6")
            st.markdown(
                f'<div class="node-card" style="border-left-color:{color}">'
                f'<b>{i}. {name}</b> <code style="color:{color}">{kind}</code>'
                f"<small>{score_str}</small><br>"
                f"<small>{nid}</small><br>"
                f"<small>{description[:_DESCRIPTION_CARD_LEN]}</small>"
                f"</div>",
                unsafe_allow_html=True,
            )

    _node_detail_section(visible, store, key_prefix="search")


def _render_node_detail(node: dict[str, Any], store: GraphStore | None = None) -> None:
    """Render a full detail card for a metabolic graph node."""
    kind = node.get("kind", "")
    color = _KIND_COLOR.get(kind, "#95A5A6")
    name = node.get("name", "") or node.get("id", "")
    node_id = node.get("id", "")
    description = (node.get("description") or "").strip()

    is_dark = st.get_option("theme.base") == "dark"
    card_bg = "rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.04)"
    text_col = "#e0e0e0" if is_dark else "#111"
    meta_col = "#aaa" if is_dark else "#555"
    id_col = "#777" if is_dark else "#888"

    st.markdown(
        f"""
        <div style="background:{card_bg};border-left:5px solid {color};
                    border-radius:8px;padding:14px 18px;margin-bottom:8px;">
          <span style="background:{color};color:#fff;border-radius:4px;
                       padding:2px 9px;font-size:12px;font-weight:bold;
                       font-family:monospace;">{kind}</span>
          &nbsp;
          <span style="font-size:17px;font-weight:bold;color:{text_col};">{name}</span>
          <br>
          <span style="color:{id_col};font-size:10px;font-family:monospace;">id: {node_id}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if description:
            st.markdown(f"**Description:** {description}")
        if kind == "compound":
            formula = node.get("formula", "")
            charge = node.get("charge", "")
            if formula:
                st.markdown(f"**Formula:** `{formula}`")
            if charge is not None and charge != "":
                st.markdown(f"**Charge:** {charge}")
        elif kind == "enzyme":
            ec = node.get("ec_number", "")
            if ec:
                st.markdown(f"**EC Number:** `{ec}`")

    with col2:
        xrefs = node.get("xrefs")
        if xrefs:
            try:
                xrefs_dict = json.loads(xrefs) if isinstance(xrefs, str) else xrefs
                st.markdown("**Cross-references**")
                for db, ext_id in xrefs_dict.items():
                    st.markdown(
                        f'<span style="color:{meta_col};font-family:monospace;font-size:12px;">'
                        f"{db}: `{ext_id}`</span>",
                        unsafe_allow_html=True,
                    )
            except (json.JSONDecodeError, TypeError):
                pass

    if store and node_id:
        st.markdown("**🔗 Edges**")
        try:
            outgoing = store.query_edges(src=node_id)
            incoming = store.query_edges(dst=node_id)
            rows = [
                {"src": e["src"], "rel": e["rel"], "dst": e["dst"]}
                for e in (outgoing + incoming)[:60]
            ]
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.caption("*No edges.*")
        except Exception:
            pass


def _node_detail_section(
    nodes: list[dict[str, Any]],
    store: GraphStore | None,
    *,
    key_prefix: str = "detail",
) -> None:
    """Render a selectbox + detail card below a result list."""
    if not nodes:
        return

    st.markdown("---")
    st.subheader("🔎 Node Detail")

    label_map: dict[str, dict[str, Any]] = {}
    for n in nodes:
        lbl = n.get("name") or n["id"]
        if lbl in label_map:
            lbl = f"{lbl}  [{n['id']}]"
        label_map[lbl] = n

    options = ["— select a node —"] + sorted(label_map.keys())
    chosen = st.selectbox(
        "Select node to inspect",
        options=options,
        index=0,
        key=f"{key_prefix}_node_select",
        help="Pick any result node to see its full detail and edges.",
    )

    if chosen and chosen != "— select a node —":
        node = label_map.get(chosen)
        if node:
            _render_node_detail(node, store=store)


# ---------------------------------------------------------------------------
# Tab: Node Details
# ---------------------------------------------------------------------------


def _tab_details(cfg: dict[str, Any]) -> None:
    """Render the Node Details tab."""
    st.subheader("📋 Node Details")

    store = _get_store()
    if store is None:
        st.error(f"❌ Database not found at `{cfg['db_path']}`")
        return

    node_id = st.text_input("Enter node ID", placeholder="e.g., cpd:kegg:C00022")

    if node_id:
        try:
            node = store.get_node(node_id)
            if node is None:
                st.warning(f"Node `{node_id}` not found")
                return

            kind = node.get("kind", "")
            color = _KIND_COLOR.get(kind, "#95A5A6")

            st.markdown(
                f'<div style="border-left:4px solid {color};padding-left:10px;">'
                f'<code style="color:{color};font-size:1.2em">{kind}</code> '
                f'<b style="font-size:1.2em">{node.get("name", node_id)}</b><br>'
                f"<small><code>{node_id}</code></small>"
                f"</div>",
                unsafe_allow_html=True,
            )

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Basic Info**")
                st.write(f"**Name:** {node.get('name', 'N/A')}")
                st.write(f"**Kind:** {kind}")
                st.write(f"**Description:** {node.get('description', 'N/A')}")

            with col2:
                st.markdown("**Additional Data**")
                if kind == "compound":
                    st.write(f"**Formula:** {node.get('formula', 'N/A')}")
                    st.write(f"**Charge:** {node.get('charge', 'N/A')}")
                elif kind == "enzyme":
                    st.write(f"**EC Number:** {node.get('ec_number', 'N/A')}")

            # Xrefs
            xrefs = node.get("xrefs")
            if xrefs:
                try:
                    xrefs_dict = json.loads(xrefs) if isinstance(xrefs, str) else xrefs
                    st.markdown("**Cross-references**")
                    for db, ext_id in xrefs_dict.items():
                        st.write(f"  {db}: `{ext_id}`")
                except (json.JSONDecodeError, TypeError):
                    pass

            # Edges
            st.markdown("---")
            try:
                incoming_edges = store.query_edges(dst=node_id)
                outgoing_edges = store.query_edges(src=node_id)

                if incoming_edges or outgoing_edges:
                    col1, col2 = st.columns(2)
                    with col1:
                        if outgoing_edges:
                            st.markdown(f"**Outgoing ({len(outgoing_edges)})**")
                            for e in outgoing_edges:
                                dst_node = store.get_node(e["dst"])
                                dst_name = dst_node.get("name", e["dst"]) if dst_node else e["dst"]
                                color = _REL_COLOR.get(e["rel"], "#95A5A6")
                                st.markdown(
                                    f'<span style="color:{color}">→</span> '
                                    f"<b>{e['rel']}</b> {dst_name}",
                                    unsafe_allow_html=True,
                                )

                    with col2:
                        if incoming_edges:
                            st.markdown(f"**Incoming ({len(incoming_edges)})**")
                            for e in incoming_edges:
                                src_node = store.get_node(e["src"])
                                src_name = src_node.get("name", e["src"]) if src_node else e["src"]
                                color = _REL_COLOR.get(e["rel"], "#95A5A6")
                                st.markdown(
                                    f'<span style="color:{color}">←</span> '
                                    f"{src_name} <b>{e['rel']}</b>",
                                    unsafe_allow_html=True,
                                )
            except Exception as e:
                st.warning(f"Could not load edges: {e}")

        except Exception as e:
            st.error(f"Error loading node: {e}")


# ---------------------------------------------------------------------------
# Tab: Simulation
# ---------------------------------------------------------------------------


def _tab_simulation(cfg: dict[str, Any]) -> None:
    """Render simulation controls and results plotting."""
    st.subheader("🧪 Simulation")

    store = _get_store()
    if store is None:
        st.error(f"❌ Database not found at `{cfg['db_path']}`")
        return

    try:
        pathways = [n for n in store.query_nodes() if n.get("kind") == "pathway"]
    except Exception as e:
        st.error(f"Could not load pathways: {e}")
        return

    if not pathways:
        st.warning("No pathways found in the current database.")
        return

    pathways = sorted(pathways, key=lambda x: x.get("name", x["id"]))
    pwy_labels = {f"{p.get('name', p['id'])} ({p['id']})": p["id"] for p in pathways}

    with st.sidebar:
        st.markdown("---")
        st.markdown("## Simulation")

        selected_label = st.selectbox("Pathway", options=list(pwy_labels.keys()))
        pathway_id = pwy_labels[selected_label]

        sim_type = st.selectbox("Simulation type", options=["ODE", "FBA"])

        t_end = st.number_input("Stop time", min_value=1.0, value=100.0, step=10.0)
        t_points = st.number_input("Points", min_value=10, max_value=2000, value=300, step=10)

        start = st.button("▶ Start", width="stretch")
        stop = st.button("⏹ Stop", width="stretch")
        reset = st.button("↺ Reset", width="stretch")

    if "sim_running" not in st.session_state:
        st.session_state["sim_running"] = False
    if "sim_result" not in st.session_state:
        st.session_state["sim_result"] = None
    if "sim_type" not in st.session_state:
        st.session_state["sim_type"] = sim_type

    if stop:
        st.session_state["sim_running"] = False
        st.info("Simulation stopped.")

    if reset:
        st.session_state["sim_running"] = False
        st.session_state["sim_result"] = None
        st.success("Simulation reset.")

    if start:
        st.session_state["sim_running"] = True
        st.session_state["sim_type"] = sim_type

        sim = MetabolicSimulator(store)
        config = SimulationConfig(
            pathway_id=pathway_id,
            t_end=float(t_end),
            t_points=int(t_points),
        )

        with st.spinner(f"Running {sim_type} simulation..."):
            if sim_type == "ODE":
                result: FBAResult | ODEResult = sim.run_ode(config)
            else:
                result = sim.run_fba(config)

        st.session_state["sim_result"] = result

    result_obj: FBAResult | ODEResult | None = st.session_state.get("sim_result")
    current_type = st.session_state.get("sim_type", sim_type)

    if result_obj is None:
        st.info("Select simulation parameters in the sidebar and click Start.")
        return

    if current_type == "ODE" and isinstance(result_obj, ODEResult):
        result = result_obj
        if result.status != "ok":
            st.error(f"ODE failed: {result.message}")
            return

        cpd_ids = sorted(result.concentrations.keys())
        selected_cpds = st.multiselect(
            "Variables (compounds)",
            options=cpd_ids,
            default=cpd_ids[: min(8, len(cpd_ids))],
            help="Choose compound concentration trajectories to plot.",
        )

        if not selected_cpds:
            st.warning("Select at least one variable to plot.")
            return

        # Cache compound names in session state (batch query)
        cpd_cache_key = f"_cpd_labels_{pathway_id}"
        if cpd_cache_key not in st.session_state:
            st.session_state[cpd_cache_key] = _build_node_label_map(cpd_ids, store)
        cpd_names = st.session_state[cpd_cache_key]

        fig, ax = plt.subplots(figsize=(10, 5))
        for cpd_id in selected_cpds:
            label = cpd_names[cpd_id]
            ax.plot(result.t, result.concentrations[cpd_id], label=label)

        ax.set_title("ODE Simulation Result")
        ax.set_xlabel("Time")
        ax.set_ylabel("Concentration [mM]")
        ax.grid(alpha=0.3)
        ax.legend(loc="best", fontsize=8)
        st.pyplot(fig, clear_figure=True)

        final_df = pd.DataFrame(
            {
                "Compound": [cpd_names[c] for c in selected_cpds],
                "Compound ID": selected_cpds,
                "Final concentration [mM]": [result.concentrations[c][-1] for c in selected_cpds],
            }
        ).sort_values("Final concentration [mM]", ascending=False)
        st.dataframe(final_df, width="stretch", hide_index=True)

    elif isinstance(result_obj, FBAResult):
        result = result_obj
        if result.status != "optimal":
            st.error(f"FBA failed: {result.message}")
            return

        fluxes = result.fluxes
        rxn_ids = sorted(fluxes.keys())
        selected_rxns = st.multiselect(
            "Variables (reactions)",
            options=rxn_ids,
            default=rxn_ids[: min(20, len(rxn_ids))],
            help="Choose reaction fluxes to display.",
        )

        if not selected_rxns:
            st.warning("Select at least one variable to plot.")
            return

        # Cache reaction names in session state (batch query)
        rxn_cache_key = f"_rxn_labels_{pathway_id}"
        if rxn_cache_key not in st.session_state:
            st.session_state[rxn_cache_key] = _build_node_label_map(rxn_ids, store)
        rxn_names = st.session_state[rxn_cache_key]

        plot_df = pd.DataFrame(
            {
                "Reaction": [rxn_names[r] for r in selected_rxns],
                "Reaction ID": selected_rxns,
                "Flux": [fluxes[r] for r in selected_rxns],
            }
        ).sort_values("Flux", ascending=False)

        fig, ax = plt.subplots(figsize=(10, 5))
        # Use short labels for the bar chart
        short_labels = [
            (
                name[:_LABEL_TRUNCATE_LEN] + _LABEL_TRUNCATE_SUFFIX
                if len(name) > _LABEL_TRUNCATE_LEN
                else name
            )
            for name in plot_df["Reaction"]
        ]
        ax.bar(short_labels, plot_df["Flux"])
        ax.set_title("FBA Simulation Result")
        ax.set_xlabel("Reaction")
        ax.set_ylabel("Flux")
        ax.tick_params(axis="x", rotation=75)
        ax.grid(alpha=0.3, axis="y")
        st.pyplot(fig, clear_figure=True)
        st.dataframe(plot_df, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Theme-aware CSS
# ---------------------------------------------------------------------------


def _inject_css() -> None:
    """Inject CSS that matches Streamlit's active theme (light or dark)."""
    is_dark = st.get_option("theme.base") == "dark"
    card_bg = "rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.04)"
    card_color = "#e0e0e0" if is_dark else "#111"
    small_color = "#aaa" if is_dark else "#555"
    edge_color = "#aaa" if is_dark else "#444"
    st.markdown(
        f"""
        <style>
        .stTabs [data-baseweb="tab-list"] {{ gap: 12px; }}
        .stTabs [data-baseweb="tab"] {{ font-size: 1rem; padding: 6px 18px; }}
        .node-card {{
            background: {card_bg};
            color: {card_color};
            border-left: 4px solid #3498DB;
            border-radius: 6px;
            padding: 10px 14px;
            margin-bottom: 8px;
            font-family: monospace;
            font-size: 0.85rem;
        }}
        .node-card small {{ color: {small_color}; }}
        .edge-row {{ font-family: monospace; font-size: 0.82rem; color: {edge_color}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Application entry point for the MetaKG Streamlit visualizer.

    Initialises session state, renders the sidebar, and dispatches to the
    three tab renderers: Graph Browser, Semantic Search, and Node Details.
    """
    _init_state()
    _inject_css()
    cfg = _render_sidebar()

    st.title("🧬 MetaboKG Explorer")
    st.caption(
        "Interactive metabolic knowledge-graph explorer. "
        "Built with [MetaboKG](https://github.com/flux-frontiers/metabo_kg) · "
        "Powered by Streamlit + pyvis."
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🗺️ Graph Browser",
            "🔍 Semantic Search",
            "📋 Node Details",
            "🧪 Simulation",
        ]
    )

    with tab1:
        _tab_graph(cfg)

    with tab2:
        _tab_search(cfg)

    with tab3:
        _tab_details(cfg)

    with tab4:
        _tab_simulation(cfg)


if __name__ == "__main__":
    main()
