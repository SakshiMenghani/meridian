import re
from dataclasses import dataclass

from app.identifiers import quote_ident

GLOSSARY = {
    "campaign_id": "short campaign code such as G001",
    "campaign_name": "advertising campaign title such as Summer Trail Push",
    "campaign_type": "advertising channel such as search, shopping, or display",
    "date": "week the ads ran",
    "impressions": "how many times the advertisement was shown or viewed",
    "clicks": "how many times someone clicked or opened the advertisement",
    "cost": "advertising spend in dollars",
    "cost_micros": "advertising spend in micros",
    "conversions": "completed goals attributed to the ads",
    "conversion_value": "value of those conversions",
    "customer_id": "customer code such as C001",
    "full_name": "customer person name",
    "email": "customer email address",
    "region": "customer region",
    "city": "customer city",
    "product_id": "product code such as P001",
    "name": "product name",
    "category": "product category",
    "unit_cost": "cost to stock one product",
    "list_price": "catalog price of one product",
    "order_id": "order code",
    "ordered_on": "date the order was placed",
    "status": "order or case status, such as fulfilled or refunded",
    "sales_channel": "sales channel such as web or store",
    "quantity": "units purchased",
    "unit_price": "price charged for one unit",
    "segment": "CRM segment such as vip or loyal",
    "loyalty_points": "CRM loyalty balance, not revenue",
    "rating": "review score",
    "title": "review or case title",
    "loan_type": "kind of loan application",
    "total_applications": "count of loan applications",
    "channel": "website traffic channel such as paid search or organic",
    "sessions": "website visits or sessions",
    "users": "unique website visitors",
    "landing_page": "first page of a website visit",
    "source": "traffic source such as google or newsletter",
    "medium": "traffic medium such as cpc or email",
}

GLOSS_SENTENCE = {
    "clicks": "Clicks count how often someone opened the ad.",
    "impressions": "Impressions count how often the ad was shown.",
    "cost": "Cost is the advertising spend.",
    "conversions": "Conversions are completed goals attributed to the ads.",
    "conversion_value": "Conversion value is the value of those goals.",
    "loyalty_points": "Loyalty points are a CRM balance, not revenue.",
}

INTENTS = {
    "overview": "explain what this dataset is about and what the columns mean",
    "analysis": "what story or overall analysis or insight does the performance show",
    "rank_high": "which one is the highest the most the top the best more than the others",
    "rank_low": "which one is the lowest the least the fewest the smallest the worst",
    "average": "what is the average or the mean value",
    "sum": "how many clicks impressions conversions or the total we received",
    "count": "how many rows or how many campaigns are there",
    "group": "break the results down and compare each group",
    "preview": "show a list or preview of the rows",
}

MEASURE_WORDS = (
    "click",
    "impression",
    "conversion",
    "purchase",
    "sale",
    "spend",
    "cost",
    "application",
    "revenue",
    "session",
    "user",
    "visitor",
)

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


def link_question(question: str, tables: list, embedder) -> SqlLink:
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
    intent = _intent(question, query_vector, intent_labels, intent_vectors)
    filters = _value_filters(table, question)
    sql = None if intent in {"overview", "analysis"} else _sql(intent, table, dimension, measure, question, filters)
    gloss = GLOSS_SENTENCE.get(measure or "", "")
    return SqlLink(intent, sql, embedder.name, gloss, table.object_name, dimension, measure, filters)


def _column_text(table, name: str, data_type: str) -> str:
    meaning = GLOSSARY.get(name, name.replace("_", " "))
    return (
        f"Table {table.object_name} in {table.source_name}. "
        f"Column {name} is {data_type}. {meaning}."
    )


def _intent(question: str, query_vector: list[float], labels: list[str], vectors: list[list[float]]) -> str:
    forced = _keyword_intent(question)
    if forced:
        return forced
    scores = [_cosine(query_vector, vector) for vector in vectors]
    return labels[max(range(len(labels)), key=lambda index: scores[index])]


def _keyword_intent(question: str) -> str | None:
    lowered = question.lower()
    if re.search(r"\b(analysis|insight|takeaway|performance story)\b", lowered):
        return "analysis"
    if re.search(r"\b(average|avg|mean)\b", lowered):
        return "average"
    if re.search(r"\b(how many|total|sum of)\b", lowered) and any(word in lowered for word in MEASURE_WORDS):
        return "sum"
    if re.search(r"\b(how many|count|number of rows|row count)\b", lowered):
        return "count"
    if re.search(r"\b(lowest|least|smallest|fewest|worst)\b", lowered):
        return "rank_low"
    if re.search(r"\b(top|highest|most|best|largest|greatest)\b", lowered):
        return "rank_high"
    if re.search(r"\b(group|break|compare)\b", lowered):
        return "group"
    if re.search(r"\b(show|list|display|preview)\b", lowered):
        return "preview"
    return None


TIME_QUESTION = re.compile(r"\b(date|week|day|daily|when|over time|trend)\b", re.I)


def _best(scored: list[tuple], numeric: bool, question: str = "") -> str | None:
    ranked = [item for item in scored if _is_number(item[3]) == numeric and item[0] > 0]
    if numeric:
        ranked = [item for item in ranked if not item[2].endswith("_id")]
    else:
        labeled = [item for item in ranked if not item[2].endswith("_id")]
        if labeled:
            ranked = labeled
        if question and not TIME_QUESTION.search(question):
            undated = [item for item in ranked if not _is_time_column(item[2])]
            if undated:
                ranked = undated
    if not ranked:
        return None
    return ranked[0][2]


