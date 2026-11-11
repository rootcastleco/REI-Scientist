"""Local-only HTTP adapter for the REI Scientist study workspace.

No network calls, device control, generated-code execution or mutation of the legacy
research engine. Do not put this unauthenticated loopback service on a public network.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from importlib import resources
from pathlib import Path
import re
import secrets
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape as xml_escape

from .workspace_store import (ConflictError, PROJECTS, WorkspaceError, WorkspaceStore,
                              new_study, normalized_objective, plan_markdown, residuals,
                              results_csv)

MAX_BODY = 256 * 1024
RECORD = re.compile(r"^/api/studies/([a-f0-9-]{36})(?:/(versions|export\.json|plan\.md|results\.csv|figure\.svg|restore))?$")


def figure_svg(study: dict) -> str:
    """Source-data-only SVG; each variable gets an independent, zero-anchored axis."""
    rows = [r for r in residuals(study) if r["baseline"] is not None and r["candidate"] is not None]
    height = max(260, 145 * len(rows) + 125)
    heading = xml_escape(study["title"])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 {height}" role="img" aria-label="Baseline vs candidate">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#101923} .hd{font-size:22px;font-weight:700}.meta{font-size:13px;fill:#596779}.lab{font-size:14px;font-weight:600}.val{font-size:12px}</style>',
           f'<text class="hd" x="44" y="48">{heading}</text>',
           '<text class="meta" x="44" y="73">Recorded measurements only · Each metric uses an independent, zero-anchored axis · NOT VERIFIED until independently reviewed</text>']
    if not rows:
        out.append('<text class="meta" x="44" y="135">NOT VERIFIED — no baseline/candidate measurements recorded.</text>')
    for i, r in enumerate(rows):
        y = 112 + i * 145
        maxabs = max(abs(r["baseline"]), abs(r["candidate"]), 1e-15)
        zero_x = 510
        width = 280
        label = xml_escape(r["variable"] + " [" + r["unit"] + "]")
        out.append(f'<text class="lab" x="44" y="{y}">{label}</text>')
        out.append(f'<line x1="{zero_x}" y1="{y+7}" x2="{zero_x}" y2="{y+84}" stroke="#5d6e80" stroke-width="1.4"/>')
        for j, name in enumerate(("baseline", "candidate")):
            value = r[name]
            bar_w = abs(value) / maxabs * width
            start = zero_x - bar_w if value < 0 else zero_x
            by = y + 23 + j * 38
            color = "#0E3D8A" if j == 0 else "#228B55"
            out.append(f'<text class="meta" x="44" y="{by+15}">{name}</text>')
            out.append(f'<rect x="{start:.2f}" y="{by}" width="{bar_w:.2f}" height="18" fill="{color}"/>')
            out.append(f'<text class="val" x="805" y="{by+14}">{value:.6g} {xml_escape(r["unit"])}</text>')
        out.append(f'<text class="meta" x="44" y="{y+116}">Residual: {r["residual"]:.6g} {xml_escape(r["unit"])} · Evidence: {xml_escape(r["verification"])}</text>')
    out.append('</svg>')
    return "".join(out)


class WorkspaceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], store: WorkspaceStore):
        if server_address[0] != "127.0.0.1":
            raise ValueError("Workspace server must bind to 127.0.0.1 only")
        self.store = store
        self.token = secrets.token_urlsafe(32)
        super().__init__(server_address, WorkspaceHandler)


class WorkspaceHandler(BaseHTTPRequestHandler):
    server: WorkspaceHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:
        # Avoid emitting user-controlled query strings and sensitive study titles.
        pass

    def _headers(self, code: int, content_type: str, size: int, extra: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        for name, val in (extra or {}).items():
            self.send_header(name, val)
        self.end_headers()

    def _bytes(self, code: int, data: str | bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        body = data.encode("utf-8") if isinstance(data, str) else data
        self.close_connection = True
        self._headers(code, content_type, len(body), extra)
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._bytes(code, json.dumps(obj, ensure_ascii=False, allow_nan=False), "application/json; charset=utf-8")

    def _allow_host(self) -> bool:
        host = self.headers.get("Host", "")
        return host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def _allow_write(self) -> bool:
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin", "")
        expected = "http://" + host
        return (self.headers.get("X-REI-Token") == self.server.token
                and (not origin or origin == expected)
                and self.headers.get("Content-Type", "").split(";", 1)[0] == "application/json")

    def _read_json(self) -> dict:
        header = self.headers.get("Content-Length", "")
        if not header.isdecimal():
            raise WorkspaceError("Content-Length required")
        size = int(header)
        if not 1 <= size <= MAX_BODY:
            raise WorkspaceError("Request exceeds workspace size limit")
        data = json.loads(self.rfile.read(size).decode("utf-8"))
        if not isinstance(data, dict):
            raise WorkspaceError("Expected a JSON object")
        return data

    def _route(self, method: str) -> None:
        if not self._allow_host():
            self._json(403, {"error": "Untrusted Host header"})
            return
        path = urlsplit(self.path).path
        try:
            if method == "GET" and path in ("/", "/app.js", "/style.css"):
                name, mime = {"/": ("workspace.html", "text/html; charset=utf-8"),
                              "/app.js": ("workspace.js", "text/javascript; charset=utf-8"),
                              "/style.css": ("workspace.css", "text/css; charset=utf-8")}[path]
                content = resources.files("rei_scientist").joinpath(name).read_bytes()
                self._bytes(200, content, mime)
                return
            if method == "GET" and path == "/api/bootstrap":
                self._json(200, {"token": self.server.token, "projects": PROJECTS})
                return
            if method == "GET" and path == "/api/templates":
                self._json(200, {p: new_study(p) for p in PROJECTS})
                return
            if path == "/api/studies":
                if method == "GET":
                    filters = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
                    self._json(200, self.server.store.list(**{k: filters.get(k, [""])[0] for k in ("q", "project", "status")}))
                elif method == "POST":
                    if not self._allow_write():
                        self._json(403, {"error": "Write token/origin/content-type rejected"})
                    else:
                        body = self._read_json()
                        if set(body) != {"study"}:
                            raise WorkspaceError("Create expects study")
                        self._json(201, self.server.store.create(body["study"]))
                else:
                    self._json(405, {"error": "Method not allowed"})
                return
            match = RECORD.fullmatch(path)
            if not match:
                self._json(404, {"error": "Unknown route"})
                return
            identifier, suffix = match.groups()
            if method == "GET":
                record = self.server.store.get(identifier)
                study = record["study"]
                if suffix is None:
                    self._json(200, record)
                elif suffix == "versions":
                    self._json(200, self.server.store.history(identifier))
                elif suffix == "export.json":
                    self._json(200, record)
                elif suffix == "plan.md":
                    self._bytes(200, plan_markdown(study, record["revision"]), "text/markdown; charset=utf-8",
                                {"Content-Disposition": 'attachment; filename="study-plan.md"'})
                elif suffix == "results.csv":
                    self._bytes(200, results_csv(study), "text/csv; charset=utf-8",
                                {"Content-Disposition": 'attachment; filename="study-results.csv"'})
                elif suffix == "figure.svg":
                    self._bytes(200, figure_svg(study), "image/svg+xml; charset=utf-8",
                                {"Content-Disposition": 'attachment; filename="study-figure.svg"'})
                else:
                    self._json(405, {"error": "Method not allowed"})
                return
            if method not in ("PUT", "POST"):
                self._json(405, {"error": "Method not allowed"})
                return
            if not self._allow_write():
                self._json(403, {"error": "Write token/origin/content-type rejected"})
                return
            body = self._read_json()
            if suffix is None and method == "PUT" and set(body) == {"revision", "study"}:
                record = self.server.store.update(identifier, body["revision"], body["study"])
            elif suffix == "restore" and method == "POST" and set(body) == {"revision", "source_revision"}:
                record = self.server.store.restore(identifier, body["revision"], body["source_revision"])
            else:
                raise WorkspaceError("Unsupported write operation")
            self._json(200, record)
        except ConflictError as exc:
            self._json(409, {"error": str(exc)})
        except KeyError:
            self._json(404, {"error": "Study or revision not found"})
        except (WorkspaceError, ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._json(422, {"error": str(exc)[:320]})
        except Exception:
            # Catch storage and unforeseen faults without exposing local paths.
            self._json(500, {"error": "Workspace internal error; no changes confirmed"})

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PUT(self):
        self._route("PUT")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REI Scientist local study workspace (loopback only)")
    parser.add_argument("--db", type=Path, default=Path.home() / ".rei-scientist" / "workspace.sqlite3")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be 0-65535")
    store = WorkspaceStore(args.db)
    server = WorkspaceHTTPServer(("127.0.0.1", args.port), store)
    print(f"REI Scientist: http://127.0.0.1:{server.server_port} (local only)")
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
