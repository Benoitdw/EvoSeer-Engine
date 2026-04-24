"""Tests for ConstantMutationRatePlugin."""

from __future__ import annotations

import pytest

from evoseer.core.cell import CellState, PluginState
from evoseer.plugins.mutation_rate import ConstantMutationRatePlugin


def test_returns_configured_mu(store, ctx):
    plugin = ConstantMutationRatePlugin(params={"mu": 0.7}, store=store)
    assert plugin.compute_score(CellState(), ctx) == pytest.approx(0.7)


def test_default_mu_when_param_absent(store, ctx):
    plugin = ConstantMutationRatePlugin(params={}, store=store)
    assert plugin.compute_score(CellState(), ctx) == pytest.approx(0.5)


def test_score_independent_of_mutations(store, ctx):
    plugin = ConstantMutationRatePlugin(params={"mu": 1.0}, store=store)
    assert plugin.compute_score(CellState(mutations={1, 2, 3}), ctx) == pytest.approx(1.0)


def test_default_init_state_is_dirty(store, ctx):
    plugin = ConstantMutationRatePlugin(params={"mu": 1.0}, store=store)
    ps = plugin.init_state(CellState(), ctx)
    assert isinstance(ps, PluginState)
    assert ps._dirty is True


def test_on_division_child_inherits_score(store, ctx):
    plugin = ConstantMutationRatePlugin(params={"mu": 1.0}, store=store)
    parent_state = CellState()
    ps = plugin.init_state(parent_state, ctx)
    ps._cached_score = 1.0
    ps._dirty = False
    parent_state.plugin_states[plugin.name] = ps

    child_ps = plugin.on_division(parent_state, ctx)

    assert child_ps._cached_score == pytest.approx(1.0)
    assert child_ps._dirty is False


def test_get_param_raises_on_missing_required(store):
    plugin = ConstantMutationRatePlugin(params={}, store=store)
    with pytest.raises(KeyError, match="required_field"):
        plugin.get_param("required_field")


def test_get_param_returns_default(store):
    plugin = ConstantMutationRatePlugin(params={}, store=store)
    assert plugin.get_param("missing", default=99) == 99


def test_get_extra_raises_on_missing_key(store, ctx):
    plugin = ConstantMutationRatePlugin(params={}, store=store)
    record = store.get(1)
    with pytest.raises(KeyError, match="nonexistent"):
        plugin.get_extra(record, "nonexistent")
