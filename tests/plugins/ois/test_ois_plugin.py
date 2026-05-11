"""Unit tests for OISPlugin and OISPluginState."""

from __future__ import annotations

from pathlib import Path

from evoseer.core.cell import CellState
from evoseer.core.context import SimContext
from evoseer.plugins.ois import OISPlugin, OISPluginState
from evoseer.services.mutation_store import InMemoryMutationStore, MutationRecord


# ── Test plugin with stable test YAML ──────────────────────────────────────────

class _TestOISPlugin(OISPlugin):
    """OIS plugin that uses tests/data/ois_test.yaml (threshold=0 for σ(0)=0.5)."""
    name = "test_ois"
    pathway_file = Path(__file__).parents[2] / "data" / "ois_test.yaml"
    involved_pathways = ["OIS"]


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _store() -> InMemoryMutationStore:
    s = InMemoryMutationStore()
    s.add_mutation(MutationRecord(1, gene_id=673,  gene_name="BRAF",   effect="GOF",
                                  pathways=["OIS"], is_driver=True))
    s.add_mutation(MutationRecord(2, gene_id=1029, gene_name="CDKN2A", effect="LOF",
                                  pathways=["OIS"], is_driver=True))
    s.add_mutation(MutationRecord(3, gene_id=7157, gene_name="TP53",   effect="LOF",
                                  pathways=["OIS"], is_driver=True))
    s.add_mutation(MutationRecord(4, gene_id=9999, gene_name="OTHER",  effect="GOF",
                                  pathways=[], is_driver=False))
    return s


def _plugin() -> _TestOISPlugin:
    return _TestOISPlugin({}, _store())


def _ctx() -> SimContext:
    return SimContext(t=0.0, step=0, N=10)


def _state_with(*mut_ids: int) -> CellState:
    return CellState(mutations=set(mut_ids))


# ── S_i scoring ───────────────────────────────────────────────────────────────

def test_wt_score_is_half():
    """WT cell: A=0, threshold=0 → S_i = σ(0) = 0.5."""
    plugin = _plugin()
    state = _state_with()
    assert abs(plugin.compute_score(state, _ctx()) - 0.5) < 1e-6


def test_braf_gof_increases_score():
    """BRAF GOF adds to weighted sum → S_i > 0.5."""
    plugin = _plugin()
    assert plugin.compute_score(_state_with(1), _ctx()) > 0.5


def test_cdkn2a_lof_decreases_score():
    """CDKN2A LOF is a suppressor → subtracts → S_i < 0.5."""
    plugin = _plugin()
    assert plugin.compute_score(_state_with(2), _ctx()) < 0.5


def test_braf_plus_cdkn2a_lof_near_zero():
    """BRAF GOF (w=0.50) + CDKN2A LOF suppressor (w=1.50) → A = −1.0 → S_i ≈ 0.07."""
    plugin = _plugin()
    score = plugin.compute_score(_state_with(1, 2), _ctx())
    assert score < 0.2


def test_unrelated_mutation_no_effect():
    """Mutation in a non-OIS gene does not change score."""
    plugin = _plugin()
    s0 = plugin.compute_score(_state_with(), _ctx())
    s1 = plugin.compute_score(_state_with(4), _ctx())
    assert abs(s0 - s1) < 1e-9


# ── OISPluginState init and division ─────────────────────────────────────────

def test_init_state_defaults():
    plugin = _plugin()
    state = _state_with()
    ps = plugin.init_state(state, _ctx())
    assert isinstance(ps, OISPluginState)
    assert ps.k == 0
    assert ps.t_trigger is None
    assert ps.is_senescent is False


def test_on_division_increments_k():
    """Both parent and child get k+1 after division."""
    plugin = _plugin()
    parent_state = _state_with()
    ps = OISPluginState(k=3, t_trigger=10)
    parent_state.plugin_states[plugin.name] = ps

    child_ps = plugin.on_division(parent_state, _ctx())

    assert ps.k == 4           # parent incremented
    assert child_ps.k == 4    # child gets same value


def test_on_division_preserves_trigger():
    plugin = _plugin()
    parent_state = _state_with()
    parent_state.plugin_states[plugin.name] = OISPluginState(k=5, t_trigger=42)

    child_ps = plugin.on_division(parent_state, _ctx())
    assert child_ps.t_trigger == 42


def test_on_division_child_not_senescent():
    """Children are never born senescent."""
    plugin = _plugin()
    parent_state = _state_with()
    parent_state.plugin_states[plugin.name] = OISPluginState(k=2, is_senescent=True)

    child_ps = plugin.on_division(parent_state, _ctx())
    assert child_ps.is_senescent is False


# ── on_mutation_acquired ──────────────────────────────────────────────────────

def test_ois_triggering_mutation_resets_k():
    """Acquiring BRAF GOF resets k to 0 and sets t_trigger."""
    plugin = _plugin()
    state = _state_with()
    ps = OISPluginState(k=10, t_trigger=5)
    state.plugin_states[plugin.name] = ps

    plugin.on_mutation_acquired(1, state, step=99)  # BRAF GOF

    assert ps.k == 0
    assert ps.t_trigger == 99


def test_non_triggering_mutation_no_reset():
    """Non-OIS-act mutations do not reset k."""
    plugin = _plugin()
    state = _state_with()
    ps = OISPluginState(k=7, t_trigger=5)
    state.plugin_states[plugin.name] = ps

    plugin.on_mutation_acquired(4, state, step=20)  # OTHER gene

    assert ps.k == 7


