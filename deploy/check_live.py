"""Check the configured endpoint; credential contents are never printed."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--public", action="store_true")
args = parser.parse_args()
access = json.loads(Path(os.environ["MCP_TEST_ACCESS_FILE"]).read_text())
transport = None if args.public else httpx.HTTPTransport(uds="/run/homework5-docs.sock")
base = "https://mcp1.leadcm.com" if args.public else "http://mcp1.leadcm.com"
headers = {
    "Authorization": "Bearer " + access["token"],
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}
evidence = {"url": base + "/mcp", "timestamp": datetime.now(UTC).isoformat(),
            "expires_at": access["expires_at"], "checks": [], "calls": []}
with httpx.Client(transport=transport, base_url=base, timeout=20) as client:
    def check(label, response, expected):
        assert response.status_code == expected, (label, response.status_code)
        evidence["checks"].append({"name": label, "http_status": response.status_code})
        time.sleep(0.6)

    check("no credential", client.post("/mcp", json={}), 401)
    check("wrong credential", client.post("/mcp", json={}, headers={
        **headers, "Authorization": "Bearer invalid"}), 401)
    check("untrusted origin", client.post("/mcp", json={}, headers={
        **headers, "Origin": "https://evil.example"}), 403)
    check("oversized body", client.post("/mcp", content=b"x" * 16385, headers=headers), 413)
    check("no query credentials", client.post("/mcp?token=invalid", json={}, headers=headers), 400)

    def rpc(method, params):
        result = client.post("/mcp", headers=headers,
                             json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        assert result.status_code == 200, (method, result.status_code)
        time.sleep(0.6)
        return result.json()["result"]

    init = rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                              "clientInfo": {"name": "live-check", "version": "1"}})
    assert init["serverInfo"]["name"] == "homework5-docs"
    evidence["serverInfo"] = init["serverInfo"]
    listed = rpc("tools/list", {})
    assert {x["name"] for x in listed["tools"]} == {"list_docs", "search_docs", "get_doc"}
    evidence["tools"] = [x["name"] for x in listed["tools"]]
    for name, params, status in [
        ("list_docs", {}, "success"),
        ("search_docs", {"query": "stdio"}, "success"),
        ("get_doc", {"path": "security.md"}, "success"),
        ("search_docs", {"query": "zzz_no_such_term"}, "success"),
        ("get_doc", {"path": "../README.md"}, "error"),
    ]:
        result = rpc("tools/call", {"name": name, "arguments": params})
        data = result["structuredContent"]
        assert data["status"] == status
        if status == "error":
            assert result["isError"] and data["error"]["code"] == "ACCESS_DENIED"
        evidence["calls"].append({"tool": name, "params": params, "result": data})
print(json.dumps(evidence, ensure_ascii=False, indent=2))
