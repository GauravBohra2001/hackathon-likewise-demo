"""Orchestrator: one LangGraph, three deterministic nodes, linear flow.

    extraction -> decision -> action

No recursion, no autonomous tool loops, no agent-calling-agent.
"""
import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.nodes.action import act_node
from src.nodes.decision import decide
from src.nodes.extraction import extract


class AgentState(TypedDict, total=False):
    message: str
    persona: str
    labeled: list
    extraction_result: dict
    decision: dict
    action: dict


def extraction_node(state: AgentState) -> AgentState:
    r = extract(state["message"])
    print(f"[NODE 1 extraction] {json.dumps(r['extraction'])}")
    print(f"[NODE 1 extraction] target={r['target']!r} confidence={r['confidence']} "
          f"{r['low_confidence_reasons']}")
    return {"extraction_result": r}


def decision_node(state: AgentState) -> AgentState:
    d = decide(state["extraction_result"], state["labeled"], state["persona"])
    # The extracted JSON is logged alongside every decision made from it.
    print(f"[NODE 2 decision  ] persona={state['persona']} label={d['label'].upper()} "
          f"rule={d['trace']['rule']}")
    print(f"[NODE 2 decision  ] from extraction: {json.dumps(d['trace']['extraction'])}")
    print(f"[NODE 2 decision  ] reason: {d['reason']}")
    return {"decision": d}


def action_node(state: AgentState) -> AgentState:
    a = act_node(state)
    print(f"[NODE 3 action    ] committed={a['committed']} :: {a['summary']}")
    return {"action": a}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("extraction", extraction_node)
    g.add_node("decision", decision_node)
    g.add_node("action", action_node)
    g.add_edge(START, "extraction")
    g.add_edge("extraction", "decision")
    g.add_edge("decision", "action")
    g.add_edge("action", END)
    return g.compile()


def load_labeled(persona):
    rows = json.load(open("data/extracted.json"))
    return [{"text": r["text"], "extraction": r["extraction"], "label": r[persona]}
            for r in rows]


def run(message, persona):
    return build_graph().invoke(
        {"message": message, "persona": persona, "labeled": load_labeled(persona)})


# ---------------------------------------------------------------- human-in-the-loop graph
def action_node_hitl(state: AgentState) -> AgentState:
    from src.nodes.action import act_node_hitl
    a = act_node_hitl(state)
    print(f"[NODE 3 action    ] committed={a['committed']} :: {a['summary']}")
    return {"action": a}


def build_graph_hitl():
    """Same three nodes, but 'ask' suspends the graph until a human resumes it."""
    from langgraph.checkpoint.memory import MemorySaver

    g = StateGraph(AgentState)
    g.add_node("extraction", extraction_node)
    g.add_node("decision", decision_node)
    g.add_node("action", action_node_hitl)
    g.add_edge(START, "extraction")
    g.add_edge("extraction", "decision")
    g.add_edge("decision", "action")
    g.add_edge("action", END)
    return g.compile(checkpointer=MemorySaver())
