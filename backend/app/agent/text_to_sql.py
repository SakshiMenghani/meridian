import re
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from app.identifiers import quote_ident

INTENTS = {
    "overview": "explain what this dataset is about and what the columns mean",
    "rank_high": "which one is the highest the most the top the best more than the others",
    "rank_low": "which one is the lowest the least the fewest the smallest the worst",
    "average": "what is the average or the mean value",
    "sum": "what is the total amount we received",
    "count": "how many rows or records are there",
    "group": "break the results down and compare each group",
    "preview": "show a list or preview of the rows",
}

MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
MONTH_PATTERN = re.compile(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b(?:\s+(\d{4}))?", re.I)
TIME_QUESTION = re.compile(r"\b(date|week|day|daily|weekly|monthly|when|over time|trend|by month)\b", re.I)


@dataclass
class SqlLink:
    intent: str
    sql: str | None
    model_name: str
    gloss: str
    table_name: str
    dimension: str | None
    measure: str | None
    filters: list[tuple[str, str]] | None = None


def link_question(question: str, tables: list, embedder, today: date | None = None) -> SqlLink:
    cards: list[tuple[object, str, str, str]] = []
    for table in tables:
        for name, data_type in table.columns:
            cards.append((table, name, data_type, _column_text(table, name, data_type)))
    if not cards:
        table = tables[0]
        return SqlLink("preview", f"SELECT * FROM {quote_ident(table.sql_name)} LIMIT 50", embedder.name, "", table.object_name, None, None)

    intent_labels = list(INTENTS)
    vectors = embedder.embed([question, *[text for *_, text in cards], *[INTENTS[label] for label in intent_labels]])
    query_vector = vectors[0]
    card_vectors = vectors[1 : 1 + len(cards)]
    intent_vectors = vectors[1 + len(cards) :]
    scored = [
        (_cosine(query_vector, vector), table, name, data_type)
        for vector, (table, name, data_type, _) in zip(card_vectors, cards, strict=True)
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    table = scored[0][1]
    on_table = [item for item in scored if item[1] is table]
    measure = _best(on_table, numeric=True)
    dimension = _best(on_table, numeric=False, question=question) or _fallback_dimension(table, question)
    intent = _intent(question, query_vector, intent_labels, intent_vectors, tables)
    filters = _value_filters(table, question)
    sql = None if intent == "overview" else _sql(intent, table, dimension, measure, question, filters, today or date.today())
    return SqlLink(intent, sql, embedder.name, "", table.object_name, dimension, measure, filters)


def _column_text(table, name: str, data_type: str) -> str:
    text = f"Table {table.object_name.replace('_', ' ')} in {table.source_name}. Column {name.replace('_', ' ')} ({data_type})."
    frame = getattr(table, "frame", None)
    if frame is not None and name in frame.columns and not _is_number(data_type) and not _is_time(name, data_type):
        values = [str(value) for value in frame[name].dropna().unique()[:5]]
        if values:
            text += " Values like " + ", ".join(values) + "."
    return text


def _intent(question: str, query_vector: list[float], labels: list[str], vectors: list[list[float]], tables: list) -> str:
    forced = _keyword_intent(question, _measure_words(tables))
    if forced:
        return forced
    scores = [_cosine(query_vector, vector) for vector in vectors]
    return labels[max(range(len(labels)), key=lambda index: scores[index])]


def _measure_words(tables: list) -> set[str]:
    words: set[str] = set()
    for table in tables:
        for name, data_type in table.columns:
            if not _is_number(data_type) or name.lower().endswith("_id"):
                continue
            for token in re.split(r"[_\s]+", name.lower()):
                if len(token) >= 3:
                    words.add(token.rstrip("s"))
    return words


def _keyword_intent(question: str, measure_words: set[str]) -> str | None:
    lowered = question.lower()
    tokens = {token.rstrip("s") for token in re.findall(r"[a-z]+", lowered)}
    if re.search(r"\b(average|avg|mean)\b", lowered):
        return "average"
    if re.search(r"\b(how many|how much|total|sum of)\b", lowered) and tokens & measure_words:
        return "sum"
    if re.search(r"\b(how many|count|number of rows|row count)\b", lowered):
        return "count"
    if re.search(r"\b(lowest|least|smallest|fewest|worst|bottom)\b", lowered):
        return "rank_low"
    if re.search(r"\b(top|highest|most|best|largest|greatest|biggest)\b", lowered):
        return "rank_high"
    if re.search(r"\b(group|break|compare|by each|per)\b", lowered):
        return "group"
    if re.search(r"\b(show|list|display|preview)\b", lowered):
        return "preview"
    return None


def _best(scored: list[tuple], numeric: bool, question: str = "") -> str | None:
    ranked = [item for item in scored if _is_number(item[3]) == numeric and item[0] > 0]
    if numeric:
        ranked = [item for item in ranked if not item[2].lower().endswith("_id")]
    else:
        labeled = [item for item in ranked if not item[2].lower().endswith("_id")]
        if labeled:
            ranked = labeled
        if question and not TIME_QUESTION.search(question):
            undated = [item for item in ranked if not _is_time(item[2], item[3])]
            if undated:
                ranked = undated
    if not ranked:
        return None
    return ranked[0][2]


def _fallback_dimension(table, question: str) -> str | None:
    names = [
        name for name, data_type in table.columns if not _is_number(data_type) and not name.lower().endswith("_id")
    ]
    if not TIME_QUESTION.search(question):
        undated = [name for name in names if not _is_time(name, dict(table.columns).get(name, ""))]
        if undated:
            names = undated
    if names:
        return names[0]
    for name, data_type in table.columns:
        if not _is_number(data_type):
            return name
    return None


def _is_time(name: str, data_type: str) -> bool:
    if data_type.lower() in {"date", "timestamp", "datetime"} or "timestamp" in data_type.lower():
        return True
    lowered = name.lower()
    return lowered == "date" or lowered.endswith("_date") or lowered.endswith("_on") or lowered.endswith("_at")


def _sql(
    intent: str,
    table,
    dimension: str | None,
    measure: str | None,
    question: str,
    filters: list[tuple[str, str]],
    today: date,
) -> str:
    quoted = quote_ident(table.sql_name)
    where = _where(table, question, filters, today)
    if intent == "average" and measure:
        return f"SELECT AVG({quote_ident(measure)}) AS average_{measure} FROM {quoted}{where}"
    if intent == "sum" and measure:
        return f"SELECT SUM({quote_ident(measure)}) AS {quote_ident(measure)} FROM {quoted}{where}"
    if intent == "count":
        return f"SELECT COUNT(*) AS row_count FROM {quoted}{where}"
    if intent == "preview" or not dimension or not measure:
        return f"SELECT * FROM {quoted}{where} LIMIT 50"
    direction = "ASC" if intent == "rank_low" else "DESC"
    top = re.search(r"\btop\s+(\d{1,3})\b", question, re.I)
    limit = int(top.group(1)) if top else (10 if intent in {"rank_high", "rank_low"} else 50)
    group = quote_ident(dimension)
    value = quote_ident(measure)
    return (
        f"SELECT {group}, SUM({value}) AS {value} FROM {quoted}{where} "
        f"GROUP BY {group} ORDER BY {value} {direction} NULLS LAST LIMIT {min(limit, 200)}"
    )


def _where(table, question: str, filters: list[tuple[str, str]], today: date) -> str:
    parts = [f"{quote_ident(column)} = {_literal(value)}" for column, value in filters]
    time = _time_filter(table, question, today)
    if time:
        parts.append(time)
    if not parts:
        return ""
    return " WHERE " + " AND ".join(parts)


def _value_filters(table, question: str) -> list[tuple[str, str]]:
    if table.frame is None or table.frame.empty:
        return []
    found: list[tuple[str, str, int]] = []
    for name, data_type in table.columns:
        if _is_number(data_type) or _is_time(name, data_type) or name not in table.frame.columns:
            continue
        values = {str(value) for value in table.frame[name].dropna().unique() if str(value).strip()}
        for value in values:
            if len(value) < 3:
                continue
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])", question, re.I):
                found.append((name, value, len(value)))
    found.sort(key=lambda item: item[2], reverse=True)
    used_columns: set[str] = set()
    filters: list[tuple[str, str]] = []
    for name, value, _length in found:
        if name in used_columns:
            continue
        used_columns.add(name)
        filters.append((name, value))
    return filters


