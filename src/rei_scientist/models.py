"""Strict contracts for research studies and immutable experiment records."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Any

BENCHMARKS = frozenset({"sphere", "rastrigin", "rosenbrock", "ackley"})
METHODS = frozenset({"random_search", "hill_climb", "simulated_annealing"})
STUDY_FIELDS = frozenset({
    "schema_version", "study_id", "question", "hypothesis", "benchmark", "dimension",
    "bounds", "evaluation_budget", "candidate_budget", "max_depth", "dev_seeds",
    "test_seeds", "minimum_improvement_pct", "methods", "source_note",
})


class StudyValidationError(ValueError):
    """Invalid study specification or proposed search configuration."""


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise StudyValidationError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _finite(value: Any, name: str, low: float, high: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise StudyValidationError(f"{name} must be finite in [{low}, {high}]")
    return float(value)


def _seeds(value: Any, name: str) -> tuple[int, ...]:
    if type(value) is not list or not 3 <= len(value) <= 20:
        raise StudyValidationError(f"{name} must contain 3-20 seeds")
    seeds = tuple(_integer(v, name, 0, 2**32 - 1) for v in value)
    if len(set(seeds)) != len(seeds):
        raise StudyValidationError(f"{name} contains duplicate seeds")
    return seeds


@dataclass(frozen=True)
class StudySpec:
    schema_version: str
    study_id: str
    question: str
    hypothesis: str
    benchmark: str
    dimension: int
    bounds: tuple[float, float]
    evaluation_budget: int
    candidate_budget: int
    max_depth: int
    dev_seeds: tuple[int, ...]
    test_seeds: tuple[int, ...]
    minimum_improvement_pct: float
    methods: tuple[str, ...]
    source_note: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StudySpec":
        if type(raw) is not dict:
            raise StudyValidationError("Study must be a JSON object")
        if set(raw) != STUDY_FIELDS:
            raise StudyValidationError(f"Study field mismatch: missing={sorted(STUDY_FIELDS-set(raw))}, extra={sorted(set(raw)-STUDY_FIELDS)}")
        if raw["schema_version"] != "1.0":
            raise StudyValidationError("Only schema_version=1.0 is supported")
        study_id = raw["study_id"]
        if not isinstance(study_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", study_id):
            raise StudyValidationError("study_id must be a safe slug of 3-64 characters")
        for field in ("question", "hypothesis", "source_note"):
            text = raw[field]
            if type(text) is not str or not 1 <= len(text.strip()) <= 2000:
                raise StudyValidationError(f"{field} must have 1-2000 non-whitespace characters")
        if raw["benchmark"] not in BENCHMARKS:
            raise StudyValidationError(f"Unregistered benchmark: {raw['benchmark']!r}")
        dimension = _integer(raw["dimension"], "dimension", 2, 16)
        bounds = raw["bounds"]
        if type(bounds) is not list or len(bounds) != 2:
            raise StudyValidationError("bounds must be [min, max]")
        lower = _finite(bounds[0], "bounds[0]", -100, 100)
        upper = _finite(bounds[1], "bounds[1]", -100, 100)
        if lower >= upper or upper - lower < 1e-6:
            raise StudyValidationError("bounds must be ordered with nonzero width")
        dev_seeds = _seeds(raw["dev_seeds"], "dev_seeds")
        test_seeds = _seeds(raw["test_seeds"], "test_seeds")
        if set(dev_seeds) & set(test_seeds):
            raise StudyValidationError("Development and holdout test seeds MUST NOT overlap")
        methods = raw["methods"]
        if type(methods) is not list or not 2 <= len(methods) <= 3:
            raise StudyValidationError("methods must list 2-3 registered algorithms")
        if len(set(methods)) != len(methods) or any(m not in METHODS for m in methods):
            raise StudyValidationError("methods must be distinct and registered")
        if methods[0] != "random_search":
            raise StudyValidationError("First method must be random_search (independent baseline)")
        return cls(
            schema_version="1.0", study_id=study_id, question=raw["question"].strip(),
            hypothesis=raw["hypothesis"].strip(), benchmark=raw["benchmark"],
            dimension=dimension, bounds=(lower, upper),
            evaluation_budget=_integer(raw["evaluation_budget"], "evaluation_budget", 20, 5000),
            candidate_budget=_integer(raw["candidate_budget"], "candidate_budget", 1, 50),
            max_depth=_integer(raw["max_depth"], "max_depth", 0, 5),
            dev_seeds=dev_seeds, test_seeds=test_seeds,
            minimum_improvement_pct=_finite(raw["minimum_improvement_pct"], "minimum_improvement_pct", 0, 100),
            methods=tuple(methods), source_note=raw["source_note"].strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in ("bounds", "dev_seeds", "test_seeds", "methods"):
            payload[field] = list(payload[field])
        return payload


@dataclass(frozen=True)
class Proposal:
    method: str
    params: tuple[tuple[str, float], ...]
    depth: int = 0
    parent: str | None = None

    @classmethod
    def build(cls, method: str, params: dict[str, Any], depth: int = 0, parent: str | None = None) -> "Proposal":
        if method not in METHODS:
            raise StudyValidationError(f"Unsupported method: {method}")
        allowed = {
            "random_search": {},
            "hill_climb": {"step_fraction": (0.001, 1.0)},
            "simulated_annealing": {"step_fraction": (0.001, 1.0), "temperature": (0.001, 100.0), "cooling": (0.5, 0.9999)},
        }[method]
        if type(params) is not dict or set(params) != set(allowed):
            raise StudyValidationError(f"{method} requires exactly {sorted(allowed)}")
        normalized = tuple(sorted((key, round(_finite(params[key], key, *limit), 8)) for key, limit in allowed.items()))
        if type(depth) is not int or not 0 <= depth <= 5:
            raise StudyValidationError("Invalid proposal depth")
        if parent is not None and not isinstance(parent, str):
            raise StudyValidationError("Invalid proposal parent")
        return cls(method=method, params=normalized, depth=depth, parent=parent)

    @property
    def key(self) -> str:
        import hashlib
        import json
        data = json.dumps([self.method, self.params], sort_keys=True).encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:12]

    def param_dict(self) -> dict[str, float]:
        return dict(self.params)

    def to_dict(self) -> dict[str, Any]:
        return {"method": self.method, "params": self.param_dict(), "depth": self.depth, "parent": self.parent, "key": self.key}


@dataclass(frozen=True)
class SeedResult:
    method: str
    params: dict[str, float]
    seed: int
    best_position: tuple[float, ...]
    best_value: float
    evaluations: int
    elapsed_ms: float
    trace_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
