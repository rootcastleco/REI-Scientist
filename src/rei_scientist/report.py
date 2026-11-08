"""Evidence-led Markdown research report, never a claim of peer review."""
from __future__ import annotations
from typing import Any
from html import escape
from .models import StudySpec
from .search import SearchOutcome


def _markdown_text(value: str) -> str:
    """Do not allow untrusted topic/bibliographic text to inject Markdown or HTML."""
    value = escape(value.replace("\r", " ").replace("\n", " "), quote=False)
    for character in ("\\", "`", "*", "_", "[", "]", "#", "|", "!"):
        value = value.replace(character, "\\" + character)
    return value


def make_report(spec: StudySpec, outcome: SearchOutcome, manifest: dict[str, Any],
                literature: list[dict[str, Any]]) -> str:
    v = outcome.verdict
    rows = [
        "| Configuration | Development mean objective | Parent |",
        "|---|---:|---|",
    ]
    for item in sorted(outcome.leaderboard, key=lambda x: x["dev_mean"]):
        rows.append(f"| `{item['method']}` {item['params']} | {item['dev_mean']:.8g} | `{item['parent'] or 'root'}` |")
    if literature:
        citation_lines = [f"- {_markdown_text(str(entry.get('title', 'Untitled')))} ({entry.get('year', '?')}); DOI: {_markdown_text(str(entry.get('doi', 'NOT VERIFIED')))}. Metadata only, content NOT VERIFIED."
                          for entry in literature]
    else:
        citation_lines = ["- No literature retrieval was executed. Related-work coverage: NOT VERIFIED."]
    baseline = v["baseline_mean"]
    candidate = v["candidate_mean"]
    result_text = (
        f"- Baseline mean: **{baseline:.8g}**\n"
        f"- Candidate mean: **{candidate:.8g}**\n"
        f"- Absolute mean improvement: **{v['mean_delta']:.8g}**\n"
        f"- Relative mean improvement: **{v['relative_improvement_pct']:.3f}%**\n"
        f"- Paired wins: **{v['paired_wins']}/{v['holdout_seeds']}**\n"
        f"- Exploratory paired bootstrap 95% CI of mean improvement: **{v['ci95_delta']}**\n"
        if baseline is not None else "- Holdout metrics: NOT VERIFIED due to verification errors.\n"
    )
    return f"""# REI Scientist research report: {spec.study_id}

## Integrity and disclosure

**Research status: {v['status']}**. This is an automated exploratory engineering experiment, **not a peer-reviewed scientific publication**.
Any model-assisted configurations must be disclosed; LLM proposals used: **{'YES' if manifest['llm_generated_proposals'] else 'NO'}**.

## Research question

{_markdown_text(spec.question)}

**Predeclared hypothesis:** {_markdown_text(spec.hypothesis)}

## Protocol

- Benchmark: `{spec.benchmark}`, dimension: {spec.dimension}, bounds: {spec.bounds}
- Objective: **minimize** analytic benchmark; independently recomputed at the reported solution
- Baseline: `random_search`; development seeds: {list(spec.dev_seeds)}
- Holdout seeds, never used for configuration selection: {list(spec.test_seeds)}
- Evaluation budget: **{spec.evaluation_budget} per method per seed**, candidates explored: {len(outcome.leaderboard)-1} / {spec.candidate_budget}
- Predeclared target: **{spec.minimum_improvement_pct:.2f}%** relative improvement, positive bootstrap lower bound
- Source note: {_markdown_text(spec.source_note)}

## Development search (not confirmatory evidence)

{chr(10).join(rows)}

**Selected configuration:** `{outcome.selected.method}` `{outcome.selected.param_dict()}`.
Selection uses only development seeds. Holdout results are evaluated once after selection.

## Independent holdout evaluation

{result_text}
**Decision: {v['status']}**. Reasons: {'; '.join(v['reasons'])}.

## Independent verification

- Feasibility bounds and dimensionality checked for every recorded solution.
- Objective values recomputed using a separate reference implementation.
- Every recorded run checked against the prescribed evaluation count.
- Exact stochastic traces are fingerprinted with SHA-256 for reproducibility investigation.

## Provenance and reproducibility

- Study SHA-256: `{manifest['study_sha256']}`
- Results SHA-256: `{manifest['results_sha256']}`
- Source snapshot SHA-256: `{manifest['source_sha256']}`
- Python: `{manifest['python_version']}`
- Total objective evaluations: {manifest['experimental_evaluations']}
- Data: {manifest['data_provenance']}
- Re-run the source study JSON and compare results, ignoring elapsed time and generated timestamps.

## Related work

{chr(10).join(citation_lines)}

## Limitations, risks and release gate

- Synthetic analytic benchmarks do not establish performance on real machinery, GNSS, medical, or industrial data.
- The percentile bootstrap is exploratory and cannot establish a formal generalization guarantee with a small holdout set.
- The hyperparameter search can overfit development seeds; holdout seeds are isolated but benchmark selection was not blinded.
- Some algorithms and benchmarks have different landscapes; results cannot be generalized to other objective functions.
- Literature metadata alone does not verify scientific claims. References must be checked against original papers before publication.
- Manuscript submission requires independent human review, full methods disclosure and external replication.

## Next experiment

Add a separately versioned real or synthetic domain-specific benchmark through a reviewed, approved adapter. Do not grant model-written code access to the host environment.
"""
