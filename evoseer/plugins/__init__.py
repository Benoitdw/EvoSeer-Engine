from evoseer.plugins.base import FeaturePlugin
from evoseer.plugins.mutation_rate import ConstantMutationRatePlugin

__all__ = ["FeaturePlugin", "ConstantMutationRatePlugin", "REGISTRY"]

REGISTRY: dict[str, type] = {
    cls.name: cls for cls in [ConstantMutationRatePlugin]
}
