"""Pre-configured mutation stores for calibration."""

from __future__ import annotations

from evoseer.services.mutation_store import InMemoryMutationStore, MutationRecord

N_PASS = 5_000
BRAF_GOF_ID = N_PASS + 1
NRAS_GOF_ID = N_PASS + 2


def build_erk_ois_store() -> InMemoryMutationStore:
    """5 000 passengers + BRAF GOF + NRAS GOF, matching erk_ois.ipynb."""
    store = InMemoryMutationStore()
    for i in range(N_PASS):
        store.add_mutation(MutationRecord(
            mutation_id=i, is_driver=False, extra={"d": 0.005, "b": 0.0}
        ))
    store.add_mutation(MutationRecord(
        mutation_id=BRAF_GOF_ID,
        gene_id=673,
        gene_name="BRAF",
        pathways=["ERK", "OIS"],
        is_driver=True,
        effect="GOF",
    ))
    store.add_mutation(MutationRecord(
        mutation_id=NRAS_GOF_ID,
        gene_id=4893,
        gene_name="NRAS",
        pathways=["ERK", "OIS"],
        is_driver=True,
        effect="GOF",
    ))
    return store
