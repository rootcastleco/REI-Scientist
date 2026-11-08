"""Replay and audit saved research: hashes, selection, objectives, seeds and traces."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from .algorithms import run_seed
from .artifacts import canonical_json, source_hash
from .models import Proposal, SeedResult, StudySpec, StudyValidationError
from .verification import compare_holdout, verify_seed


def _read_json(path: Path) -> Any:
    if not path.is_file() or path.stat().st_size > 8_000_000:
        raise ValueError(f"Missing or oversized artifact: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _decode(item: dict[str, Any]) -> SeedResult:
    return SeedResult(
        method=item["method"], params=item["params"], seed=item["seed"],
        best_position=tuple(item["best_position"]), best_value=item["best_value"],
        evaluations=item["evaluations"], elapsed_ms=item["elapsed_ms"],
        trace_sha256=item["trace_sha256"],
    )


def replay_artifacts(folder: Path) -> list[str]:
    errors: list[str] = []
    spec_data = _read_json(folder / "study.json")
    results = _read_json(folder / "results.json")
    manifest = _read_json(folder / "manifest.json")
    spec = StudySpec.from_dict(spec_data)
    if results.get("study_id") != spec.study_id or manifest.get("study_id") != spec.study_id:
        errors.append("Artifact study identities differ")
    for label, payload, key in (
        ("study", spec_data, "study_sha256"),
        ("results", results, "results_sha256"),
    ):
        calculated = hashlib.sha256(canonical_json(payload)).hexdigest()
        if calculated != manifest.get(key):
            errors.append(f"{label} SHA-256 mismatch")
    for label, file_name, digest_key in (
        ("report", "report.md", "report_sha256"),
        ("events", "events.jsonl", "events_sha256"),
        ("dashboard", "dashboard.html", "dashboard_sha256"),
    ):
        item_path = folder / file_name
        if not item_path.is_file() or hashlib.sha256(item_path.read_bytes()).hexdigest() != manifest.get(digest_key):
            errors.append(f"{label} SHA-256 mismatch")
    if source_hash() != manifest.get("source_sha256"):
        errors.append("Source code hash differs from original run")

    leaderboard = results.get("development_leaderboard", [])
    development = results.get("development_runs", {})
    if not isinstance(leaderboard, list) or not isinstance(development, dict):
        return errors + ["Malformed development search evidence"]
    dev_keys = [row.get("key") for row in leaderboard]
    if len(dev_keys) != len(set(dev_keys)) or set(dev_keys) != set(development):
        errors.append("Development leaderboard and run groups disagree")
    if len(leaderboard) < 2 or len(leaderboard) > spec.candidate_budget + 1:
        errors.append("Invalid number of explored candidates")
    selected_data = results.get("selected", {})
    try:
        winner = min((row for row in leaderboard if not row["is_baseline"]),
                     key=lambda row: (row["dev_mean"], row["key"]))
        if winner["key"] != selected_data.get("key"):
            errors.append("Selected configuration is not the development winner")
        candidate = Proposal.build(selected_data["method"], selected_data["params"])
        if candidate.key != selected_data.get("key"):
            errors.append("Selected proposal key mismatch")
    except (ValueError, KeyError, TypeError, StudyValidationError):
        errors.append("Invalid selected configuration")
    baseline_data = results.get("baseline", {})
    if baseline_data.get("method") != "random_search":
        errors.append("Baseline algorithm mismatch")

    groups: list[tuple[str, list[dict[str, Any]], tuple[int, ...]]] = []
    for row in leaderboard:
        key = row.get("key")
        group = development.get(key, [])
        if not isinstance(group, list):
            errors.append("Malformed development seed group")
            continue
        groups.append(("development", group, spec.dev_seeds))
        if [r.get("seed") for r in group] != list(spec.dev_seeds):
            errors.append("Development seed partition corrupted")
        if any(r.get("method") != row.get("method") or r.get("params") != row.get("params") for r in group):
            errors.append("Development method or parameter mismatch")
        if group and not math.isclose(mean(r["best_value"] for r in group), row["dev_mean"], rel_tol=1e-12, abs_tol=1e-12):
            errors.append("Development mean is not supported by measured runs")
    for name, field in (("baseline", "holdout_baseline"), ("selected", "holdout_selected")):
        group = results.get(field, [])
        if not isinstance(group, list):
            errors.append("Malformed holdout seed group")
            continue
        groups.append((name, group, spec.test_seeds))
        if [r.get("seed") for r in group] != list(spec.test_seeds):
            errors.append("Holdout seed partition corrupted")
        expected_method = baseline_data.get("method") if name == "baseline" else selected_data.get("method")
        expected_params = baseline_data.get("params") if name == "baseline" else selected_data.get("params")
        if any(r.get("method") != expected_method or r.get("params") != expected_params for r in group):
            errors.append("Holdout method or parameter mismatch")

    seen = 0
    evaluations = 0
    for label, group, _ in groups:
        for item in group:
            try:
                actual = _decode(item)
                proposal = Proposal.build(actual.method, actual.params)
                expected = run_seed(spec, proposal, actual.seed)
                if expected.evaluations != actual.evaluations:
                    errors.append(f"Evaluation count differs: {label}/{actual.seed}")
                if expected.trace_sha256 != actual.trace_sha256:
                    errors.append(f"Experiment trace differs: {label}/{actual.seed}")
                if expected.best_position != actual.best_position:
                    errors.append(f"Best position differs: {label}/{actual.seed}")
                if not math.isclose(expected.best_value, actual.best_value, abs_tol=1e-10, rel_tol=1e-10):
                    errors.append(f"Best objective differs: {label}/{actual.seed}")
                if verify_seed(spec, actual):
                    errors.append(f"Saved solution fails independent verification: {label}/{actual.seed}")
                seen += 1
                evaluations += actual.evaluations
            except (KeyError, TypeError, ValueError, StudyValidationError) as exc:
                errors.append(f"Malformed result entry: {type(exc).__name__}")
    if seen == 0:
        errors.append("No runs found to replay")
    if evaluations != manifest.get("experimental_evaluations"):
        errors.append("Total evaluation count differs from manifest")
    try:
        b = [_decode(item) for item in results["holdout_baseline"]]
        c = [_decode(item) for item in results["holdout_selected"]]
        verdict = compare_holdout(spec, b, c)
        if verdict != results.get("verdict"):
            errors.append("Holdout scientific verdict differs from recomputed evidence")
    except (KeyError, TypeError, ValueError, StudyValidationError):
        errors.append("Holdout verdict could not be recomputed")
    return errors
