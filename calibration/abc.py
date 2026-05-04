"""Rejection ABC orchestrator."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from calibration.config_gen import generate
from calibration.distance import REGISTRY as DISTANCE_REGISTRY
from calibration.runner import run_batch
from calibration.sampler import PriorSampler
from calibration.target import load_target


@dataclass
class CalibrationResult:
    accepted: list[tuple[dict, float]] = field(default_factory=list)
    all_distances: list[float] = field(default_factory=list)
    acceptance_rate: float = 0.0

    def to_json(self) -> str:
        return json.dumps(
            {
                "acceptance_rate": self.acceptance_rate,
                "n_accepted": len(self.accepted),
                "n_total": len(self.all_distances),
                "all_distances": self.all_distances,
                "accepted": [
                    {"params": p, "distance": d} for p, d in self.accepted
                ],
            },
            indent=2,
        )


class RejectionABC:
    def __init__(self, calibration_config_path: str | Path) -> None:
        raw = yaml.safe_load(Path(calibration_config_path).read_text())

        self._base_config = Path(raw["base_config"])
        self._n_samples: int = raw.get("n_samples", 100)
        self._n_sims: int = raw.get("n_sims", 10)
        self._epsilon: float = raw.get("epsilon", 0.1)
        self._base_seed: int = raw.get("base_seed", 42)

        dist_key = raw.get("distance", "ks")
        dist_cls = DISTANCE_REGISTRY.get(dist_key)
        if dist_cls is None:
            raise ValueError(f"Unknown distance: {dist_key!r}. Choose from {list(DISTANCE_REGISTRY)}")
        self._distance = dist_cls()

        self._sampler = PriorSampler(raw.get("priors", {}))
        self._target_cfg: dict = raw.get("target", {})

    def run(self) -> CalibrationResult:
        target = load_target(self._target_cfg)
        rng = np.random.default_rng(self._base_seed)
        result = CalibrationResult()

        for iteration in range(self._n_samples):
            print(
                f"[ABC] iteration {iteration + 1}/{self._n_samples}", file=sys.stderr
            )
            params = self._sampler.sample(rng)
            tmp_config = generate(self._base_config, params)

            try:
                pooled = run_batch(tmp_config, self._n_sims, self._base_seed)
                distance = self._distance.compute(pooled, target)
            finally:
                tmp_config.unlink(missing_ok=True)

            result.all_distances.append(distance)
            if distance < self._epsilon:
                result.accepted.append((params, distance))
                print(
                    f"  ✓ accepted (distance={distance:.4f})", file=sys.stderr
                )

        n = len(result.all_distances)
        result.acceptance_rate = len(result.accepted) / n if n > 0 else 0.0
        return result
