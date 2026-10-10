from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from app.connectors.base import ResolvedSource
from app.errors import ConnectorError
from app.identifiers import quote_ident
from app.schemas import CatalogObject, ColumnInfo, SampleResult
from app.security import json_safe

SYSTEM_SCHEMAS = {"pg_catalog", "information_schema"}


def open_engine(source: ResolvedSource):
    url = URL.create(
        "postgresql+psycopg",
        username=source.config["username"],
        password=source.secret or "",
        host=source.config["host"],
        port=int(source.config["port"]),
        database=source.config["database"],
    )
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": 5,
            "sslmode": source.config.get("sslmode", "disable"),
            "options": "-c statement_timeout=8000 -c default_transaction_read_only=on",
        },
    )


class PostgresConnector:
    source_type = "postgresql"

    def test(self, source: ResolvedSource) -> str:
        engine = open_engine(source)
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("SELECT 1"))
            return f"Connected to {source.config['database']} on {source.config['host']}."
        except Exception as exc:
            raise ConnectorError(str(exc)) from exc
        finally:
            engine.dispose()

    def catalog(self, source: ResolvedSource) -> list[CatalogObject]:
        engine = open_engine(source)
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT table_schema, table_name, table_type
                        FROM information_schema.tables
                        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                          AND table_type IN ('BASE TABLE', 'VIEW')
                        ORDER BY table_schema, table_name
                        LIMIT 200
                        """
                    )
                ).all()
                objects: list[CatalogObject] = []
                count_rows = len(rows) <= 40
                for schema_name, table_name, table_type in rows:
                    if table_name == "seed_marker":
                        continue
                    columns = [
                        ColumnInfo(
                            name=column_name,
                            data_type=data_type,
                            nullable=nullable == "YES",
                        )
                        for column_name, data_type, nullable in conn.execute(
                            text(
                                """
                                SELECT column_name, data_type, is_nullable
                                FROM information_schema.columns
                                WHERE table_schema = :schema AND table_name = :table
                                ORDER BY ordinal_position
                                """
                            ),
                            {"schema": schema_name, "table": table_name},
                        )
                    ]
                    row_count = None
                    if count_rows:
                        try:
                            qualified = f"{quote_ident(schema_name)}.{quote_ident(table_name)}"
                            row_count = int(conn.execute(text(f"SELECT COUNT(*) FROM {qualified}")).scalar_one())
                        except Exception:
                            row_count = None
                    objects.append(
                        CatalogObject(
                            schema_name=schema_name,
                            name=table_name,
                            kind="view" if table_type == "VIEW" else "table",
                            row_count=row_count,
                            columns=columns,
                        )
                    )
                return objects
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(str(exc)) from exc
        finally:
            engine.dispose()

    def sample(
        self,
        source: ResolvedSource,
        schema_name: str | None,
        object_name: str,
        limit: int,
    ) -> SampleResult:
        if not schema_name or schema_name in SYSTEM_SCHEMAS or schema_name.startswith("pg_"):
            raise ConnectorError("Choose an application schema.")
        qualified = f"{quote_ident(schema_name)}.{quote_ident(object_name)}"
        engine = open_engine(source)
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                result = conn.execute(text(f"SELECT * FROM {qualified} LIMIT :limit"), {"limit": limit + 1})
                keys = list(result.keys())
                fetched = [dict(zip(keys, row, strict=True)) for row in result]
            truncated = len(fetched) > limit
            rows = [{key: json_safe(value) for key, value in row.items()} for row in fetched[:limit]]
            return SampleResult(columns=keys, rows=rows, row_count=len(rows), truncated=truncated)
        except ConnectorError:
            raise
        except ValueError as exc:
            raise ConnectorError(str(exc)) from exc
        except Exception as exc:
            raise ConnectorError(str(exc)) from exc
        finally:
            engine.dispose()
