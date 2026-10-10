import re
from dataclasses import dataclass
from datetime import date

import duckdb
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.embeddings import get_embedder
from app.agent.text_to_sql import link_question
from app.agent.writer import polish_answer
from app.config import get_settings
from app.identifiers import quote_ident, sanitize_ident
from app.mcp import get_manager
from app.models import DataSource
from app.schemas import AskRequest, AskResponse, ChartSpec
from app.services.report import build_report, is_report_question
from app.security import json_safe
from app.services.sources import add_log

MAX_ROWS = 200
MAX_LOAD = 5_000
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|copy|attach|install|load|pragma|call|export|vacuum|replace)\b",
    re.I,
)


@dataclass
class LoadedTable:
    sql_name: str
    source_name: str
    object_name: str
    columns: list[tuple[str, str]]
    frame: pd.DataFrame


def ask_question(db: Session, payload: AskRequest) -> AskResponse:
    question = payload.question.strip()
    sources = _selected_sources(db, payload.source_ids)
    if not sources:
        raise ValueError("Enable at least one data source, or pick one to ask about.")
    tables, tools_used = _load_tables(sources, question)
    if not tables:
        raise ValueError("None of the selected sources returned rows.")
    link = None
    try:
        link = link_question(question, tables, get_embedder(str(get_settings().embedding_cache_path)))
    except Exception:
        link = None
    if _looks_like_purchases(question.lower(), tables):
        sql = _purchase_sql(tables)
        rows, columns = _run(sql, tables)
        answer, points = _answer(question, rows, columns, tables)
        chart = _chart(question, columns, rows)
    elif _is_analysis(question) or (link is not None and link.intent == "analysis"):
        answer, points, sql, columns, rows = analyze_tables(tables)
        chart = _chart(question, columns, rows)
    elif _is_overview(question) or (link is not None and link.intent == "overview"):
        answer, points, sql, columns, rows = describe_tables(tables)
        chart = None
    else:
        sql = link.sql if link is not None and link.sql else plan_sql(question, tables)
        rows, columns = _run(sql, tables)
        answer, points = _answer(question, rows, columns, tables, link)
        chart = _chart(question, columns, rows)
    answer, writer = polish_answer(question, answer, rows, columns)
    used = sorted({table.source_name for table in tables})
    add_log(db, source_id=sources[0].id, action="ask", status="ok", detail=question[:200])
    db.commit()
    note = "Answers come from rows loaded through MCP. Missing metrics are not invented."
    if link is not None and link.model_name.startswith("BAAI"):
        note += f" Schema linking used {link.model_name}."
    elif link is not None:
        note += " Schema linking used a local fallback embedding."
    if writer:
        note += f" The wording was written by {writer} from those rows."
    else:
        note += " The wording is written from the query rows."
    if any(source.source_type in {"google_ads", "google_analytics"} for source in sources):
        note += " Marketing rows are data_origin=sample unless a live adapter is connected."
    report = None
    if payload.as_report or is_report_question(question):
        report = build_report(question, tables, used)
        answer = report.summary
        if report.sections:
            first = report.sections[0]
            columns = first.columns
            rows = first.rows
            chart = first.chart
            sql = sql or question
    return AskResponse(
        answer=answer,
        points=points,
        sources_used=used,
        query=sql,
        columns=columns,
        rows=rows,
        chart=chart,
        status="ok",
        note=note,
        tools_used=tools_used,
        report=report,
    )


OVERVIEW = re.compile(
    r"\b("
    r"what(?:'s| is) this"
    r"|what(?:'s| is) (?:the |this )?(?:data|source|table|dataset|file)"
    r"|tell me about"
    r"|explain (?:this|the data|the source|these)"
    r"|describe (?:this|the data|the source)"
    r"|what does this"
    r"|what am i looking at"
    r"|overview"
    r"|understand"
    r")\b",
    re.I,
)