def test_suppressor_lof_does_not_reset_k():
    """CDKN2A LOF (suppressor, not act_R) does not reset k."""
    plugin = _plugin()
    state = _state_with()
    ps = OISPluginState(k=5, t_trigger=3)
    state.plugin_states[plugin.name] = ps

    plugin.on_mutation_acquired(2, state, step=20)  # CDKN2A LOF

    assert ps.k == 5


# ── compute_senescence_probability ─────────────────────────────────────────────────

def test_hazard_zero_before_trigger():
    """No trigger yet → λ_i^OIS = 0."""
    plugin = _plugin()
    state = _state_with(1)  # BRAF GOF
    ps = OISPluginState(k=10, t_trigger=None)
    ps._cached_score = 0.88
    ps._dirty = False
    state.plugin_states[plugin.name] = ps

    assert plugin.compute_senescence_probability(state, _ctx()) == 0.0


def test_hazard_zero_at_k_zero():
    """Hill(0, K, n) = 0 → no hazard immediately after trigger."""
    plugin = _plugin()
    state = _state_with(1)
    ps = OISPluginState(k=0, t_trigger=5)
    ps._cached_score = 0.88
    ps._dirty = False
    state.plugin_states[plugin.name] = ps

    assert plugin.compute_senescence_probability(state, _ctx()) == 0.0


def test_hazard_increases_with_k():
    """Hazard is monotonically increasing in k."""
    plugin = _plugin()
    state = _state_with(1)

    hazards = []
    for k in [1, 5, 10, 20, 50]:
        ps = OISPluginState(k=k, t_trigger=0)
        ps._cached_score = 0.88
        ps._dirty = False
        state.plugin_states[plugin.name] = ps
        hazards.append(plugin.compute_senescence_probability(state, _ctx()))

    assert all(hazards[i] < hazards[i + 1] for i in range(len(hazards) - 1))


def test_hazard_zero_when_already_senescent():
    plugin = _plugin()
    state = _state_with(1)
    ps = OISPluginState(k=50, t_trigger=0, is_senescent=True)
    ps._cached_score = 0.88
    ps._dirty = False
    state.plugin_states[plugin.name] = ps

    assert plugin.compute_senescence_probability(state, _ctx()) == 0.0


def test_hazard_zero_with_low_si():
    """CDKN2A LOF drives S_i → 0, hazard → 0."""
    plugin = _plugin()
    state = _state_with(2)  # CDKN2A LOF only
    ps = OISPluginState(k=20, t_trigger=0)
    # Cache the actual S_i
    ps._cached_score = plugin.compute_score(state, _ctx())
    ps._dirty = False
    state.plugin_states[plugin.name] = ps

    hazard = plugin.compute_senescence_probability(state, _ctx())
    assert hazard < 0.01  # nearly zero


# ── on_senescence ─────────────────────────────────────────────────────────────

def test_on_senescence_sets_flag():
    plugin = _plugin()
    state = _state_with()
    ps = OISPluginState(k=20, t_trigger=0)
    state.plugin_states[plugin.name] = ps

    plugin.on_senescence(state)

    assert ps.is_senescent is True


# ── ois_overrides ─────────────────────────────────────────────────────────────

def _plugin_with(**ois_overrides) -> _TestOISPlugin:
    return _TestOISPlugin({"ois_overrides": ois_overrides}, _store())


def test_ois_override_lambda0():
    """ois_overrides.lambda_0 replaces the YAML value."""
    plugin = _plugin_with(lambda_0=1.5)
    assert plugin._ois_lambda_0 == 1.5


def test_ois_override_K0():
    plugin = _plugin_with(K_0=3.0)
    assert plugin._ois_K == 3.0


def test_ois_override_n():
    plugin = _plugin_with(n=8.0)
    assert plugin._ois_n == 8.0


def test_ois_override_raises_hazard():
    """Higher lambda_0 produces a larger senescence hazard for the same cell state."""
    state = _state_with(1)  # BRAF GOF
    ps = OISPluginState(k=10, t_trigger=0)
    ps._cached_score = 0.88
    ps._dirty = False

    plugin_low  = _plugin_with(lambda_0=0.1)
    plugin_high = _plugin_with(lambda_0=2.0)

    state_low  = _state_with(1)
    state_low.plugin_states[plugin_low.name]  = OISPluginState(k=10, t_trigger=0)
    state_low.plugin_states[plugin_low.name]._cached_score = 0.88
    state_low.plugin_states[plugin_low.name]._dirty = False

    state_high = _state_with(1)
    state_high.plugin_states[plugin_high.name] = OISPluginState(k=10, t_trigger=0)
    state_high.plugin_states[plugin_high.name]._cached_score = 0.88
    state_high.plugin_states[plugin_high.name]._dirty = False

    assert (plugin_high.compute_senescence_probability(state_high, _ctx()) >
            plugin_low.compute_senescence_probability(state_low, _ctx()))


def test_ois_override_does_not_affect_default():
    """Overriding on one instance does not bleed into a fresh instance."""
    _ = _plugin_with(lambda_0=99.0, K_0=99.0, n=99.0)
    fresh = _plugin()
    assert fresh._ois_lambda_0 != 99.0
    assert fresh._ois_K != 99.0
    assert fresh._ois_n != 99.0
