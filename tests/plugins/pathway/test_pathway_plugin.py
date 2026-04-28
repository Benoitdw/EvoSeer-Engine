"""Tests for PathwayPlugin — parity derivation and compute_score."""

from pathlib import Path

import pytest

from evoseer.core.cell import CellState, PluginState
from evoseer.core.context import SimContext
from evoseer.plugins.pathway import PathwayDefinition, derive_roles
from evoseer.plugins.pathway.erk import ErkPathwayPlugin
from evoseer.services.mutation_store import InMemoryMutationStore, MutationRecord

ERK_YAML = Path(__file__).parents[3] / "evoseer/plugins/pathway/data/erk.yaml"


# ---------------------------------------------------------------------------
# PathwayDefinition loading
# ---------------------------------------------------------------------------

def test_load_erk_yaml():
    defn = PathwayDefinition.load(ERK_YAML)
    assert defn.name == "ERK"
    assert defn.output_node == "MAPK1"
    assert "BRAF" in defn.nodes
    assert "NF1" in defn.nodes
    assert len(defn.edges) > 0


# ---------------------------------------------------------------------------
# Parity / role derivation
# ---------------------------------------------------------------------------

def test_braf_is_activator():
    defn = PathwayDefinition.load(ERK_YAML)
    act, inh = derive_roles(defn)
    assert "BRAF" in act
    assert "BRAF" not in inh


def test_nf1_is_inhibitor():
    # NF1 -| NRAS -> BRAF -> ... -> MAPK1  (1 inhibit edge => odd parity)
    defn = PathwayDefinition.load(ERK_YAML)
    act, inh = derive_roles(defn)
    assert "NF1" in inh
    assert "NF1" not in act


def test_nras_is_activator():
    defn = PathwayDefinition.load(ERK_YAML)
    act, inh = derive_roles(defn)
    assert "NRAS" in act


def test_output_node_is_activator():
    defn = PathwayDefinition.load(ERK_YAML)
    act, inh = derive_roles(defn)
    assert defn.output_node in act


# ---------------------------------------------------------------------------
# ErkPathwayPlugin.compute_score
# ---------------------------------------------------------------------------

def _make_store(*records: MutationRecord) -> InMemoryMutationStore:
    store = InMemoryMutationStore()
    for r in records:
        store.add_mutation(r)
    return store


def _ctx() -> SimContext:
    return SimContext(t=0.0, step=0, N=1)


def test_score_zero_no_mutations():
    store = _make_store()
    plugin = ErkPathwayPlugin({}, store)
    state = CellState(mutations=set())
    score = plugin.compute_score(state, _ctx())
    # sigmoid(0) < 0.5 since threshold=0.5 → sigmoid(-slope*threshold) < 0.5
    assert 0.0 < score < 0.5


def test_braf_gof_increases_score():
    store_wt = _make_store()
    store_mut = _make_store(
        MutationRecord(mutation_id=1, gene_id=673, gene_name="BRAF",
                       pathways=["ERK"], is_driver=True, effect="GOF")
    )
    plugin_wt  = ErkPathwayPlugin({}, store_wt)
    plugin_mut = ErkPathwayPlugin({}, store_mut)

    state_wt  = CellState(mutations=set())
    state_mut = CellState(mutations={1})

    assert plugin_mut.compute_score(state_mut, _ctx()) > plugin_wt.compute_score(state_wt, _ctx())


def test_nf1_lof_increases_score():
    store = _make_store(
        MutationRecord(mutation_id=2, gene_id=4763, gene_name="NF1",
                       pathways=["ERK"], is_driver=True, effect="LOF")
    )
    plugin = ErkPathwayPlugin({}, store)
    state_wt  = CellState(mutations=set())
    state_mut = CellState(mutations={2})
    assert plugin.compute_score(state_mut, _ctx()) > plugin.compute_score(state_wt, _ctx())


def test_braf_lof_has_no_effect():
    # BRAF is an activator — LOF should not contribute to the score
    store = _make_store(
        MutationRecord(mutation_id=3, gene_id=673, gene_name="BRAF",
                       pathways=["ERK"], effect="LOF")
    )
    plugin = ErkPathwayPlugin({}, store)
    state_wt  = CellState(mutations=set())
    state_mut = CellState(mutations={3})
    assert plugin.compute_score(state_mut, _ctx()) == pytest.approx(
        plugin.compute_score(state_wt, _ctx())
    )


def test_effect_none_ignored():
    store = _make_store(
        MutationRecord(mutation_id=4, gene_id=673, gene_name="BRAF",
                       pathways=["ERK"], effect=None)
    )
    plugin = ErkPathwayPlugin({}, store)
    state_wt  = CellState(mutations=set())
    state_mut = CellState(mutations={4})
    assert plugin.compute_score(state_mut, _ctx()) == pytest.approx(
        plugin.compute_score(state_wt, _ctx())
    )
