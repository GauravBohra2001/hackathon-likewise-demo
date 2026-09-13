"""Real-call smoke test of NODE 1 on a few representative messages."""
import json

from src.nodes.extraction import extract

MESSAGES = [
    "can you close out GH #2, it's a dupe of #1",
    "just delete issue #2 entirely, the duplicate is cluttering the board",
    "bump HAC-5 to urgent, the customer is completely blocked on checkout",
    "maybe do something about that thing with the login, idk",
]

for m in MESSAGES:
    r = extract(m)
    print("=" * 78)
    print(f"MESSAGE    : {m}")
    print(f"RAW MODEL  : {r['raw_model_output']}")
    print(f"EXTRACTION : {json.dumps(r['extraction'])}")
    print(f"TARGET     : {r['target']!r}")
    print(f"CONFIDENCE : {r['confidence']}  {r['low_confidence_reasons']}")
print("=" * 78)
