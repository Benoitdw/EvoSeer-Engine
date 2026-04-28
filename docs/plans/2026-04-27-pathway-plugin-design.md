# Pathway Plugin Design

**Date**: 2026-04-27  
**Context**: Phase 1 — pure Python, flat formula, DAG for visualization and future signal propagation.

---

## Overview

Pathway plugins model how mutations in a signalling pathway affect cell fitness. The chain is:

```
Mutation → gene_id → PathwayService → MutationRecord.pathways → dirty flag → PathwayPlugin.compute_score()
```

---

## 1. Pathway Activation Formula

From equation 2.8:

```
P_R = σ_R( Σ_{g ∈ act_R} w_g · x_g^GOF  −  Σ_{g ∈ inh_R} w_g · x_g^LOF )
```

Where:
- `x_g^GOF ∈ {0,1}` — cell carries a GOF mutation in gene g
- `x_g^LOF ∈ {0,1}` — cell carries a LOF mutation in gene g
- `w_g` — weight of gene g = **prevalence of mutation in melanoma**
- `σ_R` — sigmoid with pathway-specific slope and threshold (ensures diminishing returns / mutual exclusivity)
- `act_R` — genes whose GOF drives pathway activation
- `inh_R` — genes whose LOF drives pathway activation (via disinhibition)

The sets `act_R` and `inh_R` are **derived from the DAG topology** (see section 3), not stored explicitly.

---

## 2. MutationRecord Extension

Add a first-class `effect` field to `MutationRecord`:

```python
@dataclass
class MutationRecord:
    mutation_id: int
    gene_id: int | None
    gene_name: str | None
    pathways: list[str]
    is_driver: bool | None
    effect: Literal["GOF", "LOF"] | None   # NEW
    extra: dict[str, Any]
```

`effect` is `None` for the vast majority of mutations (passenger mutations). Only driver mutations are annotated.

---

## 3. Pathway Definition Format (YAML)

The YAML is the **definitive** format — designed to support both Phase 1 (flat formula) and Phase 2 (DAG signal propagation).

```yaml
name: ERK
kegg_id: hsa04010
description: "MAPK/ERK signaling pathway, simplified to ERK axis"
output_node: ERK1_2   # anchor for DAG derivation and future propagation

sigmoid:
  slope: 2.0
  threshold: 0.5

nodes:
  NRAS:
    gene_id: 4893
    weight: 0.20      # mutation prevalence in melanoma
  BRAF:
    gene_id: 673
    weight: 0.50
  NF1:
    gene_id: 4763
    weight: 0.15
  MEK1:
    gene_id: 5604
    weight: 0.02
  ERK1_2:
    gene_id: 5595
    weight: 0.01

edges:
  - from: NRAS
    to: BRAF
    type: activates
  - from: NF1
    to: NRAS
    type: inhibits
  - from: BRAF
    to: MEK1
    type: activates
  - from: MEK1
    to: ERK1_2
    type: activates
```

Pathway YAMLs live in `evoseer/pathways/`.

### Deriving `act_R` / `inh_R` from the DAG

For each node, find all paths to `output_node` and count `inhibits` edges:

- **Even parity** → GOF mutation activates pathway → node ∈ `act_R`
- **Odd parity** → LOF mutation activates pathway (disinhibition) → node ∈ `inh_R`

Example: NF1 → NRAS (inhibits, 1 edge) → BRAF → MEK1 → ERK1_2. Parity = 1 (odd) → NF1 ∈ `inh_R`. A LOF mutation in NF1 contributes positively to `P_R`.

This derivation happens once at plugin initialisation and is cached.

---

## 4. Class Hierarchy

### `PathwayPlugin(FeaturePlugin)` — abstract parent

Responsibilities:
- Load and parse the YAML at `__init__`
- Build the DAG (dict-based, no external dependency for Phase 1)
- Derive `act_R` / `inh_R` from DAG topology (parity algorithm)
- Implement `compute_score()` using formula 2.8
- Implement `init_state()` and `on_division()`

```python
class PathwayPlugin(FeaturePlugin, ABC):
    pathway_file: ClassVar[str]   # path to YAML, defined by subclass

    def __init__(self, ...):
        self._definition = PathwayDefinition.load(self.pathway_file)
        self._act, self._inh = self._derive_roles(self._definition)
```

### `ErkPathwayPlugin(PathwayPlugin)` — concrete child

```python
class ErkPathwayPlugin(PathwayPlugin):
    name = "erk_pathway"
    pathway_file = "evoseer/pathways/erk.yaml"
    involved_pathways = ["ERK"]
```

Each new pathway = a new YAML file + a 4-line subclass. All logic stays in the parent.

---

## 5. PathwayService

Bridges gene annotations to pathway membership. Used when constructing `MutationRecord` to populate `MutationRecord.pathways`.

```python
class PathwayService:
    def gene_id_to_pathways(self, gene_id: int) -> list[str]: ...
```

- Loaded from all YAMLs in `evoseer/pathways/` at startup
- Injected into `MutationGenerator` (or wherever `MutationRecord`s are created)

---

## 6. Notebook — ERK Pathway Visualisation

Before implementation, a notebook `notebooks/erk_pathway.ipynb` will:

1. Load `erk.yaml`
2. Build the DAG with networkx
3. Visualise nodes (sized by `weight` = melanoma prevalence) and edges (color-coded: green = activates, red = inhibits)
4. Annotate derived roles (`act_R` in blue, `inh_R` in orange)
5. Serve as visual validation of the simplified ERK pathway before coding the plugin

---

## 7. Deliverables (Phase 1)

| Item | Location |
|------|----------|
| `effect` field on `MutationRecord` | `evoseer/services/mutation_store.py` |
| `evoseer/pathways/erk.yaml` | pathway definition |
| `PathwayDefinition` dataclass | `evoseer/pathways/base.py` |
| `PathwayPlugin` ABC | `evoseer/plugins/pathway.py` |
| `ErkPathwayPlugin` | `evoseer/plugins/erk_pathway.py` |
| `PathwayService` | `evoseer/services/pathway_service.py` |
| ERK visualisation notebook | `notebooks/erk_pathway.ipynb` |
| Tests | `tests/plugins/test_erk_pathway.py` |