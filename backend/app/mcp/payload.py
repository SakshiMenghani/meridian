import json
from typing import Any

from mcp.server.mcpserver import MCPServer


def result_payload(result) -> Any:
    if getattr(result, "is_error", False):
        text = ""
        for block in result.content or []:
            text += getattr(block, "text", "") or ""
        raise ValueError(text or "MCP tool returned an error.")
    if result.structured_content is not None:
        return result.structured_content
    for block in result.content or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
    return {}


def tool_summaries(server: MCPServer, namespace: str) -> list[dict]:
    import asyncio

    tools = _run(server.list_tools())
    return [
        {
            "name": f"{namespace}.{tool.name}",
            "description": tool.description or "",
            "input_schema": _schema(tool),
        }
        for tool in tools
    ]


def _schema(tool) -> dict:
    raw = getattr(tool, "input_schema", None) or {}
    if hasattr(raw, "model_dump"):
        return raw.model_dump()
    return dict(raw) if raw else {}


def _run(awaitable):
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Call MCP tools from a sync worker, not the event loop thread.")
