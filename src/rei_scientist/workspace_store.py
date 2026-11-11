"""Versioned, local-first engineering study records. No experiment execution.

Standalone adapter: never modifies legacy StudySpec, run, verify or replay semantics.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import csv
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import uuid
from typing import Any

STATUS = {"DRAFT", "ACTIVE", "ARCHIVED"}
VERDICTS = {"PASS", "FAIL", "NOT VERIFIED"}
PROJECTS = ("REI Track", "REI Balance", "GPS/IoT", "Embedded Systems", "Rootcastle / Other")
FIELDS = {"title", "project", "research_question", "requirements", "variables", "constraints",
          "datasets", "sources", "compute_budget", "version", "seed", "tolerance",
          "stop_criterion", "baseline", "candidate_methods", "hypotheses", "uncertainties",
          "not_verified", "objective", "results", "status", "verification_status"}
# Dimension vector: kg, m, s, A, K. Ratio terms are dimensionless.
DIM0 = (0, 0, 0, 0, 0)
UNITS: dict[str, tuple[tuple[int, ...], float]] = {
    "1": (DIM0, 1), "%": (DIM0, .01), "ppm": (DIM0, 1e-6),
    "rad": (DIM0, 1), "deg": (DIM0, math.pi / 180),
    "s": ((0, 0, 1, 0, 0), 1), "ms": ((0, 0, 1, 0, 0), 1e-3),
    "us": ((0, 0, 1, 0, 0), 1e-6), "min": ((0, 0, 1, 0, 0), 60),
    "Hz": ((0, 0, -1, 0, 0), 1), "rpm": ((0, 0, -1, 0, 0), 1/60),
    "m": ((0, 1, 0, 0, 0), 1), "mm": ((0, 1, 0, 0, 0), .001),
    "km": ((0, 1, 0, 0, 0), 1000),
    "m/s": ((0, 1, -1, 0, 0), 1), "mm/s": ((0, 1, -1, 0, 0), .001),
    "m/s^2": ((0, 1, -2, 0, 0), 1),
    "kg": ((1, 0, 0, 0, 0), 1), "g": ((1, 0, 0, 0, 0), .001),
    "mg": ((1, 0, 0, 0, 0), 1e-6),
    "A": ((0, 0, 0, 1, 0), 1), "mA": ((0, 0, 0, 1, 0), .001),
    "V": ((1, 2, -3, -1, 0), 1), "mV": ((1, 2, -3, -1, 0), .001),
    "W": ((1, 2, -3, 0, 0), 1), "J": ((1, 2, -2, 0, 0), 1),
    "Pa": ((1, -1, -2, 0, 0), 1),
    "K": ((0, 0, 0, 0, 1), 1),
    "B": (DIM0, 1), "kB": (DIM0, 1000), "MB": (DIM0, 1e6),
}


class WorkspaceError(ValueError):
    pass


class ConflictError(WorkspaceError):
    pass


def _text(value: Any, field: str, required: bool = False, max_len: int = 2000) -> str:
    if not isinstance(value, str) or len(value) > max_len or (required and not value.strip()):
        raise WorkspaceError(f"{field}: nonempty string required" if required else f"{field}: invalid string")
    return value.strip()


def _number(value: Any, field: str, minimum: float | None = None, maximum: float | None = None) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise WorkspaceError(f"{field}: finite numeric value required")
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise WorkspaceError(f"{field}: outside allowed bounds")
    return float(value)


def _list(value: Any, field: str, limit: int = 100) -> list:
    if not isinstance(value, list) or len(value) > limit:
        raise WorkspaceError(f"{field}: expected list (max {limit})")
    return value


def new_study(project: str = "REI Track") -> dict[str, Any]:
    if project not in PROJECTS:
        raise WorkspaceError("Unknown project template")
    base: dict[str, Any] = {
        "title": "Yeni araştırma", "project": project,
        "research_question": "Bu çalışmanın hangi ölçülebilir hipotezi sınadığı belirtilecek?",
        "requirements": [], "variables": [], "constraints": [], "datasets": [], "sources": [],
        "compute_budget": {"evaluations": 1000, "cpu_seconds": 3600, "memory_mb": 1024},
        "version": "0.1.0", "seed": 42, "tolerance": 1e-6,
        "stop_criterion": "Evaluation budget veya önceden belirlenmiş tolerans eşiği",
        "baseline": {"method": "Ölçülmemiş baseline", "notes": "NOT VERIFIED"},
        "candidate_methods": [], "hypotheses": [], "uncertainties": [],
        "not_verified": ["Gerçek saha/deney verisi henüz bağlanmadı"],
        "objective": {"sense": "min", "terms": []},
        "results": [], "status": "DRAFT", "verification_status": "NOT VERIFIED",
    }
    configs = {
        "REI Track": ("GNSS/telemetri kaybını ve yanlış cihaz durumunu, belirtilen kaynak sınırları içinde azaltmak mümkün mü?", "event_loss", "%", "10"),
        "REI Balance": ("Düzeltme ağırlığı ve faz tahmininden sonra rezidüel vibrasyon ne ölçüde azalır?", "residual_velocity", "mm/s", "1"),
        "GPS/IoT": ("Belirtilen güç bütçesinde konum güncelleme gecikmesi nasıl değişir?", "latency", "ms", "1000"),
        "Embedded Systems": ("Verilen görev zamanlamasında en kötü durum gecikmesi hangi aralıkta kalır?", "response_time", "ms", "10"),
        "Rootcastle / Other": ("Önerilen yöntem, önceden tanımlanmış baseline'a göre ölçülebilir iyileşme sağlıyor mu?", "error", "1", "1"),
    }
    question, metric, unit, scale = configs[project]
    base["research_question"] = question
    base["title"] = f"{project} — doğrulanmamış çalışma taslağı"
    base["variables"] = [{"symbol": metric, "unit": unit, "role": "metric", "lower": 0, "upper": None}]
    base["objective"]["terms"] = [{"variable": metric, "weight": 1, "scale": float(scale), "scale_unit": unit}]
    base["candidate_methods"] = ["İlk aday yöntem: tanımlanacak"]
    base["hypotheses"] = [{"statement": "Aday yöntem, aynı ölçüm koşullarında baseline'dan daha iyi sonuç verir.", "test": "Eşleştirilmiş karşılaştırma; eşik önceden belirlenecek"}]
    return base


def validate_study(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != FIELDS:
        missing = FIELDS - set(value) if isinstance(value, dict) else FIELDS
        extra = set(value) - FIELDS if isinstance(value, dict) else set()
        raise WorkspaceError(f"Study schema mismatch: missing={sorted(missing)}, extra={sorted(extra)}")
    s = deepcopy(value)
    for key in ("title", "research_question", "version", "stop_criterion"):
        _text(s[key], key, required=True)
    if s["project"] not in PROJECTS:
        raise WorkspaceError("Invalid project")
    if s["status"] not in STATUS or s["verification_status"] not in VERDICTS:
        raise WorkspaceError("Invalid status")
    if type(s["seed"]) is not int or not 0 <= s["seed"] < 2**32:
        raise WorkspaceError("seed: expected integer in [0, 2^32)")
    _number(s["tolerance"], "tolerance", minimum=0, maximum=1e6)
    budget = s["compute_budget"]
    if not isinstance(budget, dict) or set(budget) != {"evaluations", "cpu_seconds", "memory_mb"}:
        raise WorkspaceError("compute_budget: expected evaluations, cpu_seconds, memory_mb")
    for k in budget:
        _number(budget[k], k, minimum=1, maximum=1e9)
    if not isinstance(s["baseline"], dict) or set(s["baseline"]) != {"method", "notes"}:
        raise WorkspaceError("Invalid baseline")
    _text(s["baseline"]["method"], "baseline.method", required=True)
    _text(s["baseline"]["notes"], "baseline.notes")
    _list(s["requirements"], "requirements")
    for r in s["requirements"]:
        if not isinstance(r, dict) or set(r) != {"id", "description", "verification"}:
            raise WorkspaceError("Requirement expects id, description, verification")
        _text(r["id"], "requirement id", required=True, max_len=64)
        _text(r["description"], "requirement description", required=True)
        if r["verification"] not in VERDICTS:
            raise WorkspaceError("Invalid requirement verification")
    symbols: dict[str, str] = {}
    _list(s["variables"], "variables")
    for v in s["variables"]:
        if not isinstance(v, dict) or set(v) != {"symbol", "unit", "role", "lower", "upper"}:
            raise WorkspaceError("Variable expects symbol, unit, role, lower, upper")
        name = _text(v["symbol"], "symbol", required=True, max_len=64)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name) or name in symbols:
            raise WorkspaceError("Duplicate/invalid variable symbol")
        unit = v["unit"]
        if unit not in UNITS:
            raise WorkspaceError(f"Unsupported unit: {unit!r}; map it before analysis")
        symbols[name] = unit
        if v["role"] not in {"metric", "decision", "disturbance"}:
            raise WorkspaceError("Invalid variable role")
        for bound in ("lower", "upper"):
            if v[bound] is not None:
                _number(v[bound], f"{name}.{bound}")
        if v["lower"] is not None and v["upper"] is not None and v["lower"] >= v["upper"]:
            raise WorkspaceError("Variable lower bound must be less than upper bound")
    for field in ("constraints", "datasets", "sources", "hypotheses", "uncertainties"):
        _list(s[field], field)
        if not all(isinstance(row, dict) for row in s[field]):
            raise WorkspaceError(f"{field}: expected list of objects")
    for c in s["constraints"]:
        if set(c) != {"expression", "kind", "verification"} or c["kind"] not in {"hard", "soft"} or c["verification"] not in VERDICTS:
            raise WorkspaceError("Constraint expects expression, hard/soft, verification")
        _text(c["expression"], "constraint.expression", required=True)
    for d in s["datasets"]:
        if set(d) != {"name", "sha256", "source", "verification"} or d["verification"] not in VERDICTS:
            raise WorkspaceError("Dataset expects name, sha256, source, verification")
        _text(d["name"], "dataset.name", required=True)
        _text(d["source"], "dataset.source")
        if d["sha256"] and not re.fullmatch(r"[0-9a-fA-F]{64}", d["sha256"]):
            raise WorkspaceError("Dataset sha256 must contain 64 hex characters")
    for r in s["sources"]:
        if set(r) != {"title", "url"}:
            raise WorkspaceError("Source expects title and URL")
        _text(r["title"], "source.title", required=True)
        if r["url"] and (not isinstance(r["url"], str) or not r["url"].startswith("https://") or len(r["url"]) > 2000):
            raise WorkspaceError("Sources must use https URLs")
    for h in s["hypotheses"]:
        if set(h) != {"statement", "test"}:
            raise WorkspaceError("Hypothesis expects statement and test")
        _text(h["statement"], "hypothesis.statement", required=True)
        _text(h["test"], "hypothesis.test", required=True)
    for u in s["uncertainties"]:
        if set(u) != {"name", "range", "verification"} or u["verification"] not in VERDICTS:
            raise WorkspaceError("Uncertainty expects name, range, verification")
        _text(u["name"], "uncertainty.name", required=True)
        _text(u["range"], "uncertainty.range")
    for field in ("candidate_methods", "not_verified"):
        _list(s[field], field)
        for t in s[field]:
            _text(t, field, required=True)
    obj = s["objective"]
    if not isinstance(obj, dict) or set(obj) != {"sense", "terms"} or obj["sense"] not in {"min", "max"}:
        raise WorkspaceError("Objective must provide min/max and terms")
    _list(obj["terms"], "objective.terms")
    for term in obj["terms"]:
        if not isinstance(term, dict) or set(term) != {"variable", "weight", "scale", "scale_unit"}:
            raise WorkspaceError("Objective term requires variable, weight, scale, scale_unit")
        if term["variable"] not in symbols or term["scale_unit"] not in UNITS:
            raise WorkspaceError("Objective term references an unknown variable or unit")
        if UNITS[symbols[term["variable"]]][0] != UNITS[term["scale_unit"]][0]:
            raise WorkspaceError(f"DIMENSION MISMATCH for {term['variable']}: {symbols[term['variable']]} / {term['scale_unit']}")
        _number(term["weight"], "objective weight", minimum=0, maximum=1e9)
        _number(term["scale"], "objective scale", minimum=1e-15, maximum=1e15)
    _list(s["results"], "results")
    for r in s["results"]:
        if not isinstance(r, dict) or set(r) != {"variable", "baseline", "candidate", "verification"}:
            raise WorkspaceError("Result expects variable, baseline, candidate, verification")
        if r["variable"] not in symbols or r["verification"] not in VERDICTS:
            raise WorkspaceError("Result has unknown variable or invalid verification")
        for k in ("baseline", "candidate"):
            if r[k] is not None:
                _number(r[k], f"result.{k}")
        if r["verification"] == "PASS" and (r["baseline"] is None or r["candidate"] is None):
            raise WorkspaceError("PASS cannot be set without two measurements")
    if s["verification_status"] == "PASS" and (
        not s["datasets"] or not s["results"] or bool(s["not_verified"])
        or any(not d["sha256"] or d["verification"] != "PASS" for d in s["datasets"])
        or any(r["verification"] != "PASS" for r in s["results"])
    ):
        raise WorkspaceError("Study PASS requires verified dataset hashes, PASS results and no open NOT VERIFIED items")
    return s


def normalized_objective(study: dict[str, Any]) -> str:
    """Auditable dimensionless form; never evaluate arbitrary user-supplied expressions."""
    sense = "min" if study["objective"]["sense"] == "min" else "max"
    pieces = []
    for term in study["objective"]["terms"]:
        v, w, scale, unit = term["variable"], term["weight"], term["scale"], term["scale_unit"]
        pieces.append(f"{w:g} * ({v} / ({scale:g} {unit}))^2")
    return f"{sense} J(x) = " + (" + ".join(pieces) if pieces else "NOT VERIFIED — no objective terms")


def residuals(study: dict[str, Any]) -> list[dict[str, Any]]:
    units = {v["symbol"]: v["unit"] for v in study["variables"]}
    return [{"variable": r["variable"], "unit": units[r["variable"]], "baseline": r["baseline"],
             "candidate": r["candidate"],
             "residual": (r["candidate"] - r["baseline"] if r["candidate"] is not None and r["baseline"] is not None else None),
             "verification": r["verification"]} for r in study["results"]]


def plan_markdown(study: dict[str, Any], revision: int = 0) -> str:
    lines = [f"# {study['title']}", "", f"Project: {study['project']}",
             f"Study version: {study['version']} | Record revision: {revision}",
             f"Verification: {study['verification_status']}", "", "## Research question",
             study["research_question"], "", "## Requirements"]
    lines += [f"- {r['id']}: {r['description']} [{r['verification']}]" for r in study["requirements"]] or ["- NOT VERIFIED"]
    lines += ["", "## Variables and domain", "| Symbol | Unit | Role | Lower | Upper |", "|---|---|---|---:|---:|"]
    lines += [f"| {v['symbol']} | {v['unit']} | {v['role']} | {v['lower']} | {v['upper']} |" for v in study["variables"]]
    lines += ["", "## Dimensionally normalized objective", "`" + normalized_objective(study) + "`",
              "", "The sum is dimensionless only for the validated term/scale unit dimensions. The physical model itself is NOT VERIFIED.",
              "", "## Constraints"]
    lines += [f"- {c['kind'].upper()}: {c['expression']} [{c['verification']}]" for c in study["constraints"]] or ["- NOT VERIFIED"]
    lines += ["", "## Experimental protocol", f"- Baseline: {study['baseline']['method']} — {study['baseline']['notes']}",
              "- Candidate methods: " + ", ".join(study["candidate_methods"]),
              f"- Seed: {study['seed']}", f"- Tolerance: {study['tolerance']}",
              f"- Budget: {study['compute_budget']}", f"- Stopping criterion: {study['stop_criterion']}",
              "", "## Hypotheses"]
    lines += [f"- {h['statement']} — Test: {h['test']}" for h in study["hypotheses"]] or ["- NOT VERIFIED"]
    lines += ["", "## Datasets and sources"]
    lines += [f"- Dataset {d['name']}; SHA-256: {d['sha256'] or 'NOT VERIFIED'}; source: {d['source']}; {d['verification']}" for d in study["datasets"]]
    lines += [f"- Source: {r['title']} — {r['url']}" for r in study["sources"]]
    if not study["datasets"] and not study["sources"]:
        lines.append("- NOT VERIFIED")
    lines += ["", "## Results and residuals", "| Variable | Unit | Baseline | Candidate | Candidate − baseline | Evidence |", "|---|---|---:|---:|---:|---|"]
    for r in residuals(study):
        lines.append(f"| {r['variable']} | {r['unit']} | {r['baseline']} | {r['candidate']} | {r['residual']} | {r['verification']} |")
    if not study["results"]:
        lines.append("| NOT VERIFIED | — | — | — | — | NOT VERIFIED |")
    lines += ["", "## Uncertainties and remaining verification"]
    lines += [f"- {u['name']}: {u['range']} [{u['verification']}]" for u in study["uncertainties"]]
    lines += [f"- {note}" for note in study["not_verified"]]
    lines += ["", "## Reproducibility checklist", "- [ ] Fixed code commit and runtime environment recorded",
              "- [ ] Dataset SHA-256 and collection protocol recorded", "- [x] Deterministic seed and resource budget declared",
              "- [ ] Baseline and candidate independently rerun", "- [ ] Residual thresholds and numerical oracles verified",
              "- [ ] Plot exports reviewed for axis units and provenance", "- [ ] Independent scientific review and sign-off", ""]
    return "\n".join(lines)


def results_csv(study: dict[str, Any]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(["variable", "unit", "baseline", "candidate", "residual", "verification"])
    for r in residuals(study):
        # Avoid spreadsheet formula injection in exported user-controlled labels.
        vals = [r[k] for k in ("variable", "unit", "baseline", "candidate", "residual", "verification")]
        writer.writerow([("'" + str(v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v) for v in vals])
    return buf.getvalue()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class WorkspaceStore:
    """SQLite snapshots with optimistic concurrency and append-only revisions."""
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _conn(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("PRAGMA foreign_keys=ON")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self) -> None:
        with self._conn() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS studies (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, project TEXT NOT NULL,
                status TEXT NOT NULL, revision INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS revisions (
                id TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY (id, revision),
                FOREIGN KEY(id) REFERENCES studies(id))""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_studies_project ON studies(project, status)")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "revision": row["revision"], "created_at": row["created_at"],
                "updated_at": row["updated_at"], "study": json.loads(row["payload"])}

    def create(self, study: dict[str, Any]) -> dict[str, Any]:
        s = validate_study(study)
        identifier = str(uuid.uuid4())
        now = _utc()
        payload = json.dumps(s, sort_keys=True, ensure_ascii=False, allow_nan=False)
        with self._conn() as db:
            db.execute("INSERT INTO studies VALUES (?,?,?,?,?,?,?,?)",
                       (identifier, s["title"], s["project"], s["status"], 1, now, now, payload))
            db.execute("INSERT INTO revisions VALUES (?,?,?,?)", (identifier, 1, now, payload))
        return self.get(identifier)

    def list(self, q: str = "", project: str = "", status: str = "") -> list[dict[str, Any]]:
        if len(q) > 200 or len(project) > 80 or len(status) > 30:
            raise WorkspaceError("Search filter too long")
        query = "SELECT id, title, project, status, revision, updated_at FROM studies WHERE 1=1"
        params: list[str] = []
        if q:
            query += " AND (lower(title) LIKE ? ESCAPE '\\' OR lower(payload) LIKE ? ESCAPE '\\')"
            safe = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.extend([f"%{safe}%", f"%{safe}%"])
        if project:
            query += " AND project=?"
            params.append(project)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY updated_at DESC, id DESC LIMIT 500"
        with self._conn() as db:
            return [dict(row) for row in db.execute(query, params)]

    def get(self, identifier: str) -> dict[str, Any]:
        with self._conn() as db:
            row = db.execute("SELECT * FROM studies WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return self._record(row)

    def update(self, identifier: str, expected_revision: int, study: dict[str, Any]) -> dict[str, Any]:
        if type(expected_revision) is not int or expected_revision < 1:
            raise WorkspaceError("Expected revision must be a positive integer")
        s = validate_study(study)
        payload = json.dumps(s, sort_keys=True, ensure_ascii=False, allow_nan=False)
        now = _utc()
        with self._conn() as db:
            cur = db.execute("""UPDATE studies SET title=?, project=?, status=?, revision=revision+1,
                              updated_at=?, payload=? WHERE id=? AND revision=?""",
                             (s["title"], s["project"], s["status"], now, payload, identifier, expected_revision))
            if cur.rowcount != 1:
                exists = db.execute("SELECT 1 FROM studies WHERE id=?", (identifier,)).fetchone()
                if exists:
                    raise ConflictError("Record changed. Reload before saving.")
                raise KeyError(identifier)
            db.execute("INSERT INTO revisions VALUES (?,?,?,?)", (identifier, expected_revision + 1, now, payload))
        return self.get(identifier)

    def history(self, identifier: str) -> list[dict[str, Any]]:
        self.get(identifier)
        with self._conn() as db:
            return [dict(r) for r in db.execute("SELECT revision, created_at FROM revisions WHERE id=? ORDER BY revision DESC", (identifier,))]

    def restore(self, identifier: str, expected_revision: int, source_revision: int) -> dict[str, Any]:
        with self._conn() as db:
            row = db.execute("SELECT payload FROM revisions WHERE id=? AND revision=?", (identifier, source_revision)).fetchone()
        if row is None:
            raise KeyError(source_revision)
        return self.update(identifier, expected_revision, json.loads(row["payload"]))
