from typing import Any, Callable

from app.connectors.base import ResolvedSource
from app.mcp.payload import _run, result_payload, tool_summaries
from app.mcp.servers.google_ads import build_google_ads_server
from app.mcp.servers.source_tools import build_source_server

TYPE_TO_NAMESPACE = {
    "postgresql": "postgres",
    "mongodb": "mongo",
    "spreadsheet": "spreadsheet",
    "google_ads": "google-ads",
    "google_analytics": "analytics",
}

ALLOWLIST = {
    "postgres": {"catalog", "sample"},
    "mongo": {"catalog", "sample"},
    "spreadsheet": {"catalog", "sample"},
    "analytics": {"catalog", "sample"},
    "google-ads": {"list_accessible_customers", "search", "get_resource_metadata"},
}

OFFICIAL_ADS = {
    "name": "google-ads",
    "transport": "stdio",
    "command": ["google-ads-mcp"],
    "enabled": False,
    "data_origin": "live",
    "note": "Official googleads/google-ads-mcp. Left unwired until Ads credentials exist.",
}


def _resolve_registered_source(source_id: str) -> ResolvedSource:
    from app.db import SessionLocal
    from app.services.sources import require_source, resolve

    db = SessionLocal()
    try:
        return resolve(require_source(db, source_id))
    finally:
        db.close()


class McpClientManager:
    def __init__(self, resolve_source: Callable[[str], ResolvedSource] | None = None) -> None:
        resolver = resolve_source or _resolve_registered_source
        self._servers = {
            "postgres": build_source_server("postgres", "postgresql", resolver),
            "mongo": build_source_server("mongo", "mongodb", resolver),
            "spreadsheet": build_source_server("spreadsheet", "spreadsheet", resolver),
            "google-ads": build_google_ads_server(),
            "analytics": build_source_server("analytics", "google_analytics", resolver),
        }
        self._external: list[dict] = [dict(OFFICIAL_ADS)]

    def register_server(self, spec: dict) -> None:
        name = spec.get("name")
        if not name:
            raise ValueError("MCP server registration needs a name.")
        transport = spec.get("transport", "stdio")
        if transport == "in-process":
            raise ValueError("In-process servers are built into Meridian.")
        stored = {key: spec[key] for key in spec}
        stored.setdefault("enabled", False)
        stored.setdefault("data_origin", "live")
        stored.setdefault("note", "Registered but not connected.")
        self._external = [item for item in self._external if item.get("name") != name or item.get("transport") == "in-process"]
        self._external.append(stored)

    def servers(self) -> list[dict]:
        rows = [
            {
                "name": name,
                "transport": "in-process",
                "enabled": True,
                "data_origin": "sample" if name == "google-ads" else "live",
                "tools": sorted(ALLOWLIST[name]),
            }
            for name in self._servers
        ]
        rows.extend(self._external)
        return rows

    def list_tools(self) -> list[dict]:
        tools: list[dict] = []
        for namespace, server in self._servers.items():
            allowed = ALLOWLIST[namespace]
            for tool in tool_summaries(server, namespace):
                short = tool["name"].split(".", 1)[1]
                if short in allowed:
                    tools.append(tool)
        return tools

    def call(self, name: str, arguments: dict | None = None) -> Any:
        if "." not in name:
            raise ValueError("MCP tools are called as namespace.tool.")
        namespace, tool = name.split(".", 1)
        server = self._servers.get(namespace)
        if server is None:
            raise ValueError(f"Unknown MCP server: {namespace}.")
        if tool not in ALLOWLIST.get(namespace, set()):
            raise ValueError(f"Tool {name} is not on the allowlist.")
        try:
            result = _run(server.call_tool(tool, arguments or {}))
            return result_payload(result)
        except Exception as exc:
            cause = exc.__cause__ or exc
            raise ValueError(str(cause) or str(exc)) from exc

    def namespace_for(self, source_type: str) -> str:
        try:
            return TYPE_TO_NAMESPACE[source_type]
        except KeyError as exc:
            raise ValueError("Unsupported data source.") from exc


_manager: McpClientManager | None = None


def init_manager(resolve_source: Callable[[str], ResolvedSource] | None = None) -> McpClientManager:
    global _manager
    _manager = McpClientManager(resolve_source)
    return _manager


def get_manager() -> McpClientManager:
    if _manager is None:
        return init_manager()
    return _manager
