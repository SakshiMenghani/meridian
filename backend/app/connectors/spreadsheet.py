import io
import json
from pathlib import Path

import pandas as pd

from app.config import get_settings
from app.connectors.base import ResolvedSource
from app.errors import ConnectorError
from app.identifiers import quote_ident, sanitize_ident
from app.schemas import CatalogObject, ColumnInfo, ColumnProfile, ProfileResponse, SampleResult

PREVIEW_ROWS = 20
PROFILE_NOTE = (
    "Types are inferred from values. Review names and types, drop duplicates or empty rows if you want, "
    "then approve a save. You can keep the cleaned file, write it to Imported PostgreSQL or Imported MongoDB, "
    "and ask questions about either copy."
)


def allowed_file(path: Path) -> Path:
    resolved = path.resolve()
    settings = get_settings()
    roots = [settings.upload_path.resolve(), settings.seed_data_path.resolve()]
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ConnectorError("Spreadsheet path is outside the allowed directories.")
    if not resolved.is_file():
        raise ConnectorError("Spreadsheet file was not found.")
    return resolved


def read_upload(filename: str, data: bytes) -> tuple[pd.DataFrame, str | None]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Save the CSV as UTF-8 and upload it again.") from exc
        frame = pd.read_csv(io.StringIO(text))
        return frame, None
    if suffix == ".xlsx":
        workbook = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
        if not workbook.sheet_names:
            raise ValueError("The workbook has no sheets.")
        sheet = workbook.sheet_names[0]
        return pd.read_excel(workbook, sheet_name=sheet), sheet
    raise ValueError("Upload a .csv or .xlsx file.")


def read_stored(path: Path) -> tuple[pd.DataFrame, str | None]:
    safe = allowed_file(path)
    return read_upload(safe.name, safe.read_bytes())


def _missing_count(series: pd.Series) -> int:
    if pd.api.types.is_string_dtype(series) or series.dtype == object:
        text = series.astype("string")
        return int((series.isna() | text.str.strip().eq("")).sum())
    return int(series.isna().sum())


def _infer_type(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "bigint"
    if pd.api.types.is_float_dtype(series):
        non_null = series.dropna()
        if len(non_null) and (non_null % 1 == 0).all():
            return "bigint"
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return _date_or_timestamp(series.dropna())
    non_null = series.dropna()
    if non_null.empty:
        return "text"
    as_text = non_null.astype(str).str.strip()
    as_text = as_text[as_text.ne("")]
    if as_text.empty:
        return "text"
    if as_text.str.fullmatch(r"-?\d+").all():
        return "bigint"
    if as_text.str.fullmatch(r"-?\d+\.\d+").all():
        return "numeric"
    if not as_text.str.contains(r"[-/]", regex=True).any():
        return "text"
    parsed = pd.to_datetime(as_text, format="%Y-%m-%d", errors="coerce")
    if parsed.notna().mean() >= 0.9:
        return "date"
    parsed = pd.to_datetime(as_text, format="%Y-%m-%d %H:%M:%S", errors="coerce")
    if parsed.notna().mean() >= 0.9:
        return _date_or_timestamp(parsed.dropna())
    return "text"


def _date_or_timestamp(values: pd.Series) -> str:
    midnight = []
    for value in values:
        midnight.append(value.hour == 0 and value.minute == 0 and value.second == 0)
    return "date" if midnight and all(midnight) else "timestamp"


def _preview(frame: pd.DataFrame) -> list[dict]:
    preview = frame.head(PREVIEW_ROWS)
    return json.loads(preview.to_json(orient="records", date_format="iso"))


def profile_frame(frame: pd.DataFrame, table_name: str, sheet_name: str | None = None) -> ProfileResponse:
    if frame.shape[1] == 0:
        raise ValueError("The file has no columns.")
    headers = [str(column) for column in frame.columns]
    if any(not header.strip() or header.startswith("Unnamed:") for header in headers):
        raise ValueError("Every column needs a header.")
    if len(set(headers)) != len(headers):
        raise ValueError("The file has duplicate column names. Rename them and upload again.")

    used: dict[str, int] = {}
    columns = []
    ddl_lines = []
    for header, series in zip(headers, (frame[column] for column in frame.columns), strict=True):
        suggested = sanitize_ident(header)
        used[suggested] = used.get(suggested, 0) + 1
        if used[suggested] > 1:
            suggested = sanitize_ident(f"{suggested}_{used[suggested]}")
        inferred = _infer_type(series)
        missing = _missing_count(series)
        nullable = missing > 0
        columns.append(
            ColumnProfile(
                name=header,
                suggested_name=suggested,
                inferred_type=inferred,
                missing=missing,
                nullable=nullable,
            )
        )
        constraint = "" if nullable else " NOT NULL"
        ddl_lines.append(f"  {quote_ident(suggested)} {inferred}{constraint}")

    table = sanitize_ident(table_name)
    ddl = f"CREATE TABLE {quote_ident(table)} (\n" + ",\n".join(ddl_lines) + "\n);"
    return ProfileResponse(
        row_count=int(len(frame)),
        column_count=len(columns),
        duplicate_rows=int(frame.duplicated().sum()),
        columns=columns,
        preview=_preview(frame),
        suggested_ddl=ddl,
        sheet_name=sheet_name,
        table_name=table,
        note=PROFILE_NOTE,
    )


class SpreadsheetConnector:
    source_type = "spreadsheet"

    def _frame(self, source: ResolvedSource) -> tuple[pd.DataFrame, str | None, str]:
        frame, sheet = read_stored(Path(source.config["file_path"]))
        table_name = source.config.get("table_name") or Path(source.config.get("original_name", "upload")).stem
        return frame, sheet, sanitize_ident(str(table_name))

    def test(self, source: ResolvedSource) -> str:
        frame, _, _ = self._frame(source)
        return f"Read {len(frame)} rows from {source.config.get('original_name', 'the spreadsheet')}."

    def catalog(self, source: ResolvedSource) -> list[CatalogObject]:
        frame, sheet, table_name = self._frame(source)
        profile = profile_frame(frame, table_name, sheet)
        return [
            CatalogObject(
                schema_name=None,
                name=table_name,
                kind="sheet",
                row_count=profile.row_count,
                note=profile.note,
                columns=[
                    ColumnInfo(name=column.name, data_type=column.inferred_type, nullable=column.nullable)
                    for column in profile.columns
                ],
            )
        ]

    def sample(
        self,
        source: ResolvedSource,
        schema_name: str | None,
        object_name: str,
        limit: int,
    ) -> SampleResult:
        frame, _, table_name = self._frame(source)
        if object_name and object_name != table_name:
            raise ConnectorError("That sheet is not in this file.")
        records = json.loads(frame.head(limit + 1).to_json(orient="records", date_format="iso"))
        truncated = len(records) > limit
        rows = records[:limit]
        columns = [str(column) for column in frame.columns]
        return SampleResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)

    def profile(self, source: ResolvedSource) -> ProfileResponse:
        frame, sheet, table_name = self._frame(source)
        return profile_frame(frame, table_name, sheet)
