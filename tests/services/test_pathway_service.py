"""Tests for PathwayService."""

from pathlib import Path

from evoseer.services.pathway_service import PathwayService

PATHWAY_DIR = Path(__file__).parents[2] / "evoseer/plugins/pathway/data"


def test_braf_mapped_to_erk():
    service = PathwayService(PATHWAY_DIR)
    pathways = service.get_pathways(gene_id=673, gene_name="BRAF")
    assert "ERK" in pathways


def test_nf1_mapped_to_erk():
    service = PathwayService(PATHWAY_DIR)
    pathways = service.get_pathways(gene_id=4763, gene_name="NF1")
    assert "ERK" in pathways


def test_unknown_gene_returns_empty():
    service = PathwayService(PATHWAY_DIR)
    assert service.get_pathways(gene_id=99999, gene_name="UNKNOWN") == []


def test_gene_name_fallback():
    # gene_id=None triggers name lookup
    service = PathwayService(PATHWAY_DIR)
    pathways = service.get_pathways(gene_id=None, gene_name="BRAF")
    assert "ERK" in pathways
