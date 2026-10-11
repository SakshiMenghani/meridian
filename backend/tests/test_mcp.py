from datetime import date

from app.mcp.client_manager import McpClientManager
from app.mcp.servers.google_ads import run_gaql
from app.seed_data.google_ads import CUSTOMER_ID, SAMPLE_AS_OF


def test_mcp_lists_allowlisted_tools():
    manager = McpClientManager()
    names = {tool["name"] for tool in manager.list_tools()}
    assert names == {
        "postgres.catalog",
        "postgres.sample",
        "mongo.catalog",
        "mongo.sample",
        "spreadsheet.catalog",
        "spreadsheet.sample",
        "google-ads.list_accessible_customers",
        "google-ads.search",
        "google-ads.get_resource_metadata",
        "analytics.catalog",
        "analytics.sample",
    }
    official = next(server for server in manager.servers() if server["transport"] == "stdio")
    assert official["enabled"] is False
    assert official["data_origin"] == "live"


def test_google_ads_search_last_month_ranks_summer_trail_push():
    result = run_gaql(
        "SELECT campaign.name, metrics.clicks FROM campaign "
        "WHERE segments.date DURING LAST_MONTH ORDER BY metrics.clicks DESC",
        as_of=SAMPLE_AS_OF,
    )
    assert result["data_origin"] == "sample"
    assert result["row_count"] == 12
    totals: dict[str, int] = {}
    for row in result["rows"]:
        totals[row["campaign_name"]] = totals.get(row["campaign_name"], 0) + int(row["clicks"])
    assert totals["Summer Trail Push"] == 410
    assert max(totals, key=totals.get) == "Summer Trail Push"


def test_google_ads_search_via_mcp_client():
    manager = McpClientManager()
    customers = manager.call("google-ads.list_accessible_customers", {})
    assert customers["customers"][0]["id"] == CUSTOMER_ID
    result = manager.call(
        "google-ads.search",
        {
            "customer_id": CUSTOMER_ID,
            "query": (
                "SELECT campaign.name, metrics.clicks FROM campaign "
                "WHERE segments.date DURING LAST_MONTH"
            ),
        },
    )
    assert result["data_origin"] == "sample"
    assert result["row_count"] == 12


def test_google_ads_rejects_writes_and_unknown_tools():
    try:
        run_gaql("UPDATE campaign SET name = 'x'", as_of=date(2026, 10, 10))
    except ValueError as exc:
        assert "read-only" in str(exc).lower() or "select" in str(exc).lower()
    else:
        raise AssertionError("write GAQL was accepted")
    manager = McpClientManager()
    try:
        manager.call("google-ads.mutate", {"customer_id": CUSTOMER_ID})
    except ValueError as exc:
        assert "allowlist" in str(exc).lower()
        return
    raise AssertionError("mutate was allowed")
