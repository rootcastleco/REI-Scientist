"""Registered, finite analytic optimization benchmarks (minimization)."""
from __future__ import annotations
import math
from collections.abc import Sequence


def evaluate(benchmark: str, position: Sequence[float]) -> float:
    x = tuple(position)
    if len(x) < 2 or not all(math.isfinite(v) for v in x):
        raise ValueError("Objective input must be a finite vector of dimension >=2")
    if benchmark == "sphere":
        return sum(v * v for v in x)
    if benchmark == "rastrigin":
        return 10.0 * len(x) + sum(v*v - 10.0 * math.cos(2 * math.pi * v) for v in x)
    if benchmark == "rosenbrock":
        return sum(100 * (b - a*a)**2 + (1 - a)**2 for a, b in zip(x, x[1:]))
    if benchmark == "ackley":
        n = len(x)
        return (-20 * math.exp(-0.2 * math.sqrt(sum(v*v for v in x)/n))
                - math.exp(sum(math.cos(2*math.pi*v) for v in x)/n) + 20 + math.e)
    raise ValueError(f"Unknown benchmark: {benchmark}")
