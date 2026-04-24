from evoseer.rate_functions.base import RateFunction
from evoseer.rate_functions.weighted_sum import WeightedSumRate

__all__ = ["RateFunction", "WeightedSumRate", "REGISTRY"]

REGISTRY: dict[str, type] = {
    cls.name: cls for cls in [WeightedSumRate]
}
