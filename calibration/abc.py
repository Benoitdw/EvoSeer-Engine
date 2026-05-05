"""Rejection ABC orchestrator with multi-stage sequential stopping rule."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from calibration.config_gen import generate
from calibration.distance import REGISTRY as DISTANCE_REGISTRY
from calibration.runner import run_single
from calibration.sampler import PriorSampler
from calibration.target import load_target

logger = logging.getLogger(__name__)


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


def _smoothed_relative_delta(history: list[float], window: int) -> float | None:
    """Relative change between two consecutive smoothed windows."""
    if len(history) < 2 * window:
        return None
    prev = float(np.mean(history[-2 * window : -window]))
    recent = float(np.mean(history[-window:]))
    if prev == 0.0:
        return None
    return abs(recent - prev) / prev


class RejectionABC:
    # Each stage: (convergence_threshold τ, early_reject_multiplier k)
    # Stop when |ΔD/Δn| < τ; early-reject if D > k * ε at that stage.
    default_stages: list[tuple[float, int]] = [(0.10, 10), (0.05, 5), (0.01, 1)]
    default_smoothing_window: int = 10
    default_max_sims: int = 500

    def __init__(self, calibration_config_path: str | Path) -> None:
        raw = yaml.safe_load(Path(calibration_config_path).read_text())

        self._base_config = Path(raw["base_config"])
        self._n_samples: int = raw.get("n_samples", 100)
        self._epsilon: float = raw.get("epsilon", 0.1)
        self._base_seed: int = raw.get("base_seed", 42)

        self._stages: list[tuple[float, int]] = [
            (float(tau), int(k)) for tau, k in raw.get("stages", self.default_stages)
        ]
        self._smoothing_window: int = raw.get("smoothing_window", self.default_smoothing_window)
        self._max_sims: int = raw.get("max_sims", self.default_max_sims)


        self._sampler = PriorSampler(raw.get("priors", {}))
        self._target_cfg: dict = raw.get("target", {})

        dist_key = raw.get("distance", "ks")
        dist_cls = DISTANCE_REGISTRY.get(dist_key)
        if dist_cls is None:
            raise ValueError(f"Unknown distance: {dist_key!r}. Choose from {list(DISTANCE_REGISTRY)}")
        self._distance = dist_cls(target=load_target(self._target_cfg))

        logger.debug(
            "RejectionABC initialised — n_samples=%d  ε=%.4f  stages=%s  max_sims=%d",
            self._n_samples, self._epsilon, self._stages, self._max_sims,
        )

    def _evaluate(
        self,
        config_path: Path,
        base_seed: int,
    ) -> tuple[float, int, str]:
        """Run simulations with multi-stage stopping. Returns (distance, n_sims, verdict)."""
        pooled: list[float] = []
        distance_history: list[float] = []
        stage = 0

        for sim_idx in range(self._max_sims):
            clones = run_single(config_path, seed=base_seed + sim_idx)
            pooled.extend(clones)
            logger.debug("  sim %d — %d new clones  pooled=%d", sim_idx + 1, len(clones), len(pooled))

            if not pooled:
                continue

            d = self._distance.compute(pooled)
            distance_history.append(d)

            tau, k = self._stages[stage]
            delta = _smoothed_relative_delta(distance_history, self._smoothing_window)

            logger.debug(
                "  stage=%d  τ=%.2f  k=%d  D=%.4f  δ=%s",
                stage, tau, k, d, f"{delta:.4f}" if delta is not None else "n/a",
            )

            if delta is None or delta >= tau:
                continue

            if d > k * self._epsilon:
                logger.info(f"  early reject at stage {stage} — D={d:.4f} > {k}×ε ({self._epsilon:.4f})")
                return d, sim_idx + 1, "rejected_early"

            stage += 1
            logger.debug("  converged at stage %d — advancing to stage %d", stage - 1, stage)

            if stage == len(self._stages):
                verdict = "accepted" if d <= self._epsilon else "rejected"
                return d, sim_idx + 1, verdict

        d = distance_history[-1] if distance_history else float("inf")
        logger.warning("  hit max_sims=%d without full convergence — D=%.4f", self._max_sims, d)
        return d, self._max_sims, "accepted" if d <= self._epsilon else "rejected"

    def run(self) -> CalibrationResult:
        rng = np.random.default_rng(self._base_seed)
        result = CalibrationResult()

        for iteration in range(self._n_samples):
            logger.info("[ABC] iteration %d/%d", iteration + 1, self._n_samples)
            params = self._sampler.sample(rng)
            logger.debug("  sampled params: %s", params)
            tmp_config = generate(self._base_config, params)

            try:
                sim_seed = self._base_seed + iteration * self._max_sims
                distance, n_sims, verdict = self._evaluate(tmp_config, sim_seed)
            finally:
                tmp_config.unlink(missing_ok=True)

            result.all_distances.append(distance)
            if verdict == "accepted":
                result.accepted.append((params, distance))
                logger.info("  ✓ accepted  d=%.4f  n=%d", distance, n_sims)
            else:
                logger.info("  ✗ %-14s d=%.4f  n=%d", verdict, distance, n_sims)

        n = len(result.all_distances)
        result.acceptance_rate = len(result.accepted) / n if n > 0 else 0.0
        logger.info(
            "[ABC] done — accepted %d/%d  (rate=%.2f%%)",
            len(result.accepted), n, result.acceptance_rate * 100,
        )
        return result
