"""Offline, self-contained Rootcastle-branded experiment viewer (no JavaScript)."""
from __future__ import annotations
from html import escape
from typing import Any

from .models import StudySpec
from .search import SearchOutcome


def _metric(value: float | None, suffix: str = "") -> str:
    return (f"{value:.6g}{suffix}" if value is not None else "NOT VERIFIED")


def build_dashboard(spec: StudySpec, outcome: SearchOutcome, manifest: dict[str, Any]) -> str:
    """All user-controlled strings HTML-escaped; all styles and content are offline."""
    verdict = outcome.verdict
    selected = outcome.selected
    rows: list[str] = []
    max_loss = max(r["dev_mean"] for r in outcome.leaderboard)
    for item in sorted(outcome.leaderboard, key=lambda row: row["dev_mean"]):
        percent = 100 * item["dev_mean"] / max(1e-12, max_loss)
        label = escape(item["method"])
        params = escape(str(item["params"]))
        tag = "baseline" if item["is_baseline"] else ("selected" if item["key"] == selected.key else "candidate")
        rows.append(
            f'<tr><td><span class="dot {tag}"></span>{label}<div class="params">{params}</div></td>'
            f'<td><div class="bar-track"><span class="bar {tag}" style="width:{percent:.3f}%"></span></div></td>'
            f'<td class="num">{_metric(item["dev_mean"])}</td><td><code>{escape(item["key"])}</code></td></tr>'
        )
    status = verdict["status"]
    status_class = {"PASS": "pass", "FAIL": "fail", "NOT VERIFIED": "unknown"}.get(status, "unknown")
    reasons = "; ".join(verdict["reasons"])
    mean_base = _metric(verdict["baseline_mean"])
    mean_candidate = _metric(verdict["candidate_mean"])
    pct = _metric(verdict["relative_improvement_pct"], "%")
    ci = verdict["ci95_delta"]
    ci_text = (f"[{ci[0]:.5g}, {ci[1]:.5g}]" if ci is not None else "NOT VERIFIED")
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>REI Scientist | {escape(spec.study_id)}</title>
<style>
:root {{ color-scheme: dark; --bg:#090d16; --card:#111825; --ink:#ecf3fb; --muted:#a4b4c9; --line:#28364c; --blue:#0E3D8A; --green:#228B55; --amber:#c38b44; }}
* {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--ink); font-family:Inter,Segoe UI,Arial,sans-serif; line-height:1.5 }}
main {{ width:min(1120px, 94vw); margin:0 auto 5rem }} .top {{ border-bottom:1px solid var(--line); background:#080b11 }}
.top-inner {{ width:min(1120px,94vw); margin:auto; padding:1.2rem 0; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:1rem }}
.brand {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:1rem; font-weight:800; letter-spacing:0.12em; }}
.brand span {{ color:#5cc894 }} .meta {{ color:var(--muted); font-family:ui-monospace,monospace; font-size:.78rem }}
h1 {{ font-size:clamp(1.65rem,4vw,2.7rem); letter-spacing:-.03em; margin:1.7rem 0 .6rem }}
h2 {{ font-size:1.1rem; margin:0 0 1rem }} p {{ margin:.55rem 0 }}
.lead {{ color:var(--muted); max-width:830px; font-size:1.05rem }}
.status {{ display:inline-flex; border:1px solid var(--line); border-radius:3px; padding:.3rem .65rem; font-family:ui-monospace,monospace; font-size:.8rem; font-weight:800; letter-spacing:.05em }}
.status.pass {{ color:#70dba3; border-color:#27734a }} .status.fail {{ color:#f19090; border-color:#a63b3b }} .status.unknown {{ color:#e0ad66; border-color:#8b6030 }}
.section {{ margin-top:1.75rem }} .metrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.85rem; margin-top:1.6rem }}
.panel,.metric {{ padding:1.25rem; border:1px solid var(--line); background:var(--card); border-radius:7px }}
.metric small {{ display:block; color:var(--muted); font-size:.75rem; letter-spacing:.06em; text-transform:uppercase }}
.metric strong {{ font-family:ui-monospace,monospace; font-size:clamp(1.1rem,2.4vw,1.65rem); display:block; margin-top:.35rem; word-break:break-word }}
.metric.primary {{ border-top:3px solid #2f72bb }} .metric.good {{ border-top:3px solid var(--green) }}
.grid {{ display:grid; grid-template-columns:1fr 1fr; gap:.85rem }}
.kv {{ display:grid; grid-template-columns:180px minmax(0,1fr); gap:.5rem .8rem; font-size:.9rem }}
.kv dt {{ color:var(--muted) }} .kv dd {{ margin:0; overflow-wrap:anywhere }}
table {{ width:100%; border-collapse:collapse; font-size:.89rem }} th {{ text-align:left; color:var(--muted); font-weight:600; border-bottom:1px solid var(--line); padding:.7rem .4rem }} td {{ border-bottom:1px solid #1f2b3d; padding:.8rem .4rem; vertical-align:middle }}
.num {{ font-family:ui-monospace,monospace; font-variant-numeric:tabular-nums; white-space:nowrap }}
.params {{ font-family:ui-monospace,monospace; font-size:.7rem; color:var(--muted); overflow-wrap:anywhere; padding-top:.15rem }}
.bar-track {{ background:#273348; height:8px; border-radius:2px; min-width:70px; overflow:hidden }} .bar {{ display:block; height:100%; background:#55718d }} .bar.selected {{ background:var(--green) }} .bar.baseline {{ background:#b2814b }}
.dot {{ display:inline-block; width:7px; height:7px; margin-right:.5rem; background:#55718d; border-radius:2px }} .dot.selected {{ background:var(--green) }} .dot.baseline {{ background:#b2814b }}
code {{ color:#b6d5f4; font-size:.8rem }} .note {{ border-left:3px solid var(--amber); padding:.8rem 1rem; background:#191912; color:#ded8c8; margin-top:1rem }}
footer {{ color:var(--muted); padding-top:2rem; border-top:1px solid var(--line); margin-top:3rem; font-size:.8rem }}
@media(max-width:790px) {{ .metrics {{ grid-template-columns:repeat(2,minmax(0,1fr)) }} .grid {{ grid-template-columns:1fr }} .kv {{ grid-template-columns:115px 1fr }} .panel {{ overflow-x:auto }} }}
@media(max-width:460px) {{ .metrics {{ grid-template-columns:1fr }} }}
@media print {{ :root {{ color-scheme:light }} body {{ background:white;color:black }} .panel,.metric {{ background:white;color:black;border-color:#ccc }} .lead,.meta,.kv dt,.params,footer {{ color:#555 }} }}
</style>
</head>
<body>
<header class="top"><div class="top-inner"><div class="brand">ROOTCASTLE <span>/ REI SCIENTIST</span></div><div class="meta">RESEARCH ENGINE v0.1.0 &nbsp; / &nbsp; OFFLINE AUDIT</div></div></header>
<main>
<h1>{escape(spec.study_id)}</h1>
<div class="status {status_class}">{escape(status)}</div>
<p class="lead">{escape(spec.question)}</p>
<div class="metrics">
<div class="metric primary"><small>Baseline mean (holdout)</small><strong>{mean_base}</strong></div>
<div class="metric good"><small>Selected mean (holdout)</small><strong>{mean_candidate}</strong></div>
<div class="metric"><small>Relative improvement</small><strong>{pct}</strong></div>
<div class="metric"><small>Function evaluations</small><strong>{manifest['experimental_evaluations']:,}</strong></div>
</div>
<div class="grid section">
<section class="panel"><h2>Experiment protocol</h2><dl class="kv">
<dt>Benchmark</dt><dd><code>{escape(spec.benchmark)}</code></dd>
<dt>Dimension</dt><dd>{spec.dimension}</dd>
<dt>Bounds</dt><dd>{spec.bounds}</dd>
<dt>Per-run budget</dt><dd>{spec.evaluation_budget} evaluations</dd>
<dt>Development seeds</dt><dd>{escape(str(list(spec.dev_seeds)))}</dd>
<dt>Holdout seeds</dt><dd>{escape(str(list(spec.test_seeds)))}</dd>
<dt>Improvement target</dt><dd>{spec.minimum_improvement_pct:.2f}%</dd>
<dt>Bootstrap mean-delta 95% CI</dt><dd>{ci_text}</dd>
</dl></section>
<section class="panel"><h2>Predeclared hypothesis</h2><p>{escape(spec.hypothesis)}</p><h2 style="margin-top:1.4rem">Selected configuration</h2><p><code>{escape(selected.method)} {escape(str(selected.param_dict()))}</code></p><p class="meta">Development-only selection. One-time holdout. Paired wins: {verdict['paired_wins']}/{verdict['holdout_seeds']}.</p></section>
</div>
<section class="panel section"><h2>Best-first experiment exploration</h2><p class="meta">Development objective; smaller is better. Bar length represents loss, not performance gain.</p><table><thead><tr><th>Algorithm</th><th>Relative loss</th><th>Mean</th><th>Node</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section class="panel section"><h2>Verification and disclosure</h2><p>{escape(reasons)}</p><dl class="kv">
<dt>Solution feasibility</dt><dd>Independently checked</dd>
<dt>Objective values</dt><dd>Recomputed through separate formulas</dd>
<dt>Replay</dt><dd>Use <code>rei-scientist verify RUN_DIR</code></dd>
<dt>Input SHA-256</dt><dd><code>{manifest['study_sha256']}</code></dd>
<dt>Source SHA-256</dt><dd><code>{manifest['source_sha256']}</code></dd>
<dt>LLM proposals</dt><dd>{'USED' if manifest['llm_generated_proposals'] else 'NONE'}</dd>
</dl><div class="note"><b>Evidence limitation:</b> Synthetic analytic optimization benchmark only. A PASS is a local protocol gate, not proof of novelty, external validity, peer review or clinical/industrial safety.</div></section>
<footer>REI Scientist / Rootcastle Engineering &amp; Innovation &nbsp; | &nbsp; Versioned, inspectable research artifacts &nbsp; | &nbsp; {escape(manifest['created_utc'])}</footer>
</main>
</body></html>
'''
