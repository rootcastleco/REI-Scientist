"""Immutable study artifacts, provenance and safe atomic output."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
from typing import Any

from . import __version__
from .models import StudySpec
from .search import SearchOutcome


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False).encode("utf-8")


def write_json(path: Path, payload: Any) -> None:
    write_bytes(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".partial-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def source_hash() -> str:
    src_root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for file in sorted(src_root.glob("*.py")):
        digest.update(file.name.encode("utf-8"))
        digest.update(hashlib.sha256(file.read_bytes()).digest())
    return digest.hexdigest()


def save_study(out_dir: Path, spec: StudySpec, outcome: SearchOutcome, llm_used: bool,
               literature: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {out_dir}")
    out_dir.mkdir(parents=True)
    spec_data = spec.to_dict()
    record: dict[str, Any] = {
        "schema_version": "1.0", "study_id": spec.study_id,
        "baseline": outcome.baseline.to_dict(), "selected": outcome.selected.to_dict(),
        "development_leaderboard": outcome.leaderboard,
        "development_runs": {key: [r.to_dict() for r in runs]
                             for key, runs in outcome.dev_runs.items()},
        "holdout_baseline": [r.to_dict() for r in outcome.holdout_baseline],
        "holdout_selected": [r.to_dict() for r in outcome.holdout_selected],
        "verdict": outcome.verdict,
        "literature": literature or [],
    }
    write_json(out_dir / "study.json", spec_data)
    write_json(out_dir / "results.json", record)
    events = [{"seq": 1, "event": "study_validated", "study_id": spec.study_id}]
    for item in outcome.leaderboard:
        events.append({"seq": len(events) + 1, "event": "development_evaluated",
                       "proposal_key": item["key"], "method": item["method"],
                       "dev_mean": item["dev_mean"]})
    events.append({"seq": len(events) + 1, "event": "candidate_selected",
                   "proposal_key": outcome.selected.key})
    events.append({"seq": len(events) + 1, "event": "holdout_evaluated",
                   "verdict": outcome.verdict["status"]})
    event_data = b"".join(canonical_json(event) + b"\n" for event in events)
    write_bytes(out_dir / "events.jsonl", event_data)
    manifest = {
        "name": "REI Scientist", "version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "study_id": spec.study_id,
        "study_sha256": hashlib.sha256(canonical_json(spec_data)).hexdigest(),
        "results_sha256": hashlib.sha256(canonical_json(record)).hexdigest(),
        "source_sha256": source_hash(),
        "events_sha256": hashlib.sha256(event_data).hexdigest(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "llm_generated_proposals": llm_used,
        "external_literature_metadata_only": bool(literature),
        "experimental_evaluations": sum(x.evaluations for group in outcome.dev_runs.values() for x in group)
            + sum(x.evaluations for x in outcome.holdout_baseline)
            + sum(x.evaluations for x in outcome.holdout_selected),
        "data_provenance": "Analytic, deterministic synthetic benchmarks; no customer data",
    }
    from .report import make_report
    report_data = make_report(spec, outcome, manifest, literature or []).encode("utf-8")
    write_bytes(out_dir / "report.md", report_data)
    manifest["report_sha256"] = hashlib.sha256(report_data).hexdigest()
    from .dashboard import build_dashboard
    dashboard_data = build_dashboard(spec, outcome, manifest).encode("utf-8")
    write_bytes(out_dir / "dashboard.html", dashboard_data)
    manifest["dashboard_sha256"] = hashlib.sha256(dashboard_data).hexdigest()
    write_json(out_dir / "manifest.json", manifest)
    return manifest
