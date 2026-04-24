from evoseer.plugins.mutation_rate import ConstantMutationRatePlugin

REGISTRY: dict[str, type] = {
    cls.name: cls for cls in [ConstantMutationRatePlugin]
}
