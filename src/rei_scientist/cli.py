"""Research orchestrator command line; local by default, remote assistants opt-in."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from . import __version__
from .artifacts import save_study, write_json
from .literature import search_crossref
from .llm import formulate_question, propose_candidates
from .models import BENCHMARKS, StudySpec, StudyValidationError
from .replay import replay_artifacts
from .search import run_search


def _template(benchmark: str, study_id: str, question: str | None = None,
              hypothesis: str | None = None, source_note: str | None = None) -> dict:
    return {
        "schema_version": "1.0", "study_id": study_id,
        "question": question or f"Can a local search method outperform uniform random search on {benchmark} in 2D?",
        "hypothesis": hypothesis or "At equal function-evaluation budgets, local search reduces the final mean objective by at least 5% versus random search.",
        "benchmark": benchmark, "dimension": 2, "bounds": [-5.0, 5.0],
        "evaluation_budget": 120, "candidate_budget": 8, "max_depth": 2,
        "dev_seeds": [11, 23, 37], "test_seeds": [101, 103, 107, 109, 113],
        "minimum_improvement_pct": 5.0,
        "methods": ["random_search", "hill_climb", "simulated_annealing"],
        "source_note": source_note or "Synthetic analytic benchmark; no real-world measurements",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rei-scientist", description="Bounded, evidence-first scientific experiments")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a versioned research study template (no network)")
    init.add_argument("--benchmark", choices=sorted(BENCHMARKS), default="sphere")
    init.add_argument("--study-id", default="sphere-pilot")
    init.add_argument("--out", type=Path, required=True)

    ideate = commands.add_parser("ideate", help="Opt-in LLM generation of falsifiable hypothesis wording")
    ideate.add_argument("--topic-file", type=Path, required=True)
    ideate.add_argument("--benchmark", choices=sorted(BENCHMARKS), required=True)
    ideate.add_argument("--study-id", required=True)
    ideate.add_argument("--out", type=Path, required=True)

    run = commands.add_parser("run", help="Run bounded best-first search; write audit artifacts")
    run.add_argument("study", type=Path)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--llm-proposals", action="store_true", help="Explicitly send study metadata to an LLM endpoint")
    run.add_argument("--literature", action="store_true", help="Explicitly query Crossref for metadata; requires network")

    replay = commands.add_parser("verify", help="Hash-check and re-execute all saved experiments")
    replay.add_argument("directory", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            spec = StudySpec.from_dict(_template(args.benchmark, args.study_id))
            if args.out.exists():
                raise FileExistsError("Refusing to overwrite an existing study file")
            write_json(args.out, spec.to_dict())
            print(f"Study created: {args.out}")
            return 0
        if args.command == "ideate":
            if args.topic_file.stat().st_size > 5000:
                raise StudyValidationError("Topic file is too large")
            topic = args.topic_file.read_text(encoding="utf-8")
            question, hypothesis = formulate_question(topic, args.benchmark)
            spec = StudySpec.from_dict(_template(args.benchmark, args.study_id, question, hypothesis,
                "LLM-assisted hypothesis wording; human scientific validity review required"))
            if args.out.exists():
                raise FileExistsError("Refusing to overwrite an existing study file")
            write_json(args.out, spec.to_dict())
            print(f"AI-assisted study created: {args.out}; hypothesis requires review")
            return 0
        if args.command == "run":
            data = json.loads(args.study.read_text(encoding="utf-8"))
            spec = StudySpec.from_dict(data)
            if args.out.exists():
                raise FileExistsError("Refusing to overwrite experiment output")
            ideas = propose_candidates(spec) if args.llm_proposals else None
            papers = search_crossref(spec.question) if args.literature else []
            outcome = run_search(spec, ideas)
            manifest = save_study(args.out, spec, outcome, bool(args.llm_proposals), papers)
            print(f"Study: {spec.study_id}; verdict: {outcome.verdict['status']}")
            print(f"Selected: {outcome.selected.method} {outcome.selected.param_dict()}")
            print(f"Objective evaluations: {manifest['experimental_evaluations']}")
            print(f"Artifacts: {args.out}")
            return 0
        if args.command == "verify":
            problems = replay_artifacts(args.directory)
            if problems:
                for item in problems[:20]:
                    print(f"VERIFY FAIL: {item}", file=sys.stderr)
                return 2
            print("VERIFY PASS: artifacts, code hash, objective values, seeds and traces")
            return 0
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 2
