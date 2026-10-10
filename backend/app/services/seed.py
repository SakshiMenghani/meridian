import logging
from decimal import Decimal
from urllib.parse import quote_plus
from uuid import uuid4

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.connectors.mongo import ensure_mongo_user
from app.identifiers import IDENT, quote_ident
from app.db import SessionLocal
from app.models import DataSource, FieldMapping, utcnow
from app.seed_data.catalog import (
    ADS_SOURCE,
    ANALYTICS_SOURCE,
    CASES_SOURCE,
    COMMERCE_SOURCE,
    CRM_SOURCE,
    CUSTOMERS,
    MAPPINGS,
    ORDERS,
    PRODUCTS,
    REVIEWS,
    SEGMENTS,
)
from app.seed_data.google_ads import CUSTOMER_ID, CUSTOMER_NAME
from app.seed_data.google_analytics import PROPERTY_ID, PROPERTY_NAME
from app.security import encrypt_secret
from app.services.sources import create_spreadsheet_source, test_source

logger = logging.getLogger(__name__)

TABLES = [
    """
    CREATE TABLE customers (
        customer_id text PRIMARY KEY,
        full_name text NOT NULL,
        email text NOT NULL,
        region text NOT NULL,
        city text NOT NULL,
        signed_up_on date NOT NULL
    )
    """,
    """
    CREATE TABLE products (
        product_id text PRIMARY KEY,
        sku text NOT NULL UNIQUE,
        name text NOT NULL,
        category text NOT NULL,
        unit_cost numeric(10, 2) NOT NULL,
        list_price numeric(10, 2) NOT NULL
    )
    """,
    """
    CREATE TABLE orders (
        order_id text PRIMARY KEY,
        customer_id text NOT NULL REFERENCES customers (customer_id),
        ordered_on date NOT NULL,
        status text NOT NULL CHECK (status IN ('fulfilled', 'refunded')),
        channel text NOT NULL
    )
    """,
    """
    CREATE TABLE order_items (
        order_item_id integer PRIMARY KEY,
        order_id text NOT NULL REFERENCES orders (order_id),
        product_id text NOT NULL REFERENCES products (product_id),
        quantity integer NOT NULL CHECK (quantity > 0),
        unit_price numeric(10, 2) NOT NULL
    )
    """,
    """
    CREATE TABLE seed_marker (
        id integer PRIMARY KEY,
        seeded_at timestamptz NOT NULL
    )
    """,
]


def seed_demo_data() -> None:
    settings = get_settings()
    _seed_commerce(settings)
    _assert_postgres_reader(settings)
    _seed_mongo(settings)
    _ensure_import_warehouse(settings)
    _register_sources(settings)
    logger.info("Demo sources are registered.")


def _admin_engine(url):
    return create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})


def _seed_commerce(settings) -> None:
    engine = _admin_engine(settings.commerce_admin_url)
    try:
        with engine.begin() as conn:
            exists = conn.execute(text("SELECT to_regclass('public.seed_marker')")).scalar()
            if exists:
                conn.execute(text("GRANT USAGE ON SCHEMA public TO commerce_reader"))
                conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO commerce_reader"))
                return
            for statement in TABLES:
                conn.execute(text(statement))
            conn.execute(
                text(
                    """
                    INSERT INTO customers (customer_id, full_name, email, region, city, signed_up_on)
                    VALUES (:customer_id, :full_name, :email, :region, :city, :signed_up_on)
                    """
                ),
                [
                    {
                        "customer_id": row[0],
                        "full_name": row[1],
                        "email": row[2],
                        "region": row[3],
                        "city": row[4],
                        "signed_up_on": row[5],
                    }
                    for row in CUSTOMERS
                ],
            )
            conn.execute(
                text(
                    """
                    INSERT INTO products (product_id, sku, name, category, unit_cost, list_price)
                    VALUES (:product_id, :sku, :name, :category, :unit_cost, :list_price)
                    """
                ),
                [
                    {
                        "product_id": row[0],
                        "sku": row[1],
                        "name": row[2],
                        "category": row[3],
                        "unit_cost": row[4],
                        "list_price": row[5],
                    }
                    for row in PRODUCTS
                ],
            )
            conn.execute(
                text(
                    """
                    INSERT INTO orders (order_id, customer_id, ordered_on, status, channel)
                    VALUES (:order_id, :customer_id, :ordered_on, :status, :channel)
                    """
                ),
                [
                    {
                        "order_id": row[0],
                        "customer_id": row[1],
                        "ordered_on": row[2],
                        "status": row[3],
                        "channel": row[4],
                    }
                    for row in ORDERS
                ],
            )
            prices = {row[0]: Decimal(row[5]) for row in PRODUCTS}
            items = []
            item_id = 1
            for order_id, _, _, _, _, lines in ORDERS:
                for product_id, quantity in lines:
                    items.append(
                        {
                            "order_item_id": item_id,
                            "order_id": order_id,
                            "product_id": product_id,
                            "quantity": quantity,
                            "unit_price": prices[product_id],
                        }
                    )
                    item_id += 1
            conn.execute(
                text(
                    """
                    INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price)
                    VALUES (:order_item_id, :order_id, :product_id, :quantity, :unit_price)
                    """
                ),
                items,
            )
            conn.execute(text("INSERT INTO seed_marker (id, seeded_at) VALUES (1, NOW())"))
            conn.execute(text("GRANT USAGE ON SCHEMA public TO commerce_reader"))
            conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO commerce_reader"))
    finally:
        engine.dispose()


