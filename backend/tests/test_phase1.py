from decimal import Decimal
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet

from app.connectors.spreadsheet import profile_frame, read_upload
from app.identifiers import quote_ident
from app.schemas import public_config
from app.security import decrypt_secret, encrypt_secret, scrub_text
from app.seed_data.catalog import CUSTOMERS, ORDERS, PRODUCTS


def test_secret_round_trip_and_scrub():
    key = Fernet.generate_key().decode()
    token = encrypt_secret("commerce_reader", key)
    assert token != "commerce_reader"
    assert decrypt_secret(token, key) == "commerce_reader"
    assert "s3cret" not in scrub_text("login failed for s3cret", ["s3cret"])


def test_quote_ident_rejects_injection():
    assert quote_ident("customers") == '"customers"'
    try:
        quote_ident("customers; drop table orders")
    except ValueError:
        return
    raise AssertionError("identifier was accepted")


def test_public_config_hides_internal_keys():
    visible = public_config({"host": "localhost", "file_path": "/tmp/a.csv", "demo_key": "commerce"})
    assert visible == {"host": "localhost"}


def test_purchase_totals_match_the_plan():
    prices = {product_id: Decimal(price) for product_id, *_, price in PRODUCTS}
    totals: dict[str, Decimal] = {}
    september: dict[str, Decimal] = {}
    refunded = []
    for _order_id, customer_id, ordered_on, status, _channel, lines in ORDERS:
        if status == "refunded":
            refunded.append(customer_id)
            continue
        amount = sum(prices[product_id] * quantity for product_id, quantity in lines)
        totals[customer_id] = totals.get(customer_id, Decimal("0")) + amount
        if ordered_on.month == 9 and ordered_on.year == 2026:
            september[customer_id] = september.get(customer_id, Decimal("0")) + amount
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    assert ranked[:5] == [
        ("C009", Decimal("1245.00")),
        ("C002", Decimal("1036.00")),
        ("C005", Decimal("965.00")),
        ("C006", Decimal("277.00")),
        ("C010", Decimal("260.00")),
    ]
    september_ranked = sorted(september.items(), key=lambda item: item[1], reverse=True)
    assert september_ranked[:3] == [
        ("C005", Decimal("544.00")),
        ("C009", Decimal("538.00")),
        ("C002", Decimal("394.00")),
    ]
    assert refunded == ["C012"]
    assert {row[0] for row in CUSTOMERS} >= set(totals)


def test_service_cases_profile_flags_gaps_and_the_duplicate_row():
    path = Path(__file__).resolve().parents[1] / "app" / "seed_data" / "service_cases.csv"
    frame, sheet = read_upload(path.name, path.read_bytes())
    profile = profile_frame(frame, "service_cases", sheet)
    assert profile.duplicate_rows == 1
    missing = {column.name: column.missing for column in profile.columns}
    assert missing["channel"] == 1
    assert missing["status"] == 1
    opened = next(column for column in profile.columns if column.name == "opened_date")
    assert opened.inferred_type == "date"
    assert "CREATE TABLE" in profile.suggested_ddl
    assert profile.row_count == 15


def test_transform_drops_duplicates_and_blank_rows():
    from app.schemas import ColumnTransform, TransformRequest
    from app.services.transform import apply_transform

    frame = pd.DataFrame(
        {
            "Loan Type": ["Auto", "Auto", "Dental", "Home"],
            "Total Applications": [4, 4, 1, None],
        }
    )
    cleaned, dupes, emptied = apply_transform(
        frame,
        TransformRequest(
            drop_duplicates=True,
            missing="drop_rows",
            columns=[
                ColumnTransform(name="Loan Type", suggested_name="loan_type", inferred_type="text"),
                ColumnTransform(name="Total Applications", suggested_name="total_applications", inferred_type="bigint"),
            ],
        ),
    )
    assert dupes == 1
    assert emptied == 1
    assert list(cleaned.columns) == ["loan_type", "total_applications"]
    assert list(cleaned["loan_type"].astype(str)) == ["Auto", "Dental"]
    assert [int(value) for value in cleaned["total_applications"]] == [4, 1]


def test_import_requires_confirmation():
    from app.schemas import ImportRequest
    from app.services.transform import import_transform

    try:
        import_transform(
            None,  # type: ignore[arg-type]
            "unused",
            ImportRequest(confirm=False, destination="spreadsheet"),
        )
    except ValueError as exc:
        assert "Confirm" in str(exc)
        return
    raise AssertionError("import ran without confirmation")


def test_loan_question_plans_a_ranked_select():
    from app.services.ask import LoadedTable, plan_sql

    tables = [
        LoadedTable(
            sql_name="loan_chart",
            source_name="Loan file",
            object_name="loan_chart",
            columns=[("loan_type", "text"), ("total_applications", "bigint")],
            frame=pd.DataFrame(),
        )
    ]
    sql = plan_sql("Which loan type had the most applications?", tables)
    assert "ORDER BY" in sql
    assert "total_applications" in sql
    assert "DESC" in sql


def test_blank_header_is_rejected():
    frame = pd.DataFrame({"customer_id": ["C001"], "": ["x"]})
    try:
        profile_frame(frame, "broken")
    except ValueError as exc:
        assert "header" in str(exc).lower()
        return
    raise AssertionError("blank header was accepted")
