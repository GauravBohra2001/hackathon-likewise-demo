"""Live learning from correction.

When a held draft is approved or rejected, that outcome is recorded as a new labeled
example for that person. Later requests are matched against it alongside the original
labeled set.

Label mapping, stated explicitly because it is a judgement call:
  approved -> "act"     the person confirmed they wanted this done
  rejected -> "refuse"  the person said this should not happen

A rejection is deliberately recorded as "refuse" rather than "ask". Recording it as "ask"
would teach nothing, since the agent already asked; "refuse" is the informative signal.

These examples are NEVER read by the evaluation harness, which builds its labeled set
directly from the committed extraction cache. Learning affects the live agent only.
"""
import json
import os
from datetime import datetime, timezone

LEARNED_PATH = "learned_examples.json"


def _load():
    if os.path.exists(LEARNED_PATH):
        return json.load(open(LEARNED_PATH))
    return []


def record_outcome(draft, approved, note=""):
    """Persist an approval or rejection as a new labeled example."""
    rows = _load()
    entry = {
        "text": draft["message"],
        "extraction": draft["extraction"],
        "label": "act" if approved else "refuse",
        "persona": draft["persona"],
        "source": "approved draft" if approved else "rejected draft",
        "draft_id": draft["id"],
        "note": note,
        "learned_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(entry)
    json.dump(rows, open(LEARNED_PATH, "w"), indent=2)
    return entry


def load_learned(persona):
    """Examples this person taught the agent by approving or rejecting drafts."""
    return [{"text": r["text"], "extraction": r["extraction"], "label": r["label"]}
            for r in _load() if r["persona"] == persona]


def summary():
    rows = _load()
    return {"total": len(rows),
            "by_persona": {p: sum(1 for r in rows if r["persona"] == p)
                           for p in sorted({r["persona"] for r in rows})}}
