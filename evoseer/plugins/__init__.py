from evoseer.plugins.base import FeaturePlugin
from evoseer.plugins.dummies import DummyBirthPlugin, DummyDeathPlugin
from evoseer.plugins.mutation_rate import ConstantMutationRatePlugin
from evoseer.plugins.ois.melanocyte import MelanocyteOISPlugin
from evoseer.plugins.pathway.erk import ErkPathwayPlugin

__all__ = [
    "FeaturePlugin",
    "ConstantMutationRatePlugin",
    "DummyBirthPlugin",
    "DummyDeathPlugin",
    "ErkPathwayPlugin",
    "MelanocyteOISPlugin",
    "REGISTRY",
]

REGISTRY: dict[str, type] = {
    cls.name: cls
    for cls in [
        ConstantMutationRatePlugin,
        DummyBirthPlugin,
        DummyDeathPlugin,
        ErkPathwayPlugin,
        MelanocyteOISPlugin,
    ]
}
