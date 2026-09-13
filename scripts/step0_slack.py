"""Step 0A: verify Slack auth and send one real test message."""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["SLACK_BOT_TOKEN"]
CHANNEL = os.environ["SLACK_TEST_CHANNEL_ID"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json; charset=utf-8"}


def call(method, payload=None):
    url = f"https://slack.com/api/{method}"
    if payload is None:
        resp = requests.get(url, headers=HEADERS, timeout=30)
    else:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    print(f"--- {method} -> HTTP {resp.status_code} ---")
    print(json.dumps(resp.json(), indent=2))
    print()
    return resp.json()


auth = call("auth.test")
if not auth.get("ok"):
    raise SystemExit(f"FAILED auth.test: {auth.get('error')}")

post = call("chat.postMessage", {
    "channel": CHANNEL,
    "text": "Step 0A auth check - Ask Only When It Matters agent is connected.",
})
if not post.get("ok"):
    raise SystemExit(f"FAILED chat.postMessage: {post.get('error')}")

print(f"SUCCESS: message ts={post['message']['ts']} in channel={post['channel']}")
