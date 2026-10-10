from typing import Callable

from mcp.server.mcpserver import MCPServer

from app.connectors.registry import get_connector
from app.connectors.base import ResolvedSource


def build_source_server(name: str, source_type: str, resolve_source: Callable[[str], ResolvedSource]) -> MCPServer:
    server = MCPServer(
        name=name,
        instructions=f"Read-only {source_type} catalog and row samples. No writes.",
    )

    @server.tool(name="catalog", description="List tables, collections, or sheets and their columns.")
    def catalog(source_id: str) -> dict:
        source = resolve_source(source_id)
        if source.source_type != source_type:
            raise ValueError(f"Source {source_id} is not {source_type}.")
        objects = get_connector(source_type).catalog(source)
        return {
            "source_id": source_id,
            "source_name": source.name,
            "objects": [item.model_dump() for item in objects],
        }

    @server.tool(name="sample", description="Read a limited sample of rows from one object.")
    def sample(source_id: str, object_name: str, schema_name: str | None = None, limit: int = 50) -> dict:
        source = resolve_source(source_id)
        if source.source_type != source_type:
            raise ValueError(f"Source {source_id} is not {source_type}.")
        capped = max(1, min(int(limit), 5000))
        result = get_connector(source_type).sample(source, schema_name, object_name, capped)
        return {
            "source_id": source_id,
            "object_name": object_name,
            "schema_name": schema_name,
            **result.model_dump(),
        }

    return server
