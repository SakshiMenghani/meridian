import calendar
import re
from datetime import date

from mcp.server.mcpserver import MCPServer

from app.seed_data.google_ads import CUSTOMER_ID, CUSTOMER_NAME, SAMPLE_AS_OF, campaign_rows

FIELD_MAP = {
    "campaign.id": "campaign_id",
    "campaign.name": "campaign_name",
    "campaign.advertising_channel_type": "campaign_type",
    "segments.date": "date",
    "metrics.impressions": "impressions",
    "metrics.clicks": "clicks",
    "metrics.cost_micros": "cost_micros",
    "metrics.conversions": "conversions",
    "metrics.conversions_value": "conversion_value",
}

GAQL = re.compile(
    r"^SELECT\s+(?P<select>.+?)\s+FROM\s+(?P<resource>\w+)"
    r"(?:\s+WHERE\s+(?P<where>.+?))?"
    r"(?:\s+ORDER\s+BY\s+(?P<order>.+?))?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?\s*$",
    re.I | re.S,
)
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|mutate)\b", re.I)


def build_google_ads_server() -> MCPServer:
    server = MCPServer(
        name="google-ads",
        instructions="Sample Google Ads tools with the same names as the official server. data_origin is always sample.",
    )

    @server.tool(description="List Google Ads customer ids visible to this adapter.")
    def list_accessible_customers() -> dict:
        return {
            "data_origin": "sample",
            "customers": [{"id": CUSTOMER_ID, "name": CUSTOMER_NAME}],
        }

    @server.tool(description="Run a read-only GAQL search against the sample campaign dataset.")
    def search(customer_id: str, query: str) -> dict:
        if customer_id != CUSTOMER_ID:
            raise ValueError("Unknown customer id for the sample adapter.")
        return run_gaql(query, as_of=SAMPLE_AS_OF)

    @server.tool(description="Describe a Google Ads resource type such as campaign.")
    def get_resource_metadata(resource_type: str) -> dict:
        if resource_type.lower() != "campaign":
            raise ValueError("The sample adapter only documents the campaign resource.")
        return {
            "data_origin": "sample",
            "resource": "campaign",
            "fields": [{"gaql": gaql, "column": column} for gaql, column in FIELD_MAP.items()],
        }

    return server


def run_gaql(query: str, as_of: date | None = None) -> dict:
    stripped = " ".join(query.strip().rstrip(";").split())
    if FORBIDDEN.search(stripped) or not stripped.lower().startswith("select"):
        raise ValueError("Only read-only GAQL SELECT statements are allowed.")
    match = GAQL.match(stripped)
    if not match:
        raise ValueError("Could not parse that GAQL statement.")
    if match.group("resource").lower() != "campaign":
        raise ValueError("The sample adapter only supports FROM campaign.")

    fields = [item.strip() for item in match.group("select").split(",") if item.strip()]
    columns = []
    for field in fields:
        key = field.lower()
        if key not in FIELD_MAP:
            raise ValueError(f"Unsupported field: {field}")
        columns.append(FIELD_MAP[key])

    rows = [dict(row) for row in campaign_rows()]
    where = match.group("where")
    if where:
        rows = _apply_where(rows, where, as_of or date.today())
    order = match.group("order")
    if order:
        rows = _apply_order(rows, order)
    if match.group("limit"):
        rows = rows[: int(match.group("limit"))]
    projected = [{column: row[column] for column in columns} for row in rows]
    return {
        "data_origin": "sample",
        "customer_id": CUSTOMER_ID,
        "query": stripped,
        "columns": columns,
        "rows": projected,
        "row_count": len(projected),
    }


def _apply_where(rows: list[dict], clause: str, as_of: date) -> list[dict]:
    text = " ".join(clause.split())
    during = re.search(r"segments\.date\s+DURING\s+(LAST_MONTH|LAST_WEEK|THIS_MONTH)", text, re.I)
    if during:
        start, end = _range(during.group(1).upper(), as_of)
        rows = [row for row in rows if start <= date.fromisoformat(row["date"]) <= end]
        text = text[: during.start()] + text[during.end() :]
    equals = re.search(r"campaign\.id\s*=\s*'?(G\d+)'?", text, re.I)
    if equals:
        campaign_id = equals.group(1).upper()
        rows = [row for row in rows if row["campaign_id"] == campaign_id]
    return rows


def _apply_order(rows: list[dict], clause: str) -> list[dict]:
    parts = clause.split()
    field = parts[0].lower()
    if field not in FIELD_MAP:
        raise ValueError(f"Cannot order by {parts[0]}.")
    column = FIELD_MAP[field]
    reverse = len(parts) > 1 and parts[1].upper() == "DESC"

    def key(row: dict):
        value = row[column]
        if column in {"impressions", "clicks", "cost_micros", "conversions"}:
            return int(value)
        if column in {"cost", "conversion_value"}:
            return float(value)
        return value

    return sorted(rows, key=key, reverse=reverse)


def _range(token: str, as_of: date) -> tuple[date, date]:
    if token == "LAST_MONTH":
        year = as_of.year if as_of.month > 1 else as_of.year - 1
        month = as_of.month - 1 if as_of.month > 1 else 12
        start = date(year, month, 1)
        end = date(year, month, calendar.monthrange(year, month)[1])
        return start, end
    if token == "THIS_MONTH":
        start = date(as_of.year, as_of.month, 1)
        return start, as_of
    weeks = sorted({date.fromisoformat(row["date"]) for row in campaign_rows()})
    if weeks:
        return weeks[-1], weeks[-1]
    start = date.fromordinal(as_of.toordinal() - 6)
    return start, as_of
