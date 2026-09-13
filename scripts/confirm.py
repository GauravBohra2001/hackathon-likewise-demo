"""CLI: separately confirm a held draft. THIS is what commits it."""
import sys

from src.nodes.action import confirm_draft

d, summary, raw = confirm_draft(sys.argv[1])
print(f"draft     : {d['id']}")
print(f"status    : {d['status']}  committed={d['committed']}  at {d['committed_at']}")
print(f"operation : {d['operation']} on {d['target'].get('identifier') or '#' + str(d['target'].get('number'))}")
print(f"RESULT    : {summary}")
