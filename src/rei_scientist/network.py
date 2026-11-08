"""Explicitly opted-in, bounded HTTPS requests. No URL from study JSON is fetched."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class NetworkSecurityError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NetworkSecurityError("HTTP redirects are prohibited")


def secure_https(url: str, allowed_hosts: frozenset[str]) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.hostname not in allowed_hosts
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.fragment or not parsed.path.startswith("/")):
        raise NetworkSecurityError("Only approved HTTPS endpoints on port 443 are allowed")


def get_json(url: str, allowed_hosts: frozenset[str], max_bytes: int = 65536) -> Any:
    secure_https(url, allowed_hosts)
    request = urllib.request.Request(url, headers={"User-Agent": "REI-Scientist/0.1 (research metadata)"})
    return _send(request, max_bytes)


def post_json(url: str, data: dict[str, Any], key: str,
              allowed_hosts: frozenset[str], max_bytes: int = 65536) -> Any:
    secure_https(url, allowed_hosts)
    if not key or not key.strip():
        raise NetworkSecurityError("REI_SCIENTIST_API_KEY is missing")
    body = json.dumps(data, allow_nan=False).encode("utf-8")
    if len(body) > 25000:
        raise NetworkSecurityError("LLM request exceeds safety size limit")
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}",
        "User-Agent": "REI-Scientist/0.1",
    })
    return _send(request, max_bytes)


def _send(request: urllib.request.Request, max_bytes: int) -> Any:
    handler = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with handler.open(request, timeout=20) as response:
            content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise NetworkSecurityError("Network response exceeds safety size limit")
            return json.loads(content)
    except urllib.error.URLError as exc:
        # Deliberately avoid exposing request headers, keys, full upstream traces.
        raise RuntimeError(f"External request failed ({type(exc).__name__}); no fallback executed") from None
