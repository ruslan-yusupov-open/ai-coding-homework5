import hashlib
import time

import pytest
from starlette.testclient import TestClient

from http_server import MAX_BODY, KeyVerifier, create_app

KEY = "test-key-" + "x" * 48
CONFIG = {"sha256": hashlib.sha256(KEY.encode()).hexdigest(), "expires_at": 4102444800}
HEADERS = {
    "Authorization": f"Bearer {KEY}",
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-11-25",
}


@pytest.fixture
def client():
    with TestClient(create_app(CONFIG), base_url="https://mcp1.leadcm.com") as value:
        yield value


def rpc(client, method, params=None, headers=None):
    return client.post(
        "/mcp", headers=HEADERS if headers is None else headers,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )


def test_auth_and_request_boundary(client):
    assert client.get("/mcp").status_code == 401
    assert rpc(client, "tools/list", headers={}).status_code == 401
    assert rpc(client, "tools/list", headers={**HEADERS, "Authorization": "Bearer wrong"}).status_code == 401
    assert rpc(client, "tools/list", headers={**HEADERS, "Origin": "https://evil.example"}).status_code == 403
    assert rpc(client, "tools/list", headers={**HEADERS, "Host": "evil.example"}).status_code == 421
    assert client.post("/mcp?token=wrong", headers=HEADERS).status_code == 400
    assert client.post("/other", headers=HEADERS).status_code == 404
    assert client.get("/mcp", headers=HEADERS).status_code == 405
    assert client.post("/mcp", content=b"x" * (MAX_BODY + 1), headers=HEADERS).status_code == 413
    assert client.post("/mcp", content=iter([b"x" * (MAX_BODY + 1)]), headers=HEADERS).status_code == 413


def test_real_http_protocol_and_tools(client):
    response = rpc(client, "initialize", {
        "protocolVersion": "2025-11-25", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    })
    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "homework5-docs"
    result = rpc(client, "tools/list").json()["result"]
    assert {tool["name"] for tool in result["tools"]} == {"list_docs", "search_docs", "get_doc"}
    for name, args, status in [
        ("list_docs", {}, "success"),
        ("search_docs", {"query": "stdio"}, "success"),
        ("get_doc", {"path": "security.md"}, "success"),
        ("search_docs", {"query": "zzz_no_such_term"}, "success"),
        ("get_doc", {"path": "../README.md"}, "error"),
    ]:
        result = rpc(client, "tools/call", {"name": name, "arguments": args}).json()["result"]
        assert result["structuredContent"]["status"] == status
        if status == "error":
            assert result["isError"] is True
            assert result["structuredContent"]["error"]["code"] == "ACCESS_DENIED"


def test_expiry_and_invalid_startup(monkeypatch, client):
    monkeypatch.setattr(time, "time", lambda: CONFIG["expires_at"] + 1)
    assert rpc(client, "tools/list").status_code == 401
    with pytest.raises(ValueError):
        KeyVerifier(CONFIG)
    with pytest.raises(ValueError):
        KeyVerifier({"sha256": "bad", "expires_at": 4102444800})