def _assert_postgres_reader(settings) -> None:
    url = URL.create(
        "postgresql+psycopg",
        username=settings.demo_pg_username,
        password=settings.demo_pg_password,
        host=settings.demo_pg_host,
        port=settings.demo_pg_port,
        database=settings.demo_pg_database,
    )
    engine = create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            count = int(conn.execute(text("SELECT COUNT(*) FROM customers")).scalar_one())
            if count != len(CUSTOMERS):
                raise RuntimeError(f"Expected {len(CUSTOMERS)} customers, found {count}.")
            try:
                conn.execute(text("CREATE TABLE meridian_probe (id integer)"))
            except Exception as exc:
                conn.rollback()
                message = str(exc).lower()
                if "read-only" in message or "permission denied" in message:
                    return
                raise
            conn.rollback()
            raise RuntimeError("commerce_reader was able to create a table.")
    finally:
        engine.dispose()


def _seed_mongo(settings) -> None:
    ensure_mongo_user(
        settings.mongo_admin_url,
        settings.demo_mongo_database,
        settings.demo_mongo_username,
        settings.demo_mongo_password,
        "read",
    )
    ensure_mongo_user(
        settings.mongo_admin_url,
        settings.demo_mongo_database,
        settings.mongo_writer_username,
        settings.mongo_writer_password,
        "readWrite",
    )
    writer = _mongo_client(
        settings.demo_mongo_host,
        settings.demo_mongo_port,
        settings.demo_mongo_database,
        settings.mongo_writer_username,
        settings.mongo_writer_password,
        settings.demo_mongo_auth_source,
    )
    try:
        database = writer[settings.demo_mongo_database]
        customers = {row[0]: row for row in CUSTOMERS}
        profiles = database.customer_profiles
        reviews = database.product_reviews
        if profiles.count_documents({}, maxTimeMS=8000) == 0:
            profiles.insert_many(
                [
                    {
                        "customer_id": customer_id,
                        "full_name": customers[customer_id][1],
                        "email": customers[customer_id][2],
                        "region": customers[customer_id][3],
                        "city": customers[customer_id][4],
                        "segment": segment,
                        "preferred_channel": channel,
                        "loyalty_points": points,
                    }
                    for customer_id, segment, channel, points in SEGMENTS
                ]
            )
        if reviews.count_documents({}, maxTimeMS=8000) == 0:
            reviews.insert_many(
                [
                    {
                        "review_id": review_id,
                        "customer_id": customer_id,
                        "product_id": product_id,
                        "rating": rating,
                        "title": title,
                        "reviewed_on": reviewed_on,
                    }
                    for review_id, customer_id, product_id, rating, title, reviewed_on in REVIEWS
                ]
            )
        profiles.create_index("customer_id", unique=True)
        reviews.create_index("review_id", unique=True)
    finally:
        writer.close()
    _assert_mongo_reader(settings)


def _assert_mongo_reader(settings) -> None:
    reader = _mongo_client(
        settings.demo_mongo_host,
        settings.demo_mongo_port,
        settings.demo_mongo_database,
        settings.demo_mongo_username,
        settings.demo_mongo_password,
        settings.demo_mongo_auth_source,
    )
    try:
        database = reader[settings.demo_mongo_database]
        count = database.customer_profiles.count_documents({})
        if count != len(CUSTOMERS):
            raise RuntimeError(f"Expected {len(CUSTOMERS)} CRM profiles, found {count}.")
        try:
            database.customer_profiles.insert_one({"customer_id": "PROBE", "probe": True})
        except OperationFailure:
            return
        database.customer_profiles.delete_one({"customer_id": "PROBE"})
        raise RuntimeError("crm_reader was able to write. Refusing to register it.")
    finally:
        reader.close()


