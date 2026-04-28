"""
Theses two plugins are toy's plugins that allows to give an advantage or disavantage to cell based or their b or d properties.
"""

from __future__ import annotations


from evoseer.core.cell import CellState
from evoseer.core.context import SimContext
from evoseer.plugins.base import FeaturePlugin


class DummyDeathPlugin(FeaturePlugin):
    """Reads 'd' from each mutation's extra dict. Score = Σ d_mut across carried mutations."""
    name = "dummy_death"
    involved_pathways = []

    def compute_score(self, cell_state: CellState, ctx: SimContext) -> float:
        total = 0.0
        for mid in cell_state.mutations:
            try:
                total += self._store.get(mid).extra.get("d", 0.0)
            except KeyError:
                pass
        return total
    
class DummyBirthPlugin(FeaturePlugin):
    """Reads 'b' from each mutation's extra dict. Score = Σ d_mut across carried mutations."""
    name = "dummy_birth"
    involved_pathways = []

    def compute_score(self, cell_state: CellState, ctx: SimContext) -> float:
        total = 0.0
        for mid in cell_state.mutations:
            try:
                total += self._store.get(mid).extra.get("b", 0.0)
            except KeyError:
                pass
        return total