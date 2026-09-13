"""Extract ONLY rows not already in the cache. Existing cached rows are left untouched."""
import json

from src.nodes.extraction import extract

labeled = json.load(open("data/labeled_examples.json"))["examples"]
cache = json.load(open("data/extracted.json"))
have = {r["id"] for r in cache}
todo = [e for e in labeled if e["id"] not in have]
print(f"cached already : {sorted(have)}")
print(f"extracting new : {[e['id'] for e in todo]}\n")

for e in todo:
    r = extract(e["text"])
    cache.append({
        "id": e["id"], "text": e["text"], "app": e["app"], "target": e["target"],
        "extraction": r["extraction"], "extracted_target": r["target"],
        "confidence": r["confidence"], "low_confidence_reasons": r["low_confidence_reasons"],
        "cautious": e["cautious"], "trusting": e["trusting"],
    })
    print(f"#{e['id']}  op={r['extraction']['operation']:<10} conf={r['confidence']:<5} "
          f"{r['low_confidence_reasons']}")
    print(f"     raw: {r['raw_model_output']}")

cache.sort(key=lambda r: r["id"])
json.dump(cache, open("data/extracted.json", "w"), indent=2)
print(f"\ncache now {len(cache)} rows")
