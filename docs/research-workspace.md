# REI Scientist — Experimental Research Workspace

This adds a local, persistent interface **inside the existing REI Scientist Python package**. It does not deploy a new website or change the original `rei-scientist run`, `verify`, study schema (v1.0), or replay path. It is an independent versioned study-record adapter; it does **not** claim that a ChatGPT Sites project has been edited.

## Launch

```bash
pip install -e .
rei-scientist-workspace --db ./data/workspace.sqlite3 --port 8765
# Open http://127.0.0.1:8765
```

The workspace binds **only** to IPv4 loopback (`127.0.0.1`). Do not reverse-proxy it onto the Internet. This single-user local interface has no account authorization and must be placed behind a separately reviewed auth gateway before any hosted/multi-user deployment.

## Capabilities

- Turkish UI with retained English scientific terminology; Rootcastle color palette.
- Templates for REI Track, REI Balance, GPS/IoT, Embedded Systems and other Rootcastle research.
- Structured research question, requirements, variables with SI-related units, hard/soft constraints, datasets, sources, compute budgets, version, seed, tolerance, stopping criterion, baseline, candidate methods, hypotheses, uncertainties and `NOT VERIFIED` ledger.
- Normalized, dimensionless **sum of squared ratios** objective: each variable and scale must have the same dimension. Only this restricted form is checked. Arbitrary expression strings inside constraints are recorded but **not** symbolically verified or executed.
- Append-only SQLite revisions with optimistic conflict checks. Restore writes a *new revision*, preserving history.
- Search by text; filter by project and lifecycle status; export a JSON record, Markdown experiment plan, results/residual CSV, and source-data SVG. Missing measurements are **not** synthesized.
- Optional `rei-scientist-figure --db ./data/workspace.sqlite3 --id <uuid> --out ./figures/example` exports a 300-DPI PNG and vector SVG from recorded baseline/candidate values (install `pip install -e '.[figures]'`). Every variable uses its own axis, with explicit units; cross-unit quantities must not share an axis.

## Security, evidence and recovery

- Local SQLite data can contain proprietary research. Back up the DB with its revision table and any referenced datasets, and protect its filesystem permissions. `workspace.sqlite3` is set to owner-only permissions where supported. Prefer separate dataset storage over embedding large files.
- Same-origin write token, Origin/Host checks, loopback-only binding, capped JSON body, no third-party JavaScript, strict CSP, no CORS allowance. These are local hardening, **not a production authentication system**. Users sharing the same OS account may be able to access the loopback server.
- No actual experiment execution, physical machine control, device actuation, source scraping, field validation, HIL or external software integration occurs in this module.
- A manually entered `PASS` is not independently attested by the app. Independent validation, datasets and review remain necessary; keep `NOT VERIFIED` unless evidence supports the claim.
- Rollback: stop the service and revert/remove workspace entry points. The legacy research engine is unaffected. Keep the database as a separate file and do not auto-migrate the existing `run` / `verify` schema.
- If integrated into an existing ChatGPT Sites application, retain the Sites project ID and adapt through a versioned, authenticated API gateway with migrations and audit logs. **Do not create a duplicate Sites project**. The local HTTP server should not be directly exposed.

## Tests

```bash
python -m unittest discover -s tests -p 'test_workspace*.py' -v
python -m compileall -q src tests
```
