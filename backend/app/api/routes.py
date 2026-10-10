from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import ConnectorError
from app.identifiers import sanitize_ident
from app.schemas import (
    ActivityResponse,
    AskRequest,
    AskResponse,
    CatalogResponse,
    CreateSourceRequest,
    DashboardResponse,
    ImportRequest,
    ImportResponse,
    MappingResponse,
    McpRegistryResponse,
    MetaResponse,
    PreviewTransformResponse,
    ProfileResponse,
    SampleResult,
    SourceResponse,
    TestResponse,
    TransformRequest,
    UpdateSourceRequest,
    UploadResponse,
)
from app.services.ask import ask_question
from app.services.transform import import_transform, preview_transform
from app.services.sources import (
    catalog,
    create_database_source,
    create_spreadsheet_source,
    dashboard,
    delete_source,
    list_activity,
    list_mappings,
    list_sources,
    profile,
    require_source,
    sample,
    test_source,
    to_source,
    update_source,
)
from app.connectors.spreadsheet import profile_frame, read_upload
from app.mcp import get_manager

router = APIRouter()


def _guard(action):
    try:
        return action()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConnectorError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaResponse)
def meta() -> MetaResponse:
    settings = get_settings()
    return MetaResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        phase="1–4",
        seed_demo_data=settings.seed_demo_data,
        openai_configured=bool(settings.openai_api_key.strip()),
        upload_limit_mb=settings.max_upload_bytes // (1024 * 1024),
        supported_sources=["postgresql", "mongodb", "spreadsheet", "google_ads", "google_analytics"],
        embedding_model=settings.embedding_model,
        openai_model=settings.openai_model if settings.openai_api_key.strip() else "not configured",
    )


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    return dashboard(db)


@router.get("/sources", response_model=list[SourceResponse])
def get_sources(db: Session = Depends(get_db)) -> list[SourceResponse]:
    return list_sources(db)


@router.post("/sources", response_model=TestResponse, status_code=201)
def post_source(payload: CreateSourceRequest, db: Session = Depends(get_db)) -> TestResponse:
    return _guard(lambda: create_database_source(db, payload))


@router.get("/sources/{source_id}", response_model=SourceResponse)
def get_source(source_id: str, db: Session = Depends(get_db)) -> SourceResponse:
    return _guard(lambda: to_source(require_source(db, source_id)))


@router.patch("/sources/{source_id}", response_model=SourceResponse)
def patch_source(source_id: str, payload: UpdateSourceRequest, db: Session = Depends(get_db)) -> SourceResponse:
    return _guard(lambda: update_source(db, source_id, payload))


@router.delete("/sources/{source_id}")
def remove_source(source_id: str, db: Session = Depends(get_db)) -> dict:
    _guard(lambda: delete_source(db, source_id))
    return {"deleted": True}


@router.post("/sources/{source_id}/test", response_model=TestResponse)
def post_test(source_id: str, db: Session = Depends(get_db)) -> TestResponse:
    return _guard(lambda: test_source(db, source_id))


@router.get("/sources/{source_id}/catalog", response_model=CatalogResponse)
def get_catalog(source_id: str, db: Session = Depends(get_db)) -> CatalogResponse:
    return _guard(lambda: catalog(db, source_id))


@router.get("/sources/{source_id}/sample", response_model=SampleResult)
def get_sample(
    source_id: str,
    name: str = Query(min_length=1, max_length=80),
    schema: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SampleResult:
    return _guard(lambda: sample(db, source_id, schema, name, limit))


@router.get("/sources/{source_id}/profile", response_model=ProfileResponse)
def get_profile(source_id: str, db: Session = Depends(get_db)) -> ProfileResponse:
    return _guard(lambda: profile(db, source_id))


@router.post("/sources/{source_id}/preview-transform", response_model=PreviewTransformResponse)
def post_preview_transform(
    source_id: str,
    payload: TransformRequest,
    db: Session = Depends(get_db),
) -> PreviewTransformResponse:
    return _guard(lambda: preview_transform(db, source_id, payload))


@router.post("/sources/{source_id}/import", response_model=ImportResponse)
def post_import(source_id: str, payload: ImportRequest, db: Session = Depends(get_db)) -> ImportResponse:
    return _guard(lambda: import_transform(db, source_id, payload))


@router.get("/mcp/tools", response_model=McpRegistryResponse)
def get_mcp_tools() -> McpRegistryResponse:
    manager = get_manager()
    return McpRegistryResponse(servers=manager.servers(), tools=manager.list_tools())


@router.post("/ask", response_model=AskResponse)
def post_ask(payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    return _guard(lambda: ask_question(db, payload))


@router.post("/report", response_model=AskResponse)
def post_report(payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    payload.as_report = True
    return _guard(lambda: ask_question(db, payload))


@router.post("/uploads", response_model=UploadResponse, status_code=201)
def post_upload(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> UploadResponse:
    settings = get_settings()
    filename = Path(file.filename or "upload.csv").name
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the 8 MB limit.")
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")

    def action() -> UploadResponse:
        frame, sheet = read_upload(filename, data)
        label = (name or Path(filename).stem).strip()
        if not label:
            raise ValueError("Enter a name for this spreadsheet.")
        profile_body = profile_frame(frame, sanitize_ident(label) or "uploaded_table", sheet)
        destination = settings.upload_path / f"{uuid4().hex}{Path(filename).suffix.lower()}"
        destination.write_bytes(data)
        try:
            source = create_spreadsheet_source(
                db,
                name=label[:80],
                path=str(destination.resolve()),
                original_name=filename,
                table_name=profile_body.table_name,
                origin="upload",
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return UploadResponse(source=to_source(source), profile=profile_body)

    try:
        return action()
    except (ConnectorError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mappings", response_model=list[MappingResponse])
def get_mappings(db: Session = Depends(get_db)) -> list[MappingResponse]:
    return list_mappings(db)


@router.get("/activity", response_model=list[ActivityResponse])
def get_activity(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ActivityResponse]:
    return list_activity(db, limit)
