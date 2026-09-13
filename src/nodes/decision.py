"""NODE 2 - decision. Deterministic. No model call, no recursion.

Order of evaluation is fixed and must not be reordered:
  a. safety floor (destructive AND NOT reversible -> refuse, always)
  b. low extraction confidence -> ask
  c. similarity match against THIS person's labeled examples
  d. votes weighted by similarity, not flat majority
  e. act must win by a real margin (explicit act discount)
  f. nothing meaningfully similar -> ask
"""
import re
from difflib import SequenceMatcher

FLAGS = ["destructive", "reversible", "customer_facing", "evidence_of_resolution", "urgency",
         "new_information_present", "overrides_prior_decision"]

# --- similarity weights: operation match dominates, text similarity is smallest ---
W_OPERATION = 0.60
# Each flag carries a FIXED weight rather than a share of a fixed budget. Derived from the
# original 5-flag design, where the 0.30 flag budget gave each flag 0.30 / 5 = 0.06. Holding
# that per-flag value constant means adding a flag adds discriminating power instead of
# diluting every existing flag. Frozen before the evaluation that follows it.
PER_FLAG_WEIGHT = 0.06
W_TEXT = 0.10

# --- calibration constants (set from principle before the eval was run) ---
NEIGHBOR_FLOOR = 0.35   # (f) below this, an example is not "meaningfully similar"
TOP_K = 5               # how many neighbours vote
ACT_DISCOUNT = 0.70     # (e) explicit penalty applied to act votes
ACT_MARGIN = 1.20       # (e) discounted act must beat runner-up by this ratio
ACT_ABS_FLOOR = 0.60    # (e) an UNOPPOSED act still needs this much discounted support
TIE_MARGIN = 1.05       # non-act winners need only a slight edge


def _norm(text):
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split()


def text_similarity(a, b):
    ta, tb = _norm(a), _norm(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(set(ta) & set(tb)) / len(set(ta) | set(tb))
    ratio = SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    return (jaccard + ratio) / 2


def similarity(query_ex, query_text, cand_ex, cand_text):
    """Weighted similarity. Operation match is the largest single contributor."""
    op = 1.0 if query_ex["operation"] == cand_ex["operation"] else 0.0
    # Compare only flags present in BOTH extractions, so a 5-field historical cache and the
    # current 7-field schema each score against their own flag set instead of crashing.
    shared = [f for f in FLAGS if f in query_ex and f in cand_ex]
    matching_flags = sum(1 for f in shared if query_ex[f] == cand_ex[f])
    txt = text_similarity(query_text, cand_text)
    score = W_OPERATION * op + PER_FLAG_WEIGHT * matching_flags + W_TEXT * txt
    return score, {"operation_match": bool(op), "matching_flags": matching_flags,
                   "flags_compared": len(shared), "text_sim": round(txt, 3)}


def decide(extraction_result, labeled, persona):
    """labeled: [{text, extraction, label}] already labeled BY THIS PERSON."""
    ex = extraction_result["extraction"]
    trace = {"persona": persona, "extraction": ex,
             "confidence": extraction_result["confidence"]}

    # (a) SAFETY FLOOR - before any personalization. Not conditioned on customer_facing.
    if ex["destructive"] and not ex["reversible"]:
        trace["rule"] = "safety_floor"
        return {"label": "refuse", "personalized": False,
                "reason": "Safety floor: destructive and not reversible. Refused for every "
                          "user, no exceptions, no learning.",
                "trace": trace}

    # (b) low extraction confidence -> ask
    if extraction_result["confidence"] == "low":
        trace["rule"] = "low_extraction_confidence"
        trace["low_confidence_reasons"] = extraction_result["low_confidence_reasons"]
        return {"label": "ask", "personalized": False,
                "reason": "Extraction confidence was low ("
                          + "; ".join(extraction_result["low_confidence_reasons"])
                          + "), so defaulting to ask.",
                "trace": trace}

    # (c) similarity-match against this person's labeled examples
    scored = []
    for item in labeled:
        s, detail = similarity(ex, extraction_result["message"], item["extraction"], item["text"])
        scored.append({"score": s, "label": item["label"], "text": item["text"], **detail})
    scored.sort(key=lambda r: r["score"], reverse=True)

    # (f) nothing meaningfully similar -> ask
    neighbors = [r for r in scored[:TOP_K] if r["score"] >= NEIGHBOR_FLOOR]
    trace["top_candidates"] = [
        {"score": round(r["score"], 3), "label": r["label"],
         "operation_match": r["operation_match"], "matching_flags": r["matching_flags"],
         "text": r["text"][:60]}
        for r in scored[:TOP_K]
    ]
    if not neighbors:
        trace["rule"] = "no_similar_examples"
        best = round(scored[0]["score"], 3) if scored else 0.0
        return {"label": "ask", "personalized": False,
                "reason": f"Nothing in this person's labeled set was meaningfully similar "
                          f"(best similarity {best} < floor {NEIGHBOR_FLOOR}); defaulting to ask.",
                "trace": trace}

    # (d) votes weighted by similarity, not flat majority
    votes = {}
    for r in neighbors:
        votes[r["label"]] = votes.get(r["label"], 0.0) + r["score"]
    trace["raw_votes"] = {k: round(v, 3) for k, v in votes.items()}

    # (e) explicit act discount, then require a real margin
    adjusted = dict(votes)
    if "act" in adjusted:
        adjusted["act"] *= ACT_DISCOUNT
    trace["adjusted_votes"] = {k: round(v, 3) for k, v in adjusted.items()}

    ranked = sorted(adjusted.items(), key=lambda kv: kv[1], reverse=True)
    winner, top = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    required = ACT_MARGIN if winner == "act" else TIE_MARGIN
    trace["rule"] = "weighted_vote"
    trace["margin"] = {"winner": winner, "winner_score": round(top, 3),
                       "runner_up_score": round(runner_up, 3),
                       "required_ratio": required,
                       "actual_ratio": round(top / runner_up, 3) if runner_up else None}

    if runner_up > 0 and top < required * runner_up:
        return {"label": "ask", "personalized": True,
                "reason": f"'{winner}' led but did not clear the required {required}x margin "
                          f"over the next-best label; defaulting to ask.",
                "trace": trace}

    # (e cont.) an unopposed act has no runner-up to beat, so hold it to an absolute bar
    if winner == "act" and runner_up == 0 and top < ACT_ABS_FLOOR:
        trace["margin"]["abs_floor"] = ACT_ABS_FLOOR
        return {"label": "ask", "personalized": True,
                "reason": f"act was unopposed but its discounted support ({round(top, 3)}) "
                          f"fell below the absolute floor {ACT_ABS_FLOOR}; defaulting to ask.",
                "trace": trace}

    return {"label": winner, "personalized": True,
            "reason": f"Matched this person's prior labels: '{winner}' won the "
                      f"similarity-weighted vote{' after the act discount' if winner == 'act' else ''}.",
            "trace": trace}
