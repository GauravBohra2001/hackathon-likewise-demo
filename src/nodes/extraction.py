"""NODE 1 - extraction. Raw Slack message -> structured JSON via structured-output mode.

Deterministic node: one model call, strict schema, no tool loop, no recursion.
"""
import json

from src.config import deployment, llm_client

OPERATIONS = [
    "close", "assign", "comment", "bump_priority", "update_status",
    "delete", "reopen", "tell_customer", "relabel", "status_check",
]

BOOL_FIELDS = [
    "destructive", "reversible", "customer_facing",
    "evidence_of_resolution", "urgency",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": OPERATIONS},
        "destructive": {"type": "boolean"},
        "reversible": {"type": "boolean"},
        "customer_facing": {"type": "boolean"},
        "evidence_of_resolution": {"type": "boolean"},
        "urgency": {"type": "boolean"},
        "unclear_fields": {
            "type": "array",
            "items": {"type": "string", "enum": ["operation"] + BOOL_FIELDS},
            "description": "Fields you could not determine confidently from the message.",
        },
        "target": {"type": "string", "description": "Issue/ticket reference, e.g. '#2' or 'HAC-5'. Empty string if none."},
    },
    "required": ["operation"] + BOOL_FIELDS + ["unclear_fields", "target"],
    "additionalProperties": False,
}

SYSTEM = """You extract a single devops operation from a Slack message.

Definitions:
- destructive: the action removes or overwrites information that had value (deleting an issue, scrubbing content, purging data). Closing or reprioritising is NOT destructive.
- reversible: a person could undo this within the tool afterwards and restore the prior state. Deleting an issue or permanently scrubbing content is NOT reversible.
- customer_facing: the action produces something a customer or external reporter will see.
- evidence_of_resolution: the requester states a concrete reason the work is actually finished or verified (a fix shipped, a refund confirmed, a sign-off happened). A bare assertion with no evidence is false.
- urgency: the requester signals time pressure or a blocked customer.

Put any field you genuinely cannot determine into unclear_fields. Do not guess to fill a gap."""


def _conflicts(data):
    """Structural contradictions that mean we should not trust this extraction."""
    found = []
    if data["operation"] == "delete" and not data["destructive"]:
        found.append("operation=delete but destructive=false")
    if data["destructive"] and data["reversible"] and data["operation"] == "delete":
        found.append("delete marked both destructive and reversible")
    if data["operation"] == "tell_customer" and not data["customer_facing"]:
        found.append("operation=tell_customer but customer_facing=false")
    if data["operation"] == "status_check" and data["destructive"]:
        found.append("read-only status_check marked destructive")
    return found


def extract(message: str) -> dict:
    """Return the structured extraction plus a confidence verdict."""
    resp = llm_client().chat.completions.create(
        model=deployment(),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": message},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "extraction", "schema": SCHEMA, "strict": True},
        },
    )
    raw = resp.choices[0].message.content
    data = json.loads(raw)

    missing = [f for f in ["operation"] + BOOL_FIELDS if data.get(f) is None]
    unclear = list(data.get("unclear_fields") or [])
    conflicts = _conflicts(data)

    low_conf_reasons = []
    if missing:
        low_conf_reasons.append(f"missing fields: {missing}")
    if unclear:
        low_conf_reasons.append(f"model flagged unclear: {unclear}")
    if conflicts:
        low_conf_reasons.append(f"conflicting fields: {conflicts}")

    return {
        "message": message,
        "extraction": {k: data[k] for k in ["operation"] + BOOL_FIELDS},
        "target": data.get("target", ""),
        "confidence": "low" if low_conf_reasons else "high",
        "low_confidence_reasons": low_conf_reasons,
        "raw_model_output": raw,
    }
