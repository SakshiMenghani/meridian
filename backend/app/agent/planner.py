import re
from dataclasses import dataclass, field
from datetime import date

from app.agent.guard import Link
from app.agent.llm import chat_json, model_name
from app.agent.profile import good_dimension, good_measure, humanize, time_column
from app.identifiers import quote_ident

CHART_TYPES = {"bar", "line", "pie"}
MAX_QUERIES = 4

PLANNER_SYSTEM = """You plan read-only analytics queries for Meridian, a data assistant used by non-technical people.
You receive a question and a description of in-memory DuckDB tables that were loaded from the user's own data sources.
You do not know anything about this data beyond that description. Return one JSON object and nothing else.

Rules for SQL:
- DuckDB dialect. Exactly one SELECT statement. WITH clauses are allowed. No DDL, DML, PRAGMA, SET, or table functions.
- Use only the tables and columns listed. Wrap every table and column name in double quotes.
- Filter on text values exactly as they appear in a column's "values" list. Use ILIKE only when no listed value fits.
- Answer from the one table or source whose columns directly answer the question. Columns with the same name in different sources do not mean the same thing: never UNION or add up rows from different sources unless the user explicitly asks to combine them.
- Tables listed under the same "source" may be joined freely on any matching key; never ask about those joins.
- Tables from different sources may be combined only on a pair from "confirmed_links", as JOIN ... ON or as IN (SELECT ...), with table-qualified columns. Never CROSS JOIN or comma-join tables from different sources.
- Only if the question truly needs two different sources and no confirmed link connects them, return action "clarify" and name the missing link.
- Never relabel a metric. Compute derived metrics (profit, margin, conversion rate, ROI) only when every input column exists, and state the formula in "assumptions". If an input is missing or the definition is genuinely ambiguous, clarify.
- For "which is highest / lowest" questions return the ranking (up to 10 rows) rather than LIMIT 1, so the answer has context.
- Relative dates are measured from "today". If that period has no rows, use the most recent period that has rows and say so in "assumptions".
- Aggregate repeated rows (for example weekly rows) when the question asks about a group as a whole. Compute rates and ratios per group as SUM(numerator) / NULLIF(SUM(denominator), 0), never per row, and round them to 4 decimals.
- When the question asks for measures from two sources that have no confirmed link, use action "query" with one query per source (at most 3) instead of joining them. Compute rates and ratios per group as SUM(numerator) / NULLIF(SUM(denominator), 0), never per row, and round them to 4 decimals.
- When the question asks for measures from two sources that have no confirmed link, use action "query" with one query per source (at most 3) instead of joining them.
- Return at most 200 rows. Add ORDER BY for rankings and LIMIT when the user asks for a top N.
- Give result columns short readable aliases in snake_case.

Choose action:
- "query": one query answers the question, or up to 3 queries when it asks about measures that live in different sources (one query per source).
- "report": the user asked for a report, briefing, summary, or overview with charts. Plan 2 to 4 queries: a headline breakdown first, then a ranking or comparison, then a trend over time when a time column exists.
- "describe": the user asks what the data is, what it contains, or what it can answer. No SQL needed.
- "clarify": the answer would change depending on a choice only the user can make (which metric, which definition, which link). Offer 2 to 4 short options written as complete follow-up questions. Do not clarify when a sensible default exists; use it and state it in "assumptions".

Charts: "line" when the first column is a date or time period, "pie" for share of a whole with 8 or fewer parts, "bar" for comparing groups, "none" for a single value or a plain list. "category" is the label column and "value" is a numeric result column, both by their alias.

JSON shape:
{"action": "query|report|describe|clarify",
 "title": "short title for the answer",
 "assumptions": ["plain sentence", "..."],
 "queries": [{"title": "...", "purpose": "one plain sentence of what this query finds", "sql": "...",
              "chart": {"type": "bar|line|pie|none", "category": "alias", "value": "alias"}}],
 "clarify": {"question": "...", "options": ["...", "..."]}}"""

DESCRIBE = re.compile(
    r"\b(what(?:'s| is| are) (?:in )?(?:this|these|the) (?:data|dataset|source|table|file)s?"
    r"|what (?:is|does) this (?:data )?(?:contain|about|show)"
    r"|tell me about|describe|overview of|what can i ask|what am i looking at)\b",
    re.I,
)
REPORT = re.compile(r"\b(report|briefing|one[- ]pager|summary deck|dashboard)\b", re.I)


@dataclass
class QueryPlan:
    title: str
    purpose: str
    sql: str
    chart: dict | None = None


@dataclass
class Plan:
    action: str
    title: str
    planner: str
    assumptions: list[str] = field(default_factory=list)
    queries: list[QueryPlan] = field(default_factory=list)
    clarify_question: str | None = None
    options: list[str] = field(default_factory=list)


def wants_report(question: str) -> bool:
    return bool(REPORT.search(question))


