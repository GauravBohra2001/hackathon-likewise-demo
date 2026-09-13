"""CLI: poll Slack for new messages and run them through the agent.

  --once            one poll then exit
  --interval N      poll every N seconds until interrupted
  --reset-cursor    start from now, ignoring channel history
"""
import argparse
import time

from src.clients import slack_client as sl
from src.slack_listener import CURSOR_PATH, poll_once, _save_cursor

p = argparse.ArgumentParser()
p.add_argument("--once", action="store_true")
p.add_argument("--interval", type=int, default=0)
p.add_argument("--reset-cursor", action="store_true")
a = p.parse_args()

if a.reset_cursor:
    latest = sl.history(limit=1)
    ts = latest[0]["ts"] if latest else "0"
    _save_cursor(ts)
    print(f"cursor reset to {ts}; only messages after this will be processed")

def one():
    res = poll_once()
    print(f"[listener] processed {len(res)} message(s)")
    for r in res:
        print(f"    {r['persona']:<8} {r['decision'].upper():<7} committed={r['committed']}  {r['summary']}")
    return res

if a.interval:
    print(f"polling every {a.interval}s, ctrl-c to stop")
    while True:
        one()
        time.sleep(a.interval)
else:
    one()