def _time_filter(table, question: str, today: date) -> str | None:
    if table.frame is None or table.frame.empty:
        return None
    column = next(
        (
            name
            for name, data_type in table.columns
            if name in table.frame.columns and pd.api.types.is_datetime64_any_dtype(table.frame[name])
        ),
        None,
    )
    if not column:
        return None
    present = table.frame[column].dropna()
    if present.empty:
        return None
    window = _window(question, today, present)
    if not window:
        return None
    start, end = window
    return f"{quote_ident(column)} >= DATE {_literal(start.isoformat())} AND {quote_ident(column)} < DATE {_literal(end.isoformat())}"


def _window(question: str, today: date, present: pd.Series) -> tuple[date, date] | None:
    lowered = question.lower()
    latest = present.max().date()
    named = MONTH_PATTERN.search(question)
    if named and not (named.group(1).lower() == "may" and not named.group(2)):
        month = MONTHS[named.group(1).lower()]
        if named.group(2):
            year = int(named.group(2))
        else:
            years = sorted({stamp.year for stamp in present if stamp.month == month})
            year = years[-1] if years else today.year
        return _month(year, month)
    if re.search(r"\b(last|previous|prior) month\b", lowered):
        start, end = _month(*_shift_month(today.year, today.month, -1))
        if not ((present >= pd.Timestamp(start)) & (present < pd.Timestamp(end))).any():
            start, end = _month(latest.year, latest.month)
        return start, end
    if re.search(r"\bthis month\b", lowered):
        return _month(today.year, today.month)
    if re.search(r"\b(last|previous|prior) week\b", lowered):
        monday = today - timedelta(days=today.weekday())
        start, end = monday - timedelta(days=7), monday
        if not ((present >= pd.Timestamp(start)) & (present < pd.Timestamp(end))).any():
            start = latest - timedelta(days=latest.weekday())
            end = start + timedelta(days=7)
        return start, end
    days = re.search(r"\b(?:last|past) (\d{1,3}) days\b", lowered)
    if days:
        return today - timedelta(days=int(days.group(1))), today + timedelta(days=1)
    if re.search(r"\bthis year\b", lowered):
        return date(today.year, 1, 1), date(today.year + 1, 1, 1)
    return None


def _month(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(*_shift_month(year, month, 1), 1)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _is_number(data_type: str) -> bool:
    return any(token in data_type.lower() for token in ("int", "numeric", "float", "double", "decimal", "number", "real"))


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
