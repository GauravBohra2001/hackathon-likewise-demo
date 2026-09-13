"""Reset the seeded sandbox to its original Step 0 state.

GitHub #1/#2/#3 -> open
Linear HAC-5    -> priority 0 (none)
Linear HAC-6    -> Backlog
Local drafts    -> cleared
"""
import json
import os

from src.clients import github_client as gh
from src.clients import linear_client as ln
from src.config import fixtures, require

fx = fixtures()

print("### REOPENING GITHUB ISSUES ###")
for iss in fx["github"]["issues"]:
    r = gh.reopen_issue(iss["number"])
    print(f"  PATCH /issues/{iss['number']} -> state={r['state']} closed_at={r['closed_at']}")

print("\n### RESTORING LINEAR ###")
states = {s["name"]: s for s in ln.workflow_states(require("LINEAR_TEST_TEAM_ID"))}
by_ident = {i["identifier"]: i for i in fx["linear"]["issues"]}

r = ln.set_priority(by_ident["HAC-5"]["id"], 0)
i = r["data"]["issueUpdate"]["issue"]
print(f"  HAC-5 priority -> {i['priority']}")

r = ln.set_state(by_ident["HAC-6"]["id"], states["Backlog"]["id"])
i = r["data"]["issueUpdate"]["issue"]
print(f"  HAC-6 state    -> {i['state']['name']}")

if os.path.exists("drafts.json"):
    os.remove("drafts.json")
    print("\n### CLEARED drafts.json ###")
else:
    print("\n### drafts.json already absent ###")
