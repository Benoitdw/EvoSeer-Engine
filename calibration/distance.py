"""Pluggable loss functions for ABC calibration."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from scipy import stats


class Distance(ABC):
    @abstractmethod
    def compute(self, simulated: list[float], target: list[float]) -> float: ...


class L1Distance(Distance):
    def compute(self, simulated: list[float], target: list[float]) -> float:
        a = np.sort(simulated)
        b = np.sort(target)
        n = max(len(a), len(b))
        a = np.pad(a, (0, n - len(a)))
        b = np.pad(b, (0, n - len(b)))
        return float(np.mean(np.abs(a - b)))


class L2Distance(Distance):
    def compute(self, simulated: list[float], target: list[float]) -> float:
        a = np.sort(simulated)
        b = np.sort(target)
        n = max(len(a), len(b))
        a = np.pad(a, (0, n - len(a)))
        b = np.pad(b, (0, n - len(b)))
        return float(np.sqrt(np.mean((a - b) ** 2)))


class KSDistance(Distance):
    def compute(self, simulated: list[float], target: list[float]) -> float:
        if not simulated:
            return 1.0
        stat, _ = stats.ks_2samp(simulated, target)
        return float(stat)


class WassersteinDistance(Distance):
    def compute(self, simulated: list[float], target: list[float]) -> float:
        if not simulated:
            return float("inf")
        return float(stats.wasserstein_distance(simulated, target))


REGISTRY: dict[str, type[Distance]] = {
    "l1": L1Distance,
    "l2": L2Distance,
    "ks": KSDistance,
    "wasserstein": WassersteinDistance,
}
