"""
backend/tools/search_tools.py
=============================
Research-grounding tools (Person 3).

Two layers:
  1. LIVE  — if TAVILY_API_KEY is set, market context is pulled from the Tavily
             web-search API so research is grounded in current, real data.
  2. MOCK  — otherwise it falls back to curated mock_data (market_research.json).

Same function surface either way, so the Research Agent needs no changes — it
gets live data when a key is present and mock data when it isn't. Standard
library only (urllib), so no new dependencies.

Env:
  TAVILY_API_KEY   enable live web search (https://tavily.com — free tier)
"""

from __future__ import annotations

import json
import os
import urllib.request

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_data")
_TAVILY_URL = "https://api.tavily.com/search"


# --------------------------------------------------------------------------- mock
def _load(filename: str, default):
    try:
        with open(os.path.join(_DATA_DIR, filename), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _match_topic(query: str) -> dict:
    data = _load("market_research.json", {})
    topics = data.get("topics", [])
    q = (query or "").lower()
    for t in topics:
        if t.get("research_topic", "").lower() == q:
            return t
    for t in topics:
        rt = t.get("research_topic", "").lower()
        if rt and (rt in q or any(w in rt for w in q.split())):
            return t
    return data.get("default", {})


# --------------------------------------------------------------------------- live
def web_search(query: str, max_results: int = 5) -> dict | None:
    """Call Tavily if a key is configured; return raw {answer, results} or None."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return None
    try:
        payload = json.dumps({
            "api_key": key, "query": query, "max_results": max_results,
            "search_depth": "basic", "include_answer": True,
        }).encode("utf-8")
        req = urllib.request.Request(
            _TAVILY_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.load(r)
    except Exception:
        return None


# --------------------------------------------------------------------------- public
def get_market_context(query: str) -> dict:
    """Return {market_overview, trends, data_points}. Live (Tavily) if available,
    else curated mock_data."""
    live = web_search(f"{query} market trends")
    if live and live.get("results"):
        results = live["results"][:4]
        return {
            "market_overview": live.get("answer") or (results[0].get("content", "")[:300] if results else ""),
            "trends": [r.get("content", "")[:220] for r in results if r.get("content")],
            "data_points": [{"source": r.get("url", ""), "title": r.get("title", "")} for r in results],
        }
    t = _match_topic(query)
    return {
        "market_overview": t.get("market_overview", ""),
        "trends": t.get("trends", []),
        "data_points": t.get("data_points", []),
    }


def get_competitors(query: str) -> list[dict]:
    """Return [{name, strengths, weaknesses}]. Curated mock_data is preferred for
    structure; if a topic isn't in mock_data and Tavily is available, fall back to
    a live search."""
    t = _match_topic(query)
    if t.get("competitors"):
        return t["competitors"]
    products = _load("products.json", [])
    q = (query or "").lower()
    for p in products:
        name = p.get("product_name", "").lower()
        if name and (name in q or q in name) and p.get("competitors"):
            return p["competitors"]
    live = web_search(f"{query} top competitors comparison")
    if live and live.get("results"):
        return [
            {"name": r.get("title", "Competitor"),
             "strengths": [r.get("content", "")[:160]] if r.get("content") else [],
             "weaknesses": []}
            for r in live["results"][:4]
        ]
    return _load("market_research.json", {}).get("default", {}).get("competitors", [])
