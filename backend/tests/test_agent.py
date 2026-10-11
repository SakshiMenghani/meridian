from datetime import date

import pandas as pd
import pytest

from app.agent import graph as graph_module
from app.agent import planner as planner_module
from app.agent.embeddings import HashEmbedder
from app.agent.graph import choose_chart, run_agent
from app.agent.guard import Link, SqlRejected, check_sql, run_sql
from app.agent.text_to_sql import link_question
from app.agent.workspace import LoadedTable, coerce_frame, frame_columns
from app.seed_data.catalog import CRM_SOURCE, COMMERCE_SOURCE, CUSTOMERS, ORDERS, PRODUCTS, SEGMENTS
from app.seed_data.google_analytics import traffic_rows

TODAY = date(2026, 10, 11)


def _table(sql_name: str, source: str, rows: list[dict], source_id: str = "") -> LoadedTable:
    frame = coerce_frame(pd.DataFrame(rows))
    return LoadedTable(
        sql_name=sql_name,
        source_name=source,
        object_name=sql_name.split("_", 1)[1],
        columns=frame_columns(frame),
        frame=frame,
        source_id=source_id or source,
    )


@pytest.fixture()
def northline() -> list[LoadedTable]:
    prices = {product[0]: float(product[5]) for product in PRODUCTS}
    customers = [
        {"customer_id": c[0], "full_name": c[1], "email": c[2], "region": c[3], "city": c[4], "joined_on": c[5].isoformat()}
        for c in CUSTOMERS
    ]
    orders = [
        {"order_id": o[0], "customer_id": o[1], "ordered_on": o[2].isoformat(), "status": o[3], "channel": o[4]}
        for o in ORDERS
    ]
    items = [
        {"order_id": o[0], "product_id": product, "quantity": quantity, "unit_price": prices[product]}
        for o in ORDERS
        for product, quantity in o[5]
    ]
    profiles = [
        {"customer_id": s[0], "segment": s[1], "preferred_channel": s[2], "loyalty_points": s[3]} for s in SEGMENTS
    ]
    return [
        _table("po_customers", COMMERCE_SOURCE, customers),
        _table("po_orders", COMMERCE_SOURCE, orders),
        _table("po_order_items", COMMERCE_SOURCE, items),
        _table("mo_customer_profiles", CRM_SOURCE, profiles),
        _table("go_traffic", "Google Analytics (sample)", traffic_rows()),
    ]


CRM_LINK = Link("po_customers", "customer_id", "mo_customer_profiles", "customer_id")


# ---------- guard ----------


def test_guard_rejects_writes_and_multiple_statements(northline):
    for sql in ("DELETE FROM po_orders", "SELECT 1; SELECT 2", "CREATE TABLE x AS SELECT 1", "COPY po_orders TO 'x.csv'"):
        with pytest.raises(SqlRejected):
            check_sql(sql, northline, [])


def test_guard_rejects_table_functions_and_unknown_tables(northline):
    with pytest.raises(SqlRejected, match="Table functions"):
        check_sql("SELECT * FROM read_csv('/etc/passwd')", northline, [])
    with pytest.raises(SqlRejected, match="Unknown table"):
        check_sql("SELECT * FROM secrets", northline, [])


def test_guard_rejects_cross_source_join_without_confirmed_link(northline):
    sql = (
        'SELECT p.segment, COUNT(*) FROM "po_customers" c '
        'JOIN "mo_customer_profiles" p ON c.customer_id = p.customer_id GROUP BY 1'
    )
    with pytest.raises(SqlRejected, match="confirmed link"):
        check_sql(sql, northline, [])
    with pytest.raises(SqlRejected, match="confirmed link"):
        check_sql('SELECT * FROM "po_customers", "mo_customer_profiles"', northline, [CRM_LINK])
    with pytest.raises(SqlRejected, match="confirmed link"):
        check_sql(
            'SELECT * FROM "po_customers" c JOIN "mo_customer_profiles" p ON c.full_name = p.segment', northline, [CRM_LINK]
        )
    with pytest.raises(SqlRejected, match="confirmed link"):
        check_sql(
            'SELECT * FROM "po_customers" c JOIN "mo_customer_profiles" p ON c.customer_id = p.customer_id OR 1 = 1',
            northline,
            [CRM_LINK],
        )


def test_guard_accepts_confirmed_link_join_and_in_subquery(northline):
    joined = check_sql(
        'SELECT p.segment, COUNT(*) AS n FROM "po_customers" c '
        'JOIN "mo_customer_profiles" p ON c.customer_id = p.customer_id GROUP BY 1',
        northline,
        [CRM_LINK],
    )
    assert joined.links_used == [CRM_LINK]
    semi = check_sql(
        'SELECT full_name FROM "po_customers" WHERE "po_customers"."customer_id" IN '
        '(SELECT "mo_customer_profiles"."customer_id" FROM "mo_customer_profiles" WHERE segment = \'vip\')',
        northline,
        [CRM_LINK],
    )
    assert semi.links_used == [CRM_LINK]
    with pytest.raises(SqlRejected, match="confirmed link"):
        check_sql(
            'SELECT full_name FROM "po_customers" WHERE "po_customers"."customer_id" IN '
            '(SELECT "mo_customer_profiles"."customer_id" FROM "mo_customer_profiles")',
            northline,
            [],
        )


