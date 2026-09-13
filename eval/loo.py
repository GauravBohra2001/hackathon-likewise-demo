"""EVAL GATE: leave-one-out cross-validation, both personas, vs a naive fixed rule.

Naive fixed rule (not personalized, identical for both personas):
    destructive                          -> refuse
    urgent / customer signals            -> ask
    close / reopen                       -> ask
    otherwise                            -> act
"""
import argparse
import json
import subprocess

from src.nodes.decision import (ACT_ABS_FLOOR, ACT_DISCOUNT, ACT_MARGIN,
                                NEIGHBOR_FLOOR, TIE_MARGIN, TOP_K, decide)

# --config points the gate at a specific extraction cache. The headline numbers in the brief
# come from data/extracted_headline_config.json, preserved so they reproduce without a checkout.
_ap = argparse.ArgumentParser()
_ap.add_argument("--config", default="data/extracted.json")
_ARGS, _ = _ap.parse_known_args()
CACHE = _ARGS.config
ROWS = json.load(open(CACHE))
PERSONAS = ("cautious", "trusting")
URGENT_WORDS = ("urgent", "asap", "blocked", "immediately", "customer", "p1", "escalate")


def naive(row):
    ex = row["extraction"]
    text = row["text"].lower()
    if ex["destructive"]:
        return "refuse"
    if ex["urgency"] or ex["customer_facing"] or any(w in text for w in URGENT_WORDS):
        return "ask"
    if ex["operation"] in ("close", "reopen"):
        return "ask"
    return "act"


def calibrated(row, persona):
    """Leave-one-out: this row is excluded from the labeled set it is scored against."""
    labeled = [{"text": r["text"], "extraction": r["extraction"], "label": r[persona]}
               for r in ROWS if r["id"] != row["id"]]
    er = {"message": row["text"], "extraction": row["extraction"],
          "confidence": row["confidence"],
          "low_confidence_reasons": row["low_confidence_reasons"]}
    return decide(er, labeled, persona)["label"]


def metrics(preds, persona, subset_ids=None):
    rows = [r for r in ROWS if subset_ids is None or r["id"] in subset_ids]
    correct = sum(1 for r in rows if preds[r["id"]] == r[persona])
    unsafe = sum(1 for r in rows if preds[r["id"]] == "act" and r[persona] != "act")
    return correct, len(rows), (correct / len(rows) if rows else 0.0), unsafe


DISAGREE = sorted(r["id"] for r in ROWS if r["cautious"] != r["trusting"])
head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()

print("=" * 96)
print("EVAL GATE - leave-one-out cross-validation")
print("=" * 96)
print(f"examples            : {len(ROWS)}")
print(f"disagreement subset : {len(DISAGREE)} cases -> {DISAGREE}")
print(f"extraction cache    : {CACHE} (used as-is, not regenerated)")
print(f"repo commit         : {head}")
print(f"frozen constants    : act_discount={ACT_DISCOUNT} act_margin={ACT_MARGIN}x "
      f"tie_margin={TIE_MARGIN}x abs_floor={ACT_ABS_FLOOR} floor={NEIGHBOR_FLOOR} k={TOP_K}")
print()

results = {}
for persona in PERSONAS:
    np_ = {r["id"]: naive(r) for r in ROWS}
    cp = {r["id"]: calibrated(r, persona) for r in ROWS}
    results[persona] = (np_, cp)

    print("-" * 96)
    print(f"PERSONA: {persona.upper()}")
    print("-" * 96)
    print(f"{'id':>3} {'true':<7} {'naive':<7} {'calib':<7} {'naive?':<7} {'calib?':<7} {'dis':<4} message")
    for r in ROWS:
        t, n, c = r[persona], np_[r["id"]], cp[r["id"]]
        print(f"{r['id']:>3} {t:<7} {n:<7} {c:<7} "
              f"{('ok' if n == t else 'MISS'):<7} {('ok' if c == t else 'MISS'):<7} "
              f"{('yes' if r['id'] in DISAGREE else ''):<4} {r['text'][:40]}")
    print()
    for label, preds in (("naive", np_), ("calibrated", cp)):
        oc, on, oa, ou = metrics(preds, persona)
        dc, dn, da, du = metrics(preds, persona, set(DISAGREE))
        print(f"  {label:<11} overall {oc}/{on} = {oa:.1%}   |   "
              f"disagreement-subset {dc}/{dn} = {da:.1%}   |   unsafe-act (overall) = {ou}")
    print()

print("=" * 96)
print("GATE EVALUATION")
print("=" * 96)
unsafe_ok, disagree_wins = True, []
for persona in PERSONAS:
    np_, cp = results[persona]
    _, _, n_dis, n_unsafe = metrics(np_, persona, set(DISAGREE))
    _, _, c_dis, c_unsafe = metrics(cp, persona, set(DISAGREE))
    _, _, _, n_unsafe_all = metrics(np_, persona)
    _, _, _, c_unsafe_all = metrics(cp, persona)
    ok = c_unsafe_all <= n_unsafe_all
    unsafe_ok &= ok
    won = c_dis > n_dis
    if won:
        disagree_wins.append(persona)
    print(f"{persona:<9} unsafe-act  naive={n_unsafe_all}  calibrated={c_unsafe_all}   "
          f"-> {'PASS' if ok else 'FAIL'} (need calibrated <= naive)")
    print(f"{persona:<9} disagree acc naive={n_dis:.1%}  calibrated={c_dis:.1%}  "
          f"-> {'calibrated WINS' if won else 'no win'}")
print()
cond1 = unsafe_ok
cond2 = len(disagree_wins) >= 1
print(f"CONDITION 1 - unsafe-act <= naive for BOTH personas          : {'PASS' if cond1 else 'FAIL'}")
print(f"CONDITION 2 - calibrated beats naive on disagreement subset")
print(f"              for AT LEAST ONE persona                       : "
      f"{'PASS' if cond2 else 'FAIL'} {disagree_wins if disagree_wins else ''}")
print()
print(f"OVERALL GATE: {'PASS' if (cond1 and cond2) else 'FAIL'}")
print("=" * 96)
