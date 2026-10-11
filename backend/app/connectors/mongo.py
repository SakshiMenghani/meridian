import re
from urllib.parse import quote_plus

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from app.connectors.base import ResolvedSource
from app.errors import ConnectorError
from app.schemas import CatalogObject, ColumnInfo, SampleResult
from app.security import json_safe

COLLECTION = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def uses_srv(config: dict) -> bool:
    if config.get("srv") is not None:
        return bool(config["srv"])
    return str(config.get("host", "")).lower().endswith(".mongodb.net")


def mongo_uri(source: ResolvedSource) -> str:
    username = quote_plus(source.config["username"])
    password = quote_plus(source.secret or "")
    host = source.config["host"]
    database = quote_plus(source.config["database"])
    auth_source = quote_plus(source.config.get("auth_source") or source.config["database"])
    if uses_srv(source.config):
        return (
            f"mongodb+srv://{username}:{password}@{host}/{database}"
            f"?authSource={auth_source}&retryWrites=true&serverSelectionTimeoutMS=10000"
        )
    port = int(source.config["port"])
    return (
        f"mongodb://{username}:{password}@{host}:{port}/{database}"
        f"?authSource={auth_source}&serverSelectionTimeoutMS=5000"
    )


def _client(source: ResolvedSource) -> MongoClient:
    timeout = 10000 if uses_srv(source.config) else 5000
    return MongoClient(mongo_uri(source), serverSelectionTimeoutMS=timeout)


def _explain(exc: PyMongoError, config: dict) -> str:
    message = str(exc)
    host = config.get("host", "")
    if "nodename nor servname" in message or "Name or service not known" in message or "DNS" in message:
        if uses_srv(config):
            return f"Could not resolve the Atlas cluster {host}. Check the cluster address and that this machine has internet access."
        return f"Could not find host {host}. For MongoDB Atlas, turn on the SRV option and use the cluster address."
    if "Authentication failed" in message or "bad auth" in message:
        return "MongoDB rejected the username or password. For Atlas users, the auth database is usually admin."
    if uses_srv(config) and ("timed out" in message or "SSL" in message or "TLS" in message):
        return (
            f"Timed out reaching {host}. In Atlas, open Network Access and allow this machine's IP address."
        )
    return message


class MongoConnector:
    source_type = "mongodb"

    def test(self, source: ResolvedSource) -> str:
        client = _client(source)
        try:
            database = client[source.config["database"]]
            database.command("ping")
            database.list_collection_names()
            return f"Connected to {source.config['database']} on {source.config['host']}."
        except PyMongoError as exc:
            raise ConnectorError(_explain(exc, source.config)) from exc
        finally:
            client.close()

    def catalog(self, source: ResolvedSource) -> list[CatalogObject]:
        client = _client(source)
        try:
            database = client[source.config["database"]]
            names = sorted(name for name in database.list_collection_names() if not name.startswith("system."))
            objects: list[CatalogObject] = []
            for name in names[:200]:
                sample = database[name].find_one(max_time_ms=8000)
                columns = []
                if sample:
                    for key, value in sample.items():
                        if key == "_id":
                            continue
                        columns.append(
                            ColumnInfo(name=str(key), data_type=type(value).__name__, nullable=True)
                        )
                try:
                    row_count = int(database[name].count_documents({}, maxTimeMS=8000))
                except PyMongoError:
                    row_count = int(database[name].estimated_document_count())
                objects.append(
                    CatalogObject(
                        schema_name=source.config["database"],
                        name=name,
                        kind="collection",
                        row_count=row_count,
                        note="Fields are inferred from one document and may be incomplete.",
                        columns=columns,
                    )
                )
            return objects
        except PyMongoError as exc:
            raise ConnectorError(_explain(exc, source.config)) from exc
        finally:
            client.close()

    def sample(
        self,
        source: ResolvedSource,
        schema_name: str | None,
        object_name: str,
        limit: int,
    ) -> SampleResult:
        if not COLLECTION.fullmatch(object_name) or object_name.startswith("system."):
            raise ConnectorError("Invalid collection name.")
        client = _client(source)
        try:
            cursor = (
                client[source.config["database"]][object_name]
                .find({}, {"_id": 0})
                .limit(limit + 1)
                .max_time_ms(8000)
            )
            fetched = [json_safe(document) for document in cursor]
            truncated = len(fetched) > limit
            rows = fetched[:limit]
            columns: list[str] = []
            for row in rows:
                for key in row:
                    if key not in columns:
                        columns.append(key)
            return SampleResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)
        except PyMongoError as exc:
            raise ConnectorError(_explain(exc, source.config)) from exc
        finally:
            client.close()


def ensure_mongo_user(admin_url: str, database: str, username: str, password: str, role: str) -> None:
    client = MongoClient(admin_url, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        try:
            client[database].command(
                "createUser",
                username,
                pwd=password,
                roles=[{"role": role, "db": database}],
            )
        except OperationFailure as exc:
            if "already exists" not in str(exc).lower():
                raise
    finally:
        client.close()
