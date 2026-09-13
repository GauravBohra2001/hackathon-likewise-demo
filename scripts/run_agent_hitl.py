"""CLI: demonstrate LangGraph pause/resume WITHIN A SINGLE PROCESS.

On 'ask' the graph suspends at an interrupt(). Passing --approve or --reject in the
SAME invocation resumes it and shows the outcome.

IMPORTANT: state is held by an in-memory checkpointer and a fresh thread_id is
generated on every run, so a suspended graph CANNOT be resumed by a later command.
Running this without a flag shows the suspended state and then exits; that run is
gone. To approve a held draft from the CLI, use scripts.confirm (or scripts.reject),
which work off the persisted drafts file and are the supported path.

  --approve   resume this run with approval (commits the draft)
  --reject    resume this run with rejection (nothing is executed)
  neither     show the suspended state and exit; the draft remains in drafts.json

KNOWN ISSUE: when the graph resumes, LangGraph re-executes this node from the top,
so write_draft() runs a second time and a single --approve run leaves TWO drafts in
drafts.json - one committed, one orphaned as pending_confirmation. This is cosmetic
(the orphan is never executed) but it makes drafts.json misleading. scripts.confirm
does not have this problem and is the recommended path.
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
    print(f"NO INTERRUPT - decision was {r['decision']['label'].upper()}")
    print(f"RESULT  : {act['summary']}")
    raise SystemExit(0)

payload = r["__interrupt__"][0].value
print("-" * 90)
print(">>> GRAPH SUSPENDED - approval required. Nothing has been executed. <<<")
print(json.dumps(payload, indent=2))

state = graph.get_state(cfg)
print(f"\ncheckpoint next node : {state.next}")
print(f"pending interrupts   : {len(state.tasks[0].interrupts) if state.tasks else 0}")

if not (a.approve or a.reject):
    print("\nThis process is exiting, so this suspended graph cannot be resumed later.")
    print(f"The draft was still written. Approve it with:")
    print(f"  ./.venv/bin/python -m scripts.confirm {payload['draft_id']}")
    print(f"  ./.venv/bin/python -m scripts.reject  {payload['draft_id']}")
    raise SystemExit(0)

print("\n" + "-" * 90)
print(f">>> RESUMING with approved={a.approve} <<<")
r2 = graph.invoke(Command(resume={"approved": a.approve, "note": a.note}), config=cfg)
act = r2["action"]
print("-" * 90)
print(f"FINAL   : committed={act['committed']}")
print(f"RESULT  : {act['summary']}")
print("=" * 90)
