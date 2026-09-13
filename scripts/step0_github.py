"""Step 0B: verify GitHub auth and seed 3 real issues."""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["GITHUB_TOKEN"]
OWNER = os.environ["GITHUB_OWNER"]
REPO = os.environ["GITHUB_REPO"]
API = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

TITLES = [
    "Login page returns 500 on mobile Safari",
    "Duplicate of #1 -- same login issue reported by another user",
    "Customer reports being charged twice at checkout, blocked from retrying",
]


def show(label, resp, keys=None):
    print(f"--- {label} -> HTTP {resp.status_code} ---")
    try:
        body = resp.json()
    except ValueError:
        print(resp.text[:500]); print(); return None
    if keys and isinstance(body, dict):
        print(json.dumps({k: body.get(k) for k in keys}, indent=2))
    else:
        print(json.dumps(body, indent=2)[:1500])
    print()
    return body


who = requests.get(f"{API}/user", headers=HEADERS, timeout=30)
me = show("GET /user (auth check)", who, ["login", "id", "type"])
if who.status_code != 200:
    raise SystemExit(f"FAILED GitHub auth: HTTP {who.status_code}")

repo = requests.get(f"{API}/repos/{OWNER}/{REPO}", headers=HEADERS, timeout=30)
r = show(f"GET /repos/{OWNER}/{REPO}", repo,
         ["full_name", "private", "has_issues", "html_url"])
if repo.status_code != 200:
    raise SystemExit(f"FAILED repo access: HTTP {repo.status_code} -> {repo.text[:300]}")

created = []
for i, title in enumerate(TITLES, start=1):
    resp = requests.post(
        f"{API}/repos/{OWNER}/{REPO}/issues",
        headers=HEADERS,
        json={"title": title, "body": "Seeded test fixture for the 'Ask Only When It Matters' agent."},
        timeout=30,
    )
    body = show(f"POST issue {i}: {title!r}", resp,
                ["number", "title", "state", "html_url", "created_at"])
    if resp.status_code != 201:
        raise SystemExit(f"FAILED creating issue {i}: HTTP {resp.status_code} -> {resp.text[:300]}")
    created.append({"number": body["number"], "title": body["title"], "url": body["html_url"]})

print("=== REAL ISSUE NUMBERS ASSIGNED BY GITHUB ===")
for c in created:
    print(f"  #{c['number']}  {c['title']}")
    print(f"          {c['url']}")

with open("fixtures.json", "w") as f:
    json.dump({"github": {"owner": OWNER, "repo": REPO, "issues": created}}, f, indent=2)
print("\nWrote fixtures.json")
