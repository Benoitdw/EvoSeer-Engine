"""Pluggable loss functions for ABC calibration."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from scipy import stats


class Distance(ABC):
    def __init__(self, target:list[float]):
        self.target = target

    @abstractmethod
    def compute(self, simulated: list[float]) -> float: ...

class QuantileMSEDistance(Distance):
    def __init__(self, target):
        self._q_levels = np.linspace(0.005, 0.95, 50)
        self.target = np.quantile(target, self._q_levels)

    def compute(self, simulated: list[float]) -> float:
        q_sim = np.quantile(simulated, self._q_levels)
        return float(np.sqrt(np.mean((q_sim - self.target)**2)))


class L1Distance(Distance):
    def __init__(self, target):
        self.target = np.sort(target)

    def compute(self, simulated: list[float]) -> float:
        a = np.sort(simulated)
        b = self.target
        n = max(len(a), len(b))
        a = np.pad(a, (0, n - len(a)))
        b = np.pad(b, (0, n - len(b)))
        return float(np.mean(np.abs(a - b)))


class L2Distance(Distance):
    def __init__(self, target):
        self.target = np.sort(target)

    def compute(self, simulated: list[float]) -> float:
        a = np.sort(simulated)
        b = self.target
        n = max(len(a), len(b))
        a = np.pad(a, (0, n - len(a)))
        b = np.pad(b, (0, n - len(b)))
        return float(np.sqrt(np.mean((a - b) ** 2)))


class KSDistance(Distance):
    def compute(self, simulated: list[float]) -> float:
        if not simulated:
            return 1.0
        stat, _ = stats.ks_2samp(simulated, self.target)
        return float(stat)


class WassersteinDistance(Distance):
    def compute(self, simulated: list[float]) -> float:
        if not simulated:
            return float("inf")
        return float(stats.wasserstein_distance(simulated, self.target))


REGISTRY: dict[str, type[Distance]] = {
    "MSE": QuantileMSEDistance,
    "l1": L1Distance,
    "l2": L2Distance,
    "ks": KSDistance,
    "wasserstein": WassersteinDistance,
}
