"""
_processor_utils.py
====================
Small private helpers shared by the domain processors
(recruitment_processor.py, hr_processor.py, sales_processor.py,
research_processor.py, performance_processor.py).

This module exists only to remove real duplicated logic shared by the
domain processors: parsing an LLM's JSON response robustly, calculating
deterministic extraction completeness, and retaining legacy confidence
normalization for compatibility with existing tests or callers.

It is not a generic "processor framework" — it holds no models, no
prompts, no LLM-invocation logic, and no processor-specific behavior.

Explicitly NOT this module's responsibility
--------------------------------------------
- Building prompts (belongs to each processor).
- Invoking the LLM (each processor calls backend.agent_nodes.llm.llm
  directly, per project convention).
- Defining extraction models (kept close to each processor, per the
  milestone's "no shared schema hierarchy" guidance).
- Bounding, chunking, or truncating document content. Each processor
  passes the complete extracted content to the LLM. If a document is
  too large for the shared LLM's context window, that surfaces as a
  real model/context failure (caught and re-raised as a standardized
  OutputValidationError by the processor) rather than being silently
  and knowingly truncated into a partial extraction. Long-document
  handling (chunking, map-reduce, etc.) is explicitly out of scope for
  this milestone.
"""

from __future__ import annotations

import json
import re
from typing import Any

# ==============================================================
# JSON PARSING
# ==============================================================

# Strips ```json / ``` fences the model sometimes wraps its response in.
# Mirrors the regex already used ad hoc in research_agent.py / sales_agent.py.
_JSON_FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)


def parse_llm_json(raw: str) -> dict[str, Any]:
    """
    Parse a JSON object out of a raw LLM response string.

    Handles the common formatting noise LLMs introduce: surrounding
    whitespace, markdown code fences, and incidental prose before/after
    the JSON object.

    Top-level type enforcement
    ---------------------------
    The processor contract requires a top-level JSON *object*. If the
    first meaningful JSON token in the cleaned response is a '['
    (i.e. the response is, or begins with, a JSON array — including an
    array that merely contains an object, e.g. `[{"a": 1}]`), this is
    rejected outright rather than reaching into the array to salvage an
    object. A '{' found after that leading '[' does not change this: an
    array is still an array at the top level.

    Multiple-object / noisy-response behavior
    -------------------------------------------
    If a '{' is found and is not preceded by an earlier top-level '[',
    json.JSONDecoder.raw_decode() is used starting at that '{' so that
    only the first complete JSON object is parsed deterministically —
    any trailing prose or additional JSON-like fragments after it are
    ignored rather than corrupting the parse the way a naive
    first-'{'-to-last-'}' slice would.

    Does NOT silently accept malformed output — if no JSON object can
    be located and parsed, a ValueError is raised so the caller can
    surface a standardized OutputValidationError instead of proceeding
    with garbage data.

    Args:
        raw: The raw string content of the LLM's response
             (e.g. `llm.invoke(prompt).content`).

    Returns:
        The parsed JSON object as a dict.

    Raises:
        ValueError: If no JSON object can be found, if the top-level
                    JSON value is an array, or if the located object
                    is not valid JSON.
    """
    if not raw or not raw.strip():
        raise ValueError("LLM response was empty")

    cleaned = _JSON_FENCE_RE.sub("", raw).strip()

    brace_idx = cleaned.find("{")
    bracket_idx = cleaned.find("[")

    if brace_idx == -1:
        raise ValueError("LLM response did not contain a JSON object")

    if bracket_idx != -1 and bracket_idx < brace_idx:
        raise ValueError(
            "LLM response's top-level JSON value was an array, not an object"
        )

    decoder = json.JSONDecoder()
    try:
        parsed, _end_index = decoder.raw_decode(cleaned, brace_idx)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response was not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM response's JSON was not a JSON object")

    return parsed


# ==============================================================
# LEGACY CONFIDENCE NORMALIZATION
# ==============================================================

def normalize_confidence(value: Any) -> float | None:
    """
    Normalize a processor-reported confidence value into
    ProcessingResult.confidence's expected 0.0-1.0 range.

    Accepts either a 0-100 scale (the convention already used by
    document_classifier.py's LLM prompt) or an already-normalized
    0.0-1.0 value, and clamps the result defensively so a stray
    out-of-range or negative number from the LLM can never violate
    ProcessingResult's `ge=0.0, le=1.0` field constraint.

    Args:
        value: Raw confidence value from parsed LLM JSON (may be None,
               int, float, str, or an unparseable type).

    Returns:
        A float in [0.0, 1.0], or None if `value` is None or not a
        number.
    """
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if numeric > 1.0:
        numeric = numeric / 100

    return max(0.0, min(1.0, numeric))

# ==============================================================
# DETERMINISTIC EXTRACTION COMPLETENESS
# ==============================================================

def calculate_field_completeness(
    values: dict[str, Any],
    weights: dict[str, float],
) -> float:
    """
    Calculate deterministic extraction completeness.

    A field earns its configured weight when it contains a meaningful
    extracted value. The result is normalized to 0.0-1.0.
    """
    total_weight = sum(weights.values())

    if total_weight <= 0:
        return 0.0

    earned_weight = 0.0

    for field_name, weight in weights.items():
        value = values.get(field_name)

        if value is None:
            continue

        if isinstance(value, str) and not value.strip():
            continue

        if isinstance(value, (list, dict)) and not value:
            continue

        earned_weight += weight

    return round(
        max(0.0, min(1.0, earned_weight / total_weight)),
        2,
    )