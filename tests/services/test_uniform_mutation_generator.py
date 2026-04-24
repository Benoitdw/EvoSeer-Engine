"""Tests for UniformMutationGenerator."""

from __future__ import annotations

import pytest

from evoseer.services.mutation_generator import UniformMutationGenerator


def test_returns_valid_mutation_ids(store):
    gen = UniformMutationGenerator(store=store, params={"seed": 42})
    ids = gen.generate(mu=10.0)
    assert all(mid in store.all_ids() for mid in ids)


def test_zero_mu_returns_empty(store):
    gen = UniformMutationGenerator(store=store, params={"seed": 42})
    assert gen.generate(mu=0.0) == []


def test_negative_mu_returns_empty(store):
    gen = UniformMutationGenerator(store=store, params={"seed": 42})
    assert gen.generate(mu=-1.0) == []


def test_deterministic_with_same_seed(store):
    gen1 = UniformMutationGenerator(store=store, params={"seed": 7})
    gen2 = UniformMutationGenerator(store=store, params={"seed": 7})
    assert gen1.generate(mu=3.0) == gen2.generate(mu=3.0)


def test_different_seeds_produce_different_results(store):
    gen1 = UniformMutationGenerator(store=store, params={"seed": 1})
    gen2 = UniformMutationGenerator(store=store, params={"seed": 2})
    # With high mu, results are very unlikely to be identical
    results = [gen1.generate(mu=20.0) == gen2.generate(mu=20.0) for _ in range(10)]
    assert not all(results)
