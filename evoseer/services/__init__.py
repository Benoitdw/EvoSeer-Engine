from evoseer.services.mutation_generator import MutationGenerator, UniformMutationGenerator
from evoseer.services.mutation_store import MutationRecord, MutationStore

__all__ = [
    "MutationStore", "MutationRecord",
    "MutationGenerator", "UniformMutationGenerator",
    "REGISTRY",
]

REGISTRY: dict[str, type] = {
    cls.name: cls for cls in [UniformMutationGenerator]
}