OBJECT_NOTES = {
    "customers": "Retail customers. customer_id is the person, not a campaign.",
    "products": "Product catalog, with unit cost and list price.",
    "orders": "Orders. status is fulfilled or refunded.",
    "order_items": "Line items that belong to those orders.",
    "customer_profiles": "CRM profiles, with segment and loyalty points.",
    "product_reviews": "Product reviews linked by customer_id and product_id.",
    "service_cases": "Support cases that use the same customer and product ids.",
    "campaigns": "Weekly ad stats. Each row is one campaign for one week.",
    "traffic": "Website sessions by channel. Each row is one channel for one week.",
    "landing_pages": "Sessions by the first page of a visit.",
}


ANALYSIS = re.compile(r"\b(analysis|insight|takeaway|performance story)\b", re.I)


def _is_overview(question: str) -> bool:
    if _is_analysis(question):
        return False
    return bool(OVERVIEW.search(question))


def _is_analysis(question: str) -> bool:
    return bool(ANALYSIS.search(question))


def describe_tables(tables: list[LoadedTable]) -> tuple[str, list[str], str | None, list[str], list[dict]]:
    campaigns = next((table for table in tables if table.object_name == "campaigns"), None)
    if campaigns is not None and {"campaign_id", "campaign_name"}.issubset(campaigns.frame.columns):
        return _describe_campaigns(campaigns)
    traffic = next((table for table in tables if table.object_name == "traffic"), None)
    if traffic is not None and {"channel", "sessions"}.issubset(traffic.frame.columns):
        return _describe_traffic(traffic)
    source_name = tables[0].source_name
    points = []
    for table in tables:
        columns = ", ".join(name for name, _ in table.columns[:8])
        note = OBJECT_NOTES.get(table.object_name, "")
        count = len(table.frame)
        line = f"{table.object_name} — {count} rows. Columns include {columns}."
        if note:
            line = f"{line} {note}"
        points.append(line)
    if len(tables) == 1:
        answer = f"{source_name} is one table, {tables[0].object_name}."
    else:
        answer = f"{source_name} holds {len(tables)} tables. The ids below are keys inside those tables."
    quoted = quote_ident(tables[0].sql_name)
    return answer, points, f"SELECT * FROM {quoted} LIMIT 20", [], []


def analyze_tables(tables: list[LoadedTable]) -> tuple[str, list[str], str | None, list[str], list[dict]]:
    campaigns = next((table for table in tables if table.object_name == "campaigns"), None)
    if campaigns is not None and {"campaign_name", "impressions", "clicks"}.issubset(set(campaigns.frame.columns)):
        return _analyze_campaigns(campaigns)
    traffic = next((table for table in tables if table.object_name == "traffic"), None)
    if traffic is not None and {"channel", "sessions"}.issubset(set(traffic.frame.columns)):
        return _analyze_traffic(traffic)
    answer, points, sql, columns, rows = describe_tables(tables)
    if rows:
        return answer, points, sql, columns, rows
    return (
        f"{answer} There is not enough of a time series here for a performance story. "
        "Ask a specific metric if you want a total or a ranking.",
        points,
        sql,
        columns,
        rows,
    )


def _describe_traffic(table: LoadedTable) -> tuple[str, list[str], str, list[str], list[dict]]:
    sql = (
        f"SELECT {quote_ident('channel')}, MIN({quote_ident('date')}) AS first_week, "
        f"MAX({quote_ident('date')}) AS last_week, COUNT(*) AS weeks, "
        f"SUM({quote_ident('sessions')}) AS sessions, SUM({quote_ident('users')}) AS users, "
        f"SUM({quote_ident('conversions')}) AS conversions "
        f"FROM {quote_ident(table.sql_name)} "
        f"GROUP BY {quote_ident('channel')} ORDER BY sessions DESC"
    )
    rows, columns = _run(sql, [table])
    start = min(str(row["first_week"])[:10] for row in rows)
    end = max(str(row["last_week"])[:10] for row in rows)
    total = sum(_as_number(row.get("sessions")) for row in rows)
    answer = (
        f"This is weekly Google Analytics traffic for {table.source_name}. "
        f"Each row in the source is one channel for one week, from {_pretty_date(start)} through {_pretty_date(end)}. "
        f"Sessions count visits. Users count people. The mix totals {_pretty_number(total)} sessions. "
        "The figures are sample data."
    )
    points = [
        f"{row['channel']} — {_pretty_number(row['sessions'])} sessions, "
        f"{_pretty_number(row['users'])} users, {_pretty_number(row['conversions'])} conversions"
        for row in rows
    ]
    return answer, points, sql, columns, rows


