"""NODE 3 - action. Executes for real against the seeded Slack/GitHub/Linear data.

  act     -> the action is COMMITTED against the real API
  ask     -> a draft is WRITTEN but NOT committed, and reported to Slack for confirmation
  refuse  -> nothing is executed anywhere
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone

from src.clients import github_client as gh
from src.clients import linear_client as ln
from src.clients import slack_client as sl
from src import humanize, learning
from src.config import fixtures, require

DRAFTS_PATH = "drafts.json"


# ---------------------------------------------------------------- target resolution
def resolve_target(extracted_target, message):
    """Map a reference like '#2', 'GH #2' or 'HAC-5' onto a REAL seeded fixture."""
    blob = f"{extracted_target} {message}"
    fx = fixtures()

    m = re.search(r"\b(HAC-\d+)\b", blob, re.IGNORECASE)
    if m:
        ident = m.group(1).upper()
        for iss in fx["linear"]["issues"]:
            if iss["identifier"] == ident:
                return {"app": "linear", **iss}
        raise RuntimeError(f"Linear ticket {ident} is not in fixtures.json (seeded: "
                           f"{[i['identifier'] for i in fx['linear']['issues']]})")

    m = re.search(r"#(\d+)", blob)
    if m:
        num = int(m.group(1))
        for iss in fx["github"]["issues"]:
            if iss["number"] == num:
                return {"app": "github", **iss}
        raise RuntimeError(f"GitHub issue #{num} is not in fixtures.json (seeded: "
                           f"{[i['number'] for i in fx['github']['issues']]})")
    return None


# ---------------------------------------------------------------- real execution
def _linear_state(name_hint):
    """Pick a real workflow state. Prefer an actual state NAME appearing in the request;
    fall back to state type. This team has no 'In Review' state, so a request naming one
    lands on the nearest started state rather than failing."""
    states = ln.workflow_states(require("LINEAR_TEST_TEAM_ID"))
    hint = (name_hint or "").lower()

    for st in states:                      # exact name match wins
        if st["name"].lower() in hint:
            return st

    if any(w in hint for w in ("done", "complete", "finished", "signed off", "shipped")):
        want = ("completed",)
    elif any(w in hint for w in ("review", "progress", "working", "started")):
        want = ("started",)
    elif "cancel" in hint:
        want = ("canceled",)
    else:
        want = ("started", "unstarted")
    for t in want:
        for st in states:
            if st["type"] == t:
                return st
    return states[0]


def execute(operation, target, extraction, message, persona):
    """Perform the REAL mutation. Raises on any API failure - never silently degrades."""
    note = f"[ask-only-when-it-matters | persona={persona}] {message}"

    if target is None:
        raise RuntimeError(f"No seeded target could be resolved from: {message!r}")

    if target["app"] == "github":
        n = target["number"]
        if operation == "status_check":
            r = gh.get_issue(n)
            return f"GitHub #{n} state={r['state']} title={r['title']!r}", {"verified": r}

        # Perform the write, then VERIFY with a separate fresh GET. The summary is built
        # from the verification read, never from the mutation's own response, so a write
        # that did not actually land cannot be reported as success.
        if operation == "close":
            mutation = gh.close_issue(n)
        elif operation == "reopen":
            mutation = gh.reopen_issue(n)
        elif operation in ("comment", "tell_customer"):
            mutation = gh.comment(n, note)
        elif operation == "assign":
            mutation = gh.assign(n, require("GITHUB_OWNER"))
        elif operation == "relabel":
            mutation = gh.relabel(n, ["wontfix"])
        else:
            raise RuntimeError(f"Operation {operation!r} is not supported for GitHub")

        fresh = gh.get_issue(n)
        raw = {"mutation": mutation, "verified": fresh}
        if operation in ("close", "reopen"):
            expected = "closed" if operation == "close" else "open"
            if fresh["state"] != expected:
                raise RuntimeError(f"Write not verified: GitHub #{n} reads "
                                   f"state={fresh['state']!r}, expected {expected!r}")
            return f"GitHub #{n} verified state={fresh['state']}", raw
        if operation in ("comment", "tell_customer"):
            return (f"GitHub #{n} verified comment count={fresh['comments']} "
                    f"(new comment id {mutation['id']})"), raw
        if operation == "assign":
            return f"GitHub #{n} verified assignees={[a['login'] for a in fresh['assignees']]}", raw
        return f"GitHub #{n} verified labels={[l['name'] for l in fresh['labels']]}", raw

    if target["app"] == "linear":
        iid, ident = target["id"], target["identifier"]
        if operation == "status_check":
            i = ln.get_issue(ident)
            return f"Linear {ident} state={i['state']['name']} priority={i['priority']}", {"verified": i}

        # Same contract as GitHub: write, then verify with a separate fresh query.
        expect_priority = expect_state = None
        if operation == "bump_priority":
            expect_priority = 1 if extraction["urgency"] else 4
            mutation = ln.set_priority(iid, expect_priority)
        elif operation in ("update_status", "close"):
            st = _linear_state("done" if operation == "close" else message)
            expect_state = st["name"]
            mutation = ln.set_state(iid, st["id"])
        elif operation in ("comment", "tell_customer"):
            mutation = ln.comment(iid, note)
        else:
            raise RuntimeError(f"Operation {operation!r} is not supported for Linear")

        fresh = ln.get_issue_with_comments(ident)
        raw = {"mutation": mutation, "verified": fresh}
        if expect_priority is not None:
            if fresh["priority"] != expect_priority:
                raise RuntimeError(f"Write not verified: Linear {ident} reads "
                                   f"priority={fresh['priority']}, expected {expect_priority}")
            return f"Linear {ident} verified priority={fresh['priority']} (1=urgent, 4=low)", raw
        if expect_state is not None:
            if fresh["state"]["name"] != expect_state:
                raise RuntimeError(f"Write not verified: Linear {ident} reads "
                                   f"state={fresh['state']['name']!r}, expected {expect_state!r}")
            return f"Linear {ident} verified state={fresh['state']['name']}", raw
        return (f"Linear {ident} verified comment count="
                f"{len(fresh['comments']['nodes'])}"), raw

    raise RuntimeError(f"Unknown app {target['app']!r}")


# ---------------------------------------------------------------- drafts
def _load_drafts():
    if os.path.exists(DRAFTS_PATH):
        return json.load(open(DRAFTS_PATH))
    return {}


def _save_drafts(d):
    json.dump(d, open(DRAFTS_PATH, "w"), indent=2)


def write_draft(operation, target, extraction, message, persona, reason,
                slack_thread_ts=None):
    draft_id = f"draft-{uuid.uuid4().hex[:8]}"
    drafts = _load_drafts()
    drafts[draft_id] = {
        "id": draft_id, "status": "pending_confirmation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "operation": operation, "target": target, "extraction": extraction,
        "message": message, "persona": persona, "reason": reason,
        "slack_thread_ts": slack_thread_ts,
        "committed": False,
    }
    _save_drafts(drafts)
    return drafts[draft_id]


def confirm_draft(draft_id):
    """Separately confirm a held draft - THIS is what commits it."""
    drafts = _load_drafts()
    if draft_id not in drafts:
        raise RuntimeError(f"No such draft {draft_id!r}")
    d = drafts[draft_id]
    if d["committed"]:
        raise RuntimeError(f"Draft {draft_id} was already committed")
    summary, raw = execute(d["operation"], d["target"], d["extraction"], d["message"], d["persona"])
    d["committed"] = True
    d["status"] = "committed"
    d["committed_at"] = datetime.now(timezone.utc).isoformat()
    d["result"] = summary
    _save_drafts(drafts)
    learned = learning.record_outcome(d, approved=True)
    print(f"[learning         ] recorded approval as a '{learned['label']}' example "
          f"for persona '{learned['persona']}'")
    name, _, _ = humanize.describe_target(d["target"])
    sl.post(f"*Approved and done.* Someone confirmed this, so I went ahead with {name}.\n"
            f"Result: {summary}", thread_ts=d.get("slack_thread_ts"))
    return d, summary, raw


# ---------------------------------------------------------------- the node
def act_node(state):
    decision = state["decision"]
    extraction = state["extraction_result"]["extraction"]
    message = state["extraction_result"]["message"]
    persona = state["persona"]
    label = decision["label"]
    thread_ts = state.get("slack_thread_ts")
    target = resolve_target(state["extraction_result"]["target"], message)
    op = extraction["operation"]
    out = {"label": label, "committed": False, "draft": None,
           "summary": None, "raw": None, "slack": None}

    if label == "refuse":
        out["summary"] = "REFUSED - nothing executed against any app."
        out["slack"] = sl.post(humanize.refuse_message(op, target, decision), thread_ts=thread_ts)
        return out

    if label == "ask":
        draft = write_draft(op, target, extraction, message, persona, decision["reason"],
                            slack_thread_ts=thread_ts)
        out["draft"] = draft
        out["summary"] = (f"HELD as draft `{draft['id']}` - written, NOT committed. "
                          f"Confirm separately to commit.")
        out["slack"] = sl.post(
            humanize.ask_message(op, target, draft["id"], decision), thread_ts=thread_ts)
        return out

    summary, raw = execute(op, target, extraction, message, persona)
    out.update({"committed": True, "summary": summary, "raw": raw})
    out["slack"] = sl.post(
        humanize.act_message(op, target, summary, decision), thread_ts=thread_ts)
    return out


# ---------------------------------------------------------------- human-in-the-loop
def reject_draft(draft_id, note=""):
    """Mark a held draft as rejected. Nothing is executed."""
    drafts = _load_drafts()
    if draft_id not in drafts:
        raise RuntimeError(f"No such draft {draft_id!r}")
    d = drafts[draft_id]
    if d["committed"]:
        raise RuntimeError(f"Draft {draft_id} was already committed and cannot be rejected; "
                           f"the action has already run against the live API")
    if d["status"] == "rejected":
        raise RuntimeError(f"Draft {draft_id} was already rejected")
    d["status"] = "rejected"
    d["rejected_at"] = datetime.now(timezone.utc).isoformat()
    d["rejection_note"] = note
    _save_drafts(drafts)
    learned = learning.record_outcome(d, approved=False, note=note)
    print(f"[learning         ] recorded rejection as a '{learned['label']}' example "
          f"for persona '{learned['persona']}'")
    return d


def act_node_hitl(state):
    """Action node that PAUSES the graph on 'ask' via LangGraph interrupt().

    refuse -> executes nothing, returns immediately
    act    -> commits immediately
    ask    -> writes a draft, reports to Slack, then interrupt()s. The graph stays
              suspended in the checkpointer until a Command(resume=...) arrives.
              Approval commits the draft; rejection leaves it uncommitted.
    """
    from langgraph.types import interrupt

    decision = state["decision"]
    extraction = state["extraction_result"]["extraction"]
    message = state["extraction_result"]["message"]
    persona = state["persona"]
    label = decision["label"]

    if label != "ask":
        return act_node(state)

    target = resolve_target(state["extraction_result"]["target"], message)
    op = extraction["operation"]
    draft = write_draft(op, target, extraction, message, persona, decision["reason"],
                        slack_thread_ts=state.get("slack_thread_ts"))

    sl.post(humanize.ask_message(op, target, draft["id"], decision),
            thread_ts=state.get("slack_thread_ts"))

    # The graph suspends HERE. State is persisted by the checkpointer; nothing is executed.
    answer = interrupt({
        "kind": "approval_required",
        "draft_id": draft["id"],
        "persona": persona,
        "message": message,
        "proposed_operation": op,
        "target": humanize.describe_target(target)[0],
        "reason": decision["reason"],
        "extraction": extraction,
    })

    approved = bool(answer.get("approved")) if isinstance(answer, dict) else bool(answer)
    note = answer.get("note", "") if isinstance(answer, dict) else ""

    if not approved:
        d = reject_draft(draft["id"], note)
        slack = sl.post(f"*Cancelled.* Someone declined this, so nothing was changed."
                        f"{(' Reason given: ' + note) if note else ''}")
        return {"label": "ask", "committed": False, "draft": d,
                "summary": f"REJECTED - draft {draft['id']} not committed, nothing executed.",
                "raw": None, "slack": slack}

    d, summary, raw = confirm_draft(draft["id"])
    return {"label": "ask", "committed": True, "draft": d,
            "summary": f"APPROVED - {summary}", "raw": raw, "slack": None}
