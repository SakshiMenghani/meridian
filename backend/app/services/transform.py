from pathlib import Path
from uuid import uuid4

import pandas as pd
from pymongo import MongoClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.connectors.spreadsheet import profile_frame, read_stored
from app.errors import ConnectorError
from app.identifiers import IDENT, sanitize_ident
from app.models import DataSource
from app.schemas import (
    ColumnTransform,
    ImportRequest,
    ImportResponse,
    PreviewTransformResponse,
    TransformRequest,
)
from app.services.sources import add_log, require_source, resolve, test_source, to_source

MAX_IMPORT_ROWS = 20_000
WAREHOUSE_PG = "imports_pg"
WAREHOUSE_MONGO = "imports_mongo"
PG_TYPES = {
    "text": "text",
    "bigint": "bigint",
    "numeric": "numeric",
    "boolean": "boolean",
    "date": "date",
    "timestamp": "timestamp",
}


def preview_transform(db: Session, source_id: str, payload: TransformRequest) -> PreviewTransformResponse:
    source = _spreadsheet(db, source_id)
    original, sheet, _ = _load(source)
    frame, dropped_dupes, dropped_empty = apply_transform(original, payload)
    table = sanitize_ident(payload.table_name or source.config.get("table_name") or source.name)
    profile = profile_frame(frame, table, sheet)
    return PreviewTransformResponse(
        profile=profile,
        row_count=len(frame),
        dropped_duplicates=dropped_dupes,
        dropped_empty_rows=dropped_empty if payload.missing == "drop_rows" else 0,
    )


def import_transform(db: Session, source_id: str, payload: ImportRequest) -> ImportResponse:
    if not payload.confirm:
        raise ValueError("Confirm the save. Nothing is written until you approve it.")
    source = _spreadsheet(db, source_id)
    original, _sheet, _ = _load(source)
    if len(original) > MAX_IMPORT_ROWS:
        raise ValueError(f"This file has more than {MAX_IMPORT_ROWS} rows.")
    frame, _, _ = apply_transform(original, payload)
    table = sanitize_ident(payload.table_name or source.config.get("table_name") or source.name)
    if not IDENT.fullmatch(table):
        raise ValueError("Choose a simpler table name.")

    if payload.destination == "spreadsheet":
        destination = _save_cleaned_file(db, source, frame, table)
        add_log(db, source_id=source.id, action="import", status="ok", detail=f"Saved cleaned {table} as a spreadsheet.")
        db.commit()
        return ImportResponse(
            source=to_source(source),
            destination_source=to_source(destination),
            object_name=table,
            row_count=len(frame),
            message=f"Saved {len(frame)} cleaned rows in the spreadsheet. You can ask questions about this file.",
        )

    target = _warehouse(db, payload.destination)
    if payload.destination == "postgresql":
        _write_postgres(frame, table, payload.replace_existing)
    else:
        _write_mongo(frame, table, payload.replace_existing)
    test_source(db, target.id)
    db.refresh(target)
    add_log(
        db,
        source_id=source.id,
        action="import",
        status="ok",
        detail=f"Imported {len(frame)} rows into {target.name}.{table}.",
    )
    db.commit()
    place = "Imported PostgreSQL" if payload.destination == "postgresql" else "Imported MongoDB"
    return ImportResponse(
        source=to_source(source),
        destination_source=to_source(target),
        object_name=table,
        row_count=len(frame),
        message=f"Wrote {len(frame)} rows to {place} as {table}. You can browse that source or ask questions about it.",
    )


def apply_transform(frame: pd.DataFrame, payload: TransformRequest) -> tuple[pd.DataFrame, int, int]:
    if frame.empty and frame.shape[1] == 0:
        raise ValueError("The file has no columns.")
    columns = payload.columns or [
        ColumnTransform(name=column.name, suggested_name=column.suggested_name, inferred_type=column.inferred_type)
        for column in profile_frame(frame, "preview").columns
    ]
    included = [column for column in columns if column.include]
    if not included:
        raise ValueError("Keep at least one column.")
    missing = [column.name for column in included if column.name not in frame.columns]
    if missing:
        raise ValueError(f"Unknown column: {missing[0]}.")
    work = frame[[column.name for column in included]].copy()
    names = [sanitize_ident(column.suggested_name) for column in included]
    if len(set(names)) != len(names):
        raise ValueError("Two columns would get the same name. Rename one of them.")
    work.columns = names
    dropped_dupes = 0
    if payload.drop_duplicates:
        dropped_dupes = int(work.duplicated().sum())
        work = work.drop_duplicates()
    blanked = work.copy()
    for column in blanked.columns:
        if blanked[column].dtype == object or pd.api.types.is_string_dtype(blanked[column]):
            blanked[column] = blanked[column].replace(r"^\s*$", pd.NA, regex=True)
    dropped_empty = int(len(blanked) - len(blanked.dropna()))
    if payload.missing == "drop_rows":
        work = blanked.dropna()
    else:
        work = blanked
    for name, column in zip(work.columns, included, strict=True):
        work[name] = _cast(work[name], column.inferred_type)
    return work.reset_index(drop=True), dropped_dupes, dropped_empty


