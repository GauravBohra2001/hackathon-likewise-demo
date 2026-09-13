"""Real Slack Web API calls. No mocks, no fallbacks - a failure raises."""
import requests

from src.config import require


def post(text, channel=None, thread_ts=None):
    resp = requests.post("https://slack.com/api/chat.postMessage",
                         headers={"Authorization": f"Bearer {require('SLACK_BOT_TOKEN')}",
                                  "Content-Type": "application/json; charset=utf-8"},
                         json={k: v for k, v in {
                             "channel": channel or require("SLACK_TEST_CHANNEL_ID"),
                             "text": text,
                             "thread_ts": thread_ts,
                         }.items() if v is not None}, timeout=30)
    body = resp.json()
    if not body.get("ok"):
        raise RuntimeError(f"Slack chat.postMessage failed: {body}")
    return body


def history(channel=None, oldest=None, limit=50):
    """Read recent channel messages. Requires channels:history."""
    params = {"channel": channel or require("SLACK_TEST_CHANNEL_ID"), "limit": limit}
    if oldest:
        params["oldest"] = oldest
    resp = requests.get("https://slack.com/api/conversations.history",
                        headers={"Authorization": f"Bearer {require('SLACK_BOT_TOKEN')}"},
                        params=params, timeout=30)
    body = resp.json()
    if not body.get("ok"):
        raise RuntimeError(f"Slack conversations.history failed: {body}")
    return body.get("messages", [])