def _fallback_dimension(table, question: str) -> str | None:
    names = [name for name, data_type in table.columns if not _is_number(data_type) and not name.endswith("_id")]
    if not TIME_QUESTION.search(question):
        undated = [name for name in names if not _is_time_column(name)]
        if undated:
            names = undated
    if names:
        return names[0]
    for name, data_type in table.columns:
        if not _is_number(data_type):
            return name
    return None


def _is_time_column(name: str) -> bool:
    lowered = name.lower()
    return lowered == "date" or lowered.endswith("_date") or lowered.endswith("_on") or lowered.endswith("_at")


def _sql(intent: str, table, dimension: str | None, measure: str | None, question: str, filters: list[tuple[str, str]] | None = None) -> str:
    quoted = quote_ident(table.sql_name)
    where = _where(table, question, filters or [])
    if intent == "average" and measure:
        return f"SELECT AVG({quote_ident(measure)}) AS average FROM {quoted}{where}"
    if intent == "sum" and measure:
        return f"SELECT SUM({quote_ident(measure)}) AS {quote_ident(measure)} FROM {quoted}{where}"
    if intent == "count":
        if table.object_name == "campaigns" and _has(table, "campaign_id") and "campaign" in question.lower():
            return f"SELECT COUNT(DISTINCT {quote_ident('campaign_id')}) AS row_count FROM {quoted}{where}"
        return f"SELECT COUNT(*) AS row_count FROM {quoted}{where}"
    if intent in {"rank_high", "rank_low"} and dimension and measure:
        direction = "DESC" if intent == "rank_high" else "ASC"
        limit = 5 if "top 5" in question.lower() or "top five" in question.lower() else 10
        measure_sql = quote_ident(measure)
        if _rollup(question, table):
            return (
                f"SELECT {quote_ident(dimension)}, SUM({measure_sql}) AS {measure_sql} "
                f"FROM {quoted}{where} GROUP BY {quote_ident(dimension)} "
                f"ORDER BY {measure_sql} {direction} NULLS LAST LIMIT {limit}"
            )
        return (
            f"SELECT {quote_ident(dimension)}, {measure_sql} FROM {quoted}{where} "
            f"ORDER BY {measure_sql} {direction} NULLS LAST LIMIT {limit}"
        )
    if intent == "group" and dimension and measure:
        return (
            f"SELECT {quote_ident(dimension)}, SUM({quote_ident(measure)}) AS total "
            f"FROM {quoted}{where} GROUP BY {quote_ident(dimension)} ORDER BY total DESC NULLS LAST"
        )
    if intent == "preview" or not dimension or not measure:
        return f"SELECT * FROM {quoted}{where} LIMIT 50"
    if _rollup(question, table):
        return (
            f"SELECT {quote_ident(dimension)}, SUM({quote_ident(measure)}) AS {quote_ident(measure)} "
            f"FROM {quoted}{where} GROUP BY {quote_ident(dimension)} "
            f"ORDER BY {quote_ident(measure)} DESC NULLS LAST LIMIT 20"
        )
    return (
        f"SELECT {quote_ident(dimension)}, {quote_ident(measure)} FROM {quoted}{where} "
        f"ORDER BY {quote_ident(measure)} DESC NULLS LAST LIMIT 20"
    )


def _where(table, question: str, filters: list[tuple[str, str]]) -> str:
    parts = [f"{quote_ident(column)} = {_literal(value)}" for column, value in filters]
    time = _time_filter(table, question)
    if time:
        parts.append(time)
    if not parts:
        return ""
    return " WHERE " + " AND ".join(parts)


def _value_filters(table, question: str) -> list[tuple[str, str]]:
    if table.frame is None or table.frame.empty:
        return []
    lowered = question.lower()
    found: list[tuple[str, str, int]] = []
    for name, data_type in table.columns:
        if _is_number(data_type) or _is_time_column(name):
            continue
        if name not in table.frame.columns:
            continue
        values = {str(value) for value in table.frame[name].dropna().unique() if str(value).strip()}
        for value in values:
            if len(value) < 3:
                continue
            if value.lower() in lowered:
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


def _time_filter(table, question: str) -> str | None:
    if table.frame is None or table.frame.empty or "date" not in table.frame.columns:
        return None
    lowered = question.lower()
    dates = sorted({str(value)[:10] for value in table.frame["date"].dropna().unique()})
    if not dates:
        return None
    if "last week" in lowered:
        return f"{quote_ident('date')} = {_literal(dates[-1])}"
    if any(phrase in lowered for phrase in ("last month", "previous month", "prior month")):
        month = dates[-1][:7]
        month_dates = [item for item in dates if item.startswith(month)]
        if len(month_dates) < 2:
            prior = {item[:7] for item in dates}
            months = sorted(prior)
            if len(months) >= 2:
                month = months[-2]
                month_dates = [item for item in dates if item.startswith(month)]
        if month_dates:
            return f"{quote_ident('date')} BETWEEN {_literal(month_dates[0])} AND {_literal(month_dates[-1])}"
    return None


def _literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _rollup(question: str, table) -> bool:
    if table.object_name not in {"campaigns", "traffic", "landing_pages"}:
        return False
    return not re.search(r"\b(over time|trend|by date|daily|weekly|week)\b", question, re.I)


def _has(table, name: str) -> bool:
    return any(column == name for column, _ in table.columns)


def _is_number(data_type: str) -> bool:
    return any(token in data_type.lower() for token in ("int", "numeric", "float", "double", "decimal", "bigint", "number"))


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math_sqrt(sum(value * value for value in left))
    right_norm = math_sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def math_sqrt(value: float) -> float:
    return value**0.5
