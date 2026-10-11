from datetime import date
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agent import answer as writer
from app.agent.guard import Link, SqlRejected, check_sql, run_sql
from app.agent.llm import llm_available
from app.agent.planner import Plan, plan_offline, plan_with_llm, wants_report
from app.agent.profile import profile_tables

MAX_RETRIES = 2
MAX_ROWS = 200


class AgentState(TypedDict, total=False):
    question: str
    as_report: bool
    today: date
    tables: list
    links: list[Link]
    profiles: list[dict]
    embedder: Any
    plan: Plan
    attempts: list[dict]
    sections: list[dict]
    errors: list[str]
    steps: list[dict]
    answer: str
    points: list[str]
    status: str
    writer: str | None


def _step(state: AgentState, name: str, detail: str, status: str = "ok") -> list[dict]:
    return [*state.get("steps", []), {"name": name, "detail": detail, "status": status}]


def profile_node(state: AgentState) -> dict:
    profiles = profile_tables(state["tables"])
    sources = sorted({item["source"] for item in profiles})
    detail = f"Read {len(profiles)} table{'s' if len(profiles) != 1 else ''} from {', '.join(sources)}."
    if state["links"]:
        detail += f" {len(state['links'])} confirmed link{'s' if len(state['links']) != 1 else ''} available for joins."
    return {"profiles": profiles, "steps": _step(state, "Read the data", detail)}


def plan_node(state: AgentState) -> dict:
    as_report = state["as_report"] or wants_report(state["question"])
    attempts = state.get("attempts", [])
    plan = None
    if llm_available():
        plan = plan_with_llm(
            state["question"],
            state["profiles"],
            state["links"],
            as_report=as_report,
            today=state["today"],
            previous=attempts or None,
        )
    note = ""
    if plan is None:
        if attempts:
            prior = state.get("plan")
            return {"plan": prior, "steps": _step(state, "Plan", "Could not repair the query.", "error"), "status": "error"}
        plan = plan_offline(state["question"], state["tables"], state["profiles"], as_report=as_report, embedder=state["embedder"])
        note = " OpenAI is not configured, so a simpler offline planner was used." if not llm_available() else " The language model did not respond, so the offline planner was used."
    detail = {
        "describe": "Summarize what the data contains.",
        "clarify": "The question can be read more than one way, so ask first.",
        "query": f"Write {len(plan.queries)} query.",
        "report": f"Write {len(plan.queries)} queries for a report.",
    }[plan.action]
    if attempts:
        detail = f"Retry {len(attempts)}: {detail}"
    return {
        "plan": plan,
        "steps": _step(state, "Plan", f"{detail} Planner: {plan.planner}.{note}"),
    }


def route_after_plan(state: AgentState) -> str:
    if state.get("status") == "error":
        return "answer"
    action = state["plan"].action
    if action == "clarify":
        return "clarify"
    if action == "describe":
        return "describe"
    return "execute"


def clarify_node(state: AgentState) -> dict:
    plan = state["plan"]
    return {
        "answer": plan.clarify_question or "Which of these did you mean?",
        "points": [],
        "status": "needs_clarification",
        "steps": _step(state, "Ask", "Waiting for your choice before running anything."),
    }


def describe_node(state: AgentState) -> dict:
    answer, points = writer.describe(state["profiles"])
    return {
        "answer": answer,
        "points": points,
        "status": "ok",
        "sections": [],
        "steps": _step(state, "Describe", "Summarized tables, columns, and date ranges from the loaded rows."),
    }