def _mongo_client(host: str, port: int, database: str, username: str, password: str, auth_source: str) -> MongoClient:
    uri = (
        f"mongodb://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}"
        f"?authSource={quote_plus(auth_source)}&serverSelectionTimeoutMS=5000"
    )
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        client[database].command("ping")
    except PyMongoError:
        client.close()
        raise
    return client


def _register_sources(settings) -> None:
    db = SessionLocal()
    try:
        _upsert_database(
            db,
            demo_key="commerce",
            name=COMMERCE_SOURCE,
            source_type="postgresql",
            config={
                "host": settings.demo_pg_host,
                "port": settings.demo_pg_port,
                "database": settings.demo_pg_database,
                "username": settings.demo_pg_username,
                "sslmode": "disable",
            },
            secret=settings.demo_pg_password,
        )
        _upsert_database(
            db,
            demo_key="crm",
            name=CRM_SOURCE,
            source_type="mongodb",
            config={
                "host": settings.demo_mongo_host,
                "port": settings.demo_mongo_port,
                "database": settings.demo_mongo_database,
                "username": settings.demo_mongo_username,
                "auth_source": settings.demo_mongo_auth_source,
            },
            secret=settings.demo_mongo_password,
        )
        _upsert_database(
            db,
            demo_key="imports_pg",
            name="Imported PostgreSQL",
            source_type="postgresql",
            config={
                "host": settings.demo_pg_host,
                "port": settings.demo_pg_port,
                "database": settings.import_pg_database,
                "username": settings.import_pg_username,
                "sslmode": "disable",
            },
            secret=settings.import_pg_password,
        )
        _upsert_database(
            db,
            demo_key="imports_mongo",
            name="Imported MongoDB",
            source_type="mongodb",
            config={
                "host": settings.demo_mongo_host,
                "port": settings.demo_mongo_port,
                "database": settings.import_mongo_database,
                "username": settings.import_mongo_username,
                "auth_source": settings.import_mongo_auth_source,
            },
            secret=settings.import_mongo_password,
        )
        cases = settings.seed_data_path / "service_cases.csv"
        existing = _find_demo(db, "service_cases")
        if existing is None:
            created = create_spreadsheet_source(
                db,
                name=CASES_SOURCE,
                path=str(cases.resolve()),
                original_name=cases.name,
                table_name="service_cases",
                origin="sample",
                demo_key="service_cases",
            )
            if created.status != "healthy":
                raise RuntimeError(created.status_message or "Service cases file could not be read.")
        else:
            existing.config = {
                **existing.config,
                "file_path": str(cases.resolve()),
                "original_name": cases.name,
                "table_name": "service_cases",
                "demo_key": "service_cases",
            }
            db.commit()
            test_source(db, existing.id)
        _upsert_ads(db)
        _upsert_analytics(db)
        mapping_count = db.scalar(select(func.count()).select_from(FieldMapping)) or 0
        if mapping_count == 0:
            now = utcnow()
            for left_source, left_object, left_field, right_source, right_object, right_field, description in MAPPINGS:
                db.add(
                    FieldMapping(
                        id=str(uuid4()),
                        left_source_name=left_source,
                        left_object=left_object,
                        left_field=left_field,
                        right_source_name=right_source,
                        right_object=right_object,
                        right_field=right_field,
                        description=description,
                        created_at=now,
                    )
                )
            db.commit()
    finally:
        db.close()


