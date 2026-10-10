"""Official MCP SDK protocol surface, independent of console I/O."""

import argparse
import json
from contextlib import asynccontextmanager
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from flamoris_ai_agent.mcp_service import AgentService, AskRequest
from flamoris_ai_agent.personality import PersonalityRead, PersonalitySave
from flamoris_ai_agent.scoped_service import (
    OpenSessionRequest,
    ScopedAskRequest,
    SessionRequest,
    SettingsOpenRequest,
)

RequestArgument = Annotated[Any, Field(json_schema_extra=AskRequest.model_json_schema())]
SessionArgument = Annotated[Any, Field(json_schema_extra=OpenSessionRequest.model_json_schema())]
SettingsSessionArgument = Annotated[
    Any, Field(json_schema_extra=SettingsOpenRequest.model_json_schema())
]


def inline_schema(model):
    # SDK wraps the request as a nested field. Local Pydantic $defs references
    # otherwise point to the wrong root; publish this finite DTO tree inline.
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def expand(value):
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            if "$ref" in value:
                return expand(
                    {
                        **definitions[value["$ref"].split("/")[-1]],
                        **{k: v for k, v in value.items() if k != "$ref"},
                    }
                )
            return {key: expand(item) for key, item in value.items()}
        return value

    return expand(schema)


ScopedArgument = Annotated[Any, Field(json_schema_extra=inline_schema(ScopedAskRequest))]
PersonalityReadArgument = Annotated[Any, Field(json_schema_extra=inline_schema(PersonalityRead))]
PersonalitySaveArgument = Annotated[Any, Field(json_schema_extra=inline_schema(PersonalitySave))]

AvailabilityArgument = Annotated[Any, Field(json_schema_extra=SessionRequest.model_json_schema())]


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

    server = MCPServer("FLAMORIS Agent", version="1.0.1", lifespan=lifespan, log_level="CRITICAL")

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

    if getattr(service, "shared_principals", False):

        @server.tool(
            name="ask_availability",
            annotations=ToolAnnotations(
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        )
        async def availability(request: AvailabilityArgument = None) -> CallToolResult:
            """Fresh scoped prerequisites; no inference, conversation or runtime activation."""
            return tool_result(await service.availability(request))

        if getattr(service, "settings_enabled", False):

            @server.tool(name="models.allowed")
            async def models_allowed(request: SessionArgument = None) -> CallToolResult:
                """Exact principal-authorized model catalog; no inference or session allocation."""
                return tool_result(await service.settings_operation("models", request))

            @server.tool(name="personality.get")
            async def personality_get(request: PersonalityReadArgument = None) -> CallToolResult:
                """Read current Agent personality under a separate explicit read grant."""
                return tool_result(await service.settings_operation("get", request))

            @server.tool(name="personality.history")
            async def personality_history(
                request: PersonalityReadArgument = None,
            ) -> CallToolResult:
                """Read at most twenty historical revisions; no transcript or policy data."""
                return tool_result(await service.settings_operation("history", request))

            @server.tool(name="personality.save")
            async def personality_save(request: PersonalitySaveArgument = None) -> CallToolResult:
                """Atomic expected-revision save with an immutable update UUID/digest fence."""
                return tool_result(await service.settings_operation("save", request))

            @server.tool(name="sessions.open")
            async def open_settings_session(
                request: SettingsSessionArgument = None,
            ) -> CallToolResult:
                """Bind authorized model and explicit remote consent to an immutable session."""
                return tool_result(await service.open_session(request))

        else:

            @server.tool(
                name="sessions.open",
                annotations=ToolAnnotations(
                    read_only_hint=False,
                    destructive_hint=False,
                    idempotent_hint=False,
                    open_world_hint=False,
                ),
            )
            async def open_session(request: SessionArgument = None) -> CallToolResult:
                """Resolve permitted principal keys under the authenticated transport delegator."""
                return tool_result(await service.open_session(request))

        @server.tool(
            name="ask_scoped",
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=False,
                open_world_hint=True,
            ),
        )
        async def ask_scoped(request: ScopedArgument = None) -> CallToolResult:
            """One bounded turn under an immutable authorized principal session; never replay."""
            return tool_result(await service.ask_scoped(request))

        return server

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
    from flamoris_update_core.admission import wait_for_admission

    parser = argparse.ArgumentParser(description="FLAMORIS Agent MCP")
    parser.add_argument("--version", action="version", version="1.0.1")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    args = parser.parse_args(argv)
    wait_for_admission("flamoris-ai-agent")
    if args.transport == "stdio":
        create_server().run(transport="stdio")
    else:
        from flamoris_ai_agent.http_server import run_http

        try:
            run_http()
        except ValueError:
            parser.error("invalid_http_configuration")


if __name__ == "__main__":
    main()
