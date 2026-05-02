"""
Tests for ``metabokg.downloader`` — TSV manifest, integrity checks, and KEGG
REST download utilities.

Network-dependent tests are guarded behind the ``integration`` marker so the
default suite runs offline.  All other tests monkeypatch ``_fetch`` to feed
canned KEGG responses through the real download/parse code paths.

Run only the offline tests::

    pytest tests/test_downloader.py

Include the live KEGG REST checks as well::

    pytest tests/test_downloader.py -m "integration or not integration"
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from metabokg import downloader
from metabokg.downloader import (
    CORPUS_BY_NAME,
    CORPUS_SPECS,
    TSV_MANIFEST,
    CorpusSpec,
    TsvIntegrityResult,
    TsvSpec,
    check_integrity,
    download_gene_names,
    download_kegg_names,
    download_reaction_detail,
)

# ---------------------------------------------------------------------------
# Manifest sanity
# ---------------------------------------------------------------------------


def test_manifest_filenames_are_unique():
    names = [s.filename for s in TSV_MANIFEST]
    assert len(names) == len(set(names)), "duplicate TSV filenames in manifest"


def test_manifest_covers_known_files():
    """Every TSV referenced by the enrichment pipeline appears in the manifest."""
    expected = {
        "kegg_compound_names.tsv",
        "kegg_reaction_names.tsv",
        "kegg_glycan_names.tsv",
        "kegg_ko_names.tsv",
        "kegg_reaction_detail.tsv",
        "hsa_gene_names.tsv",
        "cge_gene_names.tsv",
        "sabio_cho_kinetics.tsv",
    }
    actual = {s.filename for s in TSV_MANIFEST}
    assert expected == actual


def test_corpus_specs_round_trip_through_index():
    assert set(CORPUS_BY_NAME) == {c.name for c in CORPUS_SPECS}
    for name, spec in CORPUS_BY_NAME.items():
        assert isinstance(spec, CorpusSpec)
        assert spec.name == name


def test_manual_files_are_not_marked_as_needing_fetch():
    """`download_group == 'manual'` files (e.g. SABIO-RK) must not auto-fetch."""
    sabio = next(s for s in TSV_MANIFEST if s.filename == "sabio_cho_kinetics.tsv")
    result = TsvIntegrityResult(spec=sabio, path=Path("/nope"), status="missing", rows=0)
    assert result.needs_fetch is False


def test_needs_fetch_classification():
    spec = TsvSpec("foo.tsv", min_rows=10, corpora=None, download_group="names")
    assert TsvIntegrityResult(spec, Path("/x"), "missing", 0).needs_fetch is True
    assert TsvIntegrityResult(spec, Path("/x"), "empty", 0).needs_fetch is True
    assert TsvIntegrityResult(spec, Path("/x"), "thin", 3).needs_fetch is False
    assert TsvIntegrityResult(spec, Path("/x"), "ok", 20).needs_fetch is False


# ---------------------------------------------------------------------------
# check_integrity
# ---------------------------------------------------------------------------


def _populate_tsv(path: Path, rows: int) -> None:
    """Write *rows* tab-separated lines (one column) to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"row_{i}\tval_{i}" for i in range(rows)), encoding="utf-8")


def test_check_integrity_classifies_each_status(tmp_path):
    # OK file: meets min_rows (15_000)
    _populate_tsv(tmp_path / "kegg_compound_names.tsv", 15_001)
    # THIN file: exists but below threshold (10_000)
    _populate_tsv(tmp_path / "kegg_reaction_names.tsv", 50)
    # EMPTY file: exists but no rows
    (tmp_path / "kegg_glycan_names.tsv").write_text("", encoding="utf-8")
    # MISSING: kegg_ko_names.tsv intentionally not created

    results = check_integrity(tmp_path, corpora=None)
    by_name = {r.spec.filename: r for r in results}

    assert by_name["kegg_compound_names.tsv"].status == "ok"
    assert by_name["kegg_compound_names.tsv"].rows == 15_001
    assert by_name["kegg_reaction_names.tsv"].status == "thin"
    assert by_name["kegg_glycan_names.tsv"].status == "empty"
    assert by_name["kegg_ko_names.tsv"].status == "missing"
    assert by_name["kegg_ko_names.tsv"].rows == 0