def _analyze_traffic(table: LoadedTable) -> tuple[str, list[str], str, list[str], list[dict]]:
    answer, points, sql, columns, rows = _describe_traffic(table)
    if not rows:
        return answer, points, sql, columns, rows
    total = sum(_as_number(row.get("sessions")) for row in rows)
    leader = rows[0]
    share = (_as_number(leader.get("sessions")) / total * 100) if total else 0
    analysis = (
        f"{answer} {leader['channel']} led the mix at {_pretty_number(leader['sessions'])} sessions "
        f"({share:.1f}% of traffic). Paid and organic search together show how acquisition "
        "and discovery share the site. These figures are sample data."
    )
    return analysis, points, sql, columns, rows


def _analyze_campaigns(table: LoadedTable) -> tuple[str, list[str], str, list[str], list[dict]]:
    answer, points, sql, columns, rows = _describe_campaigns(table)
    if not rows:
        return answer, points, sql, columns, rows
    impressions = sum(_as_number(row.get("impressions")) for row in rows)
    clicks = sum(_as_number(row.get("clicks")) for row in rows)
    start = min(str(row["first_week"])[:10] for row in rows)
    end = max(str(row["last_week"])[:10] for row in rows)
    weeks = max(int(_as_number(row.get("weeks"))) for row in rows)
    ranked = sorted(rows, key=lambda row: _as_number(row.get("clicks")), reverse=True)
    leader = ranked[0]
    weakest = min(
        rows,
        key=lambda row: (
            _as_number(row.get("clicks")) / _as_number(row.get("impressions"))
            if _as_number(row.get("impressions"))
            else 0
        ),
    )
    rate = (clicks / impressions * 100) if impressions else 0
    analysis = (
        f"Across {weeks} weeks from {_pretty_date(start)} through {_pretty_date(end)}, "
        f"these {len(rows)} campaigns were shown {_pretty_number(impressions)} times and opened "
        f"{_pretty_number(clicks)} times, a click-through rate of {rate:.1f}%. "
        f"{leader['campaign_name']} led, with {_pretty_number(leader['impressions'])} impressions and "
        f"{_pretty_number(leader['clicks'])} clicks. "
        f"{weakest['campaign_name']} was shown often relative to how rarely it was opened, "
        f"so it is the weakest at turning views into clicks. These figures are sample data."
    )
    return analysis, points, sql, columns, rows


