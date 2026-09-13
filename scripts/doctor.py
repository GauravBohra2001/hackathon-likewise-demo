"""Preflight health check. READ-ONLY: never writes to Slack, GitHub or Linear.

Run before a demo to confirm every dependency is live:

  make doctor

Exits 0 if everything passes, 1 if anything fails. This is a dependency check,
not an evaluation - the reliability numbers come from `make headline`.
"""
import json
import os
import subprocess
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

REQUIRED = [
    "SLACK_BOT_TOKEN", "SLACK_TEST_CHANNEL_ID",
    "GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO",
    "LINEAR_API_KEY", "LINEAR_TEST_TEAM_ID",
    "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT", "AZURE_OPENAI_API_VERSION",
]

results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((True, name, detail))
    except Exception as e:
        msg = str(e).replace("\n", " ")[:110]
        results.append((False, name, msg or e.__class__.__name__))


def env_vars():
    missing = [k for k in REQUIRED if not (os.getenv(k) or "").strip()]
    if missing:
        raise RuntimeError(f"missing or empty in .env: {missing}")
    return f"all {len(REQUIRED)} present"


def slack_auth():
    r = requests.get("https://slack.com/api/auth.test",
                     headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
                     timeout=20).json()
    if not r.get("ok"):
        raise RuntimeError(f"auth.test -> {r.get('error')}")
    return f"team={r['team']} bot={r['bot_id']}"


def slack_channel():
    ch = os.environ["SLACK_TEST_CHANNEL_ID"]
    r = requests.get("https://slack.com/api/conversations.history",
                     headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
                     params={"channel": ch, "limit": 1}, timeout=20).json()
    if not r.get("ok"):
        raise RuntimeError(f"conversations.history -> {r.get('error')} "
                           f"(needs channels:history and the bot in the channel)")
    return f"channel {ch} readable"


def github_repo():
    o, rp = os.environ["GITHUB_OWNER"], os.environ["GITHUB_REPO"]
    r = requests.get(f"https://api.github.com/repos/{o}/{rp}",
                     headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} for {o}/{rp}")
    b = r.json()
    return f"{b['full_name']} issues={'on' if b['has_issues'] else 'OFF'}"


def linear_team():
    r = requests.post("https://api.linear.app/graphql",
                      headers={"Authorization": os.environ["LINEAR_API_KEY"],
                               "Content-Type": "application/json"},
                      json={"query": "{ teams { nodes { id key name } } }"}, timeout=20).json()
    if "errors" in r:
        raise RuntimeError(str(r["errors"])[:100])
    teams = r["data"]["teams"]["nodes"]
    want = os.environ["LINEAR_TEST_TEAM_ID"]
    match = [t for t in teams if t["id"] == want]
    if not match:
        raise RuntimeError(f"LINEAR_TEST_TEAM_ID not among {[t['key'] for t in teams]}")
    return f"team {match[0]['key']} reachable"


def fixtures_resolve():
    fx = json.load(open("fixtures.json"))
    o, rp = os.environ["GITHUB_OWNER"], os.environ["GITHUB_REPO"]
    gh_h = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
    missing = []
    for iss in fx["github"]["issues"]:
        r = requests.get(f"https://api.github.com/repos/{o}/{rp}/issues/{iss['number']}",
                         headers=gh_h, timeout=20)
        if r.status_code != 200:
            missing.append(f"GH#{iss['number']}")
    for iss in fx["linear"]["issues"]:
        r = requests.post("https://api.linear.app/graphql",
                          headers={"Authorization": os.environ["LINEAR_API_KEY"],
                                   "Content-Type": "application/json"},
                          json={"query": "query($id: String!){ issue(id:$id){ identifier } }",
                                "variables": {"id": iss["identifier"]}}, timeout=20).json()
        if r.get("errors") or not r.get("data", {}).get("issue"):
            missing.append(iss["identifier"])
    if missing:
        raise RuntimeError(f"fixtures not found: {missing}")
    n = len(fx["github"]["issues"]) + len(fx["linear"]["issues"])
    return f"all {n} seeded targets resolve"


def foundry():
    from openai import AzureOpenAI
    c = AzureOpenAI(api_version=os.environ["AZURE_OPENAI_API_VERSION"],
                    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                    api_key=os.environ["AZURE_OPENAI_API_KEY"])
    r = c.chat.completions.create(model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                                  messages=[{"role": "user", "content": "reply with: ok"}])
    return f"{r.model} responded"


EXPECTED = ["78.3%", "88.9%", "77.8%", "OVERALL GATE: FAIL"]


def eval_runs():
    p = subprocess.run([sys.executable, "-m", "eval.loo",
                        "--config", "data/extracted_headline_config.json"],
                       capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise RuntimeError(f"eval exited {p.returncode}: {p.stderr.strip()[:100]}")
    absent = [e for e in EXPECTED if e not in p.stdout]
    if absent:
        raise RuntimeError(f"headline numbers changed, missing from output: {absent}")
    return "headline numbers reproduce (78.3 / 88.9 / 77.8, gate FAIL)"


CHECKS = [
    ("environment variables", env_vars),
    ("Slack token", slack_auth),
    ("Slack channel readable", slack_channel),
    ("GitHub repo", github_repo),
    ("Linear team", linear_team),
    ("seeded fixtures", fixtures_resolve),
    ("Azure OpenAI (Foundry)", foundry),
    ("eval reproduces headline", eval_runs),
]

print("=" * 72)
print(" DOCTOR - preflight check (read-only, nothing is written anywhere)")
print("=" * 72)
for name, fn in CHECKS:
    check(name, fn)
    ok, _, detail = results[-1]
    print(f"  [{'PASS' if ok else 'FAIL'}]  {name:<26} {detail}")
print("=" * 72)
failed = [r for r in results if not r[0]]
if failed:
    print(f" {len(failed)} of {len(results)} checks FAILED:")
    for _, name, detail in failed:
        print(f"   - {name}: {detail}")
    print("=" * 72)
    sys.exit(1)
print(f" all {len(results)} checks passed - safe to demo")
print("=" * 72)