def test_check_integrity_filters_by_corpus(tmp_path):
    """Per-corpus TSVs only appear when their corpus is selected."""
    results_hsa = check_integrity(tmp_path, corpora={"hsa"})
    names_hsa = {r.spec.filename for r in results_hsa}
    assert "hsa_gene_names.tsv" in names_hsa
    assert "cge_gene_names.tsv" not in names_hsa
    assert "sabio_cho_kinetics.tsv" not in names_hsa
    # Universal TSVs are still checked
    assert "kegg_compound_names.tsv" in names_hsa

    results_cge = check_integrity(tmp_path, corpora={"cge"})
    names_cge = {r.spec.filename for r in results_cge}
    assert "cge_gene_names.tsv" in names_cge
    assert "sabio_cho_kinetics.tsv" in names_cge
    assert "hsa_gene_names.tsv" not in names_cge


def test_check_integrity_preserves_manifest_order(tmp_path):
    results = check_integrity(tmp_path, corpora=None)
    actual_order = [r.spec.filename for r in results]
    expected_order = [s.filename for s in TSV_MANIFEST]
    assert actual_order == expected_order


# ---------------------------------------------------------------------------
# Download paths — _fetch monkeypatched to avoid network
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_fetch(monkeypatch):
    """Replace ``downloader._fetch`` with a stub returning canned text per URL."""
    canned: dict[str, str] = {}

    def _stub(url: str, *, quiet: bool = False) -> str:  # noqa: ARG001
        if url not in canned:
            raise AssertionError(f"unexpected URL fetched: {url}")
        return canned[url]

    monkeypatch.setattr(downloader, "_fetch", _stub)
    monkeypatch.setattr(downloader.time, "sleep", lambda _s: None)  # no rate-limit waits
    return canned


def test_download_kegg_names_writes_each_endpoint(tmp_path, fake_fetch):
    fake_fetch[f"{downloader._KEGG_BASE}/list/compound"] = "C00001\tH2O\nC00002\tATP\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/reaction"] = "R00001\tname1\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/glycan"] = "G00001\tname1\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/ko"] = "K00001\tname1\n"

    written = download_kegg_names(tmp_path, quiet=True)

    assert set(written) == {
        "kegg_compound_names.tsv",
        "kegg_reaction_names.tsv",
        "kegg_glycan_names.tsv",
        "kegg_ko_names.tsv",
    }
    cpd = (tmp_path / "kegg_compound_names.tsv").read_text(encoding="utf-8")
    assert "C00001\tH2O" in cpd
    assert "C00002\tATP" in cpd


def test_download_kegg_names_skips_existing_without_force(tmp_path, fake_fetch):
    """Pre-existing files must not be re-fetched unless force=True."""
    pre = tmp_path / "kegg_compound_names.tsv"
    pre.write_text("PRE_EXISTING\tdo_not_overwrite", encoding="utf-8")
    # Provide endpoints only for the *other* three files; if compound is fetched,
    # the assert in fake_fetch raises.
    fake_fetch[f"{downloader._KEGG_BASE}/list/reaction"] = "R\tx\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/glycan"] = "G\tx\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/ko"] = "K\tx\n"

    download_kegg_names(tmp_path, quiet=True)
    assert pre.read_text(encoding="utf-8") == "PRE_EXISTING\tdo_not_overwrite"


def test_download_kegg_names_force_overwrites(tmp_path, fake_fetch):
    pre = tmp_path / "kegg_compound_names.tsv"
    pre.write_text("OLD", encoding="utf-8")
    fake_fetch[f"{downloader._KEGG_BASE}/list/compound"] = "NEW\tdata\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/reaction"] = "R\tx\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/glycan"] = "G\tx\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/ko"] = "K\tx\n"

    download_kegg_names(tmp_path, force=True, quiet=True)
    assert "NEW\tdata" in pre.read_text(encoding="utf-8")
    assert "OLD" not in pre.read_text(encoding="utf-8")


