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


# ---------------------------------------------------------------- terminal rendering
W = 78


def _rule(ch="-"):
    return ch * W


def _wrap(text, indent=0, width=None):
    width = width or (W - indent)
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return [" " * indent + ln for ln in lines]


def render(rec, top_n=4):
    """Human-readable decision trace for the terminal. No raw JSON."""
    out = [_rule("="), f" DECISION TRACE   persona: {rec['persona']}", _rule("=")]
    out += _wrap(f'Message: "{rec["raw_message"]}"')

    ex = rec["extraction"]
    on = [k.replace("_", " ") for k in ex if k != "operation" and ex[k] is True]
    out.append("")
    out.append(f"  Understood as : {ex['operation']}"
               + (f"  on {rec['extraction_target']}" if rec.get("extraction_target") else ""))
    out.append(f"  Flags set     : {', '.join(on) if on else '(none)'}")
    out.append(f"  Confidence    : {rec['extraction_confidence']}")

    sf = rec["safety_floor"]
    out.append(f"  Safety floor  : {'TRIGGERED - refused outright' if sf['triggered'] else 'not triggered'}")

    nb = rec.get("top_neighbors")
    if nb:
        out.append("")
        out.append(f"  Closest past requests from this person (top {min(top_n, len(nb))}):")
        out.append(f"    {'score':>6}  {'label':<7} {'op':<4} {'flags':<6} request")
        for c in nb[:top_n]:
            out.append(f"    {c['score']:>6.3f}  {c['label']:<7} "
                       f"{('yes' if c['operation_match'] else 'no'):<4} "
                       f"{str(c['matching_flags']) + '/7':<6} {c['text'][:38]}")

    v = rec.get("vote_scores") or {}
    if v.get("raw"):
        fmt = lambda d: "  ".join(f"{k}={val:.3f}" for k, val in sorted((d or {}).items()))
        out.append("")
        out.append(f"  Votes (weighted by similarity) : {fmt(v['raw'])}")
        out.append(f"  After the act discount         : {fmt(v['after_act_discount'])}")

    m = rec.get("act_margin")
    if m:
        need, got = m.get("required_ratio"), m.get("actual_ratio")
        verdict = ("unopposed" if got is None
                   else ("clears the bar" if got >= need else "FAILS the bar - falls back to ask"))
        out.append(f"  Margin check                   : {m['winner']} {m['winner_score']:.3f} vs "
                   f"runner-up {m['runner_up_score']:.3f}, needs {need}x -> {verdict}")

    out.append("")
    out.append(f"  DECISION: {rec['decision'].upper()}"
               + ("  (committed)" if rec["action"]["committed"] else "  (nothing committed)"))
    out += _wrap(f"Why: {rec['reason']}", indent=2)
    out.append(_rule("="))
    return "\n".join(out)
