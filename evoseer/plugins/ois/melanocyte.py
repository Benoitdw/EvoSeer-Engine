"""MelanocyteOISPlugin — OIS pathway for melanocytes."""

from pathlib import Path

from evoseer.plugins.ois import OISPlugin


class MelanocyteOISPlugin(OISPlugin):
    name = "melanocyte_ois"
    pathway_file = Path(__file__).parent / "data" / "melanocyte_ois.yaml"
    involved_pathways = ["OIS"]
