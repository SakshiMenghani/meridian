import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

HIDDEN_CONFIG_KEYS = {"file_path", "demo_key"}
TOKEN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def public_config(config: dict) -> dict:
    return {key: value for key, value in config.items() if key not in HIDDEN_CONFIG_KEYS}


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or re.search(r"[\x00-\x1f]", cleaned):
        raise ValueError("Enter a name without control characters.")
    return cleaned


def _safe_token(value: str) -> str:
    if not TOKEN.fullmatch(value):
        raise ValueError("Use letters, numbers, dots, underscores, or hyphens only.")
    return value


class PostgresConfig(BaseModel):
    model_config = {"extra": "forbid"}

    host: str
    port: int = Field(ge=1, le=65535)
    database: str
    username: str
    sslmode: Literal["disable", "require", "verify-ca", "verify-full"] = "disable"

    @field_validator("host", "database", "username")
    @classmethod
    def tokens(cls, value: str) -> str:
        return _safe_token(value)


class MongoConfig(BaseModel):
    model_config = {"extra": "forbid"}

    host: str
    port: int = Field(ge=1, le=65535)
    database: str
    username: str
    auth_source: str = "admin"

    @field_validator("host", "database", "username", "auth_source")
    @classmethod
    def tokens(cls, value: str) -> str:
        return _safe_token(value)


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    nullable: bool | None = None


class CatalogObject(BaseModel):
    schema_name: str | None = None
    name: str
    kind: str
    row_count: int | None = None
    note: str | None = None
    columns: list[ColumnInfo] = []


class CatalogResponse(BaseModel):
    objects: list[CatalogObject]


class SampleResult(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool


class ColumnProfile(BaseModel):
    name: str
    suggested_name: str
    inferred_type: str
    missing: int
    nullable: bool


class ProfileResponse(BaseModel):
    row_count: int
    column_count: int
    duplicate_rows: int
    columns: list[ColumnProfile]
    preview: list[dict]
    suggested_ddl: str
    sheet_name: str | None = None
    table_name: str
    note: str


class SourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    origin: str
    enabled: bool
    status: str
    status_message: str | None
    last_checked_at: datetime | None
    has_secret: bool
    config: dict
    created_at: datetime
    updated_at: datetime


class CreateSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    source_type: Literal["postgresql", "mongodb"]
    config: dict
    secret: str = Field(min_length=1, max_length=200)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def clean(cls, value: str) -> str:
        return _clean_name(value)


class UpdateSourceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    enabled: bool | None = None
    config: dict | None = None
    secret: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def clean(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_name(value)


class TestResponse(BaseModel):
    ok: bool
    message: str
    source: SourceResponse


class MappingResponse(BaseModel):
    id: str
    left_source_name: str
    left_object: str
    left_field: str
    right_source_name: str
    right_object: str
    right_field: str
    description: str


class ActivityResponse(BaseModel):
    id: str
    source_id: str | None
    source_name: str | None
    action: str
    status: str
    detail: str
    created_at: datetime


class DashboardResponse(BaseModel):
    counts: dict[str, int]
    sources: list[SourceResponse]
    activity: list[ActivityResponse]
    mappings: list[MappingResponse]


class MetaResponse(BaseModel):
    app_name: str
    version: str
    phase: str
    seed_demo_data: bool
    openai_configured: bool
    upload_limit_mb: int
    supported_sources: list[str]
    embedding_model: str
    openai_model: str


class UploadResponse(BaseModel):
    source: SourceResponse
    profile: ProfileResponse


COLUMN_TYPES = ("text", "bigint", "numeric", "boolean", "date", "timestamp")


class ColumnTransform(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    suggested_name: str = Field(min_length=1, max_length=80)
    inferred_type: Literal["text", "bigint", "numeric", "boolean", "date", "timestamp"]
    include: bool = True


class TransformRequest(BaseModel):
    drop_duplicates: bool = False
    missing: Literal["keep", "drop_rows"] = "keep"
    columns: list[ColumnTransform] | None = None
    table_name: str | None = Field(default=None, max_length=80)


class PreviewTransformResponse(BaseModel):
    profile: ProfileResponse
    row_count: int
    dropped_duplicates: int
    dropped_empty_rows: int


class ImportRequest(TransformRequest):
    confirm: bool
    destination: Literal["spreadsheet", "postgresql", "mongodb"]
    replace_existing: bool = False


class ImportResponse(BaseModel):
    source: SourceResponse
    destination_source: SourceResponse
    object_name: str
    row_count: int
    message: str


class ChartSpec(BaseModel):
    type: Literal["bar", "line", "pie"]
    category: str
    value: str
    title: str


class ReportSection(BaseModel):
    title: str
    body: str
    columns: list[str]
    rows: list[dict]
    chart: ChartSpec | None = None


class ReportDocument(BaseModel):
    title: str
    summary: str
    generated_at: datetime
    sections: list[ReportSection]
    sources_used: list[str] = []


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    source_ids: list[str] | None = None
    as_report: bool = False


class AskResponse(BaseModel):
    answer: str
    points: list[str] = []
    sources_used: list[str]
    query: str | None
    columns: list[str]
    rows: list[dict]
    chart: ChartSpec | None = None
    status: str
    note: str | None = None
    tools_used: list[str] = []
    report: ReportDocument | None = None


class McpToolResponse(BaseModel):
    name: str
    description: str
    input_schema: dict = {}


class McpServerResponse(BaseModel):
    name: str
    transport: str
    enabled: bool
    data_origin: str | None = None
    tools: list[str] | None = None
    command: list[str] | None = None
    note: str | None = None


class McpRegistryResponse(BaseModel):
    servers: list[McpServerResponse]
    tools: list[McpToolResponse]
