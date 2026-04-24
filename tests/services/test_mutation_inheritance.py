"""Tests for child/parent mutation inheritance via the engine."""

from __future__ import annotations

from tests.conftest import FixedMutationGenerator


def test_child_mutations_superset_of_parent(store, ctx, engine_factory):
    gen = FixedMutationGenerator(store, {"ids": [2]})
    engine = engine_factory(generator=gen)

    parent = engine.make_founder_cell()
    parent.state.mutations = {1, 3}
    engine._cells[parent.id] = parent

    engine._execute_division(parent, step=1, ctx=ctx)

    child = next(c for c in engine._cells.values() if c.id != parent.id)
    assert {1, 3} <= child.state.mutations


def test_child_acquires_new_mutations(store, ctx, engine_factory):
    gen = FixedMutationGenerator(store, {"ids": [2]})
    engine = engine_factory(generator=gen)

    parent = engine.make_founder_cell()
    parent.state.mutations = {1}
    engine._cells[parent.id] = parent

    engine._execute_division(parent, step=1, ctx=ctx)

    child = next(c for c in engine._cells.values() if c.id != parent.id)
    assert 2 in child.state.mutations


def test_no_new_mutations_when_generator_empty(store, ctx, engine_factory):
    gen = FixedMutationGenerator(store, {"ids": []})
    engine = engine_factory(generator=gen)

    parent = engine.make_founder_cell()
    parent.state.mutations = {1, 3}
    engine._cells[parent.id] = parent

    engine._execute_division(parent, step=1, ctx=ctx)

    child = next(c for c in engine._cells.values() if c.id != parent.id)
    assert child.state.mutations == {1, 3}
