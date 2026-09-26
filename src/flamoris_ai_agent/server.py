"""Official MCP SDK protocol surface, independent of console I/O."""

import argparse
import json
from contextlib import asynccontextmanager
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from flamoris_ai_agent.mcp_service import AgentService, AskRequest

RequestArgument = Annotated[Any, Field(json_schema_extra=AskRequest.model_json_schema())]


def tool_result(data):
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=False))],
        structured_content=data,
        is_error=not data["ok"],
    )


def create_server(service=None):
    service = service or AgentService()

    @asynccontextmanager
    async def lifespan(server):
        try:
            yield None
        finally:
            await service.aclose()

    server = MCPServer("FLAMORIS Agent", version="0.1.0", lifespan=lifespan, log_level="ERROR")

    @server.tool(
        name="health",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
    async def health() -> CallToolResult:
        """Process liveness and admission state; dependency readiness is not inferred."""
        return tool_result(service.health())

    @server.tool(
        name="ask",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )
    async def ask(request: RequestArgument = None) -> CallToolResult:
        """One persistent turn; request_id UUID, text, optional previous_conversation_id.
        Creates/closes a new conversation. Never automatically retry an uncertain ask.
        """
        return tool_result(await service.ask(request))

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="FLAMORIS Agent MCP")
    parser.add_argument("--version", action="version", version="0.1.0")
    parser.parse_args(argv)
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
