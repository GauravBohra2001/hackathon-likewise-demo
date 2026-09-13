"""Decision trace: one JSON record per action, written for every real run."""
import json
import os
from datetime import datetime, timezone

TRACE_PATH = "traces.jsonl"


def build(extraction_result, decision, action, persona):
    t = decision["trace"]
    rec = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "persona": persona,
        "raw_message": extraction_result["message"],
        "extraction": extraction_result["extraction"],
        "extraction_target": extraction_result["target"],
        "extraction_confidence": extraction_result["confidence"],
        "low_confidence_reasons": extraction_result["low_confidence_reasons"],
        "safety_floor": {
            "triggered": t["rule"] == "safety_floor",
            "destructive": extraction_result["extraction"]["destructive"],
            "reversible": extraction_result["extraction"]["reversible"],
            "outcome": "refuse" if t["rule"] == "safety_floor" else "not triggered",
        },
        "rule_applied": t["rule"],
        "top_neighbors": t.get("top_candidates"),
        "vote_scores": {"raw": t.get("raw_votes"), "after_act_discount": t.get("adjusted_votes")},
        "act_margin": t.get("margin"),
        "decision": decision["label"],
        "personalized": decision["personalized"],
        "reason": decision["reason"],
        "action": {
            "committed": action["committed"],
            "summary": action["summary"],
            "draft_id": (action.get("draft") or {}).get("id"),
        },
    }
    return rec


def write(rec, path=TRACE_PATH):
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
