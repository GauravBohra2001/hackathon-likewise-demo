"""Step 0C part 2: create 3 real Linear tickets in the discovered team."""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

KEY = os.environ["LINEAR_API_KEY"]
URL = "https://api.linear.app/graphql"
HEADERS = {"Authorization": KEY, "Content-Type": "application/json"}

TITLES = [
    "Bump priority: customer blocked on checkout",
    "Update status: waiting on design review",
    "Low priority cleanup: remove unused feature flag",
]

MUTATION = """
mutation CreateIssue($teamId: String!, $title: String!, $description: String!) {
  issueCreate(input: {teamId: $teamId, title: $title, description: $description}) {
    success
    issue { id identifier title url state { name } priority }
  }
}
"""


def gql(query, variables=None, label=""):
    resp = requests.post(URL, headers=HEADERS,
                         json={"query": query, "variables": variables or {}}, timeout=30)
    body = resp.json()
    print(f"--- {label} -> HTTP {resp.status_code} ---")
    print(json.dumps(body, indent=2))
    print()
    if "errors" in body:
        raise SystemExit(f"FAILED {label}: {body['errors']}")
    return body


team_id = (os.getenv("LINEAR_TEST_TEAM_ID") or "").strip()
if not team_id:
    teams = gql("{ teams { nodes { id name key } } }", label="teams query (team id not yet in .env)")
    team_id = teams["data"]["teams"]["nodes"][0]["id"]
    print(f"Using discovered team id: {team_id}\n")
else:
    print(f"Using LINEAR_TEST_TEAM_ID from .env: {team_id}\n")

created = []
for i, title in enumerate(TITLES, start=1):
    body = gql(MUTATION,
               {"teamId": team_id, "title": title,
                "description": "Seeded test fixture for the 'Ask Only When It Matters' agent."},
               label=f"issueCreate {i}: {title!r}")
    payload = body["data"]["issueCreate"]
    if not payload["success"]:
        raise SystemExit(f"FAILED creating Linear ticket {i}")
    issue = payload["issue"]
    created.append({"id": issue["id"], "identifier": issue["identifier"],
                    "title": issue["title"], "url": issue["url"],
                    "state": issue["state"]["name"], "priority": issue["priority"]})

print("=== REAL LINEAR TICKET IDENTIFIERS ===")
for c in created:
    print(f"  {c['identifier']}  {c['title']}")
    print(f"           state={c['state']} priority={c['priority']}  {c['url']}")

fixtures = {}
if os.path.exists("fixtures.json"):
    with open("fixtures.json") as f:
        fixtures = json.load(f)
fixtures["linear"] = {"team_id": team_id, "team_key": "HAC", "issues": created}
with open("fixtures.json", "w") as f:
    json.dump(fixtures, f, indent=2)
print("\nUpdated fixtures.json")