def test_download_gene_names_per_organism(tmp_path, fake_fetch):
    fake_fetch[f"{downloader._KEGG_BASE}/list/hsa"] = "hsa:1\tGENE1\n"
    fake_fetch[f"{downloader._KEGG_BASE}/list/cge"] = "cge:1\tGENE2\n"

    written = download_gene_names(["hsa", "cge"], tmp_path, quiet=True)
    assert set(written) == {"hsa", "cge"}
    assert (tmp_path / "hsa_gene_names.tsv").read_text(encoding="utf-8").startswith("hsa:1")
    assert (tmp_path / "cge_gene_names.tsv").read_text(encoding="utf-8").startswith("cge:1")


# ---------------------------------------------------------------------------
# Reaction-detail download (parsing + KGML scan)
# ---------------------------------------------------------------------------


_KGML_SAMPLE = textwrap.dedent(
    """\
<?xml version="1.0"?>
<pathway name="path:hsa00010" org="hsa" number="00010">
  <reaction id="1" name="rn:R00001 rn:R00200" type="irreversible">
    <substrate name="cpd:C00031"/>
    <product   name="cpd:C00022"/>
  </reaction>
  <reaction id="2" name="rn:R00710" type="reversible">
    <substrate name="cpd:C00084"/>
    <product   name="cpd:C00033"/>
  </reaction>
</pathway>
"""
)

_KEGG_REACTION_FLAT = textwrap.dedent(
    """\
ENTRY       R00200                      Reaction
NAME        ATP:pyruvate 2-O-phosphotransferase;
            pyruvate kinase
DEFINITION  ATP + Pyruvate <=> ADP + Phosphoenolpyruvate
EQUATION    C00002 + C00022 <=> C00008 + C00074
ENZYME      2.7.1.40
///
"""
)


def test_collect_rxn_ids_from_kgml_extracts_unique_ids(tmp_path):
    kgml_dir = tmp_path / "hsa_pathways"
    kgml_dir.mkdir()
    (kgml_dir / "hsa00010.kgml").write_text(_KGML_SAMPLE, encoding="utf-8")

    ids = downloader._collect_rxn_ids_from_kgml([kgml_dir])
    assert ids == ["R00001", "R00200", "R00710"]


def test_collect_rxn_ids_ignores_malformed_xml(tmp_path):
    kgml_dir = tmp_path / "hsa_pathways"
    kgml_dir.mkdir()
    (kgml_dir / "good.kgml").write_text(_KGML_SAMPLE, encoding="utf-8")
    (kgml_dir / "bad.kgml").write_text("<not></valid>", encoding="utf-8")

    ids = downloader._collect_rxn_ids_from_kgml([kgml_dir])
    assert "R00200" in ids  # good file was still parsed


def test_parse_kegg_reaction_flat_extracts_canonical_fields():
    parsed = downloader._parse_kegg_reaction_flat(_KEGG_REACTION_FLAT)
    assert parsed is not None
    assert parsed["reaction_id"] == "R00200"
    # First semicolon-delimited synonym is the canonical name
    assert parsed["name"] == "ATP:pyruvate 2-O-phosphotransferase"
    assert "Pyruvate" in parsed["definition"]
    assert "C00002 + C00022" in parsed["equation"]
    assert parsed["ec_numbers"] == "2.7.1.40"


def test_parse_kegg_reaction_flat_handles_multiple_ec_numbers():
    text = textwrap.dedent(
        """\
ENTRY       R00710
NAME        Acetaldehyde:NAD+ oxidoreductase
ENZYME      1.2.1.3 1.2.1.4 1.2.1.5
///
"""
    )
    parsed = downloader._parse_kegg_reaction_flat(text)
    assert parsed is not None
    assert parsed["ec_numbers"] == "1.2.1.3; 1.2.1.4; 1.2.1.5"


