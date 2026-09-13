"""Real Linear GraphQL calls. No mocks, no fallbacks - a failure raises."""
import requests

from src.config import require

URL = "https://api.linear.app/graphql"


def gql(query, variables=None):
    resp = requests.post(URL,
                         headers={"Authorization": require("LINEAR_API_KEY"),
                                  "Content-Type": "application/json"},
                         json={"query": query, "variables": variables or {}}, timeout=30)
    body = resp.json()
    if resp.status_code != 200 or "errors" in body:
        raise RuntimeError(f"Linear call failed: HTTP {resp.status_code} {body}")
    return body


ISSUE_FIELDS = "id identifier title url priority state { name }"

_UPDATE = f"""
mutation Update($id: String!, $input: IssueUpdateInput!) {{
  issueUpdate(id: $id, input: $input) {{ success issue {{ {ISSUE_FIELDS} }} }}
}}"""


def get_issue(identifier):
    body = gql(f"""query($id: String!) {{ issue(id: $id) {{ {ISSUE_FIELDS} }} }}""",
               {"id": identifier})
    return body["data"]["issue"]


def set_priority(issue_id, priority):
    """Linear priority: 0 none, 1 urgent, 2 high, 3 medium, 4 low."""
    return gql(_UPDATE, {"id": issue_id, "input": {"priority": priority}})


def set_state(issue_id, state_id):
    return gql(_UPDATE, {"id": issue_id, "input": {"stateId": state_id}})


def workflow_states(team_id):
    body = gql("""query($teamId: ID!) {
      workflowStates(filter: {team: {id: {eq: $teamId}}}) { nodes { id name type } }
    }""", {"teamId": team_id})
    return body["data"]["workflowStates"]["nodes"]


def comment(issue_id, body_text):
    return gql("""mutation($issueId: String!, $body: String!) {
      commentCreate(input: {issueId: $issueId, body: $body}) {
        success comment { id url }
      }
    }""", {"issueId": issue_id, "body": body_text})


def get_issue_with_comments(identifier):
    """Fresh read including comment count, used to verify a write landed."""
    body = gql(f"""query($id: String!) {{
      issue(id: $id) {{ {ISSUE_FIELDS} comments {{ nodes {{ id }} }} }}
    }}""", {"id": identifier})
    return body["data"]["issue"]
