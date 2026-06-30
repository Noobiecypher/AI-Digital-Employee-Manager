"""
backend/tools/sales_tools.py
============================
Sales-domain data tools (Person 3).

get_sales_metrics has two layers:
  1. LIVE  — if SALES_METRICS_API_URL is set, metrics are fetched from a CRM /
             metrics API (e.g. a HubSpot or Salesforce summary endpoint).
  2. MOCK  — otherwise it reads the curated sales_metrics.json.

Same return shape either way, so collect_sales_metrics needs no changes.
Standard library only (urllib). Every function degrades to a safe default.

Env:
  SALES_METRICS_API_URL   metrics endpoint; receives ?period=&departments=
  SALES_METRICS_API_KEY   optional bearer token for that endpoint
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mock_data")

# expected metric keys, with common aliases an API might return
_ALIASES = {
    "revenue_inr": ["revenue_inr", "revenue", "total_revenue"],
    "deals_won": ["deals_won", "deals", "won_deals", "closed_won"],
    "pipeline_inr": ["pipeline_inr", "pipeline", "open_pipeline"],
    "win_rate_pct": ["win_rate_pct", "win_rate", "winRate"],
    "outreach_sent": ["outreach_sent", "emails_sent", "touches"],
    "demos_booked": ["demos_booked", "meetings_booked", "demos"],
}


def _load(filename: str, default):
    try:
        with open(os.path.join(_DATA_DIR, filename), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def get_product_profile(product_name: str) -> dict:
    products = _load("products.json", [])
    if not products:
        return {}
    if product_name:
        for p in products:
            if p.get("product_name", "").lower() == product_name.lower():
                return p
    return products[0]


# --------------------------------------------------------------------------- live
def _fetch_crm_metrics(report_period: str, departments: list[str] | None) -> dict | None:
    """GET metrics from a configured CRM/metrics API; return raw dict or None."""
    base = os.environ.get("SALES_METRICS_API_URL")
    if not base:
        return None
    try:
        params = {"period": report_period or ""}
        if departments:
            params["departments"] = ",".join(departments)
        url = base + ("&" if "?" in base else "?") + urllib.parse.urlencode(params)
        headers = {"Accept": "application/json"}
        tok = os.environ.get("SALES_METRICS_API_KEY")
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.load(r)
    except Exception:
        return None


def _normalize(raw: dict) -> dict:
    """Map an API payload onto our canonical metric keys."""
    flat = raw.get("metrics", raw) if isinstance(raw, dict) else {}
    out = {}
    for canon, names in _ALIASES.items():
        for n in names:
            if isinstance(flat, dict) and n in flat and flat[n] is not None:
                out[canon] = flat[n]
                break
    return out


# --------------------------------------------------------------------------- public
def get_sales_metrics(report_period: str, departments: list[str] | None = None) -> dict:
    """Sales metrics for a period (optionally summed over departments).
    Live CRM if configured, else mock_data."""
    live = _fetch_crm_metrics(report_period, departments)
    if live:
        norm = _normalize(live)
        if norm:
            return norm

    data = _load("sales_metrics.json", {})
    periods = data.get("periods", {})
    block = periods.get(report_period) or data.get("default_period", {"company": {}})

    if departments:
        by_dept = block.get("by_department", {})
        agg: dict = {}
        for dept in departments:
            for k, v in by_dept.get(dept, {}).items():
                if isinstance(v, (int, float)):
                    agg[k] = agg.get(k, 0) + v
        if agg:
            picked = [by_dept[d]["win_rate_pct"] for d in departments if d in by_dept and "win_rate_pct" in by_dept[d]]
            if picked:
                agg["win_rate_pct"] = round(sum(picked) / len(picked))
            return agg

    return dict(block.get("company", {}))
