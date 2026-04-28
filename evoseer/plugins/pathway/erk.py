"""ErkPathwayPlugin — MAPK/ERK signaling pathway (melanoma)."""

from pathlib import Path

from evoseer.plugins.pathway import PathwayPlugin


class ErkPathwayPlugin(PathwayPlugin):
    name = "erk_pathway"
    pathway_file = Path(__file__).parent / "data" / "erk.yaml"
    involved_pathways = ["ERK"]
