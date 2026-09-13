"""CLI: reject a held draft. Nothing is executed, and the outcome is learned."""
import sys

from src.clients import slack_client as sl
from src.nodes.action import reject_draft

draft_id = sys.argv[1]
note = sys.argv[2] if len(sys.argv) > 2 else ""
d = reject_draft(draft_id, note)
sl.post(f"*Cancelled.* Someone declined this, so nothing was changed."
        f"{(' Reason given: ' + note) if note else ''}\n"
        f"_I saved this as a 'refuse' example for the {d['persona']} profile, "
        f"so it counts towards similar requests in future._",
        thread_ts=d.get("slack_thread_ts"))
print(f"draft  : {d['id']}")
print(f"status : {d['status']}  committed={d['committed']}")
print(f"RESULT : nothing executed against any app")
