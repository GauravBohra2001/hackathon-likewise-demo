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
        if operation == "close":
            r = gh.close_issue(n)
            return f"GitHub #{n} state={r['state']}", r
        if operation == "reopen":
            r = gh.reopen_issue(n)
            return f"GitHub #{n} state={r['state']}", r
        if operation in ("comment", "tell_customer"):
            r = gh.comment(n, note)
            return f"GitHub #{n} comment {r['id']}", r
        if operation == "assign":
            r = gh.assign(n, require("GITHUB_OWNER"))
            return f"GitHub #{n} assignees={[a['login'] for a in r['assignees']]}", r
        if operation == "relabel":
            r = gh.relabel(n, ["wontfix"])
            return f"GitHub #{n} labels={[l['name'] for l in r]}", r
        if operation == "status_check":
            r = gh.get_issue(n)
            return f"GitHub #{n} state={r['state']} title={r['title']!r}", r
        raise RuntimeError(f"Operation {operation!r} is not supported for GitHub")

    if target["app"] == "linear":
        iid, ident = target["id"], target["identifier"]
        if operation == "bump_priority":
            pr = 1 if extraction["urgency"] else 4
            r = ln.set_priority(iid, pr)
            i = r["data"]["issueUpdate"]["issue"]
            return f"Linear {ident} priority={i['priority']} (1=urgent, 4=low)", r
        if operation in ("update_status", "close"):
            st = _linear_state("done" if operation == "close" else message)
            r = ln.set_state(iid, st["id"])
            i = r["data"]["issueUpdate"]["issue"]
            return f"Linear {ident} state={i['state']['name']}", r
        if operation in ("comment", "tell_customer"):
            r = ln.comment(iid, note)
            return f"Linear {ident} comment created", r
        if operation == "status_check":
            i = ln.get_issue(ident)
            return f"Linear {ident} state={i['state']['name']} priority={i['priority']}", i
        raise RuntimeError(f"Operation {operation!r} is not supported for Linear")

    raise RuntimeError(f"Unknown app {target['app']!r}")


# ---------------------------------------------------------------- drafts
def _load_drafts():
    if os.path.exists(DRAFTS_PATH):
        return json.load(open(DRAFTS_PATH))
    return {}


def _save_drafts(d):
    json.dump(d, open(DRAFTS_PATH, "w"), indent=2)


def write_draft(operation, target, extraction, message, persona, reason):
    draft_id = f"draft-{uuid.uuid4().hex[:8]}"
    drafts = _load_drafts()
    drafts[draft_id] = {
        "id": draft_id, "status": "pending_confirmation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "operation": operation, "target": target, "extraction": extraction,
        "message": message, "persona": persona, "reason": reason,
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
    sl.post(f"[CONFIRMED] Draft `{draft_id}` approved and committed: {summary}")
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
        out["slack"] = sl.post(
            f"*[REFUSED]* {message}\n"
            f"> {decision['reason']}\n"
            f"> Nothing was executed in GitHub or Linear.", thread_ts=thread_ts)
        return out

    if label == "ask":
        draft = write_draft(op, target, extraction, message, persona, decision["reason"])
        out["draft"] = draft
        out["summary"] = (f"HELD as draft `{draft['id']}` - written, NOT committed. "
                          f"Confirm separately to commit.")
        tgt = (target or {}).get("identifier") or f"#{(target or {}).get('number', '?')}"
        out["slack"] = sl.post(
            f"*[ASKING FIRST]* {message}\n"
            f"> {decision['reason']}\n"
            f"> Proposed: `{op}` on *{tgt}*. Draft `{draft['id']}` written but NOT committed.",
            thread_ts=thread_ts)
        return out

    summary, raw = execute(op, target, extraction, message, persona)
    out.update({"committed": True, "summary": summary, "raw": raw})
    out["slack"] = sl.post(
        f"*[DONE]* {message}\n"
        f"> {decision['reason']}\n"
        f"> Executed: {summary}", thread_ts=thread_ts)
    return out


# ---------------------------------------------------------------- human-in-the-loop
def reject_draft(draft_id, note=""):
    """Mark a held draft as rejected. Nothing is executed."""
    drafts = _load_drafts()
    if draft_id not in drafts:
        raise RuntimeError(f"No such draft {draft_id!r}")
    d = drafts[draft_id]
    d["status"] = "rejected"
    d["rejected_at"] = datetime.now(timezone.utc).isoformat()
    d["rejection_note"] = note
    _save_drafts(drafts)
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
    draft = write_draft(op, target, extraction, message, persona, decision["reason"])
    tgt = (target or {}).get("identifier") or f"#{(target or {}).get('number', '?')}"

    sl.post(f"*[ASKING FIRST]* {message}\n"
            f"> {decision['reason']}\n"
            f"> Proposed: `{op}` on *{tgt}*. Draft `{draft['id']}` held, awaiting approval.")

    # The graph suspends HERE. State is persisted by the checkpointer; nothing is executed.
    answer = interrupt({
        "kind": "approval_required",
        "draft_id": draft["id"],
        "persona": persona,
        "message": message,
        "proposed_operation": op,
        "target": tgt,
        "reason": decision["reason"],
        "extraction": extraction,
    })

    approved = bool(answer.get("approved")) if isinstance(answer, dict) else bool(answer)
    note = answer.get("note", "") if isinstance(answer, dict) else ""

    if not approved:
        d = reject_draft(draft["id"], note)
        slack = sl.post(f"*[REJECTED]* Draft `{draft['id']}` was not approved. "
                        f"Nothing executed.{(' Note: ' + note) if note else ''}")
        return {"label": "ask", "committed": False, "draft": d,
                "summary": f"REJECTED - draft {draft['id']} not committed, nothing executed.",
                "raw": None, "slack": slack}

    d, summary, raw = confirm_draft(draft["id"])
    return {"label": "ask", "committed": True, "draft": d,
            "summary": f"APPROVED - {summary}", "raw": raw, "slack": None}
