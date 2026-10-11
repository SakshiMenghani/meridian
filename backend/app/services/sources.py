from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.connectors.base import ResolvedSource
from app.connectors.registry import get_connector
from app.errors import ConnectorError
from app.models import AccessLog, DataSource, FieldMapping, utcnow
from app.schemas import (
    ActivityResponse,
    CatalogResponse,
    CreateSourceRequest,
    DashboardResponse,
    MappingResponse,
    MongoConfig,
    PostgresConfig,
    ProfileResponse,
    SampleResult,
    SourceResponse,
    TestResponse,
    UpdateSourceRequest,
    public_config,
)
from app.security import decrypt_secret, encrypt_secret, rotate_secret, scrub_text

PARSE = {
    "postgresql": PostgresConfig,
    "mongodb": MongoConfig,
}


def to_source(source: DataSource) -> SourceResponse:
    return SourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        origin=source.origin,
        enabled=source.enabled,
        status=source.status,
        status_message=source.status_message,
        last_checked_at=source.last_checked_at,
        has_secret=bool(source.secret_ciphertext),
        config=public_config(source.config or {}),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def parse_config(source_type: str, config: dict) -> dict:
    model = PARSE.get(source_type)
    if model is None:
        raise ValueError("Choose PostgreSQL or MongoDB.")
    try:
        return model.model_validate(config).model_dump()
    except ValidationError as exc:
        message = "; ".join(error["msg"].removeprefix("Value error, ") for error in exc.errors())
        raise ValueError(message) from exc


def require_source(db: Session, source_id: str) -> DataSource:
    source = db.get(DataSource, source_id)
    if source is None:
        raise LookupError("Data source not found.")
    return source


def resolve(source: DataSource) -> ResolvedSource:
    secret = None
    if source.secret_ciphertext:
        settings = get_settings()
        secret = decrypt_secret(source.secret_ciphertext, settings.app_secret_key, settings.previous_secret_keys)
    return ResolvedSource(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        config=source.config,
        secret=secret,
    )


def rotate_stored_secrets(db: Session) -> int:
    settings = get_settings()
    if not settings.previous_secret_keys:
        return 0
    rotated = 0
    for source in db.scalars(select(DataSource).where(DataSource.secret_ciphertext.is_not(None))).all():
        source.secret_ciphertext = rotate_secret(
            source.secret_ciphertext, settings.app_secret_key, settings.previous_secret_keys
        )
        rotated += 1
    db.commit()
    return rotated


def add_log(db: Session, *, source_id: str | None, action: str, status: str, detail: str) -> None:
    db.add(
        AccessLog(
            id=str(uuid4()),
            source_id=source_id,
            action=action,
            status=status,
            detail=detail[:500],
            created_at=utcnow(),
        )
    )


def list_sources(db: Session) -> list[SourceResponse]:
    rows = db.scalars(select(DataSource).order_by(DataSource.created_at)).all()
    return [to_source(row) for row in rows]


def create_database_source(db: Session, payload: CreateSourceRequest) -> TestResponse:
    config = parse_config(payload.source_type, payload.config)
    now = utcnow()
    source = DataSource(
        id=str(uuid4()),
        name=payload.name,
        source_type=payload.source_type,
        origin="external",
        enabled=payload.enabled,
        status="unknown",
        status_message=None,
        config=config,
        secret_ciphertext=encrypt_secret(payload.secret, get_settings().app_secret_key),
        created_at=now,
        updated_at=now,
    )
    db.add(source)
    db.commit()
    return test_source(db, source.id)


def create_spreadsheet_source(
    db: Session,
    *,
    name: str,
    path: str,
    original_name: str,
    table_name: str,
    origin: str,
    demo_key: str | None = None,
) -> DataSource:
    now = utcnow()
    config = {"file_path": path, "original_name": original_name, "table_name": table_name}
    if demo_key:
        config["demo_key"] = demo_key
    source = DataSource(
        id=str(uuid4()),
        name=name,
        source_type="spreadsheet",
        origin=origin,
        enabled=True,
        status="unknown",
        status_message=None,
        config=config,
        secret_ciphertext=None,
        created_at=now,
        updated_at=now,
    )
    db.add(source)
    db.commit()
    test_source(db, source.id)
    add_log(db, source_id=source.id, action="upload", status="ok", detail=f"Registered {original_name}.")
    db.commit()
    return source


def update_source(db: Session, source_id: str, payload: UpdateSourceRequest) -> SourceResponse:
    source = require_source(db, source_id)
    if payload.name is not None:
        source.name = payload.name
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.config is not None:
        if source.source_type == "spreadsheet":
            raise ValueError("Spreadsheet files are replaced by uploading a new file.")
        if source.source_type in {"google_ads", "google_analytics"}:
            raise ValueError("Marketing sample settings are managed by the seed adapter.")
        parsed = parse_config(source.source_type, payload.config)
        demo_key = (source.config or {}).get("demo_key")
        if demo_key:
            parsed["demo_key"] = demo_key
        source.config = parsed
    if payload.secret:
        source.secret_ciphertext = encrypt_secret(payload.secret, get_settings().app_secret_key)
    source.updated_at = utcnow()
    db.commit()
    if payload.config is not None or payload.secret:
        return test_source(db, source.id).source
    add_log(
        db,
        source_id=source.id,
        action="update",
        status="ok",
        detail=("Enabled." if source.enabled else "Disabled.") if payload.enabled is not None else "Renamed.",
    )
    db.commit()
    return to_source(source)


