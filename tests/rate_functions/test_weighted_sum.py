"""Tests for WeightedSumRate."""

from __future__ import annotations

import pytest

from evoseer.core.config import PluginConfig, RateFunctionConfig
from evoseer.rate_functions.weighted_sum import WeightedSumRate


def _pc(name: str, category: str, weight: float = 1.0, alpha: float = 0.0) -> PluginConfig:
    return PluginConfig(name=name, plugin_type=name, target="rate_function",
                        category=category, weight=weight, alpha=alpha)


def _rate_fn(baseline_birth: float = 0.0, baseline_death: float = 0.0) -> WeightedSumRate:
    return WeightedSumRate(RateFunctionConfig(
        function_type="weighted_sum",
        baseline_birth_rate=baseline_birth,
        baseline_death_rate=baseline_death,
    ))


def test_baseline_only():
    b, d = _rate_fn(baseline_birth=1.0, baseline_death=0.5).compute_rates({}, {}, N=10)
    assert b == pytest.approx(1.0)
    assert d == pytest.approx(0.5)


def test_proliferative_adds_to_birth():
    b, d = _rate_fn().compute_rates({"p": 2.0}, {"p": _pc("p", "proliferative", weight=3.0)}, N=1)
    assert b == pytest.approx(6.0)
    assert d == pytest.approx(0.0)


def test_deleterious_adds_to_death():
    b, d = _rate_fn().compute_rates({"p": 2.0}, {"p": _pc("p", "deleterious", weight=3.0)}, N=1)
    assert b == pytest.approx(0.0)
    assert d == pytest.approx(6.0)


def test_density_dependence_alpha_1():
    b, d = _rate_fn().compute_rates({"p": 0.1}, {"p": _pc("p", "deleterious", alpha=1.0)}, N=50)
    assert d == pytest.approx(0.1 * 50)


def test_density_dependence_alpha_2():
    b, d = _rate_fn().compute_rates({"p": 1.0}, {"p": _pc("p", "deleterious", alpha=2.0)}, N=4)
    assert d == pytest.approx(1.0 * 4 ** 2)


def test_rates_clamped_to_zero():
    b, d = _rate_fn(baseline_birth=-10.0, baseline_death=-10.0).compute_rates({}, {}, N=1)
    assert b == pytest.approx(0.0)
    assert d == pytest.approx(0.0)


def test_unknown_plugin_in_scores_ignored():
    b, d = _rate_fn(baseline_birth=1.0).compute_rates({"ghost": 99.0}, {}, N=1)
    assert b == pytest.approx(1.0)


def test_multiple_plugins():
    scores = {"birth1": 1.0, "birth2": 2.0, "death1": 0.5}
    pcs = {
        "birth1": _pc("birth1", "proliferative"),
        "birth2": _pc("birth2", "proliferative"),
        "death1": _pc("death1", "deleterious"),
    }
    b, d = _rate_fn().compute_rates(scores, pcs, N=1)
    assert b == pytest.approx(3.0)
    assert d == pytest.approx(0.5)
