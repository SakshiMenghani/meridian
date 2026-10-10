from datetime import datetime, timezone

from datetime import date as date_type

import duckdb

from app.agent.writer import polish_answer
from app.identifiers import quote_ident
from app.schemas import ChartSpec, ReportDocument, ReportSection
from app.security import json_safe


def is_report_question(question: str) -> bool:
    lowered = question.lower()
    return any(word in lowered for word in ("report", "briefing", "one-pager", "one pager", "deck", "download"))


def build_report(question: str, tables: list, source_names: list[str]) -> ReportDocument:
    table = _pick(tables)
    dimension, measure = _axes(table)
    mix_sql = (
        f"SELECT {quote_ident(dimension)}, SUM({quote_ident(measure)}) AS {quote_ident(measure)} "
        f"FROM {quote_ident(table.sql_name)} GROUP BY {quote_ident(dimension)} "
        f"ORDER BY {quote_ident(measure)} DESC NULLS LAST"
    )
    mix_rows, mix_cols = _run(mix_sql, [table])
    total = sum(_num(row.get(measure)) for row in mix_rows)
    leader = mix_rows[0] if mix_rows else {}
    summary = (
        f"{table.source_name} covers {len(table.frame)} weekly rows. "
        f"The mix is led by {leader.get(dimension, 'the top group')} at "
        f"{_pretty_number(leader.get(measure))} {measure.replace('_', ' ')}"
        + (f", {(_num(leader.get(measure)) / total * 100):.1f}% of the total." if total else ".")
    )
    summary, _writer = polish_answer(question, summary, mix_rows, mix_cols)
    sections = [
        ReportSection(
            title=f"Share of {measure.replace('_', ' ')}",
            body=f"How {measure.replace('_', ' ')} split across {dimension.replace('_', ' ')}.",
            columns=mix_cols,
            rows=mix_rows,
            chart=ChartSpec(type="pie", category=dimension, value=measure, title=f"{measure} by {dimension}"),
        ),
        ReportSection(
            title="Ranking",
            body="Largest groups first.",
            columns=mix_cols,
            rows=mix_rows,
            chart=ChartSpec(type="bar", category=dimension, value=measure, title=f"{measure} by {dimension}"),
        ),
    ]
    if any(name == "date" for name, _ in table.columns):
        trend_sql = (
            f"SELECT {quote_ident('date')}, SUM({quote_ident(measure)}) AS {quote_ident(measure)} "
            f"FROM {quote_ident(table.sql_name)} GROUP BY {quote_ident('date')} ORDER BY {quote_ident('date')}"
        )
        trend_rows, trend_cols = _run(trend_sql, [table])
        if trend_rows:
            start = _pretty_date(str(trend_rows[0]["date"])[:10])
            end = _pretty_date(str(trend_rows[-1]["date"])[:10])
            sections.append(
                ReportSection(
                    title="Over time",
                    body=f"{measure.replace('_', ' ')} from {start} through {end}.",
                    columns=trend_cols,
                    rows=trend_rows,
                    chart=ChartSpec(type="line", category="date", value=measure, title=f"{measure} over time"),
                )
            )
    title = question.strip().rstrip("?")
    if len(title) < 12:
        title = f"{table.source_name} briefing"
    return ReportDocument(
        title=title[:80],
        summary=summary,
        generated_at=datetime.now(timezone.utc),
        sections=sections,
        sources_used=source_names,
    )


def _run(sql: str, tables: list) -> tuple[list[dict], list[str]]:
    conn = duckdb.connect(":memory:")
    try:
        for table in tables:
            conn.register(table.sql_name, table.frame)
        result = conn.execute(sql)
        keys = [item[0] for item in result.description]
        rows = [{key: json_safe(value) for key, value in zip(keys, row, strict=True)} for row in result.fetchall()]
        return rows, keys
    finally:
        conn.close()


def _pretty_number(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _pretty_date(value: str) -> str:
    parsed = date_type.fromisoformat(str(value)[:10])
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _pick(tables: list):
    preferred = ("traffic", "campaigns", "landing_pages")
    for name in preferred:
        for table in tables:
            if table.object_name == name:
                return table
    return tables[0]


def _axes(table) -> tuple[str, str]:
    dimension = next(
        (
            name
            for name, data_type in table.columns
            if not _numeric_type(data_type) and name not in {"date", "source", "medium", "campaign_id"}
        ),
        table.columns[0][0],
    )
    measure = next(
        (name for name, data_type in table.columns if _numeric_type(data_type) and name in {"sessions", "clicks", "impressions", "users"}),
        next((name for name, data_type in table.columns if _numeric_type(data_type)), table.columns[-1][0]),
    )
    return dimension, measure


def _numeric_type(data_type: str) -> bool:
    return any(token in data_type.lower() for token in ("int", "numeric", "float", "double", "decimal", "bigint"))


def _num(value) -> float:
    if value is None or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0
