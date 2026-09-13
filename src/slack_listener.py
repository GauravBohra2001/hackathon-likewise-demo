"""Slack ingestion: poll the channel, run new human messages through the graph.

Read-only polling via conversations.history, so no Socket Mode websocket and no
public event endpoint is needed. The cursor file records the last processed
timestamp so a restart does not reprocess old messages.
"""
import json
import os

from src.clients import slack_client as sl
from src.config import require
from src.graph import run

CURSOR_PATH = ".slack_cursor"
PERSONAS_PATH = "data/personas.json"


def _cursor():
    if os.path.exists(CURSOR_PATH):
        return open(CURSOR_PATH).read().strip() or None
    return None


def _save_cursor(ts):
    with open(CURSOR_PATH, "w") as f:
        f.write(str(ts))


def persona_for(user_id):
    cfg = json.load(open(PERSONAS_PATH))
    return cfg.get("users", {}).get(user_id, cfg.get("default", "cautious"))


def is_actionable(m):
    """Only real human messages. Bot posts, joins and edits are skipped.

    Without this the agent would answer its own replies in a loop, since every
    outcome it reports is itself a message in the same channel.
    """
    if m.get("bot_id") or m.get("app_id"):
        return False, "bot message"
    if m.get("subtype"):
        return False, f"subtype={m['subtype']}"
    if not m.get("user"):
        return False, "no user"
    if not (m.get("text") or "").strip():
        return False, "empty text"
    return True, None


def poll_once(verbose=True):
    """Fetch, filter and process. Returns the list of processed results."""
    oldest = _cursor()
    msgs = sl.history(oldest=oldest)
    msgs = sorted(msgs, key=lambda m: float(m["ts"]))
    if oldest:
        msgs = [m for m in msgs if float(m["ts"]) > float(oldest)]

    if verbose:
        print(f"[listener] cursor={oldest or '(none, first run)'} fetched={len(msgs)}")

    processed = []
    for m in msgs:
        ok, why = is_actionable(m)
        if not ok:
            if verbose:
                print(f"[listener] SKIP ts={m['ts']} ({why}): {(m.get('text') or '')[:50]!r}")
            _save_cursor(m["ts"])
            continue

        persona = persona_for(m["user"])
        if verbose:
            print(f"[listener] PROCESS ts={m['ts']} user={m['user']} persona={persona}")
            print(f"[listener]   text: {m['text']!r}")
        result = run(m["text"], persona, slack_thread_ts=m["ts"])
        processed.append({"ts": m["ts"], "user": m["user"], "persona": persona,
                          "text": m["text"], "decision": result["decision"]["label"],
                          "committed": result["action"]["committed"],
                          "summary": result["action"]["summary"]})
        _save_cursor(m["ts"])
    return processed