def execute_node(state: AgentState) -> dict:
    plan = state["plan"]
    sections: list[dict] = []
    failures: list[dict] = []
    steps = state.get("steps", [])
    for query in plan.queries:
        try:
            checked = check_sql(query.sql, state["tables"], state["links"])
            rows, columns, truncated = run_sql(checked.sql, state["tables"], max_rows=MAX_ROWS)
        except SqlRejected as exc:
            failures.append({"sql": query.sql, "error": str(exc)})
            steps = [*steps, {"name": "Check", "detail": f"{query.title}: {exc}", "status": "error"}]
            continue
        detail = f"{query.title}: {len(rows)} row{'s' if len(rows) != 1 else ''}"
        detail += f" from {', '.join(sorted(checked.tables))}."
        if checked.links_used:
            detail += " Joined on " + "; ".join(link.label() for link in checked.links_used) + "."
        steps = [*steps, {"name": "Run", "detail": detail, "status": "ok"}]
        sections.append(
            {
                "title": query.title,
                "purpose": query.purpose,
                "sql": checked.sql,
                "columns": columns,
                "rows": rows,
                "truncated": truncated,
                "chart": choose_chart(query.chart, columns, rows),
            }
        )
    attempts = state.get("attempts", [])
    if failures:
        attempts = [*attempts, *failures]
    return {"sections": sections, "errors": [item["error"] for item in failures], "attempts": attempts, "steps": steps}


def route_after_execute(state: AgentState) -> str:
    failed = bool(state.get("errors"))
    retries = len({item["sql"] for item in state.get("attempts", [])})
    if failed and not state.get("sections") and llm_available() and retries <= MAX_RETRIES and not state["plan"].planner.startswith("offline"):
        return "plan"
    return "answer"


def answer_node(state: AgentState) -> dict:
    sections = state.get("sections") or []
    plan = state.get("plan")
    assumptions = plan.assumptions if plan else []
    if not sections:
        reason = (state.get("errors") or ["No query could be planned."])[-1]
        return {
            "answer": f"I could not answer that safely. {reason}",
            "points": [],
            "status": "error",
            "sections": [],
            "steps": _step(state, "Answer", "Stopped without an answer.", "error"),
        }
    draft, points = writer.draft_answer(sections, assumptions)
    text, points, model = writer.polish(state["question"], assumptions, sections, draft, points)
    detail = f"Written by {model} from the result rows; numbers were checked." if model else "Written from the result rows."
    return {
        "answer": text,
        "points": points,
        "status": "ok",
        "writer": model,
        "steps": _step(state, "Answer", detail),
    }


def choose_chart(wanted: dict | None, columns: list[str], rows: list[dict]) -> dict | None:
    if len(rows) < 2 or len(columns) < 2:
        return None
    numeric = [name for name in columns if writer.is_number(rows[0].get(name))]
    labels = [name for name in columns if name not in numeric]
    if not numeric or not labels:
        return None
    if wanted and wanted["category"] in columns and wanted["value"] in numeric:
        kind = wanted["type"]
        if kind == "pie" and (len(rows) > 8 or any((row.get(wanted["value"]) or 0) < 0 for row in rows)):
            kind = "bar"
        return {"type": kind, "category": wanted["category"], "value": wanted["value"]}
    category, value = labels[0], numeric[0]
    looks_like_time = all(isinstance(row.get(category), str) and row[category][:4].isdigit() and "-" in row[category][:8] for row in rows[:5])
    if looks_like_time:
        return {"type": "line", "category": category, "value": value}
    if len(rows) > 30:
        return None
    return {"type": "bar", "category": category, "value": value}


@lru_cache(maxsize=1)
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("profile", profile_node)
    graph.add_node("plan", plan_node)
    graph.add_node("clarify", clarify_node)
    graph.add_node("describe", describe_node)
    graph.add_node("execute", execute_node)
    graph.add_node("answer", answer_node)
    graph.add_edge(START, "profile")
    graph.add_edge("profile", "plan")
    graph.add_conditional_edges("plan", route_after_plan, ["clarify", "describe", "execute", "answer"])
    graph.add_conditional_edges("execute", route_after_execute, ["plan", "answer"])
    graph.add_edge("clarify", END)
    graph.add_edge("describe", END)
    graph.add_edge("answer", END)
    return graph.compile()


def run_agent(question: str, tables: list, links: list[Link], *, as_report: bool, embedder, today: date | None = None) -> AgentState:
    state: AgentState = {
        "question": question,
        "as_report": as_report,
        "today": today or date.today(),
        "tables": tables,
        "links": links,
        "embedder": embedder,
        "steps": [],
        "attempts": [],
    }
    return build_graph().invoke(state, {"recursion_limit": 20})