def delete_source(db: Session, source_id: str) -> None:
    source = require_source(db, source_id)
    if source.source_type == "spreadsheet":
        from pathlib import Path

        file_path = Path(source.config.get("file_path", ""))
        upload_root = get_settings().upload_path.resolve()
        resolved = file_path.resolve() if file_path else None
        if resolved and resolved.is_file() and (resolved == upload_root or upload_root in resolved.parents):
            resolved.unlink()
    name = source.name
    db.delete(source)
    add_log(db, source_id=None, action="delete", status="ok", detail=f"Removed {name}.")
    db.commit()


def test_source(db: Session, source_id: str) -> TestResponse:
    source = require_source(db, source_id)
    resolved = resolve(source)
    secrets = [resolved.secret]
    try:
        message = get_connector(source.source_type).test(resolved)
        source.status = "healthy"
        source.status_message = message
        ok = True
    except Exception as exc:
        message = scrub_text(str(exc), secrets)
        source.status = "error"
        source.status_message = message
        ok = False
    source.last_checked_at = utcnow()
    source.updated_at = source.last_checked_at
    add_log(db, source_id=source.id, action="test", status="ok" if ok else "error", detail=message)
    db.commit()
    return TestResponse(ok=ok, message=message, source=to_source(source))


def catalog(db: Session, source_id: str) -> CatalogResponse:
    source = require_source(db, source_id)
    resolved = resolve(source)
    try:
        objects = get_connector(source.source_type).catalog(resolved)
    except Exception as exc:
        message = scrub_text(str(exc), [resolved.secret])
        add_log(db, source_id=source.id, action="catalog", status="error", detail=message)
        db.commit()
        raise ConnectorError(message) from exc
    add_log(db, source_id=source.id, action="catalog", status="ok", detail=f"{len(objects)} objects.")
    db.commit()
    return CatalogResponse(objects=objects)


def sample(db: Session, source_id: str, schema_name: str | None, object_name: str, limit: int) -> SampleResult:
    source = require_source(db, source_id)
    resolved = resolve(source)
    try:
        result = get_connector(source.source_type).sample(resolved, schema_name, object_name, limit)
    except Exception as exc:
        message = scrub_text(str(exc), [resolved.secret])
        add_log(db, source_id=source.id, action="sample", status="error", detail=message)
        db.commit()
        raise ConnectorError(message) from exc
    label = f"{schema_name}.{object_name}" if schema_name else object_name
    add_log(db, source_id=source.id, action="sample", status="ok", detail=f"Read {result.row_count} rows from {label}.")
    db.commit()
    return result


def profile(db: Session, source_id: str) -> ProfileResponse:
    source = require_source(db, source_id)
    if source.source_type != "spreadsheet":
        raise ValueError("Profiles are available for spreadsheets.")
    resolved = resolve(source)
    try:
        return get_connector(source.source_type).profile(resolved)
    except Exception as exc:
        raise ConnectorError(scrub_text(str(exc), [])) from exc


def list_mappings(db: Session) -> list[MappingResponse]:
    rows = db.scalars(select(FieldMapping).order_by(FieldMapping.created_at)).all()
    return [
        MappingResponse(
            id=row.id,
            left_source_name=row.left_source_name,
            left_object=row.left_object,
            left_field=row.left_field,
            right_source_name=row.right_source_name,
            right_object=row.right_object,
            right_field=row.right_field,
            description=row.description,
        )
        for row in rows
    ]


def list_activity(db: Session, limit: int) -> list[ActivityResponse]:
    logs = db.scalars(select(AccessLog).order_by(AccessLog.created_at.desc()).limit(limit)).all()
    names = {source.id: source.name for source in db.scalars(select(DataSource)).all()}
    return [
        ActivityResponse(
            id=row.id,
            source_id=row.source_id,
            source_name=names.get(row.source_id) if row.source_id else None,
            action=row.action,
            status=row.status,
            detail=row.detail,
            created_at=row.created_at,
        )
        for row in logs
    ]


def dashboard(db: Session) -> DashboardResponse:
    sources = list_sources(db)
    return DashboardResponse(
        counts={
            "total": len(sources),
            "healthy": sum(source.status == "healthy" for source in sources),
            "enabled": sum(source.enabled for source in sources),
            "attention": sum(source.status == "error" for source in sources),
        },
        sources=sources,
        activity=list_activity(db, 8),
        mappings=list_mappings(db),
    )