def test_parse_kegg_reaction_flat_returns_none_for_garbage():
    assert downloader._parse_kegg_reaction_flat("") is None
    assert downloader._parse_kegg_reaction_flat("   \n   ") is None
    assert downloader._parse_kegg_reaction_flat("NAME        no entry line") is None


def test_download_reaction_detail_writes_tsv(tmp_path, fake_fetch):
    kgml_dir = tmp_path / "hsa_pathways"
    kgml_dir.mkdir()
    (kgml_dir / "hsa00010.kgml").write_text(_KGML_SAMPLE, encoding="utf-8")

    # Provide a canned response only for R00200; R00001 and R00710 will be fetched
    # but get a minimal stub so they at least parse.
    minimal = "ENTRY       {rid}\nNAME        stub\n///\n"
    fake_fetch[f"{downloader._KEGG_BASE}/get/rn:R00001"] = minimal.format(rid="R00001")
    fake_fetch[f"{downloader._KEGG_BASE}/get/rn:R00200"] = _KEGG_REACTION_FLAT
    fake_fetch[f"{downloader._KEGG_BASE}/get/rn:R00710"] = minimal.format(rid="R00710")

    n_written = download_reaction_detail(tmp_path, kgml_dirs=[kgml_dir], quiet=True)
    assert n_written == 3

    out = tmp_path / "kegg_reaction_detail.tsv"
    body = out.read_text(encoding="utf-8")
    assert body.startswith("reaction_id\tname\tdefinition\tequation\tec_numbers")
    assert "R00200" in body
    assert "ATP:pyruvate 2-O-phosphotransferase" in body
    assert "2.7.1.40" in body


def test_download_reaction_detail_skips_already_cached(tmp_path, fake_fetch):
    """A reaction already in the output TSV must not be re-fetched."""
    kgml_dir = tmp_path / "hsa_pathways"
    kgml_dir.mkdir()
    (kgml_dir / "hsa00010.kgml").write_text(_KGML_SAMPLE, encoding="utf-8")

    # Pre-populate the output with all three reactions
    out = tmp_path / "kegg_reaction_detail.tsv"
    out.write_text(
        "reaction_id\tname\tdefinition\tequation\tec_numbers\n"
        "R00001\tcached1\t\t\t\n"
        "R00200\tcached2\t\t\t\n"
        "R00710\tcached3\t\t\t\n",
        encoding="utf-8",
    )

    # No URLs registered — if the function tries to fetch, fake_fetch raises.
    n_written = download_reaction_detail(tmp_path, kgml_dirs=[kgml_dir], quiet=True)
    assert n_written == 0

    # Cached content must remain intact
    body = out.read_text(encoding="utf-8")
    assert "cached2" in body


def test_download_reaction_detail_no_ids_returns_zero(tmp_path, fake_fetch):  # noqa: ARG001
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    n_written = download_reaction_detail(tmp_path, kgml_dirs=[empty_dir], quiet=True)
    assert n_written == 0


# ---------------------------------------------------------------------------
# _fetch error surface
# ---------------------------------------------------------------------------


def test_fetch_wraps_network_errors_as_runtime_error(monkeypatch):
    import urllib.error

    def _boom(_req, timeout=60):  # noqa: ARG001
        raise urllib.error.URLError("simulated DNS failure")

    monkeypatch.setattr(downloader.urllib.request, "urlopen", _boom)
    with pytest.raises(RuntimeError, match="download failed"):
        downloader._fetch("https://rest.kegg.jp/list/compound", quiet=True)


# ---------------------------------------------------------------------------
# Integration: live KEGG REST (skipped by default)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
def test_kegg_endpoint_reachable():
    """Smoke-check that the KEGG list endpoint responds with non-empty data."""
    text = downloader._fetch(f"{downloader._KEGG_BASE}/list/compound", quiet=True)
    assert text and "\t" in text
