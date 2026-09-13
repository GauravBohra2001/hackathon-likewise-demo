"""Plain-English Slack wording.

The full technical record (similarity scores, vote totals, margins, rule names) goes to
traces.jsonl. Nothing in this module is read by the decision logic; it only decides how an
outcome is described to a person reading Slack.
"""

# What the agent did, in words a non-engineer reads without stopping.
PAST = {
    "close": "closed", "reopen": "reopened", "comment": "added a note to",
    "assign": "assigned", "relabel": "relabelled", "bump_priority": "changed the priority on",
    "update_status": "moved", "status_check": "looked up", "tell_customer": "posted a reply on",
}
FUTURE = {
    "close": "close", "reopen": "reopen", "comment": "add a note to",
    "assign": "assign", "relabel": "relabel", "bump_priority": "change the priority on",
    "update_status": "move", "status_check": "look up", "tell_customer": "post a reply on",
}


def describe_target(target):
    """'GitHub issue #2' / 'Linear ticket HAC-5', with its title and link when known."""
    if not target:
        return "the item you mentioned", None, None
    if target.get("app") == "github":
        return f"GitHub issue #{target['number']}", target.get("title"), target.get("url")
    return f"Linear ticket {target['identifier']}", target.get("title"), target.get("url")


def _reference(target):
    name, title, url = describe_target(target)
    line = f"{name}"
    if title:
        line += f' - "{title}"'
    if url:
        line += f"\n{url}"
    return line


def why(decision):
    """One plain sentence. Never mentions rule names, weights or vote totals."""
    rule = decision["trace"]["rule"]
    label = decision["label"]

    if rule == "safety_floor":
        return "This one permanently removes something, and that cannot be undone afterwards."
    if rule == "low_extraction_confidence":
        return "I could not tell for certain what was being asked, so I would rather check."
    if rule == "no_similar_examples":
        return "I have not seen you handle a request like this before, so I have nothing to go on."
    if rule == "weighted_vote":
        margin_winner = (decision["trace"].get("margin") or {}).get("winner")
        if label == "ask" and margin_winner and margin_winner != "ask":
            return "Your past calls on requests like this have been mixed, so it is not clear cut."
        if label == "act":
            return "You have consistently wanted requests like this handled without checking first."
        return "You have usually wanted to confirm requests like this before they go through."
    return "Defaulting to checking with you."


def act_message(operation, target, summary, decision):
    verb = PAST.get(operation, operation.replace("_", " "))
    name, _, _ = describe_target(target)
    return (f"*Done.* I {verb} {name}.\n"
            f"{_reference(target)}\n"
            f"_{why(decision)}_\n"
            f"Result: {summary}")


def ask_message(operation, target, draft_id, decision):
    verb = FUTURE.get(operation, operation.replace("_", " "))
    name, _, _ = describe_target(target)
    return (f"*Checking with you first.* I have not made any changes yet.\n"
            f"What I would do: {verb} {name}.\n"
            f"{_reference(target)}\n"
            f"_{why(decision)}_\n"
            f"There is no approve button in Slack yet, so this waits until someone runs "
            f"`python -m scripts.confirm {draft_id}` from the repo. Nothing changes until then.")


def refuse_message(operation, target, decision):
    verb = FUTURE.get(operation, operation.replace("_", " "))
    name, _, _ = describe_target(target)
    return (f"*Not doing this one.* I will not {verb} {name}.\n"
            f"_{why(decision)}_\n"
            f"Nothing was changed in GitHub or Linear.")
