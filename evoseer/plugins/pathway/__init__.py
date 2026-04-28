"""PathwayPlugin ABC and PathwayDefinition — base for all pathway-level plugins."""

from __future__ import annotations

import math
from abc import ABC
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml

from evoseer.core.cell import CellState
from evoseer.core.context import SimContext
from evoseer.plugins.base import FeaturePlugin
from evoseer.services.mutation_store import MutationStore


@dataclass
class NodeDef:
    weight: float
    gene_id: int | None = None


@dataclass
class EdgeDef:
    from_node: str
    to_node: str
    type: Literal["activates", "inhibits"]


@dataclass
class PathwayDefinition:
    name: str
    output_node: str
    sigmoid_slope: float
    sigmoid_threshold: float
    nodes: dict[str, NodeDef]
    edges: list[EdgeDef]
    suppressors: dict[str, NodeDef] = field(default_factory=dict)
    kegg_id: str | None = None
    description: str = ""

    @classmethod
    def load(cls, path: Path) -> PathwayDefinition:
        with open(path) as f:
            data = yaml.safe_load(f)

        nodes = {
            name: NodeDef(
                gene_id=attrs.get("gene_id"),
                weight=float(attrs["weight"]),
            )
            for name, attrs in data["nodes"].items()
        }
        edges = [
            EdgeDef(from_node=e["from"], to_node=e["to"], type=e["type"])
            for e in data["edges"]
        ]
        suppressors = {
            name: NodeDef(
                gene_id=attrs.get("gene_id"),
                weight=float(attrs["weight"]),
            )
            for name, attrs in data.get("suppressors", {}).items()
        }
        return cls(
            name=data["name"],
            kegg_id=data.get("kegg_id"),
            description=data.get("description", ""),
            output_node=data["output_node"],
            sigmoid_slope=float(data["sigmoid"]["slope"]),
            sigmoid_threshold=float(data["sigmoid"]["threshold"]),
            nodes=nodes,
            edges=edges,
            suppressors=suppressors,
        )


def _parity_to_output(
    start: str,
    output: str,
    adj: dict[str, list[tuple[str, str]]],
) -> int | None:
    """DFS from start to output counting inhibit-edge parity on first found path."""
    if start == output:
        return 0
    stack = [(start, 0, frozenset({start}))]
    while stack:
        current, inhibits, visited = stack.pop()
        for neighbor, edge_type in adj.get(current, []):
            if neighbor in visited:
                continue
            new_inhibits = inhibits + (1 if edge_type == "inhibits" else 0)
            if neighbor == output:
                return new_inhibits % 2
            stack.append((neighbor, new_inhibits, visited | {neighbor}))
    return None


def derive_roles(
    definition: PathwayDefinition,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Derive act_R and inh_R from DAG topology.

    Even parity of inhibit edges to output_node → activator (GOF drives pathway).
    Odd parity → inhibitor (LOF drives pathway via disinhibition).

    Returns (act_weights, inh_weights) keyed by gene_name.
    """
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in definition.edges:
        adj[edge.from_node].append((edge.to_node, edge.type))

    act: dict[str, float] = {}
    inh: dict[str, float] = {}
    for node_name, node_def in definition.nodes.items():
        parity = _parity_to_output(node_name, definition.output_node, adj)
        if parity is None:
            continue
        if parity % 2 == 0:
            act[node_name] = node_def.weight
        else:
            inh[node_name] = node_def.weight

    return act, inh


class PathwayPlugin(FeaturePlugin, ABC):
    """
    Abstract base for pathway-level feature plugins.

    Subclasses define:
        name              -- unique string identifier
        pathway_file      -- Path to the YAML definition
        involved_pathways -- pathway names for dirty-flag triggering
    """

    pathway_file: ClassVar[Path]

    def __init__(self, params: dict[str, Any], store: MutationStore) -> None:
        super().__init__(params, store)
        self._definition = PathwayDefinition.load(self.pathway_file)
        self._act, self._inh = derive_roles(self._definition)
        self._act_by_id: dict[int, float] = {
            self._definition.nodes[n].gene_id: w
            for n, w in self._act.items()
            if self._definition.nodes[n].gene_id is not None
        }
        self._inh_by_id: dict[int, float] = {
            self._definition.nodes[n].gene_id: w
            for n, w in self._inh.items()
            if self._definition.nodes[n].gene_id is not None
        }
        # Suppressors: LOF subtracts from weighted sum (e.g. CDKN2A in OIS)
        self._suppressor_by_id: dict[int, float] = {
            nd.gene_id: nd.weight
            for nd in self._definition.suppressors.values()
            if nd.gene_id is not None
        }
        self._suppressor_by_name: dict[str, float] = {
            name: nd.weight
            for name, nd in self._definition.suppressors.items()
        }

    def compute_score(self, cell_state: CellState, ctx: SimContext) -> float:
        """P_R = σ_R( Σ w·x^GOF_act  −  Σ w·x^LOF_inh )"""
        weighted_sum = 0.0
        for mut_id in cell_state.mutations:
            try:
                record = self._store.get(mut_id)
            except KeyError:
                continue
            if record.effect is None:
                continue
            if record.gene_id is not None:
                if record.effect == "GOF":
                    weighted_sum += self._act_by_id.get(record.gene_id, 0.0)
                elif record.effect == "LOF":
                    weighted_sum += self._inh_by_id.get(record.gene_id, 0.0)
                    weighted_sum -= self._suppressor_by_id.get(record.gene_id, 0.0)
            elif record.gene_name is not None:
                if record.effect == "GOF":
                    weighted_sum += self._act.get(record.gene_name, 0.0)
                elif record.effect == "LOF":
                    weighted_sum += self._inh.get(record.gene_name, 0.0)
                    weighted_sum -= self._suppressor_by_name.get(record.gene_name, 0.0)
        return self._sigmoid(weighted_sum)

    def _sigmoid(self, x: float) -> float:
        d = self._definition
        return 1.0 / (1.0 + math.exp(-d.sigmoid_slope * (x - d.sigmoid_threshold)))
