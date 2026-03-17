"""
store.py — MetaStore: SQLite persistence layer for the metabolic knowledge graph.

Schema:
  meta_nodes   — all entity nodes (compound, reaction, enzyme, pathway)
  meta_edges   — all directed edges
  xref_index   — flattened cross-reference lookup (db_name, ext_id → node_id)

Follows the same WAL/NORMAL pragma pattern as code_kg.store.GraphStore.
"""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from metakg.primitives import (
    DEFAULT_RELS,
    REL_PRODUCT_OF,
    REL_SUBSTRATE_OF,
    KineticParam,
    MetaEdge,
    MetaNode,
    RegulatoryInteraction,
)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS meta_nodes (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT,
    formula       TEXT,
    charge        INTEGER,
    ec_number     TEXT,
    stoichiometry TEXT,
    xrefs         TEXT,
    source_format TEXT,
    source_file   TEXT,
    category      TEXT
);

CREATE TABLE IF NOT EXISTS meta_edges (
    src      TEXT NOT NULL,
    rel      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    evidence TEXT,
    PRIMARY KEY (src, rel, dst)
);

CREATE TABLE IF NOT EXISTS xref_index (
    node_id  TEXT NOT NULL,
    db_name  TEXT NOT NULL,
    ext_id   TEXT NOT NULL,
    PRIMARY KEY (db_name, ext_id)
);

CREATE TABLE IF NOT EXISTS kinetic_parameters (
    id                   TEXT PRIMARY KEY,
    enzyme_id            TEXT,
    reaction_id          TEXT,
    substrate_id         TEXT,
    km                   REAL,
    kcat                 REAL,
    vmax                 REAL,
    ki                   REAL,
    hill_coefficient     REAL,
    delta_g_prime        REAL,
    equilibrium_constant REAL,
    ph                   REAL,
    temperature_celsius  REAL,
    ionic_strength       REAL,
    source_database      TEXT,
    literature_reference TEXT,
    organism             TEXT,
    tissue               TEXT,
    confidence_score     REAL,
    measurement_error    REAL
);

CREATE TABLE IF NOT EXISTS regulatory_interactions (
    id               TEXT PRIMARY KEY,
    enzyme_id        TEXT NOT NULL,
    compound_id      TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    ki_allosteric    REAL,
    hill_coefficient REAL,
    site             TEXT,
    organism         TEXT,
    source_database  TEXT
);