def _ensure_import_warehouse(settings) -> None:
    for name in (
        settings.import_pg_database,
        settings.import_pg_username,
        settings.import_pg_writer_username,
        settings.import_mongo_database,
        settings.import_mongo_username,
        settings.import_mongo_writer_username,
    ):
        if not IDENT.fullmatch(name):
            raise RuntimeError("Import warehouse names must be simple identifiers.")
    engine = _admin_engine(settings.platform_database_url)
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for role, password, readonly in (
                (settings.import_pg_writer_username, settings.import_pg_writer_password, False),
                (settings.import_pg_username, settings.import_pg_password, True),
            ):
                exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}).scalar()
                if not exists:
                    escaped = password.replace("'", "''")
                    conn.execute(text(f"CREATE USER {quote_ident(role)} WITH PASSWORD '{escaped}'"))
                if readonly:
                    conn.execute(text(f"ALTER ROLE {quote_ident(role)} SET default_transaction_read_only = on"))
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": settings.import_pg_database},
            ).scalar()
            if not exists:
                conn.execute(
                    text(
                        f"CREATE DATABASE {quote_ident(settings.import_pg_database)} "
                        f"OWNER {quote_ident(settings.import_pg_writer_username)}"
                    )
                )
    finally:
        engine.dispose()

    imports = _admin_engine(make_url(settings.platform_database_url).set(database=settings.import_pg_database))
    try:
        with imports.begin() as conn:
            conn.execute(text("GRANT USAGE ON SCHEMA public TO " + quote_ident(settings.import_pg_username)))
            conn.execute(text("GRANT CREATE ON SCHEMA public TO " + quote_ident(settings.import_pg_writer_username)))
            conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO " + quote_ident(settings.import_pg_username)))
            conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE "
                    + quote_ident(settings.import_pg_writer_username)
                    + " IN SCHEMA public GRANT SELECT ON TABLES TO "
                    + quote_ident(settings.import_pg_username)
                )
            )
    finally:
        imports.dispose()

    ensure_mongo_user(
        settings.mongo_admin_url,
        settings.import_mongo_database,
        settings.import_mongo_username,
        settings.import_mongo_password,
        "read",
    )
    ensure_mongo_user(
        settings.mongo_admin_url,
        settings.import_mongo_database,
        settings.import_mongo_writer_username,
        settings.import_mongo_writer_password,
        "readWrite",
    )


def _upsert_ads(db) -> None:
    existing = _find_demo(db, "google_ads")
    config = {
        "customer_id": CUSTOMER_ID,
        "customer_name": CUSTOMER_NAME,
        "data_origin": "sample",
        "adapter": "in-process",
        "demo_key": "google_ads",
    }
    if existing is None:
        now = utcnow()
        existing = DataSource(
            id=str(uuid4()),
            name=ADS_SOURCE,
            source_type="google_ads",
            origin="sample",
            enabled=True,
            status="unknown",
            status_message=None,
            config=config,
            secret_ciphertext=None,
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
        db.commit()
    else:
        existing.config = config
        existing.secret_ciphertext = None
        existing.updated_at = utcnow()
        db.commit()
    result = test_source(db, existing.id)
    if not result.ok:
        raise RuntimeError(result.message)


def _upsert_analytics(db) -> None:
    existing = _find_demo(db, "google_analytics")
    config = {
        "property_id": PROPERTY_ID,
        "property_name": PROPERTY_NAME,
        "data_origin": "sample",
        "adapter": "in-process",
        "demo_key": "google_analytics",
    }
    if existing is None:
        now = utcnow()
        existing = DataSource(
            id=str(uuid4()),
            name=ANALYTICS_SOURCE,
            source_type="google_analytics",
            origin="sample",
            enabled=True,
            status="unknown",
            status_message=None,
            config=config,
            secret_ciphertext=None,
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
        db.commit()
    else:
        existing.config = config
        existing.secret_ciphertext = None
        existing.updated_at = utcnow()
        db.commit()
    result = test_source(db, existing.id)
    if not result.ok:
        raise RuntimeError(result.message)


def _find_demo(db, demo_key: str) -> DataSource | None:
    for source in db.scalars(select(DataSource)).all():
        if (source.config or {}).get("demo_key") == demo_key:
            return source
    return None


def _upsert_database(db, *, demo_key: str, name: str, source_type: str, config: dict, secret: str) -> None:
    existing = _find_demo(db, demo_key)
    stored = {**config, "demo_key": demo_key}
    if existing is None:
        now = utcnow()
        existing = DataSource(
            id=str(uuid4()),
            name=name,
            source_type=source_type,
            origin="sample",
            enabled=True,
            status="unknown",
            status_message=None,
            config=stored,
            secret_ciphertext=encrypt_secret(secret, get_settings().app_secret_key),
            created_at=now,
            updated_at=now,
        )
        db.add(existing)
        db.commit()
    else:
        existing.config = stored
        existing.secret_ciphertext = encrypt_secret(secret, get_settings().app_secret_key)
        existing.updated_at = utcnow()
        db.commit()
    result = test_source(db, existing.id)
    if not result.ok:
        raise RuntimeError(result.message)
