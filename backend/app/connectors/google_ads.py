from app.connectors.base import ResolvedSource
from app.errors import ConnectorError
from app.schemas import CatalogObject, ColumnInfo, SampleResult
from app.seed_data.google_ads import CUSTOMER_ID, CUSTOMER_NAME, campaign_rows

COLUMNS = [
    ColumnInfo(name="campaign_id", data_type="text", nullable=False),
    ColumnInfo(name="campaign_name", data_type="text", nullable=False),
    ColumnInfo(name="campaign_type", data_type="text", nullable=False),
    ColumnInfo(name="date", data_type="date", nullable=False),
    ColumnInfo(name="impressions", data_type="bigint", nullable=False),
    ColumnInfo(name="clicks", data_type="bigint", nullable=False),
    ColumnInfo(name="cost", data_type="numeric", nullable=False),
    ColumnInfo(name="cost_micros", data_type="bigint", nullable=False),
    ColumnInfo(name="conversions", data_type="bigint", nullable=False),
    ColumnInfo(name="conversion_value", data_type="numeric", nullable=False),
]


class GoogleAdsConnector:
    source_type = "google_ads"

    def test(self, source: ResolvedSource) -> str:
        customer = source.config.get("customer_name") or CUSTOMER_NAME
        customer_id = source.config.get("customer_id") or CUSTOMER_ID
        origin = source.config.get("data_origin") or "sample"
        return f"Sample Google Ads adapter for {customer} ({customer_id}). data_origin={origin}."

    def catalog(self, source: ResolvedSource) -> list[CatalogObject]:
        rows = campaign_rows()
        return [
            CatalogObject(
                schema_name=None,
                name="campaigns",
                kind="resource",
                row_count=len(rows),
                note="Synthetic Google Ads campaigns. data_origin=sample. Swap the MCP registration to use live Ads.",
                columns=list(COLUMNS),
            )
        ]

    def sample(
        self,
        source: ResolvedSource,
        schema_name: str | None,
        object_name: str,
        limit: int,
    ) -> SampleResult:
        if object_name and object_name not in {"campaigns", "campaign"}:
            raise ConnectorError("The sample adapter only exposes campaigns.")
        rows = campaign_rows()
        truncated = len(rows) > limit
        sliced = rows[:limit]
        return SampleResult(
            columns=[column.name for column in COLUMNS],
            rows=sliced,
            row_count=len(sliced),
            truncated=truncated,
        )
