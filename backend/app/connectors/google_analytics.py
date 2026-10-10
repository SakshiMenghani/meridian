from app.connectors.base import ResolvedSource
from app.errors import ConnectorError
from app.schemas import CatalogObject, ColumnInfo, SampleResult
from app.seed_data.google_analytics import PROPERTY_ID, PROPERTY_NAME, landing_rows, traffic_rows

TRAFFIC_COLUMNS = [
    ColumnInfo(name="date", data_type="date", nullable=False),
    ColumnInfo(name="channel", data_type="text", nullable=False),
    ColumnInfo(name="source", data_type="text", nullable=False),
    ColumnInfo(name="medium", data_type="text", nullable=False),
    ColumnInfo(name="sessions", data_type="bigint", nullable=False),
    ColumnInfo(name="users", data_type="bigint", nullable=False),
    ColumnInfo(name="conversions", data_type="bigint", nullable=False),
]

LANDING_COLUMNS = [
    ColumnInfo(name="date", data_type="date", nullable=False),
    ColumnInfo(name="landing_page", data_type="text", nullable=False),
    ColumnInfo(name="sessions", data_type="bigint", nullable=False),
    ColumnInfo(name="users", data_type="bigint", nullable=False),
]


class GoogleAnalyticsConnector:
    source_type = "google_analytics"

    def test(self, source: ResolvedSource) -> str:
        property_name = source.config.get("property_name") or PROPERTY_NAME
        property_id = source.config.get("property_id") or PROPERTY_ID
        origin = source.config.get("data_origin") or "sample"
        return f"Sample Google Analytics adapter for {property_name} ({property_id}). data_origin={origin}."

    def catalog(self, source: ResolvedSource) -> list[CatalogObject]:
        return [
            CatalogObject(
                name="traffic",
                kind="resource",
                row_count=len(traffic_rows()),
                note="Website sessions by channel. data_origin=sample.",
                columns=list(TRAFFIC_COLUMNS),
            ),
            CatalogObject(
                name="landing_pages",
                kind="resource",
                row_count=len(landing_rows()),
                note="Sessions by landing page. data_origin=sample.",
                columns=list(LANDING_COLUMNS),
            ),
        ]

    def sample(self, source: ResolvedSource, schema_name: str | None, object_name: str, limit: int) -> SampleResult:
        if object_name == "landing_pages":
            rows = landing_rows()
            columns = [column.name for column in LANDING_COLUMNS]
        elif object_name in {"traffic", "sessions", ""}:
            rows = traffic_rows()
            columns = [column.name for column in TRAFFIC_COLUMNS]
        else:
            raise ConnectorError("The sample adapter only exposes traffic and landing_pages.")
        sliced = rows[:limit]
        return SampleResult(columns=columns, rows=sliced, row_count=len(sliced), truncated=len(rows) > limit)
