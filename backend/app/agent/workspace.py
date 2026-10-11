import re
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.guard import Link
from app.identifiers import sanitize_ident
from app.mcp import get_manager
from app.models import DataSource, FieldMapping

MAX_LOAD = 5_000
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")

ADS_SELECT = (
    "SELECT campaign.id, campaign.name, campaign.advertising_channel_type, segments.date, "
    "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, "
    "metrics.conversions_value FROM campaign"
)


@dataclass
class LoadedTable:
    sql_name: str
    source_name: str
    object_name: str
    columns: list[tuple[str, str]]
    frame: pd.DataFrame
    truncated: bool = False
    source_id: str = ""


def selected_sources(db: Session, source_ids: list[str] | None) -> list[DataSource]:
    rows = list(db.scalars(select(DataSource)).all())
    if source_ids:
        wanted = set(source_ids)
        chosen = [row for row in rows if row.id in wanted]
        if len(chosen) != len(wanted):
            raise ValueError("One of the selected sources was not found.")
        return chosen
    return [row for row in rows if row.enabled]


def load_tables(sources: list[DataSource]) -> tuple[list[LoadedTable], list[str]]:
    manager = get_manager()
    tables: list[LoadedTable] = []
    tools_used: list[str] = []
    for source in sources:
        if source.source_type == "google_ads":
            payload = manager.call(
                "google-ads.search",
                {"customer_id": source.config.get("customer_id"), "query": ADS_SELECT},
            )
            tools_used.append("google-ads.search")
            frame = coerce_frame(_ads_frame(payload.get("rows") or [], payload.get("columns") or []))
            if frame.empty:
                continue
            tables.append(
                LoadedTable(
                    sql_name=_unique_sql_name(tables, source, "campaigns"),
                    source_name=source.name,
                    object_name="campaigns",
                    columns=frame_columns(frame),
                    frame=frame,
                    source_id=source.id,
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
            frame = coerce_frame(pd.DataFrame(sample.get("rows") or []))
            columns_meta = sample.get("columns") or []
            if frame.empty and not columns_meta:
                continue
            if frame.empty:
                frame = pd.DataFrame(columns=columns_meta)
                columns = [
                    (column["name"], column.get("data_type") or "text") for column in obj.get("columns") or []
                ] or [(name, "text") for name in frame.columns]
            else:
                columns = frame_columns(frame)
            tables.append(
                LoadedTable(
                    sql_name=_unique_sql_name(tables, source, obj["name"]),
                    source_name=source.name,
                    object_name=obj["name"],
                    columns=columns,
                    frame=frame,
                    truncated=bool(sample.get("truncated")),
                    source_id=source.id,
                )
            )
    seen: list[str] = []
    for name in tools_used:
        if name not in seen:
            seen.append(name)
    return tables, seen


def confirmed_links(db: Session, tables: list[LoadedTable]) -> list[Link]:
    by_object = {(table.source_name, table.object_name): table.sql_name for table in tables}
    links: list[Link] = []
    for mapping in db.scalars(select(FieldMapping)).all():
        left = by_object.get((mapping.left_source_name, mapping.left_object))
        right = by_object.get((mapping.right_source_name, mapping.right_object))
        if left and right:
            links.append(Link(left, mapping.left_field, right, mapping.right_field))
    return links


def coerce_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    for column in out.columns:
        series = out[column]
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            continue
        present = series.dropna()
        if present.empty:
            continue
        converted = pd.to_numeric(series, errors="coerce")
        if converted.notna().sum() >= len(present) * 0.9:
            out[column] = converted
            continue
        as_text = present.astype(str)
        if as_text.str.match(ISO_DATE).mean() >= 0.9:
            parsed = pd.to_datetime(series, errors="coerce", format="ISO8601", utc=as_text.str.contains(r"Z|[+-]\d{2}:?\d{2}$").any())
            if parsed.notna().sum() >= len(present) * 0.9:
                if getattr(parsed.dt, "tz", None) is not None:
                    parsed = parsed.dt.tz_convert(None)
                out[column] = parsed
    return out


def frame_columns(frame: pd.DataFrame) -> list[tuple[str, str]]:
    columns = []
    for name in frame.columns:
        series = frame[name]
        if pd.api.types.is_bool_dtype(series):
            kind = "boolean"
        elif pd.api.types.is_integer_dtype(series):
            kind = "bigint"
        elif pd.api.types.is_numeric_dtype(series):
            kind = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(series):
            times = series.dropna()
            kind = "date" if times.empty or (times.dt.normalize() == times).all() else "timestamp"
        else:
            kind = "text"
        columns.append((str(name), kind))
    return columns


def _unique_sql_name(tables: list[LoadedTable], source: DataSource, object_name: str) -> str:
    sql_name = sanitize_ident(f"{source.source_type[:2]}_{object_name}")
    used = {table.sql_name for table in tables}
    if sql_name in used:
        sql_name = sanitize_ident(f"{sql_name}_{source.id[:4]}")
    return sql_name


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
