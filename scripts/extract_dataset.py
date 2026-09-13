"""Run NODE 1 over all 20 labeled examples, cache to data/extracted.json."""
import json

from src.nodes.extraction import extract

data = json.load(open("data/labeled_examples.json"))
out = []
for e in data["examples"]:
    r = extract(e["text"])
    out.append({
        "id": e["id"], "text": e["text"], "app": e["app"], "target": e["target"],
        "extraction": r["extraction"], "extracted_target": r["target"],
        "confidence": r["confidence"], "low_confidence_reasons": r["low_confidence_reasons"],
        "cautious": e["cautious"], "trusting": e["trusting"],
    })
    ex = r["extraction"]
    flags = "".join(k[0].upper() if ex[k] else "-" for k in
                    ["destructive", "reversible", "customer_facing", "evidence_of_resolution", "urgency"])
    print(f"{e['id']:>2}. op={ex['operation']:<14} flags[DRCEU]={flags}  conf={r['confidence']:<4} "
          f"| cautious={e['cautious']:<6} trusting={e['trusting']:<6} | {e['text'][:44]}")

json.dump(out, open("data/extracted.json", "w"), indent=2)
print(f"\nWrote data/extracted.json ({len(out)} rows)")
lows = [r['id'] for r in out if r['confidence'] == 'low']
print(f"low-confidence extractions: {lows if lows else 'none'}")
