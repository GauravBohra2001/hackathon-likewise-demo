"""CLI: run one Slack message through the orchestrator for a given persona."""
import argparse

from src.graph import run

p = argparse.ArgumentParser()
p.add_argument("message")
p.add_argument("--persona", default="cautious", choices=["cautious", "trusting"])
a = p.parse_args()

print("=" * 90)
print(f"MESSAGE : {a.message}")
print(f"PERSONA : {a.persona}")
print("=" * 90)
r = run(a.message, a.persona)
print("-" * 90)
act = r["action"]
print(f"FINAL   : {r['decision']['label'].upper()}  committed={act['committed']}")
print(f"RESULT  : {act['summary']}")
if act["slack"]:
    print(f"SLACK   : ok={act['slack']['ok']} ts={act['slack']['ts']} channel={act['slack']['channel']}")
print("=" * 90)
