from datetime import date

import pandas as pd

from app.agent.embeddings import HashEmbedder
from app.mcp.client_manager import McpClientManager
from app.mcp.servers.google_ads import run_gaql
from app.seed_data.google_ads import CUSTOMER_ID, SAMPLE_AS_OF
from app.services.ask import LoadedTable, plan_sql


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


def test_text_to_sql_embeddings_link_opened_ads_to_clicks():
    from app.agent.embeddings import HashEmbedder
    from app.agent.text_to_sql import link_question
    from app.services.ask import LoadedTable

    tables = [
        LoadedTable(
            sql_name="go_campaigns",
            source_name="Google Ads (sample)",
            object_name="campaigns",
            columns=[
                ("campaign_id", "text"),
                ("campaign_name", "text"),
                ("campaign_type", "text"),
                ("date", "date"),
                ("impressions", "bigint"),
                ("clicks", "bigint"),
            ],
            frame=pd.DataFrame(),
        )
    ]
    link = link_question("Which advertisement was opened the most?", tables, HashEmbedder())
    assert link.intent == "rank_high"
    assert link.measure == "clicks"
    assert link.dimension == "campaign_name"
    assert link.sql is not None
    assert "SUM" in link.sql
    assert "campaign_name" in link.sql
    assert "campaign_id" not in link.sql
    assert "Clicks count" in link.gloss


def test_text_to_sql_does_not_group_a_campaign_question_by_date():
    from app.agent.text_to_sql import link_question
    from app.services.ask import LoadedTable

    class DateBiased:
        name = "BAAI/bge-small-en-v1.5"

        def embed(self, texts: list[str]) -> list[list[float]]:
            vectors = []
            for text in texts:
                if "Column date" in text:
                    vectors.append([1.0, 0.0])
                elif "Column clicks" in text:
                    vectors.append([0.8, 0.2])
                elif "Column campaign_name" in text:
                    vectors.append([0.4, 0.1])
                elif text.startswith("Which"):
                    vectors.append([1.0, 0.0])
                else:
                    vectors.append([0.0, 1.0])
            return vectors

    tables = [
        LoadedTable(
            sql_name="go_campaigns",
            source_name="Google Ads (sample)",
            object_name="campaigns",
            columns=[
                ("campaign_name", "text"),
                ("date", "date"),
                ("clicks", "bigint"),
            ],
            frame=pd.DataFrame(),
        )
    ]
    link = link_question("Which advertisement was opened the most last month?", tables, DateBiased())
    assert link.dimension == "campaign_name"
    assert link.measure == "clicks"
    assert 'GROUP BY "campaign_name"' in (link.sql or "")


def test_ridge_apparel_clicks_sum_and_last_week_filter():
    from app.agent.text_to_sql import link_question
    from app.services.ask import LoadedTable

    frame = pd.DataFrame(
        [
            {"campaign_name": "Ridge Apparel", "date": "2026-09-14", "clicks": 70, "impressions": 6100},
            {"campaign_name": "Ridge Apparel", "date": "2026-09-21", "clicks": 85, "impressions": 5400},
            {"campaign_name": "Summer Trail Push", "date": "2026-09-21", "clicks": 110, "impressions": 9800},
        ]
    )
    tables = [
        LoadedTable(
            sql_name="go_campaigns",
            source_name="Google Ads (sample)",
            object_name="campaigns",
            columns=[
                ("campaign_name", "text"),
                ("date", "date"),
                ("clicks", "bigint"),
                ("impressions", "bigint"),
            ],
            frame=frame,
        )
    ]
    total = link_question("tell me how many clicks we received for Ridge Apparel", tables, HashEmbedder())
    assert total.intent == "sum"
    assert total.measure == "clicks"
    assert total.filters == [("campaign_name", "Ridge Apparel")]
    assert "SUM" in (total.sql or "")
    assert "Ridge Apparel" in (total.sql or "")
    assert "COUNT" not in (total.sql or "")

    week = link_question(
        "tell me how many clicks we received for Ridge Apparel in last week",
        tables,
        HashEmbedder(),
    )
    assert week.intent == "sum"
    assert "2026-09-21" in (week.sql or "")


