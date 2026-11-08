"""Bounded experiment implementations. No generated Python is executed here."""
from __future__ import annotations
import hashlib
import math
import random
import struct
import time

from .models import Proposal, SeedResult, StudySpec
from .objectives import evaluate


def run_seed(spec: StudySpec, proposal: Proposal, seed: int) -> SeedResult:
    """Run exactly evaluation_budget objective calls, without shell/network access."""
    rng = random.Random(seed)
    lo, hi = spec.bounds
    width = hi - lo
    count = 0
    best_value = float("inf")
    best_position: tuple[float, ...] = ()
    trace_digest = hashlib.sha256()
    params = proposal.param_dict()
    start = time.perf_counter()

    def score(position: tuple[float, ...]) -> float:
        nonlocal count, best_value, best_position
        if count >= spec.evaluation_budget:
            raise RuntimeError("Evaluation budget exceeded")
        if any(not lo <= x <= hi or not math.isfinite(x) for x in position):
            raise RuntimeError("Candidate is out of bounds")
        value = evaluate(spec.benchmark, position)
        if not math.isfinite(value):
            raise RuntimeError("Objective returned non-finite result")
        count += 1
        trace_digest.update(struct.pack("!d", value))
        if value < best_value:
            best_value = value
            best_position = position
        return value

    def sample() -> tuple[float, ...]:
        return tuple(rng.uniform(lo, hi) for _ in range(spec.dimension))

    def mutate(position: tuple[float, ...], step_fraction: float) -> tuple[float, ...]:
        return tuple(min(hi, max(lo, x + rng.gauss(0, step_fraction * width))) for x in position)

    if proposal.method == "random_search":
        for _ in range(spec.evaluation_budget):
            score(sample())
    elif proposal.method in ("hill_climb", "simulated_annealing"):
        current = sample()
        current_value = score(current)
        no_progress = 0
        temperature = params.get("temperature", 1.0)
        for _ in range(spec.evaluation_budget - 1):
            if proposal.method == "hill_climb" and no_progress >= 20:
                current = sample()
                current_value = score(current)
                no_progress = 0
                continue
            trial = mutate(current, params["step_fraction"])
            trial_value = score(trial)
            delta = trial_value - current_value
            accept = delta <= 0
            if proposal.method == "simulated_annealing":
                if not accept and temperature > 1e-12:
                    accept = rng.random() < math.exp(-min(delta / temperature, 700))
                temperature *= params["cooling"]
            if accept:
                current, current_value = trial, trial_value
                no_progress = 0 if delta < 0 else no_progress + 1
            else:
                no_progress += 1
    else:
        raise ValueError("Unregistered solver")
    return SeedResult(
        method=proposal.method, params=params, seed=seed,
        best_position=best_position, best_value=best_value,
        evaluations=count, elapsed_ms=round((time.perf_counter()-start)*1000, 4),
        trace_sha256=trace_digest.hexdigest(),
    )
