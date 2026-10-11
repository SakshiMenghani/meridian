import pandas as pd

from app.security import json_safe

MAX_LISTED_VALUES = 25
EXAMPLES = 3


def profile_tables(tables) -> list[dict]:
    return [profile_table(table) for table in tables]


def profile_table(table) -> dict:
    frame = table.frame
    columns = []
    for name, kind in table.columns:
        entry: dict = {"name": name, "type": kind}
        if name in frame.columns:
            series = frame[name]
            present = series.dropna()
            entry["nulls"] = int(series.isna().sum())
            if kind in {"date", "timestamp"} and not present.empty:
                entry["min"] = _iso(present.min())
                entry["max"] = _iso(present.max())
            elif kind in {"bigint", "numeric"} and not present.empty:
                entry["min"] = json_safe(_plain(present.min()))
                entry["max"] = json_safe(_plain(present.max()))
                entry["sum"] = json_safe(_plain(present.sum()))
            elif not present.empty:
                texts = present.astype(str)
                distinct = texts.nunique()
                entry["distinct"] = int(distinct)
                if distinct <= MAX_LISTED_VALUES:
                    entry["values"] = sorted(texts.unique().tolist())
                else:
                    entry["examples"] = [value[:60] for value in texts.head(EXAMPLES).tolist()]
        columns.append(entry)
    return {
        "table": table.sql_name,
        "source": table.source_name,
        "object": table.object_name,
        "rows": int(len(frame)),
        "rows_capped": bool(getattr(table, "truncated", False)),
        "columns": columns,
    }


def kind_of(column: dict) -> str:
    kind = column.get("type", "text")
    if kind in {"date", "timestamp"}:
        return "time"
    if kind in {"bigint", "numeric"}:
        return "number"
    return "text"


def is_identifier(column: dict, rows: int) -> bool:
    name = column["name"].lower()
    if name == "id" or name.endswith("_id"):
        return True
    distinct = column.get("distinct")
    return kind_of(column) == "text" and distinct is not None and rows > 0 and distinct == rows and rows > MAX_LISTED_VALUES


def good_dimension(profile: dict) -> dict | None:
    rows = profile["rows"]
    candidates = [
        column
        for column in profile["columns"]
        if kind_of(column) == "text" and not is_identifier(column, rows) and 2 <= (column.get("distinct") or 0) <= 30
    ]
    candidates.sort(key=lambda column: column.get("distinct") or 0)
    return candidates[0] if candidates else None


def good_measure(profile: dict) -> dict | None:
    rows = profile["rows"]
    candidates = [
        column for column in profile["columns"] if kind_of(column) == "number" and not is_identifier(column, rows)
    ]
    return candidates[0] if candidates else None


def time_column(profile: dict) -> dict | None:
    return next((column for column in profile["columns"] if kind_of(column) == "time"), None)


def humanize(name: str) -> str:
    return name.replace("_", " ").strip()


def _iso(value) -> str:
    if isinstance(value, pd.Timestamp):
        if value == value.normalize():
            return value.date().isoformat()
        return value.isoformat()
    return str(value)


def _plain(value):
    if hasattr(value, "item"):
        return value.item()
    return value