CREATE INDEX IF NOT EXISTS idx_meta_nodes_kind  ON meta_nodes(kind);
CREATE INDEX IF NOT EXISTS idx_meta_nodes_name  ON meta_nodes(name);
CREATE INDEX IF NOT EXISTS idx_meta_nodes_ec    ON meta_nodes(ec_number);
CREATE INDEX IF NOT EXISTS idx_meta_edges_src   ON meta_edges(src);
CREATE INDEX IF NOT EXISTS idx_meta_edges_dst   ON meta_edges(dst);
CREATE INDEX IF NOT EXISTS idx_meta_edges_rel   ON meta_edges(rel);
CREATE INDEX IF NOT EXISTS idx_xref_node        ON xref_index(node_id);
CREATE INDEX IF NOT EXISTS idx_kp_enzyme        ON kinetic_parameters(enzyme_id);
CREATE INDEX IF NOT EXISTS idx_kp_reaction      ON kinetic_parameters(reaction_id);
CREATE INDEX IF NOT EXISTS idx_ri_enzyme        ON regulatory_interactions(enzyme_id);
CREATE INDEX IF NOT EXISTS idx_ri_compound      ON regulatory_interactions(compound_id);
"""


class MetaStore:
    """
    SQLite persistence layer for the metabolic knowledge graph.

    :param db_path: Path to the SQLite database file.  Created on first use.
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialise and open the database.

        :param db_path: File path for the SQLite database.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_schema()

    def _apply_schema(self) -> None:
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()
        self._migrate()

    def _migrate(self) -> None:
        """Apply incremental schema additions to existing databases."""
        cur = self._conn.execute("PRAGMA table_info(meta_nodes)")
        existing_cols = {row[1] for row in cur.fetchall()}
        if "category" not in existing_cols:
            self._conn.execute("ALTER TABLE meta_nodes ADD COLUMN category TEXT")
            self._conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(
        self,
        nodes: Iterable[MetaNode],
        edges: Iterable[MetaEdge],
        *,
        wipe: bool = False,
    ) -> None:
        """
        Write nodes and edges to SQLite.

        :param nodes: Iterable of :class:`~code_kg.metakg.primitives.MetaNode`.
        :param edges: Iterable of :class:`~code_kg.metakg.primitives.MetaEdge`.
        :param wipe: If ``True``, truncate all tables before writing.
        """
        cur = self._conn.cursor()
        if wipe:
            cur.execute("DELETE FROM meta_edges")
            cur.execute("DELETE FROM xref_index")
            cur.execute("DELETE FROM meta_nodes")

        node_rows = [
            (
                n.id,
                n.kind,
                n.name,
                n.description,
                n.formula,
                n.charge,
                n.ec_number,
                n.stoichiometry,
                n.xrefs,
                n.source_format,
                n.source_file,
                n.category,
            )
            for n in nodes
        ]
        cur.executemany(
            """
            INSERT OR REPLACE INTO meta_nodes
            (id, kind, name, description, formula, charge, ec_number,
             stoichiometry, xrefs, source_format, source_file, category)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            node_rows,
        )

        edge_rows = [(e.src, e.rel, e.dst, e.evidence) for e in edges]
        cur.executemany(
            "INSERT OR IGNORE INTO meta_edges (src, rel, dst, evidence) VALUES (?,?,?,?)",
            edge_rows,
        )

        self._conn.commit()

    def build_xref_index(self) -> int:
        """
        Expand the ``xrefs`` JSON blob on every node into ``xref_index`` rows.

        Analogous to ``GraphStore.resolve_symbols()``.  Call once after
        all nodes are written.

        :return: Number of xref rows inserted.
        """
        cur = self._conn.cursor()
        cur.execute("DELETE FROM xref_index")

        cur.execute("SELECT id, xrefs FROM meta_nodes WHERE xrefs IS NOT NULL")
        rows = cur.fetchall()

        xref_rows: list[tuple[str, str, str]] = []
        for row in rows:
            nid = row["id"]
            try:
                xrefs = json.loads(row["xrefs"])
            except (json.JSONDecodeError, TypeError):
                continue
            for db_name, ext_id in xrefs.items():
                if not db_name or not ext_id:
                    continue
                # ext_id may be a list (multi-gene enzyme groups) or a scalar.
                # Expand lists so each member gets its own xref_index row.
                members = ext_id if isinstance(ext_id, list) else [ext_id]
                for member in members:
                    xref_rows.append((nid, db_name.lower(), str(member)))

        cur.executemany(
            "INSERT OR REPLACE INTO xref_index (node_id, db_name, ext_id) VALUES (?,?,?)",
            xref_rows,
        )
        self._conn.commit()
        return len(xref_rows)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def node(self, node_id: str) -> dict | None:
        """
        Fetch a single node by its stable ID.

        :param node_id: Node identifier string.
        :return: Node dict or ``None`` if not found.
        """
        cur = self._conn.execute("SELECT * FROM meta_nodes WHERE id = ?", (node_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def nodes(self, node_ids: list[str]) -> dict[str, dict | None]:
        """
        Fetch multiple nodes by their IDs in a single batch query.

        :param node_ids: List of node identifier strings.
        :return: Dict mapping node_id → node dict (or None if not found).
        """
        if not node_ids:
            return {}
        placeholders = ",".join("?" * len(node_ids))
        cur = self._conn.execute(
            f"SELECT * FROM meta_nodes WHERE id IN ({placeholders})",
            node_ids,
        )
        result: dict[str, dict | None] = {}
        for row in cur.fetchall():
            node_dict = dict(row)
            result[node_dict["id"]] = node_dict
        # Include missing nodes as None for consistency
        for node_id in node_ids:
            if node_id not in result:
                result[node_id] = None
        return result

    def node_by_xref(self, db_name: str, ext_id: str) -> dict | None:
        """
        Resolve an external database ID to a MetaStore node.

        :param db_name: Database name, e.g. ``"kegg"`` or ``"chebi"``.
        :param ext_id: External identifier, e.g. ``"C00022"``.
        :return: Node dict or ``None`` if not found.
        """
        cur = self._conn.execute(
            "SELECT node_id FROM xref_index WHERE db_name=? AND ext_id=?",
            (db_name.lower(), ext_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        return self.node(row["node_id"])

    def resolve_id(self, user_id: str) -> str | None:
        """
        Resolve a user-provided ID to an internal node ID.

        Accepts:
        - Internal ID directly (``cpd:kegg:C00022``)
        - Shorthand ``db:ext_id`` (``kegg:C00022``)
        - Plain external ID if unambiguous

        :param user_id: User-supplied identifier string.
        :return: Internal node ID or ``None`` if not resolvable.
        """
        # Direct hit
        if self.node(user_id):
            return user_id

        # db:ext_id shorthand
        if ":" in user_id:
            parts = user_id.split(":", 1)
            node = self.node_by_xref(parts[0], parts[1])
            if node:
                return node["id"]

        # Name-based fallback
        cur = self._conn.execute(
            "SELECT id FROM meta_nodes WHERE LOWER(name)=? LIMIT 1",
            (user_id.lower(),),
        )
        row = cur.fetchone()
        return row["id"] if row else None

    def edges_of(self, node_id: str) -> list[dict]:
        """
        Return all edges where *node_id* is either source or destination.

        :param node_id: Node identifier.
        :return: List of edge dicts with keys ``src``, ``rel``, ``dst``, ``evidence``.
        """
        cur = self._conn.execute(
            "SELECT src, rel, dst, evidence FROM meta_edges WHERE src=? OR dst=?",
            (node_id, node_id),
        )
        return [dict(r) for r in cur.fetchall()]

    def neighbours(self, node_id: str, *, rels: tuple[str, ...] = DEFAULT_RELS) -> list[str]:
        """
        Return IDs of nodes reachable from *node_id* in one hop along *rels*.

        :param node_id: Source node identifier.
        :param rels: Edge relations to follow.
        :return: List of neighbour node IDs.
        """
        placeholders = ",".join("?" * len(rels))
        cur = self._conn.execute(
            f"SELECT dst FROM meta_edges WHERE src=? AND rel IN ({placeholders})",
            (node_id, *rels),
        )
        out = [r[0] for r in cur.fetchall()]
        cur = self._conn.execute(
            f"SELECT src FROM meta_edges WHERE dst=? AND rel IN ({placeholders})",
            (node_id, *rels),
        )
        out += [r[0] for r in cur.fetchall()]
        return out

    def edges_within(self, node_ids: set[str]) -> list[dict]:
        """
        Return all edges where both endpoints are in *node_ids*.

        :param node_ids: Set of node IDs to filter by.
        :return: List of edge dicts.
        """
        if not node_ids:
            return []
        placeholders = ",".join("?" * len(node_ids))
        ids = list(node_ids)
        cur = self._conn.execute(
            f"""
            SELECT src, rel, dst, evidence FROM meta_edges
            WHERE src IN ({placeholders}) AND dst IN ({placeholders})
            """,
            ids + ids,
        )
        return [dict(r) for r in cur.fetchall()]

    def reaction_detail(self, rxn_id: str) -> dict | None:
        """
        Retrieve a reaction node with its full substrate, product, and enzyme context.

        :param rxn_id: Reaction node ID.
        :return: Dict with reaction fields plus ``substrates``, ``products``, ``enzymes``,
                 or ``None`` if not found.
        """
        rxn = self.node(rxn_id)
        if not rxn:
            return None

        substrates: list[dict] = []
        products: list[dict] = []
        enzymes: list[dict] = []

        for edge in self.edges_of(rxn_id):
            if edge["rel"] == REL_SUBSTRATE_OF and edge["dst"] == rxn_id:
                cmpd = self.node(edge["src"])
                if cmpd:
                    ev = json.loads(edge["evidence"]) if edge["evidence"] else {}
                    substrates.append({**cmpd, "stoich": ev.get("stoich", 1.0)})
            elif edge["rel"] == REL_PRODUCT_OF and edge["src"] == rxn_id:
                cmpd = self.node(edge["dst"])
                if cmpd:
                    ev = json.loads(edge["evidence"]) if edge["evidence"] else {}
                    products.append({**cmpd, "stoich": ev.get("stoich", 1.0)})
            elif edge["rel"] in ("CATALYZES", "INHIBITS", "ACTIVATES") and edge["dst"] == rxn_id:
                enz = self.node(edge["src"])
                if enz:
                    enzymes.append({**enz, "role": edge["rel"]})

        return {
            **rxn,
            "substrates": substrates,
            "products": products,
            "enzymes": enzymes,
        }

    def find_shortest_path(
        self,
        from_id: str,
        to_id: str,
        *,
        max_hops: int = 6,
    ) -> dict:
        """
        Find the shortest metabolic path between two compound nodes.

        Uses bidirectional BFS through ``SUBSTRATE_OF`` and ``PRODUCT_OF`` edges,
        traversing reaction nodes as intermediaries.

        :param from_id: Source compound node ID.
        :param to_id: Target compound node ID.
        :param max_hops: Maximum reaction steps (default 6).
        :return: Dict with keys ``path`` (list of node dicts), ``hops`` (int),
                 and ``edges`` (list of edge dicts), or ``{"error": ..., "searched_hops": n}``.
        """
        if from_id == to_id:
            n = self.node(from_id)
            return {"path": [n] if n else [], "hops": 0, "edges": []}

        # BFS: compound → reaction (via SUBSTRATE_OF outgoing from compound)
        #      reaction → compound (via PRODUCT_OF outgoing from reaction)
        # We traverse the directed graph; expand from both ends simultaneously.

        # Forward frontier: {node_id: predecessor_node_id}
        fwd: dict[str, str | None] = {from_id: None}
        bwd: dict[str, str | None] = {to_id: None}
        fwd_queue: deque[str] = deque([from_id])
        bwd_queue: deque[str] = deque([to_id])

        def _fwd_neighbours(nid: str) -> list[str]:
            """From a compound, reach reactions; from a reaction, reach products."""
            node = self.node(nid)
            if not node:
                return []
            if node["kind"] == "compound":
                cur = self._conn.execute(
                    "SELECT dst FROM meta_edges WHERE src=? AND rel='SUBSTRATE_OF'",
                    (nid,),
                )
                return [r[0] for r in cur.fetchall()]
            if node["kind"] == "reaction":
                cur = self._conn.execute(
                    "SELECT dst FROM meta_edges WHERE src=? AND rel='PRODUCT_OF'",
                    (nid,),
                )
                return [r[0] for r in cur.fetchall()]
            return []

        def _bwd_neighbours(nid: str) -> list[str]:
            """Reverse: from compound find reactions it is produced by; from reaction find substrates."""
            node = self.node(nid)
            if not node:
                return []
            if node["kind"] == "compound":
                cur = self._conn.execute(
                    "SELECT src FROM meta_edges WHERE dst=? AND rel='PRODUCT_OF'",
                    (nid,),
                )
                return [r[0] for r in cur.fetchall()]
            if node["kind"] == "reaction":
                cur = self._conn.execute(
                    "SELECT src FROM meta_edges WHERE dst=? AND rel='SUBSTRATE_OF'",
                    (nid,),
                )
                return [r[0] for r in cur.fetchall()]
            return []

        def _reconstruct(meet: str) -> list[str]:
            fwd_path: list[str] = []
            cur = meet
            while cur is not None:
                fwd_path.append(cur)
                cur = fwd[cur]  # type: ignore[assignment]
            fwd_path.reverse()
            bwd_path: list[str] = []
            cur = bwd[meet]
            while cur is not None:
                bwd_path.append(cur)
                cur = bwd[cur]  # type: ignore[assignment]
            return fwd_path + bwd_path

        for _ in range(max_hops * 2 + 2):  # *2 because each BFS step is half a reaction hop
            # Expand forward
            next_fwd: deque[str] = deque()
            while fwd_queue:
                nid = fwd_queue.popleft()
                for nb in _fwd_neighbours(nid):
                    if nb not in fwd:
                        fwd[nb] = nid
                        next_fwd.append(nb)
                    if nb in bwd:
                        path_ids = _reconstruct(nb)
                        path_nodes = cast(
                            list[dict],
                            [n for n in [self.node(pid) for pid in path_ids] if n is not None],
                        )
                        rxn_count = sum(1 for n in path_nodes if n["kind"] == "reaction")
                        edges = self.edges_within(set(path_ids))
                        return {"path": path_nodes, "hops": rxn_count, "edges": edges}
            fwd_queue = next_fwd

            # Expand backward
            next_bwd: deque[str] = deque()
            while bwd_queue:
                nid = bwd_queue.popleft()
                for nb in _bwd_neighbours(nid):
                    if nb not in bwd:
                        bwd[nb] = nid
                        next_bwd.append(nb)
                    if nb in fwd:
                        path_ids = _reconstruct(nb)
                        path_nodes = cast(
                            list[dict],
                            [n for n in [self.node(pid) for pid in path_ids] if n is not None],
                        )
                        rxn_count = sum(1 for n in path_nodes if n["kind"] == "reaction")
                        edges = self.edges_within(set(path_ids))
                        return {"path": path_nodes, "hops": rxn_count, "edges": edges}
            bwd_queue = next_bwd

            if not fwd_queue and not bwd_queue:
                break

        return {"error": "no path found", "searched_hops": max_hops}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """
        Return node and edge counts broken down by kind and relation.

        :return: Dict with keys ``total_nodes``, ``total_edges``,
                 ``node_counts`` (by kind), and ``edge_counts`` (by relation).
        """
        cur = self._conn.cursor()

        cur.execute("SELECT kind, COUNT(*) FROM meta_nodes GROUP BY kind")
        node_counts = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT rel, COUNT(*) FROM meta_edges GROUP BY rel")
        edge_counts = {r[0]: r[1] for r in cur.fetchall()}

        return {
            "total_nodes": sum(node_counts.values()),
            "total_edges": sum(edge_counts.values()),
            "node_counts": node_counts,
            "edge_counts": edge_counts,
        }

    def all_nodes(self, *, kind: str | None = None, category: str | None = None) -> list[dict]:
        """
        Return all nodes, optionally filtered by kind and/or category.

        :param kind: If provided, only nodes of this kind are returned.
        :param category: If provided, only nodes with this category are returned.
        :return: List of node dicts.
        """
        conditions: list[str] = []
        params: list[str] = []
        if kind:
            conditions.append("kind=?")
            params.append(kind)
        if category:
            conditions.append("category=?")
            params.append(category)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        cur = self._conn.execute(f"SELECT * FROM meta_nodes{where}", params)
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Kinetic parameters
    # ------------------------------------------------------------------

    def upsert_kinetic_param(self, param: KineticParam) -> None:
        """
        Insert or replace a :class:`~metakg.primitives.KineticParam` row.

        :param param: KineticParam instance to persist.
        """
        self._conn.execute(
            """
            INSERT OR REPLACE INTO kinetic_parameters
            (id, enzyme_id, reaction_id, substrate_id,
             km, kcat, vmax, ki, hill_coefficient,
             delta_g_prime, equilibrium_constant,
             ph, temperature_celsius, ionic_strength,
             source_database, literature_reference,
             organism, tissue, confidence_score, measurement_error)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                param.id,
                param.enzyme_id,
                param.reaction_id,
                param.substrate_id,
                param.km,
                param.kcat,
                param.vmax,
                param.ki,
                param.hill_coefficient,
                param.delta_g_prime,
                param.equilibrium_constant,
                param.ph,
                param.temperature_celsius,
                param.ionic_strength,
                param.source_database,
                param.literature_reference,
                param.organism,
                param.tissue,
                param.confidence_score,
                param.measurement_error,
            ),
        )
        self._conn.commit()

    def upsert_kinetic_params(self, params: list[KineticParam]) -> int:
        """
        Bulk insert/replace a list of :class:`~metakg.primitives.KineticParam` rows.

        :param params: List of KineticParam instances.
        :return: Number of rows written.
        """
        rows = [
            (
                p.id,
                p.enzyme_id,
                p.reaction_id,
                p.substrate_id,
                p.km,
                p.kcat,
                p.vmax,
                p.ki,
                p.hill_coefficient,
                p.delta_g_prime,
                p.equilibrium_constant,
                p.ph,
                p.temperature_celsius,
                p.ionic_strength,
                p.source_database,
                p.literature_reference,
                p.organism,
                p.tissue,
                p.confidence_score,
                p.measurement_error,
            )
            for p in params
        ]
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO kinetic_parameters
            (id, enzyme_id, reaction_id, substrate_id,
             km, kcat, vmax, ki, hill_coefficient,
             delta_g_prime, equilibrium_constant,
             ph, temperature_celsius, ionic_strength,
             source_database, literature_reference,
             organism, tissue, confidence_score, measurement_error)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        self._conn.commit()
        return len(rows)

    def kinetic_params_for_reaction(self, reaction_id: str) -> list[dict]:
        """
        Fetch all kinetic parameter rows for a reaction node.

        :param reaction_id: Reaction node ID.
        :return: List of row dicts.
        """
        cur = self._conn.execute(
            "SELECT * FROM kinetic_parameters WHERE reaction_id=?", (reaction_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    def kinetic_params_for_enzyme(self, enzyme_id: str) -> list[dict]:
        """
        Fetch all kinetic parameter rows for an enzyme node.

        :param enzyme_id: Enzyme node ID.
        :return: List of row dicts.
        """
        cur = self._conn.execute("SELECT * FROM kinetic_parameters WHERE enzyme_id=?", (enzyme_id,))
        return [dict(r) for r in cur.fetchall()]

    def all_kinetic_params(self) -> list[dict]:
        """Return every row in kinetic_parameters."""
        cur = self._conn.execute("SELECT * FROM kinetic_parameters")
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Regulatory interactions
    # ------------------------------------------------------------------

    def upsert_regulatory_interaction(self, ri: RegulatoryInteraction) -> None:
        """
        Insert or replace a :class:`~metakg.primitives.RegulatoryInteraction` row.

        :param ri: RegulatoryInteraction instance to persist.
        """
        self._conn.execute(
            """
            INSERT OR REPLACE INTO regulatory_interactions
            (id, enzyme_id, compound_id, interaction_type,
             ki_allosteric, hill_coefficient, site, organism, source_database)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                ri.id,
                ri.enzyme_id,
                ri.compound_id,
                ri.interaction_type,
                ri.ki_allosteric,
                ri.hill_coefficient,
                ri.site,
                ri.organism,
                ri.source_database,
            ),
        )
        self._conn.commit()

    def upsert_regulatory_interactions(self, interactions: list[RegulatoryInteraction]) -> int:
        """
        Bulk insert/replace regulatory interaction rows.

        :param interactions: List of RegulatoryInteraction instances.
        :return: Number of rows written.
        """
        rows = [
            (
                ri.id,
                ri.enzyme_id,
                ri.compound_id,
                ri.interaction_type,
                ri.ki_allosteric,
                ri.hill_coefficient,
                ri.site,
                ri.organism,
                ri.source_database,
            )
            for ri in interactions
        ]
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO regulatory_interactions
            (id, enzyme_id, compound_id, interaction_type,
             ki_allosteric, hill_coefficient, site, organism, source_database)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        self._conn.commit()
        return len(rows)

    def regulatory_interactions_for_enzyme(self, enzyme_id: str) -> list[dict]:
        """
        Fetch all regulatory interactions for an enzyme.

        :param enzyme_id: Enzyme node ID.
        :return: List of row dicts.
        """
        cur = self._conn.execute(
            "SELECT * FROM regulatory_interactions WHERE enzyme_id=?", (enzyme_id,)
        )
        return [dict(r) for r in cur.fetchall()]

    def regulatory_interactions_for_reaction(self, reaction_id: str) -> list[dict]:
        """
        Fetch regulatory interactions affecting any enzyme that catalyses a reaction.

        :param reaction_id: Reaction node ID.
        :return: List of row dicts joined with enzyme info.
        """
        cur = self._conn.execute(
            """
            SELECT ri.*
            FROM regulatory_interactions ri
            WHERE ri.enzyme_id IN (
                SELECT src FROM meta_edges WHERE rel='CATALYZES' AND dst=?
            )
            """,
            (reaction_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __enter__(self) -> MetaStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# GraphStore — compatibility wrapper for visualization tools
# ---------------------------------------------------------------------------


class GraphStore(MetaStore):
    """
    Convenience wrapper around MetaStore with query methods for visualization.

    Provides additional methods compatible with the Streamlit visualization app.
    """

    def query_nodes(self, *, kind: str | None = None) -> list[dict]:
        """
        Query all nodes, optionally filtered by kind.

        :param kind: If provided, only nodes of this kind are returned.
        :return: List of node dicts.
        """
        return self.all_nodes(kind=kind)

    def query_edges(self, *, src: str | None = None, dst: str | None = None) -> list[dict]:
        """
        Query edges, optionally filtered by source or destination.

        :param src: If provided, only edges from this node are returned.
        :param dst: If provided, only edges to this node are returned.
        :return: List of edge dicts.
        """
        if src and dst:
            cur = self._conn.execute(
                "SELECT src, rel, dst, evidence FROM meta_edges WHERE src=? AND dst=?",
                (src, dst),
            )
        elif src:
            cur = self._conn.execute(
                "SELECT src, rel, dst, evidence FROM meta_edges WHERE src=?", (src,)
            )
        elif dst:
            cur = self._conn.execute(
                "SELECT src, rel, dst, evidence FROM meta_edges WHERE dst=?", (dst,)
            )
        else:
            cur = self._conn.execute("SELECT src, rel, dst, evidence FROM meta_edges")
        return [dict(r) for r in cur.fetchall()]

    def get_node(self, node_id: str) -> dict | None:
        """
        Get a single node by ID (alias for :meth:`node`).

        :param node_id: Node identifier.
        :return: Node dict or ``None`` if not found.
        """
        return self.node(node_id)

    def query_text(self, query: str, k: int = 10) -> list[dict]:
        """
        Find nodes by substring match on name and description fields.

        Text-filter fallback for the Streamlit visualiser.  For true semantic
        (vector) search use :class:`~metakg.index.MetaIndex`.

        :param query: Query string (case-insensitive substring match).
        :param k: Maximum number of results to return.
        :return: List of node dicts sorted by relevance (name match > description match).
        """
        # Simple text-based search if embeddings are not available
        query_lower = query.lower()
        nodes = self.all_nodes()
        matches = []

        for node in nodes:
            name = (node.get("name") or "").lower()
            desc = (node.get("description") or "").lower()

            if query_lower in name:
                matches.append((node, 2))  # name match scores higher
            elif query_lower in desc:
                matches.append((node, 1))

        # Sort by relevance score (descending) and limit results
        matches.sort(key=lambda x: x[1], reverse=True)
        return [node for node, _ in matches[:k]]
