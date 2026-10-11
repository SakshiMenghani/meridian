from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agent.answer import starter_questions
from app.agent.embeddings import get_embedder
from app.agent.graph import run_agent
from app.agent.llm import chat_json, llm_available, model_name
from app.agent.profile import profile_tables
from app.agent.workspace import LoadedTable, confirmed_links, load_tables, selected_sources
from app.config import get_settings
from app.schemas import AgentStep, AskRequest, AskResponse, ChartSpec, ReportDocument, ReportSection, SuggestionsResponse
from app.services.sources import add_log

__all__ = ["LoadedTable", "ask_question", "suggest_questions"]

SUGGEST_SYSTEM = """You suggest starter questions for a data assistant used by non-technical people.
You receive descriptions of tables loaded from the user's own data and the confirmed links between sources.
Write 6 short, specific questions that this data can answer with numbers, using the real table, column, and value names in plain words.
Include at least one trend over time when a date column exists, and one question that combines two sources when a confirmed link exists.
Return JSON: {"questions": ["...", "..."]}"""


def ask_question(db: Session, payload: AskRequest) -> AskResponse:
    question = payload.question.strip()
    sources = selected_sources(db, payload.source_ids)
    if not sources:
        raise ValueError("Enable at least one data source, or pick one to ask about.")
    tables, tools_used = load_tables(sources)
    if not tables:
        raise ValueError("None of the selected sources returned rows.")
    links = confirmed_links(db, tables)
    state = run_agent(
        question,
        tables,
        links,
        as_report=payload.as_report,
        embedder=get_embedder(str(get_settings().embedding_cache_path)),
    )
    plan = state.get("plan")
    sections = state.get("sections") or []
    used = sorted({table.source_name for table in tables})
    first = sections[0] if sections else None
    report = None
    if plan is not None and sections and (plan.action == "report" or len(sections) > 1):
        report = ReportDocument(
            title=(plan.title or question.rstrip("?"))[:80],
            summary=state.get("answer", ""),
            generated_at=datetime.now(timezone.utc),
            sections=[
                ReportSection(
                    title=item["title"],
                    body=item.get("purpose") or "",
                    columns=item["columns"],
                    rows=item["rows"],
                    chart=_chart(item),
                    sql=item["sql"],
                )
                for item in sections
            ],
            sources_used=used,
        )
    status = state.get("status") or "error"
    add_log(db, source_id=sources[0].id, action="ask", status="ok" if status != "error" else "error", detail=question[:200])
    db.commit()
    return AskResponse(
        answer=state.get("answer") or "No answer was produced.",
        points=state.get("points") or [],
        sources_used=used,
        query="\n\n".join(item["sql"] for item in sections) or None,
        columns=first["columns"] if first else [],
        rows=first["rows"] if first else [],
        chart=_chart(first) if first else None,
        status=status,
        note=_note(sources, tables, state),
        tools_used=tools_used,
        report=report,
        steps=[AgentStep(**step) for step in state.get("steps") or []],
        options=plan.options if plan is not None and status == "needs_clarification" else [],
        assumptions=plan.assumptions if plan is not None else [],
        planner=plan.planner if plan is not None else None,
        truncated=bool(first and first["truncated"]),
    )


def suggest_questions(db: Session, source_ids: list[str] | None) -> SuggestionsResponse:
    sources = selected_sources(db, source_ids)
    if not sources:
        return SuggestionsResponse(questions=[], generated_by="none")
    tables, _ = load_tables(sources)
    profiles = profile_tables(tables)
    links = confirmed_links(db, tables)
    summary = [
        {"table": item["table"], "source": item["source"], "object": item["object"], "rows": item["rows"]} for item in profiles
    ]
    if llm_available():
        data = chat_json(SUGGEST_SYSTEM, {"tables": profiles, "confirmed_links": [link.label() for link in links]}, temperature=0.4)
        questions = [str(item).strip() for item in (data or {}).get("questions") or [] if 8 <= len(str(item).strip()) <= 200]
        if questions:
            return SuggestionsResponse(questions=questions[:6], generated_by=model_name(), tables=summary)
    return SuggestionsResponse(questions=starter_questions(profiles, links), generated_by="data profile", tables=summary)


def _chart(section: dict | None) -> ChartSpec | None:
    if not section or not section.get("chart"):
        return None
    chart = section["chart"]
    return ChartSpec(type=chart["type"], category=chart["category"], value=chart["value"], title=section["title"])


def _note(sources, tables: list[LoadedTable], state) -> str:
    parts = ["Answers come only from rows loaded from your sources through MCP."]
    capped = [table.object_name for table in tables if table.truncated]
    if capped:
        parts.append(f"Large tables were sampled to the first 5,000 rows: {', '.join(capped[:4])}.")
    if not llm_available():
        parts.append("Add an OpenAI key to plan questions with a language model; the offline planner handles simple questions.")
    if any(source.source_type in {"google_ads", "google_analytics"} for source in sources):
        parts.append("Marketing rows are sample data until a live adapter is connected.")
    return " ".join(parts)
