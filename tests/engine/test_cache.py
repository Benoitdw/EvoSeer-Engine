"""Tests for the engine's dirty/cache and pathway-recompute mechanism."""

from __future__ import annotations

import pytest

from evoseer.core.config import PluginConfig

from tests.conftest import FixedMutationGenerator, SumExtraPlugin


def _pc(name: str = "sum_extra") -> PluginConfig:
    return PluginConfig(name=name, plugin_type=name, target="rate_function", category="proliferative")


def test_child_plugin_marked_dirty_when_pathway_mutation_acquired(store, ctx, engine_factory):
    """After a division introducing mutation 1 (pathway_A), child plugin watching pathway_A must be dirty."""
    plugin = SumExtraPlugin(params={}, store=store, field="b", pathways=["pathway_A"])
    engine = engine_factory(
        plugins={"sum_extra": plugin},
        plugin_configs={"sum_extra": _pc()},
        generator=FixedMutationGenerator(store, {"ids": [1]}),
    )

    parent = engine.make_founder_cell()
    parent.state.mutations = {3}
    engine._cells[parent.id] = parent

    ps = plugin.init_state(parent.state, ctx)
    ps._cached_score = plugin.compute_score(parent.state, ctx)
    ps._dirty = False
    parent.state.plugin_states["sum_extra"] = ps

    engine._execute_division(parent, step=1, ctx=ctx)

    child = next(c for c in engine._cells.values() if c.id != parent.id)
    assert child.state.plugin_states["sum_extra"]._dirty is True


def test_child_not_dirty_when_mutation_outside_pathway(store, ctx, engine_factory):
    """After a division introducing mutation 3 (pathway_B), child plugin watching only pathway_A must NOT be dirty."""
    plugin = SumExtraPlugin(params={}, store=store, field="b", pathways=["pathway_A"])
    engine = engine_factory(
        plugins={"sum_extra": plugin},
        plugin_configs={"sum_extra": _pc()},
        generator=FixedMutationGenerator(store, {"ids": [3]}),
    )

    parent = engine.make_founder_cell()
    engine._cells[parent.id] = parent

    ps = plugin.init_state(parent.state, ctx)
    ps._cached_score = 0.0
    ps._dirty = False
    parent.state.plugin_states["sum_extra"] = ps

    engine._execute_division(parent, step=1, ctx=ctx)

    child = next(c for c in engine._cells.values() if c.id != parent.id)
    child_ps = child.state.plugin_states["sum_extra"]
    assert child_ps._dirty is False
    assert child_ps._cached_score == pytest.approx(0.0)


def test_parent_also_marked_dirty_after_pathway_mutation(store, ctx, engine_factory):
    """Parent plugin state must also be dirty after acquiring a mutation in a watched pathway."""
    plugin = SumExtraPlugin(params={}, store=store, field="b", pathways=["pathway_A"])
    engine = engine_factory(
        plugins={"sum_extra": plugin},
        plugin_configs={"sum_extra": _pc()},
        generator=FixedMutationGenerator(store, {"ids": [1]}),
    )

    parent = engine.make_founder_cell()
    engine._cells[parent.id] = parent

    ps = plugin.init_state(parent.state, ctx)
    ps._cached_score = 0.0
    ps._dirty = False
    parent.state.plugin_states["sum_extra"] = ps

    engine._execute_division(parent, step=1, ctx=ctx)

    assert parent.state.plugin_states["sum_extra"]._dirty is True
