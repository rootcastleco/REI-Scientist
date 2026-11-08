"""Source metadata lookup only. Never pretend that abstracts/full texts were verified."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlencode

from .network import get_json


def search_crossref(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not 1 <= len(query) <= 300 or not 1 <= limit <= 5:
        raise ValueError("Invalid Crossref query or result limit")
    url = "https://api.crossref.org/works?" + urlencode({
        "query.bibliographic": query, "rows": limit,
        "select": "DOI,title,published,author",
    })
    data = get_json(url, frozenset({"api.crossref.org"}), max_bytes=131072)
    if not isinstance(data, dict) or not isinstance(data.get("message"), dict):
        raise ValueError("Unexpected Crossref response structure")
    items = data["message"].get("items")
    if not isinstance(items, list):
        raise ValueError("Crossref returned no items list")
    entries = []
    for entry in items[:limit]:
        if not isinstance(entry, dict):
            continue
        title_list = entry.get("title") or []
        title = str(title_list[0])[:400] if isinstance(title_list, list) and title_list else "Untitled"
        doi = str(entry.get("DOI") or "")[:200]
        parts = entry.get("published", {}).get("date-parts", [[]])
        year = parts[0][0] if parts and parts[0] else None
        if not doi:
            continue
        entries.append({"title": title, "doi": doi, "year": year,
                        "url": "https://doi.org/" + doi,
                        "provenance": "Crossref bibliographic metadata only; full text not read"})
    return entries
