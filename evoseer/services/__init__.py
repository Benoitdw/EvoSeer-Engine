from evoseer.services.mutation_generator import UniformMutationGenerator

REGISTRY: dict[str, type] = {
    cls.name: cls for cls in [UniformMutationGenerator]
}
