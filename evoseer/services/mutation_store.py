"""MutationStore ABC and InMemoryMutationStore for testing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class MutationRecord:
    """
    All annotations for a single mutation.

    Fields are intentionally sparse for Phase 1 — additional annotation
    sources (boostdm, genebe, neoantigen scores, etc.) will be added in v2
    when the database schema is extended.
    """

    mutation_id: int
    gene_id: int | None = None
    gene_name: str | None = None
    pathways: list[str] = field(default_factory=list)
    is_driver: bool | None = None
    effect: Literal["GOF", "LOF"] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class MutationStore(ABC):
    """
    Abstract in-memory lookup for mutation annotations.

    Implementations may back this with a SQLite database, a CSV file, or an
    in-memory dict. The engine and plugins interact only with this interface.
    """

    @abstractmethod
    def get(self, mutation_id: int) -> MutationRecord:
        """Return all annotations for a mutation. Raises KeyError if unknown."""
        ...

    @abstractmethod
    def get_gene_pathways(self, mutation_id: int) -> list[str]:
        """Return pathway names associated with the gene this mutation affects."""
        ...

    @abstractmethod
    def is_driver(self, mutation_id: int) -> bool | None:
        """Return True/False if flagged as driver, None if unknown."""
        ...

    @abstractmethod
    def all_ids(self) -> list[int]:
        """Return all known mutation IDs (needed for distribution setup)."""
        ...


class InMemoryMutationStore(MutationStore):
    """
    Dict-backed MutationStore for testing and prototyping.

    Populate via ``add_mutation`` before running the simulation.
    """

    def __init__(self) -> None:
        self._records: dict[int, MutationRecord] = {}

    def add_mutation(self, record: MutationRecord) -> None:
        """Register a mutation record."""
        self._records[record.mutation_id] = record

    def get(self, mutation_id: int) -> MutationRecord:
        """Return the record for mutation_id, raising KeyError if absent."""
        if mutation_id not in self._records:
            raise KeyError(f"Unknown mutation_id: {mutation_id}")
        return self._records[mutation_id]

    def get_gene_pathways(self, mutation_id: int) -> list[str]:
        """Return pathways for the mutation's gene, or [] if unknown."""
        try:
            return self._records[mutation_id].pathways
        except KeyError:
            return []

    def is_driver(self, mutation_id: int) -> bool | None:
        """Return driver flag, or None if the mutation is unknown."""
        try:
            return self._records[mutation_id].is_driver
        except KeyError:
            return None

    def all_ids(self) -> list[int]:
        """Return all registered mutation IDs."""
        return list(self._records.keys())