def _as_number(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0


def _describe_campaigns(table: LoadedTable) -> tuple[str, list[str], str, list[str], list[dict]]:
    sql = (
        f"SELECT {quote_ident('campaign_name')}, {quote_ident('campaign_id')}, {quote_ident('campaign_type')}, "
        f"MIN({quote_ident('date')}) AS first_week, MAX({quote_ident('date')}) AS last_week, "
        f"COUNT(*) AS weeks, SUM({quote_ident('impressions')}) AS impressions, "
        f"SUM({quote_ident('clicks')}) AS clicks "
        f"FROM {quote_ident(table.sql_name)} "
        f"GROUP BY {quote_ident('campaign_name')}, {quote_ident('campaign_id')}, {quote_ident('campaign_type')} "
        f"ORDER BY {quote_ident('campaign_name')}"
    )
    rows, columns = _run(sql, [table])
    start = min(str(row["first_week"])[:10] for row in rows)
    end = max(str(row["last_week"])[:10] for row in rows)
    answer = (
        f"This is weekly Google Ads performance for {table.source_name}. "
        f"Each row in the source is one campaign for one week, from {_pretty_date(start)} through {_pretty_date(end)}. "
        "G001 and the other codes are campaign ids. Impressions count how often an ad was shown, "
        "and clicks count how often someone opened it. The figures are sample data."
    )
    points = [
        f"{row['campaign_name']} ({row['campaign_id']}, {str(row['campaign_type']).title()}) — "
        f"{_pretty_number(row['weeks'])} weeks, {_pretty_number(row['impressions'])} impressions, "
        f"{_pretty_number(row['clicks'])} clicks"
        for row in rows
    ]
    return answer, points, sql, columns, rows


def _pretty_date(value: str) -> str:
    parsed = date.fromisoformat(str(value)[:10])
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def plan_sql(question: str, tables: list[LoadedTable]) -> str:
    lowered = question.lower()
    table = _pick_table(lowered, tables)
    text_col = _pick_column(lowered, table, prefer="text") or _first_column(table, prefer="text")
    number_col = _pick_column(lowered, table, prefer="number") or _first_column(table, prefer="number")
    quoted = quote_ident(table.sql_name)

    if re.search(r"\b(average|avg|mean)\b", lowered) and number_col:
        return f"SELECT AVG({quote_ident(number_col)}) AS average FROM {quoted}"

    if text_col and re.search(r"\b(how many|count|number).*(each|by|per|status|type)\b", lowered):
        return (
            f"SELECT {quote_ident(text_col)}, COUNT(*) AS count "
            f"FROM {quoted} GROUP BY {quote_ident(text_col)} ORDER BY count DESC"
        )

    if table.object_name == "campaigns" and re.search(r"\b(how many|count|number of)\s+campaigns?\b", lowered):
        return f"SELECT COUNT(DISTINCT {quote_ident('campaign_id')}) AS row_count FROM {quoted}"

    if re.search(r"\b(how many|count|number of rows|row count)\b", lowered):
        return f"SELECT COUNT(*) AS row_count FROM {quoted}"

    if _looks_like_purchases(lowered, tables):
        return _purchase_sql(tables)

    if number_col and text_col and re.search(r"\b(top|highest|most|best|largest|greatest)\b", lowered):
        limit = 5 if "top 5" in lowered or "top five" in lowered else 10
        if _roll_up_campaigns(lowered, table):
            return (
                f"SELECT {quote_ident(text_col)}, SUM({quote_ident(number_col)}) AS {quote_ident(number_col)} "
                f"FROM {quoted} GROUP BY {quote_ident(text_col)} "
                f"ORDER BY {quote_ident(number_col)} DESC NULLS LAST LIMIT {limit}"
            )
        return (
            f"SELECT {quote_ident(text_col)}, {quote_ident(number_col)} "
            f"FROM {quoted} ORDER BY {quote_ident(number_col)} DESC NULLS LAST LIMIT {limit}"
        )
    if number_col and text_col and re.search(r"\b(lowest|least|smallest|fewest|worst)\b", lowered):
        return (
            f"SELECT {quote_ident(text_col)}, {quote_ident(number_col)} "
            f"FROM {quoted} ORDER BY {quote_ident(number_col)} ASC NULLS LAST LIMIT 10"
        )
    if number_col and text_col and re.search(r"\b(group|break|by type|by loan|by campaign|per campaign|compare)\b", lowered):
        return (
            f"SELECT {quote_ident(text_col)}, SUM({quote_ident(number_col)}) AS total "
            f"FROM {quoted} GROUP BY {quote_ident(text_col)} ORDER BY total DESC NULLS LAST"
        )
    if re.search(r"\b(show|list|display|preview)\b", lowered):
        return f"SELECT * FROM {quoted} LIMIT 50"
    if number_col and text_col:
        return (
            f"SELECT {quote_ident(text_col)}, {quote_ident(number_col)} "
            f"FROM {quoted} ORDER BY {quote_ident(number_col)} DESC NULLS LAST LIMIT 20"
        )
    return f"SELECT * FROM {quoted} LIMIT 50"


def _looks_like_purchases(question: str, tables: list[LoadedTable]) -> bool:
    names = {table.object_name for table in tables}
    return {"customers", "orders", "order_items"} <= names and any(
        word in question for word in ("purchase", "top 5 customer", "highest spend", "total sales")
    )


def _purchase_sql(tables: list[LoadedTable]) -> str:
    by_name = {table.object_name: table.sql_name for table in tables}
    customers = quote_ident(by_name["customers"])
    orders = quote_ident(by_name["orders"])
    items = quote_ident(by_name["order_items"])
    return (
        f"SELECT c.customer_id, c.full_name, SUM(oi.quantity * oi.unit_price) AS purchases "
        f"FROM {customers} c "
        f"JOIN {orders} o ON o.customer_id = c.customer_id "
        f"JOIN {items} oi ON oi.order_id = o.order_id "
        f"WHERE o.status = 'fulfilled' "
        f"GROUP BY c.customer_id, c.full_name "
        f"ORDER BY purchases DESC LIMIT 5"
    )


def _selected_sources(db: Session, source_ids: list[str] | None) -> list[DataSource]:
    rows = list(db.scalars(select(DataSource)).all())
    if source_ids:
        wanted = set(source_ids)
        chosen = [row for row in rows if row.id in wanted]
        if len(chosen) != len(wanted):
            raise ValueError("One of the selected sources was not found.")
        return chosen
    return [row for row in rows if row.enabled]


ADS_SELECT = (
    "SELECT campaign.id, campaign.name, campaign.advertising_channel_type, segments.date, "
    "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, "
    "metrics.conversions_value FROM campaign"
)


def _load_tables(sources: list[DataSource], question: str) -> tuple[list[LoadedTable], list[str]]:
    manager = get_manager()
    tables: list[LoadedTable] = []
    tools_used: list[str] = []
    for source in sources:
        if source.source_type == "google_ads":
            query = _ads_query(question)
            payload = manager.call(
                "google-ads.search",
                {"customer_id": source.config.get("customer_id"), "query": query},
            )
            tools_used.append("google-ads.search")
            frame = _coerce_frame(_ads_frame(payload.get("rows") or [], payload.get("columns") or []))
            if frame.empty:
                continue
            tables.append(
                LoadedTable(
                    sql_name=_unique_sql_name(tables, source, "campaigns"),
                    source_name=source.name,
                    object_name="campaigns",
                    columns=_ads_columns(frame),
                    frame=frame,
                )
            )
            continue
        namespace = manager.namespace_for(source.source_type)
        catalog = manager.call(f"{namespace}.catalog", {"source_id": source.id})
        tools_used.append(f"{namespace}.catalog")
        for obj in catalog.get("objects") or []:
            sample = manager.call(
                f"{namespace}.sample",
                {
                    "source_id": source.id,
                    "object_name": obj["name"],
                    "schema_name": obj.get("schema_name"),
                    "limit": MAX_LOAD,
                },
            )
            tools_used.append(f"{namespace}.sample")
            frame = _coerce_frame(pd.DataFrame(sample.get("rows") or []))
            columns_meta = sample.get("columns") or []
            if frame.empty and not columns_meta:
                continue
            if frame.empty:
                frame = pd.DataFrame(columns=columns_meta)
            catalog_columns = [
                (column["name"], column.get("data_type") or "text") for column in obj.get("columns") or []
            ] or [(name, "text") for name in frame.columns]
            tables.append(
                LoadedTable(
                    sql_name=_unique_sql_name(tables, source, obj["name"]),
                    source_name=source.name,
                    object_name=obj["name"],
                    columns=catalog_columns,
                    frame=frame,
                )
            )
    # Keep catalog/sample once each even if many objects were read.
    seen: list[str] = []
    for name in tools_used:
        if name not in seen:
            seen.append(name)
    return tables, seen


def _unique_sql_name(tables: list[LoadedTable], source: DataSource, object_name: str) -> str:
    sql_name = sanitize_ident(f"{source.source_type[:2]}_{object_name}")
    used = {table.sql_name for table in tables}
    if sql_name in used:
        sql_name = sanitize_ident(f"{sql_name}_{source.id[:4]}")
    return sql_name


def _ads_query(question: str) -> str:
    del question
    return ADS_SELECT


def _ads_frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty and columns:
        frame = pd.DataFrame(columns=columns)
    if "cost_micros" in frame.columns and "cost" not in frame.columns:
        frame["cost"] = pd.to_numeric(frame["cost_micros"], errors="coerce") / 1_000_000
    for column in ("impressions", "clicks", "cost_micros", "conversions", "cost", "conversion_value"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _ads_columns(frame: pd.DataFrame) -> list[tuple[str, str]]:
    types = {
        "campaign_id": "text",
        "campaign_name": "text",
        "campaign_type": "text",
        "date": "date",
        "impressions": "bigint",
        "clicks": "bigint",
        "cost": "numeric",
        "cost_micros": "bigint",
        "conversions": "bigint",
        "conversion_value": "numeric",
    }
    return [(name, types.get(name, "text")) for name in frame.columns]


def _roll_up_campaigns(question: str, table: LoadedTable) -> bool:
    if table.object_name not in {"campaigns", "traffic", "landing_pages"}:
        return False
    return not re.search(r"\b(over time|trend|by date|daily|weekly|week)\b", question)


def _run(sql: str, tables: list[LoadedTable]) -> tuple[list[dict], list[str]]:
    stripped = sql.strip().rstrip(";")
    if FORBIDDEN.search(stripped) or not re.match(r"^(select|with)\b", stripped, re.I):
        raise ValueError("Only read-only SELECT queries are allowed.")
    conn = duckdb.connect(":memory:")
    try:
        for table in tables:
            conn.register(table.sql_name, table.frame)
        result = conn.execute(stripped)
        keys = [item[0] for item in result.description]
        fetched = result.fetchmany(MAX_ROWS + 1)
        rows = [{key: json_safe(value) for key, value in zip(keys, row, strict=True)} for row in fetched[:MAX_ROWS]]
        return rows, keys
    except Exception as exc:
        raise ValueError(f"The query could not be run: {exc}") from exc
    finally:
        conn.close()


def _answer(question: str, rows: list[dict], columns: list[str], tables: list[LoadedTable], link=None) -> tuple[str, list[str]]:
    used = ", ".join(sorted({table.source_name for table in tables}))
    if not rows:
        return f"No rows matched in {used}.", []
    if len(rows) == 1 and len(columns) == 1 and columns[0] not in {"row_count", "average"} and _numeric(rows[0].get(columns[0])):
        metric = columns[0]
        value = _pretty_number(rows[0][metric])
        subject = _subject(question, link)
        window = _window(question)
        if subject and window:
            return f"{subject} received {value} {metric} {window}.", []
        if subject:
            return f"{subject} received {value} {metric}.", []
        return f"The total {metric} is {value}.", []
    if columns == ["row_count"]:
        return f"There are {rows[0]['row_count']} rows in {used}.", []
    if columns == ["average"]:
        value = _pretty_number(rows[0]["average"])
        metric = _metric_label(question) or "value"
        return f"The average {metric} is {value}.", []
    if "purchases" in columns and "full_name" in columns:
        points = [f"{row['full_name']} — {_pretty_number(row['purchases'])}" for row in rows[:8]]
        return "Top customers by fulfilled purchases:", points
    if len(columns) >= 2 and _numeric(rows[0].get(columns[1])):
        label, metric = columns[0], columns[1]
        points = [f"{row[label]} — {_pretty_number(row[metric])}" for row in rows[:12]]
        if re.search(r"\b(break|each|group|by type|by loan|compare|status)\b", question.lower()):
            return f"Here is the breakdown by {label.replace('_', ' ')}:", points
        return (
            f"{rows[0][label]} has the highest {metric.replace('_', ' ')} at {_pretty_number(rows[0][metric])}.",
            points,
        )
    if len(rows) == 1:
        parts = [f"{key.replace('_', ' ')} {_pretty_number(rows[0][key])}" for key in columns]
        return "Here is the result: " + ", ".join(parts) + ".", []
    lead = columns[0]
    points = [str(row.get(lead)) for row in rows[:12]]
    return f"I found {len(rows)} rows in {used}.", points


def _chart(question: str, columns: list[str], rows: list[dict]) -> ChartSpec | None:
    if len(rows) < 2 or len(columns) < 2:
        return None
    category = columns[0]
    value = next((column for column in columns[1:] if _numeric(rows[0].get(column))), None)
    if value is None:
        return None
    lowered = question.lower()
    if re.search(r"\b(share|mix|split|pie|breakdown|percent|by channel|by type|by campaign)\b", lowered):
        kind = "pie"
    elif re.search(r"\b(over time|trend|daily)\b", lowered) or "date" in category.lower():
        kind = "line"
    else:
        kind = "bar"
    title = f"{value.replace('_', ' ')} by {category.replace('_', ' ')}"
    return ChartSpec(type=kind, category=category, value=value, title=title)


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


def _subject(question: str, link) -> str | None:
    if link is not None and link.filters:
        return link.filters[0][1]
    match = re.search(r"\bfor ([A-Za-z][A-Za-z0-9 '.-]{2,60})", question)
    if match:
        return match.group(1).strip().rstrip("?.")
    return None


def _window(question: str) -> str | None:
    lowered = question.lower()
    if "last week" in lowered:
        return "in the latest week of this sample"
    if "last month" in lowered:
        return "last month"
    return None


def _metric_label(question: str) -> str | None:
    match = re.search(r"average ([a-z ]+?)(?:\s+of|\s+for|$)", question.lower())
    if match:
        return match.group(1).strip()
    return None


def _numeric(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _pick_table(question: str, tables: list[LoadedTable]) -> LoadedTable:
    scored = []
    for table in tables:
        hay = " ".join([table.object_name, table.source_name] + [name for name, _ in table.columns]).lower()
        score = sum(1 for token in re.findall(r"[a-z0-9]+", question) if token in hay and len(token) > 2)
        scored.append((score, table))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored[0][0] else tables[0]


def _pick_column(question: str, table: LoadedTable, prefer: str) -> str | None:
    tokens = set(re.findall(r"[a-z0-9]+", question))
    matches: list[str] = []
    for name, data_type in table.columns:
        needle = name.lower().replace("_", " ")
        if prefer == "number" and not _is_number(data_type):
            continue
        if prefer == "text" and _is_number(data_type):
            continue
        if any(token in needle or needle in token for token in tokens if len(token) > 2):
            matches.append(name)
    if not matches:
        return None
    if "id" not in tokens:
        labeled = [name for name in matches if not name.lower().endswith("_id")]
        if labeled:
            return labeled[0]
    return matches[0]


def _coerce_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    for column in out.columns:
        series = out[column]
        if pd.api.types.is_numeric_dtype(series):
            continue
        converted = pd.to_numeric(series, errors="coerce")
        if series.notna().sum() and converted.notna().sum() >= series.notna().sum() * 0.9:
            out[column] = converted
    return out


def _first_column(table: LoadedTable, prefer: str) -> str | None:
    for name, data_type in table.columns:
        if prefer == "number" and _is_number(data_type):
            return name
        if prefer == "text" and not _is_number(data_type):
            return name
    return table.columns[0][0] if table.columns else None


def _is_number(data_type: str) -> bool:
    return any(
        token in data_type.lower()
        for token in ("int", "numeric", "float", "double", "decimal", "bigint", "number")
    )
