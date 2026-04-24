from evoseer.services.mutation_generator import MutationGenerator, NoMutationGenerator, UniformMutationGenerator
from evoseer.services.mutation_store import MutationRecord, MutationStore

__all__ = [
    "MutationStore", "MutationRecord",
    "MutationGenerator", "NoMutationGenerator", "UniformMutationGenerator",
    "REGISTRY",
]

REGISTRY: dict[str, type] = {
    cls.name: cls for cls in [UniformMutationGenerator, NoMutationGenerator]
}
