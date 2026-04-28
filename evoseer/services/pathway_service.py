"""PathwayService — maps gene annotations to pathway membership."""

from __future__ import annotations

from pathlib import Path

from evoseer.plugins.pathway import PathwayDefinition


class PathwayService:
    """
    Loaded from all pathway YAMLs in a directory.
    Injected wherever MutationRecords are created to populate the pathways field.
    """

    def __init__(self, pathway_dir: Path) -> None:
        self._by_gene_id: dict[int, list[str]] = {}
        self._by_gene_name: dict[str, list[str]] = {}

        for yaml_path in sorted(pathway_dir.glob("*.yaml")):
            defn = PathwayDefinition.load(yaml_path)
            for gene_name, node_def in defn.nodes.items():
                self._by_gene_name.setdefault(gene_name, []).append(defn.name)
                if node_def.gene_id is not None:
                    self._by_gene_id.setdefault(node_def.gene_id, []).append(defn.name)

    def get_pathways(self, gene_id: int | None, gene_name: str | None) -> list[str]:
        """Return pathway names for a gene, preferring gene_id lookup."""
        if gene_id is not None and gene_id in self._by_gene_id:
            return self._by_gene_id[gene_id]
        if gene_name is not None:
            return self._by_gene_name.get(gene_name, [])
        return []