def _cast(series: pd.Series, inferred: str) -> pd.Series:
    if inferred == "text":
        return series.astype("string")
    if inferred == "boolean":
        return series.map(_as_bool, na_action="ignore").astype("boolean")
    if inferred == "bigint":
        numeric = pd.to_numeric(series, errors="coerce")
        return numeric.round().astype("Int64")
    if inferred == "numeric":
        return pd.to_numeric(series, errors="coerce")
    if inferred in {"date", "timestamp"}:
        parsed = pd.to_datetime(series, errors="coerce")
        if inferred == "date":
            return parsed.dt.date
        return parsed
    return series


def _as_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    return pd.NA


def _spreadsheet(db: Session, source_id: str) -> DataSource:
    source = require_source(db, source_id)
    if source.source_type != "spreadsheet":
        raise ValueError("Only spreadsheet sources can be cleaned or imported.")
    return source


def _load(source: DataSource):
    frame, sheet = read_stored(Path(source.config["file_path"]))
    table = sanitize_ident(str(source.config.get("table_name") or source.name))
    return frame, sheet, table


def _save_cleaned_file(db: Session, source: DataSource, frame: pd.DataFrame, table: str) -> DataSource:
    settings = get_settings()
    path = settings.upload_path / f"{uuid4().hex}.csv"
    frame.to_csv(path, index=False)
    previous = Path(source.config.get("file_path", ""))
    upload_root = settings.upload_path.resolve()
    source.config = {
        **source.config,
        "file_path": str(path.resolve()),
        "table_name": table,
        "original_name": f"{table}.csv",
    }
    db.commit()
    test_source(db, source.id)
    resolved = previous.resolve() if previous else None
    if resolved and resolved.is_file() and upload_root in resolved.parents and resolved != path.resolve():
        resolved.unlink(missing_ok=True)
    return source


def _warehouse(db: Session, destination: str) -> DataSource:
    key = WAREHOUSE_PG if destination == "postgresql" else WAREHOUSE_MONGO
    for source in db.scalars(select(DataSource)).all():
        if (source.config or {}).get("demo_key") == key:
            return source
    raise ValueError("The import warehouse is not registered. Restart the API so it can be created.")


def _write_postgres(frame: pd.DataFrame, table: str, replace: bool) -> None:
    settings = get_settings()
    url = URL.create(
        "postgresql+psycopg",
        username=settings.import_pg_writer_username,
        password=settings.import_pg_writer_password,
        host=settings.demo_pg_host,
        port=settings.demo_pg_port,
        database=settings.import_pg_database,
    )
    engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})
    try:
        inspector = inspect(engine)
        exists = table in inspector.get_table_names()
        if exists and not replace:
            raise ValueError(f"Table {table} already exists. Enable replace if you mean to overwrite it.")
        if exists and replace:
            with engine.begin() as conn:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
        typed = _for_sql(frame)
        typed.to_sql(table, engine, index=False, if_exists="fail", schema="public")
        with engine.begin() as conn:
            conn.execute(text(f'GRANT SELECT ON TABLE "{table}" TO "{settings.import_pg_username}"'))
    except ConnectorError:
        raise
    except ValueError:
        raise
    except Exception as exc:
        raise ConnectorError(str(exc)) from exc
    finally:
        engine.dispose()


def _write_mongo(frame: pd.DataFrame, collection: str, replace: bool) -> None:
    settings = get_settings()
    from urllib.parse import quote_plus

    uri = (
        f"mongodb://{quote_plus(settings.import_mongo_writer_username)}:"
        f"{quote_plus(settings.import_mongo_writer_password)}@"
        f"{settings.demo_mongo_host}:{settings.demo_mongo_port}/"
        f"{settings.import_mongo_database}?authSource={quote_plus(settings.import_mongo_auth_source)}"
        "&serverSelectionTimeoutMS=5000"
    )
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        database = client[settings.import_mongo_database]
        existing = collection in database.list_collection_names()
        if existing and not replace:
            raise ValueError(f"Collection {collection} already exists. Enable replace if you mean to overwrite it.")
        if existing and replace:
            database[collection].drop()
        records = _for_mongo(frame)
        if records:
            database[collection].insert_many(records)
        elif collection not in database.list_collection_names():
            database.create_collection(collection)
    finally:
        client.close()


def _for_sql(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            continue
        if out[column].dtype == object:
            sample = next((value for value in out[column] if value is not None and not pd.isna(value)), None)
            if hasattr(sample, "year") and hasattr(sample, "month") and not hasattr(sample, "hour"):
                out[column] = pd.to_datetime(out[column], errors="coerce")
    return out


def _missing(value) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _for_mongo(frame: pd.DataFrame) -> list[dict]:
    records = []
    for row in frame.to_dict(orient="records"):
        clean = {}
        for key, value in row.items():
            if value is None or _missing(value):
                clean[key] = None
            elif hasattr(value, "isoformat"):
                clean[key] = value.isoformat()
            else:
                clean[key] = value
        records.append(clean)
    return records
