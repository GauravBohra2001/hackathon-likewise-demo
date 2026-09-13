"""Feature 1 demo: does correcting the agent change what it decides?

Runs the real flow end to end - real drafts, real approvals, real API calls - and
measures the same request after 0, 3, 5 and 6 corrections. Resets the sandbox at the end.

  ./.venv/bin/python -m scripts.correction_curve
"""
import contextlib
import io
import json
import os

from src import learning
from src.graph import run
from src.nodes.action import confirm_draft
from src.nodes.decision import decide
from src.nodes.extraction import extract

TEST = "close #2, it's a dupe of #1"
PERSONA = "cautious"
TEACHING = [
    "close #1 - we shipped the Safari fix and verified it on staging",
    "close #3, the customer confirmed the duplicate charge was reversed",
    "close #2 as a duplicate, the original reporter has been told",
    "close #1, the mobile Safari fix is live in production now",
    "close #3, finance confirmed the duplicate charge was refunded",
    "close #3 as a duplicate, the billing team already handled it",
]
CHECKPOINTS = [0, 3, 5, 6]
BAR = "=" * 74


def measure(er):
    rows = json.load(open("data/extracted.json"))
    base = [{"text": r["text"], "extraction": r["extraction"], "label": r[PERSONA]} for r in rows]
    learned = learning.load_learned(PERSONA)
    with contextlib.redirect_stdout(io.StringIO()):
        d = decide(er, base + learned, PERSONA)
    v = d["trace"].get("adjusted_votes") or {}
    return len(learned), v.get("ask"), v.get("act"), d["label"]


def teach(message):
    # the graph prints its own node trace; keep it out of this view
    with contextlib.redirect_stdout(io.StringIO()):
        run(message, PERSONA)
    drafts = json.load(open("drafts.json"))
    pending = [k for k, v in drafts.items()
               if not v["committed"] and v["status"] == "pending_confirmation"]
    with contextlib.redirect_stdout(io.StringIO()):
        confirm_draft(pending[-1])


for f in ("learned_examples.json", "drafts.json"):
    if os.path.exists(f):
        os.remove(f)

print(BAR)
print(f" CORRECTION CURVE   persona: {PERSONA}")
print(f' request measured each time: "{TEST}"')
print(BAR)
print("Each correction is one held draft that a human approved.")
print("Votes shown are AFTER the 0.70 act discount.\n")

with contextlib.redirect_stdout(io.StringIO()):
    er = extract(TEST)
rows = []
for i in range(max(CHECKPOINTS) + 1):
    if i in CHECKPOINTS:
        n, ask, act, label = measure(er)
        rows.append((n, ask, act, label))
        a = f"{ask:.3f}" if ask is not None else "none"
        c = f"{act:.3f}" if act is not None else "none"
        print(f"  after {n} correction(s): ask={a:>7}  act={c:>7}   ->  {label.upper()}")
    if i < max(CHECKPOINTS):
        print(f"     teaching correction {i + 1}: approving a held draft ...")
        teach(TEACHING[i])

print()
print(BAR)
print(f"  {'corrections':>12} | {'ask vote':>9} | {'act vote':>9} | decision")
print(f"  {'-'*12}-+-{'-'*9}-+-{'-'*9}-+---------")
for n, ask, act, label in rows:
    a = f"{ask:.3f}" if ask is not None else "none"
    c = f"{act:.3f}" if act is not None else "none"
    print(f"  {n:>12} | {a:>9} | {c:>9} | {label.upper()}")
print(BAR)
print("Corrections move the vote toward acting. The 0.70 act discount and the")
print("1.20x margin deliberately hold the decision at ASK until evidence is decisive.")
print(BAR)

print("\nrestoring sandbox...")
os.system("./.venv/bin/python -m scripts.reset_sandbox > /dev/null 2>&1")
os.system("""./.venv/bin/python -c "
import requests
from src.config import require
o, r = require('GITHUB_OWNER'), require('GITHUB_REPO')
h = {'Authorization': 'Bearer ' + require('GITHUB_TOKEN')}
for n in (1,2,3):
    requests.put(f'https://api.github.com/repos/{o}/{r}/issues/{n}/labels', headers=h, json={'labels': []}, timeout=30)
" > /dev/null 2>&1""")
for f in ("learned_examples.json", "drafts.json", "traces.jsonl"):
    if os.path.exists(f):
        os.remove(f)
print("sandbox restored, learned examples cleared.")
