"""Tests for SimulationExporter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from evoseer.core.config import (
    MutationGeneratorConfig,
    PluginConfig,
    RateFunctionConfig,
    SimulationConfig,
)
from evoseer.engine.events import DeathEvent, DriverEvent, DivisionEvent
from evoseer.recording.exporter import SimulationExporter
from evoseer.recording.recorder import SimulationResult, Snapshot
from evoseer.services.mutation_store import InMemoryMutationStore, MutationRecord


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _store_with(*records: MutationRecord) -> InMemoryMutationStore:
    s = InMemoryMutationStore()
    for r in records:
        s.add_mutation(r)
    return s


def _minimal_result() -> SimulationResult:
    """One founder, no divisions, no drivers, two snapshots."""
    result = SimulationResult()
    result.stop_reason = "max_cells"
    result.snapshots = [
        Snapshot(step=0, t=0.0, n_alive=1, n_dead_cumulative=0),
        Snapshot(step=10, t=0.5, n_alive=1, n_dead_cumulative=0),
    ]
    return result


# ── Metadata ─────────────────────────────────────────────────────────────────

def test_metadata_without_config():
    result = _minimal_result()
    store = _store_with()
    exp = SimulationExporter(result, store, config=None)
    meta = exp.export()["metadata"]
    assert meta["stop_reason"] == "max_cells"
    assert "seed" not in meta
    assert "plugins" not in meta


def test_metadata_with_config():
    result = _minimal_result()
    store = _store_with()
    config = SimulationConfig(
        seed=42,
        max_steps=1000,
        max_time=100.0,
        max_cells=500,
        plugins=[
            PluginConfig(
                name="erk_pathway",
                plugin_type="erk_pathway",
                target="rate_function",
                category="proliferative",
                weight=5.0,
                alpha=1.0,
            )
        ],
        rate_function=RateFunctionConfig(
            function_type="weighted_sum",
            baseline_birth_rate=0.5,
            baseline_death_rate=0.2,
        ),
        mutation_generator=MutationGeneratorConfig(generator_type="uniform"),
    )
    exp = SimulationExporter(result, store, config=config)
    meta = exp.export()["metadata"]

    assert meta["seed"] == 42
    assert meta["simulation"]["max_steps"] == 1000
    assert meta["rate_function"]["type"] == "weighted_sum"
    assert meta["rate_function"]["baseline_birth_rate"] == 0.5
    assert meta["mutation_generator"]["type"] == "uniform"
    assert len(meta["plugins"]) == 1
    assert meta["plugins"][0]["name"] == "erk_pathway"
    assert meta["plugins"][0]["weight"] == 5.0


# ── Snapshots round-trip ─────────────────────────────────────────────────────

def test_snapshots_round_trip():
    result = _minimal_result()
    store = _store_with()
    exported = SimulationExporter(result, store).export()["snapshots"]
    assert exported[0] == {"step": 0, "t": 0.0, "n_alive": 1, "n_dead_cumulative": 0}
    assert exported[1] == {"step": 10, "t": 0.5, "n_alive": 1, "n_dead_cumulative": 0}


# ── Clonal fractions ─────────────────────────────────────────────────────────

def test_clonal_fractions_wt_only():
    """No drivers → all cells in wt clone."""
    # 3 founders dividing once each → 6 alive cells
    result = SimulationResult()
    result.stop_reason = "max_steps"
    result.divisions = [
        DivisionEvent(step=1, parent_id=0, child_id=3),
        DivisionEvent(step=1, parent_id=1, child_id=4),
        DivisionEvent(step=1, parent_id=2, child_id=5),
    ]
    result.snapshots = [
        Snapshot(step=0, t=0.0, n_alive=3, n_dead_cumulative=0),
        Snapshot(step=5, t=0.5, n_alive=6, n_dead_cumulative=0),
    ]
    store = _store_with()
    fracs = SimulationExporter(result, store).export()["clonal_fractions"]

    assert fracs[0]["wt"] == 3
    assert fracs[1]["wt"] == 6


def test_clonal_fractions_with_driver():
    """Cell acquires a driver: from that snapshot onward it forms its own clone."""
    # Founder=0, divides at step 1 → child=1.  Child acquires driver mut=10 at step 3.
    result = SimulationResult()
    result.stop_reason = "max_cells"
    result.divisions = [DivisionEvent(step=1, parent_id=0, child_id=1)]
    result.drivers   = [DriverEvent(step=3, cell_id=1, mutation_id=10)]
    result.snapshots = [
        Snapshot(step=0, t=0.0, n_alive=1, n_dead_cumulative=0),
        Snapshot(step=2, t=0.1, n_alive=2, n_dead_cumulative=0),  # before driver
        Snapshot(step=5, t=0.3, n_alive=2, n_dead_cumulative=0),  # after driver
    ]
    store = _store_with(
        MutationRecord(10, gene_name="BRAF", effect="GOF", is_driver=True)
    )
    fracs = SimulationExporter(result, store).export()["clonal_fractions"]

    # step 0: only founder alive
    assert fracs[0]["wt"] == 1
    assert "10_0" not in fracs[0]

    # step 2: both cells alive, no driver yet
    assert fracs[1]["wt"] == 2
    assert fracs[1].get("10_0", 0) == 0

    # step 5: cell 1 now in clone "10_0" (first acquisition of mut 10), cell 0 still wt
    assert fracs[2]["wt"] == 1
    assert fracs[2]["10_0"] == 1


# ── Clone tree ────────────────────────────────────────────────────────────────

def test_clone_tree_single_driver():
    result = SimulationResult()
    result.stop_reason = "max_cells"
    result.divisions = [DivisionEvent(step=1, parent_id=0, child_id=1)]
    result.drivers   = [DriverEvent(step=3, cell_id=1, mutation_id=10)]
    result.snapshots = [
        Snapshot(step=0, t=0.0, n_alive=1, n_dead_cumulative=0),
        Snapshot(step=5, t=0.5, n_alive=2, n_dead_cumulative=0),
    ]
    store = _store_with(
        MutationRecord(10, gene_name="BRAF", effect="GOF", is_driver=True)
    )
    tree = SimulationExporter(result, store).export()["clone_tree"]

    node_ids = {n["id"] for n in tree["nodes"]}
    assert "wt" in node_ids
    assert "10_0" in node_ids

    # wt node has correct fields
    wt_node = next(n for n in tree["nodes"] if n["id"] == "wt")
    assert wt_node["acq_step"] == 0
    assert wt_node["acq_t"] == 0.0

    # driver node acquired at step 3; clone ID encodes acquisition index
    driver_node = next(n for n in tree["nodes"] if n["id"] == "10_0")
    assert driver_node["acq_step"] == 3
    assert driver_node["gene"] == "BRAF"
    assert driver_node["effect"] == "GOF"
    assert driver_node["mutation_id"] == 10

    # edge: wt → 10_0
    assert tree["edges"] == [{"parent": "wt", "child": "10_0"}]


def test_clone_tree_nested_drivers():
    """Cell A acquires mut 10 (wt→10). A child acquires mut 20 (10→20)."""
    result = SimulationResult()
    result.stop_reason = "max_cells"
    # 0 is founder; 0 divides → 1; 1 acquires 10; 1 divides → 2; 2 acquires 20
    result.divisions = [
        DivisionEvent(step=1, parent_id=0, child_id=1),
        DivisionEvent(step=5, parent_id=1, child_id=2),
    ]
    result.drivers = [
        DriverEvent(step=3, cell_id=1, mutation_id=10),
        DriverEvent(step=7, cell_id=2, mutation_id=20),
    ]
    result.snapshots = [
        Snapshot(step=0,  t=0.0, n_alive=1, n_dead_cumulative=0),
        Snapshot(step=10, t=1.0, n_alive=3, n_dead_cumulative=0),
    ]
    store = _store_with(
        MutationRecord(10, gene_name="NRAS", effect="GOF", is_driver=True),
        MutationRecord(20, gene_name="BRAF", effect="GOF", is_driver=True),
    )
    tree = SimulationExporter(result, store).export()["clone_tree"]

    edges = {(e["parent"], e["child"]) for e in tree["edges"]}
    assert ("wt", "10_0") in edges
    # cell 2 inherited clone 10_0 from cell 1 before acquiring mut 20 → parent clone is "10_0"
    assert ("10_0", "20_0") in edges


def test_clone_tree_independent_drivers():
    """Two cells independently acquire drivers → both children of wt."""
    result = SimulationResult()
    result.stop_reason = "max_cells"
    # founders: 0, 1 (both parents, neither is a child)
    result.divisions = [
        DivisionEvent(step=1, parent_id=0, child_id=2),
        DivisionEvent(step=1, parent_id=1, child_id=3),
    ]
    result.drivers = [
        DriverEvent(step=3, cell_id=2, mutation_id=10),
        DriverEvent(step=3, cell_id=3, mutation_id=20),
    ]
    result.snapshots = [
        Snapshot(step=0, t=0.0, n_alive=2, n_dead_cumulative=0),
        Snapshot(step=5, t=0.5, n_alive=4, n_dead_cumulative=0),
    ]
    store = _store_with(
        MutationRecord(10, gene_name="BRAF", effect="GOF", is_driver=True),
        MutationRecord(20, gene_name="NRAS", effect="GOF", is_driver=True),
    )
    tree = SimulationExporter(result, store).export()["clone_tree"]
    edges = {(e["parent"], e["child"]) for e in tree["edges"]}
    assert ("wt", "10_0") in edges
    assert ("wt", "20_0") in edges


# ── Final sizes ──────────────────────────────────────────────────────────────

def test_final_sizes():
    """final_size in clone_tree nodes reflects surviving cell counts."""
    result = SimulationResult()
    result.stop_reason = "max_cells"
    # founder=0, divides twice → children 1,2; child 1 acquires driver 10
    result.divisions = [
        DivisionEvent(step=1, parent_id=0, child_id=1),
        DivisionEvent(step=1, parent_id=0, child_id=2),
    ]
    result.drivers = [DriverEvent(step=3, cell_id=1, mutation_id=10)]
    result.snapshots = [
        Snapshot(step=0, t=0.0, n_alive=1, n_dead_cumulative=0),
        Snapshot(step=5, t=0.5, n_alive=3, n_dead_cumulative=0),
    ]
    store = _store_with(MutationRecord(10, gene_name="BRAF", effect="GOF"))
    tree = SimulationExporter(result, store).export()["clone_tree"]

    wt_node     = next(n for n in tree["nodes"] if n["id"] == "wt")
    driver_node = next(n for n in tree["nodes"] if n["id"] == "10_0")
    # cells 0 and 2 in wt; cell 1 in clone 10_0
    assert wt_node["final_size"] == 2
    assert driver_node["final_size"] == 1


def test_independent_acquisitions_same_mutation_create_distinct_clones():
    """Two lineages independently acquiring the same mutation_id are separate clones."""
    result = SimulationResult()
    result.stop_reason = "max_cells"
    # Two founders (0, 1); each divides → children (2, 3); each child acquires mut 10
    result.divisions = [
        DivisionEvent(step=1, parent_id=0, child_id=2),
        DivisionEvent(step=1, parent_id=1, child_id=3),
    ]
    result.drivers = [
        DriverEvent(step=3, cell_id=2, mutation_id=10),
        DriverEvent(step=3, cell_id=3, mutation_id=10),  # same mutation, different lineage
    ]
    result.snapshots = [
        Snapshot(step=0, t=0.0, n_alive=2, n_dead_cumulative=0),
        Snapshot(step=5, t=0.5, n_alive=4, n_dead_cumulative=0),
    ]
    store = _store_with(MutationRecord(10, gene_name="BRAF", effect="GOF", is_driver=True))
    exported = SimulationExporter(result, store).export()

    tree = exported["clone_tree"]
    node_ids = {n["id"] for n in tree["nodes"]}
    # Two distinct clone events even though mutation_id is the same
    assert "10_0" in node_ids
    assert "10_1" in node_ids

    edges = {(e["parent"], e["child"]) for e in tree["edges"]}
    assert ("wt", "10_0") in edges
    assert ("wt", "10_1") in edges

    fracs = exported["clonal_fractions"]
    final = fracs[-1]
    # Founders 0 and 1 remain in wt; children 2 and 3 are in distinct BRAF clones
    assert final["wt"] == 2
    assert final.get("10_0", 0) == 1
    assert final.get("10_1", 0) == 1


# ── JSON serialisability ─────────────────────────────────────────────────────

def test_save_round_trip(tmp_path: Path):
    result = _minimal_result()
    store = _store_with()
    path = tmp_path / "run.evoseer.json"
    SimulationExporter(result, store).save(path)
    loaded = json.loads(path.read_text())
    assert "metadata" in loaded
    assert "clonal_fractions" in loaded
    assert "clone_tree" in loaded