def test_analysis_question_is_not_treated_as_a_schema_overview():
    from app.services.ask import _is_analysis, _is_overview, analyze_tables

    assert _is_analysis("what kind of overall analysis that data is giving?")
    assert not _is_overview("what kind of overall analysis that data is giving?")
    frame = pd.DataFrame(
        [
            {
                "campaign_name": "Summer Trail Push",
                "campaign_id": "G001",
                "campaign_type": "SEARCH",
                "date": "2026-08-03",
                "impressions": 8200,
                "clicks": 210,
            },
            {
                "campaign_name": "Weekend Pack Promo",
                "campaign_id": "G004",
                "campaign_type": "DISPLAY",
                "date": "2026-08-03",
                "impressions": 6900,
                "clicks": 70,
            },
        ]
    )
    tables = [
        LoadedTable(
            sql_name="go_campaigns",
            source_name="Google Ads (sample)",
            object_name="campaigns",
            columns=[
                ("campaign_name", "text"),
                ("campaign_id", "text"),
                ("campaign_type", "text"),
                ("date", "date"),
                ("impressions", "bigint"),
                ("clicks", "bigint"),
            ],
            frame=frame,
        )
    ]
    answer, _points, _sql, _columns, _rows = analyze_tables(tables)
    assert "click-through rate" in answer
    assert "Summer Trail Push" in answer
    assert "sample data" in answer


def test_overview_question_explains_campaigns_instead_of_ranking_weeks():
    from app.services.ask import LoadedTable, _is_overview, describe_tables

    frame = pd.DataFrame(
        [
            {
                "campaign_id": "G001",
                "campaign_name": "Summer Trail Push",
                "campaign_type": "SEARCH",
                "date": "2026-09-14",
                "impressions": 11000,
                "clicks": 160,
            },
            {
                "campaign_id": "G001",
                "campaign_name": "Summer Trail Push",
                "campaign_type": "SEARCH",
                "date": "2026-08-03",
                "impressions": 8200,
                "clicks": 210,
            },
            {
                "campaign_id": "G004",
                "campaign_name": "Weekend Pack Promo",
                "campaign_type": "DISPLAY",
                "date": "2026-09-14",
                "impressions": 7300,
                "clicks": 45,
            },
        ]
    )
    tables = [
        LoadedTable(
            sql_name="go_campaigns",
            source_name="Google Ads (sample)",
            object_name="campaigns",
            columns=[
                ("campaign_id", "text"),
                ("campaign_name", "text"),
                ("campaign_type", "text"),
                ("date", "date"),
                ("impressions", "bigint"),
                ("clicks", "bigint"),
            ],
            frame=frame,
        )
    ]
    assert _is_overview("can you tell me what is this data about?")
    answer, points, _sql, _columns, rows = describe_tables(tables)
    assert "weekly Google Ads" in answer
    assert "campaign ids" in answer
    assert "August 3, 2026" in answer
    assert "September 14, 2026" in answer
    assert any("Summer Trail Push (G001" in point for point in points)
    assert rows[0]["campaign_name"] != "11,000"
    assert {row["campaign_id"] for row in rows} == {"G001", "G004"}


def test_ads_question_plans_a_campaign_rollup():
    tables = [
        LoadedTable(
            sql_name="go_campaigns",
            source_name="Google Ads (sample)",
            object_name="campaigns",
            columns=[("campaign_name", "text"), ("clicks", "bigint"), ("date", "date")],
            frame=pd.DataFrame(),
        )
    ]
    sql = plan_sql("Which campaign had the most clicks last month?", tables)
    assert "GROUP BY" in sql
    assert "campaign_name" in sql
    assert "clicks" in sql
    assert "campaign_id" not in sql
