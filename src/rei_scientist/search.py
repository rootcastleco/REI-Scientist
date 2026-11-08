"""Bounded best-first configuration search with isolated development and holdout seeds."""
from __future__ import annotations
from dataclasses import dataclass
import heapq
from statistics import mean
from typing import Any

from .algorithms import run_seed
from .models import Proposal, SeedResult, StudySpec
from .verification import compare_holdout, verify_seed


@dataclass
class SearchOutcome:
    baseline: Proposal
    selected: Proposal
    leaderboard: list[dict[str, Any]]
    dev_runs: dict[str, list[SeedResult]]
    holdout_baseline: list[SeedResult]
    holdout_selected: list[SeedResult]
    verdict: dict[str, Any]


def defaults(spec: StudySpec) -> list[Proposal]:
    values = {
        "hill_climb": {"step_fraction": 0.12},
        "simulated_annealing": {"step_fraction": 0.12, "temperature": 2.0, "cooling": 0.97},
    }
    return [Proposal.build(method, values[method]) for method in spec.methods[1:]]


def neighbors(parent: Proposal) -> list[Proposal]:
    """Generate only pre-approved numeric mutations, not arbitrary Python code."""
    values = parent.param_dict()
    actions: list[tuple[str, float]] = []
    if parent.method == "hill_climb":
        actions = [("step_fraction", 0.5), ("step_fraction", 1.5)]
    elif parent.method == "simulated_annealing":
        actions = [("step_fraction", 0.5), ("step_fraction", 1.5),
                   ("temperature", 0.5), ("temperature", 2.0),
                   ("cooling", 0.97), ("cooling", 1.02)]
    children: list[Proposal] = []
    for key, multiplier in actions:
        altered = values.copy()
        altered[key] = altered[key] * multiplier
        try:
            children.append(Proposal.build(parent.method, altered, depth=parent.depth+1, parent=parent.key))
        except ValueError:
            continue
    return children


def _evaluate(spec: StudySpec, proposal: Proposal, seeds: tuple[int, ...]) -> list[SeedResult]:
    runs = [run_seed(spec, proposal, seed) for seed in seeds]
    for run in runs:
        errors = verify_seed(spec, run)
        if errors:
            raise RuntimeError(f"Verification failed for {proposal.key}: {errors}")
    return runs


def run_search(spec: StudySpec, initial_proposals: list[Proposal] | None = None) -> SearchOutcome:
    baseline = Proposal.build("random_search", {})
    base_dev = _evaluate(spec, baseline, spec.dev_seeds)
    dev_runs = {baseline.key: base_dev}
    leaderboard: list[dict[str, Any]] = [{
        "key": baseline.key, "method": baseline.method, "params": {},
        "depth": 0, "parent": None, "dev_mean": mean(r.best_value for r in base_dev),
        "is_baseline": True,
    }]
    pending: list[tuple[float, int, Proposal]] = []
    queued: set[str] = {baseline.key}
    index = 0
    initial = defaults(spec) + (initial_proposals or [])
    for proposal in initial:
        if proposal.method not in spec.methods[1:]:
            raise ValueError(f"Not a permitted candidate: {proposal.method}")
        if proposal.depth != 0:
            raise ValueError("External root proposals must have depth=0")
        if proposal.key not in queued:
            heapq.heappush(pending, (0.0, index, proposal))
            queued.add(proposal.key)
            index += 1
    if not pending:
        raise ValueError("At least one candidate must be proposed")
    attempted = 0
    while pending and attempted < spec.candidate_budget:
        _, _, proposal = heapq.heappop(pending)
        runs = _evaluate(spec, proposal, spec.dev_seeds)
        dev_runs[proposal.key] = runs
        loss = mean(r.best_value for r in runs)
        leaderboard.append({"key": proposal.key, "method": proposal.method,
                            "params": proposal.param_dict(), "depth": proposal.depth,
                            "parent": proposal.parent, "dev_mean": loss,
                            "is_baseline": False})
        attempted += 1
        if proposal.depth < spec.max_depth:
            for child in neighbors(proposal):
                if child.key not in queued:
                    heapq.heappush(pending, (loss, index, child))
                    queued.add(child.key)
                    index += 1
    candidates = [row for row in leaderboard if not row["is_baseline"]]
    best_row = min(candidates, key=lambda entry: (entry["dev_mean"], entry["key"]))
    selected = next(p for p in _all_proposals(leaderboard) if p.key == best_row["key"])
    base_test = _evaluate(spec, baseline, spec.test_seeds)
    selected_test = _evaluate(spec, selected, spec.test_seeds)
    verdict = compare_holdout(spec, base_test, selected_test)
    return SearchOutcome(baseline, selected, leaderboard, dev_runs, base_test, selected_test, verdict)


def _all_proposals(leaderboard: list[dict[str, Any]]) -> list[Proposal]:
    return [Proposal.build(row["method"], row["params"], row["depth"], row["parent"])
            for row in leaderboard]
