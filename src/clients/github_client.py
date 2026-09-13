"""Real GitHub API calls. No mocks, no fallbacks - a failure raises."""
import os

import requests

from src.config import require

API = "https://api.github.com"


def _headers():
    return {"Authorization": f"Bearer {require('GITHUB_TOKEN')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _repo():
    return f"{require('GITHUB_OWNER')}/{require('GITHUB_REPO')}"


def _call(method, path, payload=None, ok=(200, 201)):
    url = f"{API}/repos/{_repo()}{path}"
    resp = requests.request(method, url, headers=_headers(), json=payload, timeout=30)
    if resp.status_code not in ok:
        raise RuntimeError(f"GitHub {method} {path} failed: HTTP {resp.status_code} {resp.text[:300]}")
    return resp.json()


def close_issue(number):
    return _call("PATCH", f"/issues/{number}", {"state": "closed"})


def reopen_issue(number):
    return _call("PATCH", f"/issues/{number}", {"state": "open"})


def comment(number, body):
    return _call("POST", f"/issues/{number}/comments", {"body": body})


def assign(number, assignee):
    return _call("POST", f"/issues/{number}/assignees", {"assignees": [assignee]})


def relabel(number, labels):
    return _call("PUT", f"/issues/{number}/labels", {"labels": labels})


def get_issue(number):
    return _call("GET", f"/issues/{number}")
