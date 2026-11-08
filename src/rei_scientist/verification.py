"""Independent scoring, constraint checks and conservative claim classification."""
from __future__ import annotations
import math
import random
from statistics import mean
from typing import Any, Iterable

from .models import SeedResult, StudySpec


def reference_objective(name: str, position: tuple[float, ...]) -> float:
    """Independent formula path: intentionally does not call objectives.evaluate."""
    if name == "sphere":
        return math.fsum(map(lambda z: z**2, position))
    if name == "rastrigin":
        return math.fsum(10 + z**2 - 10 * math.cos(math.tau * z) for z in position)
    if name == "rosenbrock":
        return math.fsum((1-position[i])**2 + 100*(position[i+1]-position[i]**2)**2
                         for i in range(len(position)-1))
    if name == "ackley":
        rms = math.sqrt(math.fsum(z**2 for z in position)/len(position))
        c = math.fsum(math.cos(math.tau*z) for z in position)/len(position)
        return 20 + math.e - 20*math.exp(-rms/5) - math.exp(c)
    raise ValueError(f"No reference implementation: {name}")


def verify_seed(spec: StudySpec, result: SeedResult) -> list[str]:
    errors: list[str] = []
    if result.evaluations != spec.evaluation_budget:
        errors.append(f"evaluation budget mismatch: {result.evaluations}")
    if len(result.best_position) != spec.dimension:
        return [*errors, "wrong solution dimension"]
    if not all(math.isfinite(x) and spec.bounds[0] <= x <= spec.bounds[1] for x in result.best_position):
        return [*errors, "infeasible best position"]
    if not math.isfinite(result.best_value):
        return [*errors, "non-finite reported best score"]
    expected = reference_objective(spec.benchmark, result.best_position)
    if not math.isclose(result.best_value, expected, rel_tol=1e-9, abs_tol=1e-8):
        errors.append(f"independent objective mismatch: reported={result.best_value}, expected={expected}")
    if not isinstance(result.trace_sha256, str) or len(result.trace_sha256) != 64:
        errors.append("missing trace digest")
    return errors


def bootstrap_mean_difference_interval(differences: list[float], samples: int = 2000) -> tuple[float, float]:
    """Paired percentile bootstrap CI; purely exploratory for small n."""
    rng = random.Random(0x5EED)
    n = len(differences)
    estimates = [mean(differences[rng.randrange(n)] for _ in range(n)) for _ in range(samples)]
    estimates.sort()
    return (estimates[int(samples*0.025)], estimates[min(samples-1, int(samples*0.975))])


def compare_holdout(spec: StudySpec, baseline: list[SeedResult], candidate: list[SeedResult]) -> dict[str, Any]:
    failures: list[str] = []
    if len(baseline) != len(spec.test_seeds) or len(candidate) != len(spec.test_seeds):
        failures.append("holdout seed count mismatch")
    if [r.seed for r in baseline] != list(spec.test_seeds) or [r.seed for r in candidate] != list(spec.test_seeds):
        failures.append("holdout seed identity/order mismatch")
    for group_name, group in (("baseline", baseline), ("candidate", candidate)):
        for r in group:
            failures.extend(f"{group_name}/{r.seed}: {failure}" for failure in verify_seed(spec, r))
    if failures:
        return {"status": "NOT VERIFIED", "reasons": failures, "baseline_mean": None,
                "candidate_mean": None, "mean_delta": None, "relative_improvement_pct": None,
                "ci95_delta": None, "paired_wins": None, "holdout_seeds": len(spec.test_seeds)}
    base_mean = mean(r.best_value for r in baseline)
    cand_mean = mean(r.best_value for r in candidate)
    differences = [b.best_value-c.best_value for b, c in zip(baseline, candidate)]
    ci = bootstrap_mean_difference_interval(differences)
    delta = base_mean - cand_mean
    relative = 100 * delta / max(abs(base_mean), 1e-12)
    wins = sum(d > 0 for d in differences)
    # A small sample cannot substantiate an improvement claim.
    if len(spec.test_seeds) < 5:
        status = "NOT VERIFIED"
        reasons = ["Fewer than 5 holdout seeds; evidence is insufficient for this release gate"]
    elif delta > 0 and relative >= spec.minimum_improvement_pct and ci[0] > 0:
        status = "PASS"
        reasons = ["Target met and paired-bootstrap lower bound > 0; exploratory result only"]
    else:
        status = "FAIL"
        reasons = ["Pre-registered improvement target and positive CI lower bound were not both met"]
    return {
        "status": status, "reasons": reasons,
        "baseline_mean": base_mean, "candidate_mean": cand_mean, "mean_delta": delta,
        "relative_improvement_pct": relative, "ci95_delta": list(ci),
        "paired_wins": wins, "holdout_seeds": len(spec.test_seeds),
    }
