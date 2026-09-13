"""CLI: run a message through the human-in-the-loop graph.

On 'ask' the graph SUSPENDS. Approve or reject to resume it.
  --approve   resume with approval (commits the draft)
  --reject    resume with rejection (nothing is executed)
  neither     leave it suspended and print the pending interrupt
"""
import argparse
import json
import uuid

from langgraph.types import Command

from src.graph import build_graph_hitl, load_labeled

p = argparse.ArgumentParser()
p.add_argument("message")
p.add_argument("--persona", default="cautious", choices=["cautious", "trusting"])
p.add_argument("--approve", action="store_true")
p.add_argument("--reject", action="store_true")
p.add_argument("--note", default="")
a = p.parse_args()

graph = build_graph_hitl()
cfg = {"configurable": {"thread_id": f"demo-{uuid.uuid4().hex[:8]}"}}

print("=" * 90)
print(f"MESSAGE : {a.message}")
print(f"PERSONA : {a.persona}")
print(f"THREAD  : {cfg['configurable']['thread_id']}")
print("=" * 90)

r = graph.invoke({"message": a.message, "persona": a.persona,
                  "labeled": load_labeled(a.persona)}, config=cfg)

if "__interrupt__" not in r:
    act = r["action"]
    print("-" * 90)
    print(f"NO INTERRUPT — decision was {r['decision']['label'].upper()}")
    print(f"RESULT  : {act['summary']}")
    raise SystemExit(0)

payload = r["__interrupt__"][0].value
print("-" * 90)
print(">>> GRAPH SUSPENDED — approval required. Nothing has been executed. <<<")
print(json.dumps(payload, indent=2))

state = graph.get_state(cfg)
print(f"\ncheckpoint next node : {state.next}")
print(f"pending interrupts   : {len(state.tasks[0].interrupts) if state.tasks else 0}")

if not (a.approve or a.reject):
    print("\nLeft suspended. Re-run with --approve or --reject to resume.")
    raise SystemExit(0)

print("\n" + "-" * 90)
print(f">>> RESUMING with approved={a.approve} <<<")
r2 = graph.invoke(Command(resume={"approved": a.approve, "note": a.note}), config=cfg)
act = r2["action"]
print("-" * 90)
print(f"FINAL   : committed={act['committed']}")
print(f"RESULT  : {act['summary']}")
print("=" * 90)
