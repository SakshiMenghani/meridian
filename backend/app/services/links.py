from itertools import combinations
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.workspace import LoadedTable, load_tables, selected_sources
from app.models import DataSource, FieldMapping, utcnow
from app.schemas import LinkCreateRequest, LinkSuggestion, MappingResponse
from app.services.sources import add_log

MIN_OVERLAP = 0.6
MIN_SHARED = 3
MAX_SUGGESTIONS = 12


def create_link(db: Session, payload: LinkCreateRequest) -> MappingResponse:
    left = db.get(DataSource, payload.left_source_id)
    right = db.get(DataSource, payload.right_source_id)
    if left is None or right is None:
        raise ValueError("One of the sources was not found.")
    tables, _ = load_tables([left] if left.id == right.id else [left, right])
    _require_column(tables, left.name, payload.left_object, payload.left_field)
    _require_column(tables, right.name, payload.right_object, payload.right_field)
    if (left.name, payload.left_object) == (right.name, payload.right_object):
        raise ValueError("Pick two different tables to link.")
    for existing in db.scalars(select(FieldMapping)).all():
        pair = {
            (existing.left_source_name, existing.left_object, existing.left_field),
            (existing.right_source_name, existing.right_object, existing.right_field),
        }
        if pair == {(left.name, payload.left_object, payload.left_field), (right.name, payload.right_object, payload.right_field)}:
            raise ValueError("That link is already confirmed.")
    row = FieldMapping(
        id=str(uuid4()),
        left_source_name=left.name,
        left_object=payload.left_object,
        left_field=payload.left_field,
        right_source_name=right.name,
        right_object=payload.right_object,
        right_field=payload.right_field,
        description=payload.description.strip()
        or f"{payload.left_object}.{payload.left_field} matches {payload.right_object}.{payload.right_field}.",
        created_at=utcnow(),
    )
    db.add(row)
    add_log(db, source_id=left.id, action="link", status="ok", detail=row.description[:200])
    db.commit()
    return _response(row)


def delete_link(db: Session, link_id: str) -> None:
    row = db.get(FieldMapping, link_id)
    if row is None:
        raise LookupError("Link not found.")
    db.delete(row)
    add_log(db, source_id=None, action="unlink", status="ok", detail=row.description[:200])
    db.commit()


def suggest_links(db: Session, source_ids: list[str] | None = None) -> list[LinkSuggestion]:
    sources = selected_sources(db, source_ids)
    if len(sources) < 2:
        return []
    tables, _ = load_tables(sources)
    existing = {
        frozenset(
            {
                (row.left_source_name, row.left_object, row.left_field),
                (row.right_source_name, row.right_object, row.right_field),
            }
        )
        for row in db.scalars(select(FieldMapping)).all()
    }
    keys = [(table, column, values) for table in tables for column, values in _key_columns(table)]
    found: list[LinkSuggestion] = []
    for (left, left_col, left_values), (right, right_col, right_values) in combinations(keys, 2):
        if left.source_id == right.source_id:
            continue
        pair = frozenset({(left.source_name, left.object_name, left_col), (right.source_name, right.object_name, right_col)})
        if pair in existing:
            continue
        shared = left_values & right_values
        if len(shared) < MIN_SHARED:
            continue
        overlap = len(shared) / min(len(left_values), len(right_values))
        if overlap < MIN_OVERLAP:
            continue
        found.append(
            LinkSuggestion(
                left_source_id=left.source_id,
                left_source_name=left.source_name,
                left_object=left.object_name,
                left_field=left_col,
                right_source_id=right.source_id,
                right_source_name=right.source_name,
                right_object=right.object_name,
                right_field=right_col,
                overlap=round(overlap, 3),
                shared_values=len(shared),
                examples=sorted(shared)[:3],
            )
        )
    found.sort(
        key=lambda item: (
            not (_key_like(item.left_field) and _key_like(item.right_field)),
            item.left_field.lower() != item.right_field.lower(),
            -item.overlap,
            -item.shared_values,
        )
    )
    return found[:MAX_SUGGESTIONS]


def _key_columns(table: LoadedTable) -> list[tuple[str, set[str]]]:
    out = []
    frame = table.frame
    for column, kind in table.columns:
        if column not in frame.columns or kind in {"numeric", "date", "timestamp", "boolean"}:
            continue
        series = frame[column].dropna()
        if series.empty or pd.api.types.is_float_dtype(series):
            continue
        values = {str(value).strip().lower() for value in series if str(value).strip()}
        if len(values) < MIN_SHARED:
            continue
        if _key_like(column) or len(values) / len(series) >= 0.5:
            out.append((column, values))
    return out


def _key_like(column: str) -> bool:
    name = column.lower()
    return name == "id" or name.endswith(("_id", "_key", "_code", "email", "sku"))


def _require_column(tables: list[LoadedTable], source_name: str, object_name: str, field: str) -> None:
    table = next((item for item in tables if item.source_name == source_name and item.object_name == object_name), None)
    if table is None:
        raise ValueError(f'"{object_name}" was not found in {source_name}.')
    if field not in {name for name, _ in table.columns}:
        raise ValueError(f'"{field}" was not found in {object_name}.')


def _response(row: FieldMapping) -> MappingResponse:
    return MappingResponse(
        id=row.id,
        left_source_name=row.left_source_name,
        left_object=row.left_object,
        left_field=row.left_field,
        right_source_name=row.right_source_name,
        right_object=row.right_object,
        right_field=row.right_field,
        description=row.description,
    )
