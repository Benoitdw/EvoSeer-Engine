from evoseer.rate_functions.weighted_sum import WeightedSumRate

REGISTRY: dict[str, type] = {
    cls.name: cls for cls in [WeightedSumRate]
}
