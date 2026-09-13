"""Real trace of NODE 2 for both personas on identical inputs (leave-one-out style)."""
import json

from src.nodes.decision import decide

rows = json.load(open("data/extracted.json"))


def labeled_set(persona, exclude_id):
    return [{"text": r["text"], "extraction": r["extraction"], "label": r[persona]}
            for r in rows if r["id"] != exclude_id]


for target_id in (1, 2, 15):
    row = next(r for r in rows if r["id"] == target_id)
    print("=" * 78)
    print(f"INPUT #{target_id}: {row['text']}")
    print(f"EXTRACTED: {json.dumps(row['extraction'])}  confidence={row['confidence']}")
    for persona in ("cautious", "trusting"):
        er = {"message": row["text"], "extraction": row["extraction"],
              "confidence": row["confidence"],
              "low_confidence_reasons": row["low_confidence_reasons"]}
        d = decide(er, labeled_set(persona, target_id), persona)
        print(f"\n  --- {persona.upper()} (true label: {row[persona]}) ---")
        print(f"  DECISION : {d['label']}   (predicted {'CORRECT' if d['label'] == row[persona] else 'WRONG'})")
        print(f"  RULE     : {d['trace']['rule']}")
        print(f"  REASON   : {d['reason']}")
        if d["trace"]["rule"] == "weighted_vote":
            print(f"  raw votes      : {d['trace']['raw_votes']}")
            print(f"  after discount : {d['trace']['adjusted_votes']}")
            print(f"  margin         : {d['trace']['margin']}")
            print(f"  top neighbours :")
            for c in d["trace"]["top_candidates"]:
                print(f"      sim={c['score']:<6} label={c['label']:<6} op_match={str(c['operation_match']):<5} "
                      f"flags={c['matching_flags']}/5  {c['text']}")
    print()
