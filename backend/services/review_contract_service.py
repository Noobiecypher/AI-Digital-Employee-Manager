"""
review_contract_service.py
===========================
Shared resolver for supported import-draft business contracts.

Single source of truth for "what real business schema does a given
ImportDraft (target_business_entity, operation) correspond to", plus a
small amount of UI-only metadata (labels, input types, field order)
needed to render a generic review form on the frontend.

This module NEVER duplicates validation rules. Required/optional
status, data types, defaults, nullability, and min/max/length
constraints are all derived by introspecting the real Pydantic business
request schemas in backend.api.business_schemas -- the same schemas
already used as the single source of truth by BusinessImportService and
the business CRUD routes. Introspection is done via
`Model.model_json_schema()` rather than by hand-mirroring `Field(...)`
arguments, so a constraint added or changed on a business schema is
picked up automatically everywhere this resolver is used.

Supported (target_business_entity, operation) combinations
------------------------------------------------------------
These mirror exactly what BusinessImportService currently supports --
no scope expansion:

    ("candidate", CREATE_ENTITY)  -> CandidateCreateRequest
    ("product",   CREATE_ENTITY)  -> ProductCreateRequest
    ("product",   ENRICH_ENTITY)  -> ProductCreateRequest

ATTACH_EVIDENCE drafts have no corresponding strict Pydantic business
request schema -- evidence is attached as a freeform reviewed payload
keyed by target_context, and BusinessImportService does not run schema
validation against it today. This resolver reflects that by returning
None only for ATTACH_EVIDENCE. Any other unregistered combination is
treated as unsupported and raises ValueError.

Used by
-------
  - GET  /documents/drafts/{draft_id}/requirements  (document_routes.py)
  - ImportDraftService.approve()                    (pre-approval validation)
  - BusinessImportService                           (final import validation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from backend.api.business_schemas import CandidateCreateRequest, ProductCreateRequest
from backend.document_processing.document_models import DraftOperation


# ==============================================================
# UI-only metadata
# ==============================================================

@dataclass(frozen=True)
class FieldUIMeta:
    """
    Presentation-only hints for one field. Never carries a validation
    rule -- required/type/constraints always come from the real schema.
    """

    label: str
    input_type: str
    order: int


# Keyed by business-schema field name. Purely presentational; adding or
# removing a *validation* rule never requires touching these maps --
# only add an entry here if a brand-new field needs a label/order.
_CANDIDATE_UI_META: dict[str, FieldUIMeta] = {
    "name": FieldUIMeta("Candidate Name", "text", 0),
    "role_applied": FieldUIMeta("Role Applied For", "text", 1),
    "skills": FieldUIMeta("Skills", "tag_list", 2),
    "experience_years": FieldUIMeta("Years of Experience", "number", 3),
    "email": FieldUIMeta("Email Address", "email", 4),
    "phone": FieldUIMeta("Phone Number", "tel", 5),
}

_PRODUCT_UI_META: dict[str, FieldUIMeta] = {
    "product_name": FieldUIMeta("Product Name", "text", 0),
    "description": FieldUIMeta("Description", "textarea", 1),
    "pain_points": FieldUIMeta("Pain Points", "tag_list", 2),
    "target_industries": FieldUIMeta("Target Industries", "tag_list", 3),
    "category": FieldUIMeta("Category", "text", 4),
    "price_range": FieldUIMeta("Price Range", "text", 5),
}

# Resolver table: (target_business_entity, operation) -> (schema, ui_meta)
_CONTRACTS: dict[tuple[str, DraftOperation], tuple[type[BaseModel], dict[str, FieldUIMeta]]] = {
    ("candidate", DraftOperation.CREATE_ENTITY): (CandidateCreateRequest, _CANDIDATE_UI_META),
    ("product", DraftOperation.CREATE_ENTITY): (ProductCreateRequest, _PRODUCT_UI_META),
    ("product", DraftOperation.ENRICH_ENTITY): (ProductCreateRequest, _PRODUCT_UI_META),
}


# ==============================================================
# Frontend-facing field requirement
# ==============================================================

@dataclass(frozen=True)
class ResolvedFieldRequirement:
    """One field's frontend review-form requirements, resolved from the
    real business schema plus UI-only metadata."""

    field_name: str
    label: str
    field_type: str
    input_type: str
    required: bool
    order: int
    constraints: dict[str, Any] = field(default_factory=dict)


# ==============================================================
# Public resolver API
# ==============================================================

def resolve_operation(raw_operation: str) -> DraftOperation:
    """
    Normalize a draft's stored operation string to a DraftOperation,
    mapping the legacy ENTITY_IMPORT alias onto CREATE_ENTITY.

    This mirrors the normalization BusinessImportService has always
    applied, centralized here so every caller (requirements endpoint,
    approval validation, import validation) agrees on it.
    """
    if raw_operation == DraftOperation.ENTITY_IMPORT.value:
        return DraftOperation.CREATE_ENTITY
    return DraftOperation(raw_operation)


def resolve_contract(
    target_business_entity: str, operation: DraftOperation
) -> type[BaseModel] | None:
    """
    Return the real Pydantic business request schema for a
    (target_business_entity, operation) combination.

    Returns None only for ATTACH_EVIDENCE, which is intentionally
    schema-less. Any other combination not registered in _CONTRACTS is
    treated as unsupported/misconfigured and raises ValueError, rather
    than silently returning None -- so callers cannot mistake
    "unsupported" for "no validation needed".
    """
    if operation == DraftOperation.ATTACH_EVIDENCE:
        return None
    entry = _CONTRACTS.get((target_business_entity, operation))
    if entry is None:
        raise ValueError(
            f"Unsupported import-draft contract combination: "
            f"target_business_entity={target_business_entity!r}, "
            f"operation={operation.value!r}."
        )
    return entry[0]


def get_field_requirements(
    target_business_entity: str, operation: DraftOperation
) -> list[ResolvedFieldRequirement] | None:
    """
    Build frontend-friendly field requirements for a supported
    combination by introspecting the real schema's JSON Schema
    representation.

    Returns None only for ATTACH_EVIDENCE, which is intentionally
    schema-less. Raises ValueError for any other unregistered
    combination (see resolve_contract).
    """
    if operation == DraftOperation.ATTACH_EVIDENCE:
        return None
    entry = _CONTRACTS.get((target_business_entity, operation))
    if entry is None:
        raise ValueError(
            f"Unsupported import-draft contract combination: "
            f"target_business_entity={target_business_entity!r}, "
            f"operation={operation.value!r}."
        )
    schema, ui_meta = entry
    return _build_field_requirements(schema, ui_meta)


def validate_reviewed_data(
    target_business_entity: str, operation: DraftOperation, data: dict[str, Any]
) -> dict[str, Any]:
    """
    Validate `data` against the resolved real business schema and return
    the validated (and defaulted/coerced) dict.

    Raises pydantic.ValidationError on failure. When the combination has
    no schema-based contract (e.g. ATTACH_EVIDENCE), this is a no-op that
    returns `data` unchanged.
    """
    schema = resolve_contract(target_business_entity, operation)
    if schema is None:
        return data
    return schema.model_validate(data).model_dump()


def format_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """
    Convert a pydantic ValidationError into the project's field-level
    error shape: [{"field": ..., "message": ..., "type": ...}, ...]
    """
    errors: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        errors.append(
            {
                "field": ".".join(str(part) for part in loc) if loc else None,
                "message": err.get("msg", "Invalid value."),
                "type": err.get("type", "value_error"),
            }
        )
    return errors


# ==============================================================
# Internal: schema introspection
# ==============================================================

_CONSTRAINT_KEYS = (
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "pattern",
    "minItems",
    "maxItems",
    "default",
)


def _build_field_requirements(
    schema: type[BaseModel], ui_meta: dict[str, FieldUIMeta]
) -> list[ResolvedFieldRequirement]:
    json_schema = schema.model_json_schema()
    required_fields: set[str] = set(json_schema.get("required", []))
    properties: dict[str, dict[str, Any]] = json_schema.get("properties", {})

    requirements: list[ResolvedFieldRequirement] = []
    for index, (field_name, prop) in enumerate(properties.items()):
        meta = ui_meta.get(field_name)
        requirements.append(
            ResolvedFieldRequirement(
                field_name=field_name,
                label=meta.label if meta else field_name.replace("_", " ").title(),
                field_type=_resolve_field_type(prop),
                input_type=meta.input_type if meta else "text",
                required=field_name in required_fields,
                order=meta.order if meta else 1000 + index,
                constraints=_extract_constraints(prop),
            )
        )

    requirements.sort(key=lambda item: item.order)
    return requirements


def _resolve_field_type(prop: dict[str, Any]) -> str:
    """Resolve a JSON-Schema property to a simple frontend type string,
    unwrapping the anyOf/oneOf shape Pydantic v2 uses for `X | None`."""
    json_type = prop.get("type")
    if json_type:
        return json_type
    for candidate in (*prop.get("anyOf", ()), *prop.get("oneOf", ())):
        candidate_type = candidate.get("type")
        if candidate_type and candidate_type != "null":
            return candidate_type
    return "string"


def _extract_constraints(prop: dict[str, Any]) -> dict[str, Any]:
    """Pull the relevant subset of JSON-Schema keywords (as produced by
    the real Pydantic Field(...) constraints) into a flat dict, without
    re-declaring any constraint values by hand."""
    constraints: dict[str, Any] = {}
    sources = (prop, *prop.get("anyOf", ()), *prop.get("oneOf", ()))
    for source in sources:
        for key in _CONSTRAINT_KEYS:
            if key in source and key not in constraints:
                constraints[key] = source[key]
    return constraints
