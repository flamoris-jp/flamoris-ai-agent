"""Run through docker exec stdin: real socket/installed package, no live dependencies."""

import asyncio
import os

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from flamoris_ai_agent.healthcheck import main as healthcheck


async def check():
    assert os.geteuid() == 10001
    assert healthcheck() == 0
    url = "http://127.0.0.1:8768/mcp"
    async with httpx2.AsyncClient(trust_env=False) as client:
        response = await client.post(url, json={})
        assert response.status_code == 401
    async with httpx2.AsyncClient(
        trust_env=False, headers={"Authorization": "Bearer " + os.environ["AGENT_MCP_TOKEN"]}
    ) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                assert {t.name for t in (await session.list_tools()).tools} == {"health", "ask"}
                result = await session.call_tool("health")
                assert result.structured_content["dependencies"] == "not_checked"
    print("Non-root container, health, auth, real HTTP MCP: OK")


asyncio.run(check())