def test_guard_allows_same_source_joins_and_ctes(northline):
    checked = check_sql(
        'WITH spend AS (SELECT o.customer_id, SUM(i.quantity * i.unit_price) AS total FROM "po_orders" o '
        'JOIN "po_order_items" i ON o.order_id = i.order_id GROUP BY 1) '
        'SELECT c.full_name, s.total FROM spend s JOIN "po_customers" c ON c.customer_id = s.customer_id',
        northline,
        [],
    )
    assert set(checked.tables) == {"po_orders", "po_order_items", "po_customers"}


def test_run_sql_is_locked_down(northline):
    with pytest.raises(SqlRejected):
        run_sql("SELECT * FROM read_csv('/etc/hosts')", northline)
    rows, columns, truncated = run_sql('SELECT * FROM "po_orders"', northline, max_rows=5)
    assert len(rows) == 5 and truncated and "ordered_on" in columns
    assert rows[0]["ordered_on"] == "2026-08-03"


# ---------- end to end with a scripted planner ----------


class ScriptedLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, system, payload, temperature=0):
        self.calls.append(payload)
        if "previous_attempts" not in payload and "results" in payload:
            return None
        return self.responses.pop(0) if self.responses else None


def _ask(monkeypatch, tables, plans, question, links=(), as_report=False):
    fake = ScriptedLLM(*plans)
    monkeypatch.setattr(planner_module, "chat_json", fake)
    monkeypatch.setattr(graph_module, "llm_available", lambda: True)
    monkeypatch.setattr(planner_module, "model_name", lambda: "fake-planner")
    monkeypatch.setattr(graph_module.writer, "chat_json", lambda *args, **kwargs: None)
    state = run_agent(question, tables, list(links), as_report=as_report, embedder=HashEmbedder(), today=TODAY)
    return state, fake


def _query(sql, chart=None, title="Result"):
    return {"action": "query", "title": title, "assumptions": [], "queries": [{"title": title, "purpose": "", "sql": sql, "chart": chart}]}


def test_refunded_orders_counts_orders_not_line_items(monkeypatch, northline):
    state, fake = _ask(
        monkeypatch,
        northline,
        [_query("SELECT COUNT(*) AS refunded_orders FROM \"po_orders\" WHERE \"status\" = 'refunded'")],
        "How many orders were refunded?",
    )
    assert state["status"] == "ok"
    assert state["sections"][0]["rows"] == [{"refunded_orders": 1}]
    assert "refunded" in str(fake.calls[0]["tables"])


def test_september_top_customers_by_purchases(monkeypatch, northline):
    sql = (
        'SELECT c."full_name", SUM(i."quantity" * i."unit_price") AS purchases FROM "po_orders" o '
        'JOIN "po_order_items" i ON o."order_id" = i."order_id" JOIN "po_customers" c ON c."customer_id" = o."customer_id" '
        "WHERE o.\"ordered_on\" >= DATE '2026-09-01' AND o.\"ordered_on\" < DATE '2026-10-01' "
        "GROUP BY 1 ORDER BY purchases DESC LIMIT 3"
    )
    state, _ = _ask(monkeypatch, northline, [_query(sql, {"type": "bar", "category": "full_name", "value": "purchases"})], "Top 3 customers in September?")
    rows = state["sections"][0]["rows"]
    assert [(row["full_name"], row["purchases"]) for row in rows] == [
        ("Elena Vasquez", 544.0),
        ("Sofia Rossi", 538.0),
        ("Andre Wallace", 394.0),
    ]
    assert state["sections"][0]["chart"]["type"] == "bar"
    assert "Elena Vasquez" in state["answer"]


def test_vip_customers_across_sources_with_confirmed_link(monkeypatch, northline):
    sql = (
        'SELECT c."full_name" FROM "po_customers" c JOIN "mo_customer_profiles" p '
        "ON c.\"customer_id\" = p.\"customer_id\" WHERE p.\"segment\" = 'vip' ORDER BY 1"
    )
    state, _ = _ask(monkeypatch, northline, [_query(sql)], "Who are our VIP customers?", links=[CRM_LINK])
    assert [row["full_name"] for row in state["sections"][0]["rows"]] == ["Andre Wallace", "Elena Vasquez", "Sofia Rossi"]
    assert any("Joined on" in step["detail"] for step in state["steps"])


