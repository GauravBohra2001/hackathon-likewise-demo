"""Real Slack Web API calls. No mocks, no fallbacks - a failure raises."""
import requests

from src.config import require


def post(text, channel=None):
    resp = requests.post("https://slack.com/api/chat.postMessage",
                         headers={"Authorization": f"Bearer {require('SLACK_BOT_TOKEN')}",
                                  "Content-Type": "application/json; charset=utf-8"},
                         json={"channel": channel or require("SLACK_TEST_CHANNEL_ID"),
                               "text": text}, timeout=30)
    body = resp.json()
    if not body.get("ok"):
        raise RuntimeError(f"Slack chat.postMessage failed: {body}")
    return body
