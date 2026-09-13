"""Exercise real MCP stdio messages; this is NOT evidence of an IDE chat session."""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent
CASES = [
    ("Покажи список документов через list_docs.", "list_docs", {}, "success"),
    ("Найди stdio в документации через search_docs.", "search_docs", {"query": "stdio"}, "success"),
    ("Прочитай security.md через get_doc.", "get_doc", {"path": "security.md"}, "success"),
    (
        "Найди несуществующий термин zzz_no_such_term.",
        "search_docs",
        {"query": "zzz_no_such_term"},
        "success",
    ),
    (
        "Попробуй прочитать ../README.md через get_doc.",
        "get_doc",
        {"path": "../README.md"},
        "error",
    ),
    ("Проверь пустой запрос.", "search_docs", {"query": ""}, "error"),
    ("Проверь отсутствующий документ.", "get_doc", {"path": "absent.md"}, "error"),
    ("Проверь лишние параметры.", "list_docs", {"extra": True}, "error"),
]


async def validate(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "server.py")],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONUTF8": "1", "MCP_LOG_FILE": "logs/validation.jsonl"},
    )
    report = {
        "source": "automated MCP SDK client (not IDE)",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": [],
    }
    with (output / "stdio-stderr.log").open("w", encoding="utf-8") as stderr:
        async with stdio_client(params, errlog=stderr) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                tools = (await session.list_tools()).tools
                assert {tool.name for tool in tools} == {"list_docs", "search_docs", "get_doc"}
                report["server"] = initialized.model_dump(mode="json")
                report["tools"] = [tool.model_dump(mode="json") for tool in tools]
                for prompt, name, arguments, status in CASES:
                    result = await session.call_tool(name, arguments)
                    data = result.structuredContent
                    assert data is not None, result
                    jsonschema.validate(data, next(t.outputSchema for t in tools if t.name == name))
                    assert data["status"] == status, result
                    assert result.isError == (status == "error")
                    assert json.loads(result.content[0].text) == data
                    if name == "list_docs" and status == "success":
                        assert data["data"]["count"] == 3
                    if arguments.get("query") == "stdio":
                        assert data["data"]["count"] > 0
                    if arguments.get("query") == "zzz_no_such_term":
                        assert data["data"]["matches"] == []
                    if arguments.get("path") == "../README.md":
                        assert data["error"]["code"] == "ACCESS_DENIED"
                    report["checks"].append(
                        {
                            "prompt": prompt,
                            "tool": name,
                            "arguments": arguments,
                            "result": data,
                            "passed": True,
                        }
                    )
    # Keep only this run's server audit records, excluding SDK diagnostic lines.
    call_ids = {check["result"]["call_id"] for check in report["checks"]}
    records = []
    for line in (ROOT / "logs/validation.jsonl").read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["call_id"] in call_ids:
            records.append(record)
    assert len(records) == len(CASES), "Every call must have a server audit record"
    (output / "server.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    (output / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    report = asyncio.run(validate(ROOT / "validation" / "automated"))
    print(f"PASS: {len(report['checks'])} real MCP stdio calls; evidence: validation/automated")
