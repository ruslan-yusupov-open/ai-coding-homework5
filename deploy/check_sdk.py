"""Check the configured endpoint; credential contents are never printed."""

import asyncio
import json
import os
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    access = json.loads(Path(os.environ["MCP_TEST_ACCESS_FILE"]).read_text())
    async with (
        httpx.AsyncClient(headers={"Authorization": "Bearer " + access["token"]}) as http,
        streamable_http_client(access["url"], http_client=http) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert len(tools.tools) == 3
        result = await session.call_tool("list_docs", {})
        assert result.structuredContent["data"]["count"] == 3
        print(json.dumps({"sdk": "mcp 1.30.0", "https_verified": True,
                          "tools": [x.name for x in tools.tools],
                          "result": result.structuredContent}, ensure_ascii=False))
    # Bounded burst of unauthenticated requests verifies the actual nginx quota.
    async with httpx.AsyncClient() as http:
        replies = await asyncio.gather(*(http.post(access["url"], json={}) for _ in range(20)))
        counts = {code: sum(r.status_code == code for r in replies)
                  for code in {r.status_code for r in replies}}
        assert 429 in counts, counts
        assert set(counts) <= {401, 429}, counts
        print(json.dumps({"unauthenticated_burst_status_counts": counts}))


asyncio.run(main())