def test_cross_source_join_returns_every_crm_customer(monkeypatch, northline):
    sql = (
        'SELECT COUNT(DISTINCT p."customer_id") AS customers FROM "mo_customer_profiles" p '
        'JOIN "po_customers" c ON c."customer_id" = p."customer_id" JOIN "po_orders" o ON o."customer_id" = c."customer_id"'
    )
    state, _ = _ask(monkeypatch, northline, [_query(sql)], "How many CRM customers have orders?", links=[CRM_LINK])
    assert state["sections"][0]["rows"] == [{"customers": 12}]


def test_unlinked_join_is_retried_with_the_error(monkeypatch, northline):
    bad = _query(
        'SELECT p."segment", COUNT(*) AS n FROM "po_customers" c JOIN "mo_customer_profiles" p ON c."customer_id" = p."customer_id" GROUP BY 1'
    )
    clarify = {
        "action": "clarify",
        "title": "Link needed",
        "clarify": {"question": "Should customers be matched by customer_id?", "options": ["Yes, link customer_id", "No"]},
    }
    state, fake = _ask(monkeypatch, northline, [bad, clarify], "Customers by segment")
    assert state["status"] == "needs_clarification"
    assert "confirmed link" in fake.calls[1]["previous_attempts"][0]["error"]
    assert state["plan"].options == ["Yes, link customer_id", "No"]


def test_report_mode_returns_several_charted_sections(monkeypatch, northline):
    plan = {
        "action": "report",
        "title": "Traffic report",
        "assumptions": ["Covers every week in the data."],
        "queries": [
            {
                "title": "Sessions by channel",
                "purpose": "Share of visits.",
                "sql": 'SELECT "channel", SUM("sessions") AS sessions FROM "go_traffic" GROUP BY 1 ORDER BY 2 DESC',
                "chart": {"type": "pie", "category": "channel", "value": "sessions"},
            },
            {
                "title": "Sessions over time",
                "purpose": "Weekly trend.",
                "sql": 'SELECT "date", SUM("sessions") AS sessions FROM "go_traffic" GROUP BY 1 ORDER BY 1',
                "chart": {"type": "line", "category": "date", "value": "sessions"},
            },
        ],
    }
    state, _ = _ask(monkeypatch, northline, [plan], "Traffic report", as_report=True)
    first, second = state["sections"]
    assert first["rows"][0] == {"channel": "Organic Search", "sessions": 5265}
    assert first["chart"]["type"] == "pie" and second["chart"]["type"] == "line"


def test_writer_numbers_are_checked(monkeypatch, northline):
    from app.agent import answer

    sections = [{"title": "Refunds", "columns": ["n"], "rows": [{"n": 1}], "truncated": False}]
    monkeypatch.setattr(answer, "chat_json", lambda *a, **k: {"answer": "There were 43 refunds.", "points": []})
    text, _, model = answer.polish("How many refunds?", [], sections, "N: 1.", [])
    assert text == "N: 1." and model is None
    monkeypatch.setattr(answer, "chat_json", lambda *a, **k: {"answer": "One order, 1 in total, was refunded.", "points": []})
    text, _, _ = answer.polish("How many refunds?", [], sections, "N: 1.", [])
    assert "1 in total" in text


def test_pie_falls_back_to_bar_when_too_many_parts():
    rows = [{"name": f"n{i}", "value": i} for i in range(12)]
    assert choose_chart({"type": "pie", "category": "name", "value": "value"}, ["name", "value"], rows)["type"] == "bar"
    dated = [{"date": "2026-09-0" + str(i), "v": i} for i in range(1, 5)]
    assert choose_chart(None, ["date", "v"], dated)["type"] == "line"


# ---------- offline planner ----------


def test_offline_linker_matches_whole_words_only(northline):
    link = link_question("Which customers stored the most items?", northline, HashEmbedder(), today=TODAY)
    assert ("channel", "store") not in (link.filters or [])


def test_offline_linker_understands_named_months(northline):
    orders = [table for table in northline if table.sql_name == "po_orders"]
    link = link_question("How many orders in September?", orders, HashEmbedder(), today=TODAY)
    assert "DATE '2026-09-01'" in link.sql and "DATE '2026-10-01'" in link.sql
    rows, _, _ = run_sql(link.sql, orders)
    assert rows == [{"row_count": 15}]


def test_offline_flow_without_openai(monkeypatch, northline):
    monkeypatch.setattr(graph_module, "llm_available", lambda: False)
    monkeypatch.setattr(graph_module.writer, "chat_json", lambda *args, **kwargs: None)
    state = run_agent("What is in this data?", northline, [], as_report=False, embedder=HashEmbedder(), today=TODAY)
    assert state["status"] == "ok" and state["plan"].action == "describe"
    assert "5 tables" in state["answer"]
    report = run_agent("Make a report", northline, [], as_report=True, embedder=HashEmbedder(), today=TODAY)
    assert report["plan"].action == "report"
    assert {section["chart"]["type"] for section in report["sections"]} >= {"pie", "bar"}
