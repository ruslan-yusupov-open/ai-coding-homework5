"""MCP stdio server. stdout is reserved exclusively for protocol messages."""

import asyncio
import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from documents import DocumentError, Documents, is_link

ROOT = Path(__file__).resolve().parent
documents = Documents(ROOT / "knowledge")
server = Server("homework5-docs", version="0.1.0")
audit = logging.getLogger("homework5.audit")


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ListParams(Params):
    pass


class SearchParams(Params):
    query: str = Field(
        min_length=1,
        max_length=200,
        pattern=r"\S",
        description="Literal substring, case-insensitive; no secrets.",
    )
    limit: int = Field(default=10, ge=1, le=20, description="Maximum number of matching lines.")


class GetParams(Params):
    path: str = Field(
        min_length=1,
        max_length=240,
        description="Relative .md path from list_docs, for example security.md.",
    )


class ErrorInfo(BaseModel):
    code: str
    message: str


class Output(BaseModel):
    status: Literal["success", "error"]
    call_id: str
    data: dict | None = None
    error: ErrorInfo | None = None


TOOLS = {
    "list_docs": (
        ListParams,
        "List local Markdown documents and titles in knowledge.",
        documents.list_docs,
    ),
    "search_docs": (
        SearchParams,
        (
            "Search local documentation by literal substring; return paths, "
            "line numbers and excerpts. Use for questions about setup or security."
        ),
        documents.search_docs,
    ),
    "get_doc": (
        GetParams,
        (
            "Read a complete local Markdown document using its relative path. "
            "Use after list_docs or search_docs. Cannot read files outside knowledge."
        ),
        documents.get_doc,
    ),
}


def safe_params(arguments: dict) -> dict:
    """Keep useful public arguments; redact common credential patterns and unknown fields."""
    secret = re.compile(
        r"(?i)(sk-[\w-]+|gh[pousr]_[\w]+|github_pat_[\w]+|bearer\s+\S+|"
        r"(?:password|token|secret|api[_-]?key)\s*[:=]\s*\S+|[\w-]{40,})"
    )
    return {
        str(key)[:80]: (
            secret.sub("[REDACTED]", value)[:240]
            if isinstance(value, str)
            else value
            if type(value) in (int, bool) or value is None
            else "[REDACTED]"
        )
        if key in {"path", "query", "limit"}
        else "[REDACTED]"
        for key, value in arguments.items()
    }


def configure_logging() -> None:
    name = os.getenv("MCP_LOG_FILE", "logs/server.jsonl").replace("\\", "/")
    if not re.fullmatch(r"logs/[a-zA-Z0-9_-]+\.jsonl", name):
        raise ValueError("MCP_LOG_FILE must be logs/<name>.jsonl")
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    if is_link(log_dir):
        raise ValueError("Log directory cannot be a link")
    target = ROOT / name
    if target.exists() and is_link(target):
        raise ValueError("Log file cannot be a link")
    audit.setLevel(logging.INFO)
    audit.propagate = False
    for handler in audit.handlers[:]:
        audit.removeHandler(handler)
        handler.close()
    for handler in (logging.StreamHandler(), logging.FileHandler(target, encoding="utf-8")):
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit.addHandler(handler)


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=name,
            description=description,
            inputSchema=model.model_json_schema(),
            outputSchema=Output.model_json_schema(),
            annotations=types.ToolAnnotations(
                readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
            ),
        )
        for name, (model, description, _) in TOOLS.items()
    ]


# Validate here so invalid arguments also get a structured error and an audit record.
@server.call_tool(validate_input=False)
async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
    call_id = str(uuid4())
    try:
        if name not in TOOLS:
            raise DocumentError("UNKNOWN_TOOL", "Unknown tool name.")
        model, _, function = TOOLS[name]
        params = model.model_validate(arguments)
        data = function(**params.model_dump())
        output = Output(status="success", call_id=call_id, data=data)
    except ValidationError:
        output = Output(
            status="error",
            call_id=call_id,
            error=ErrorInfo(
                code="INVALID_PARAMS", message="Arguments do not match the tool input schema."
            ),
        )
    except DocumentError as exc:
        output = Output(
            status="error", call_id=call_id, error=ErrorInfo(code=exc.code, message=str(exc))
        )
    except FileNotFoundError:
        output = Output(
            status="error",
            call_id=call_id,
            error=ErrorInfo(
                code="NOT_FOUND", message="Document or knowledge directory does not exist."
            ),
        )
    except (OSError, ValueError):
        output = Output(
            status="error",
            call_id=call_id,
            error=ErrorInfo(code="READ_ERROR", message="Cannot read the requested document."),
        )
    except Exception:  # noqa: BLE001 - protocol boundary must not expose exception details
        output = Output(
            status="error",
            call_id=call_id,
            error=ErrorInfo(code="INTERNAL_ERROR", message="Unexpected server error."),
        )
    payload = output.model_dump(mode="json")
    audit.info(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "call_id": call_id,
                "tool": name[:100],
                "params": safe_params(arguments),
                "status": output.status,
                "error_code": output.error.code if output.error else None,
            },
            ensure_ascii=False,
        )
    )
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload,
        isError=output.status == "error",
    )


async def main() -> None:
    configure_logging()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