def plan_with_llm(
    question: str,
    profiles: list[dict],
    links: list[Link],
    *,
    as_report: bool,
    today: date,
    previous: list[dict] | None = None,
) -> Plan | None:
    sources: dict[str, list[str]] = {}
    for profile in profiles:
        sources.setdefault(profile["source"], []).append(profile["table"])
    payload = {
        "question": question,
        "today": today.isoformat(),
        "mode": "report" if as_report else "answer",
        "sources": sources,
        "tables": profiles,
        "confirmed_links": [link.label() for link in links],
    }
    if previous:
        payload["previous_attempts"] = previous
        payload["instruction"] = "The previous SQL failed the checks or did not run. Fix it using the error message."
    data = chat_json(PLANNER_SYSTEM, payload)
    if not data:
        return None
    return _parse_plan(data, as_report)


def _parse_plan(data: dict, as_report: bool) -> Plan | None:
    action = str(data.get("action") or "").lower()
    if action not in {"query", "report", "describe", "clarify"}:
        return None
    if as_report and action == "query":
        action = "report"
    if not as_report and action == "report":
        action = "query"
        data["queries"] = (data.get("queries") or [])[:1]
    plan = Plan(
        action=action,
        title=str(data.get("title") or "")[:120],
        planner=model_name(),
        assumptions=[str(item)[:240] for item in (data.get("assumptions") or []) if str(item).strip()][:4],
    )
    for raw in (data.get("queries") or [])[:MAX_QUERIES]:
        if not isinstance(raw, dict) or not str(raw.get("sql") or "").strip():
            continue
        plan.queries.append(
            QueryPlan(
                title=str(raw.get("title") or plan.title or "Result")[:120],
                purpose=str(raw.get("purpose") or "")[:240],
                sql=str(raw["sql"]).strip(),
                chart=_chart(raw.get("chart")),
            )
        )
    if action == "clarify":
        clarify = data.get("clarify") or {}
        plan.clarify_question = str(clarify.get("question") or "Which of these did you mean?")[:240]
        plan.options = [str(item)[:160] for item in (clarify.get("options") or []) if str(item).strip()][:4]
    if action in {"query", "report"} and not plan.queries:
        return None
    return plan


def _chart(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("type") or "").lower()
    if kind not in CHART_TYPES or not raw.get("category") or not raw.get("value"):
        return None
    return {"type": kind, "category": str(raw["category"]), "value": str(raw["value"])}


def plan_offline(question: str, tables, profiles: list[dict], *, as_report: bool, embedder) -> Plan:
    if DESCRIBE.search(question) and not as_report:
        return Plan(action="describe", title="About this data", planner="offline")
    if as_report:
        return _offline_report(profiles)
    from app.agent.text_to_sql import link_question

    link = link_question(question, tables, embedder)
    if link.intent in {"overview", "analysis"} or not link.sql:
        return Plan(action="describe", title="About this data", planner=f"offline ({link.model_name})")
    return Plan(
        action="query",
        title=question.strip().rstrip("?")[:120],
        planner=f"offline ({link.model_name})",
        queries=[QueryPlan(title="Result", purpose="Matched the question to columns with local embeddings.", sql=link.sql)],
    )


def _offline_report(profiles: list[dict]) -> Plan:
    ranked = sorted(
        (profile for profile in profiles if good_dimension(profile) and good_measure(profile)),
        key=lambda profile: profile["rows"],
        reverse=True,
    )
    if not ranked:
        return Plan(action="describe", title="About this data", planner="offline")
    profile = ranked[0]
    table = quote_ident(profile["table"])
    dimension = good_dimension(profile)["name"]
    measure = good_measure(profile)["name"]
    dim, mea = quote_ident(dimension), quote_ident(measure)
    queries = [
        QueryPlan(
            title=f"Share of {humanize(measure)} by {humanize(dimension)}",
            purpose=f"How {humanize(measure)} splits across {humanize(dimension)}.",
            sql=f"SELECT {dim}, SUM({mea}) AS {mea} FROM {table} GROUP BY {dim} ORDER BY {mea} DESC",
            chart={"type": "pie", "category": dimension, "value": measure},
        ),
        QueryPlan(
            title=f"{humanize(dimension).capitalize()} ranked by {humanize(measure)}",
            purpose="Largest groups first.",
            sql=f"SELECT {dim}, SUM({mea}) AS {mea} FROM {table} GROUP BY {dim} ORDER BY {mea} DESC LIMIT 10",
            chart={"type": "bar", "category": dimension, "value": measure},
        ),
    ]
    when = time_column(profile)
    if when:
        moment = quote_ident(when["name"])
        queries.append(
            QueryPlan(
                title=f"{humanize(measure).capitalize()} over time",
                purpose=f"{humanize(measure).capitalize()} by {humanize(when['name'])}.",
                sql=f"SELECT {moment}, SUM({mea}) AS {mea} FROM {table} GROUP BY {moment} ORDER BY {moment}",
                chart={"type": "line", "category": when["name"], "value": measure},
            )
        )
    return Plan(
        action="report",
        title=f"{profile['source']} — {humanize(profile['object'])}",
        planner="offline",
        assumptions=[f"Built from {profile['object']}, the largest table with a category and a number."],
        queries=queries,
    )
