"""Private Streamable HTTP endpoint; manually provisioned expiring API key, not OAuth."""

import hashlib
import hmac
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
from mcp.server.auth.provider import AccessToken
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import Response
from starlette.routing import Route

from server import ROOT, audit, server

RESOURCE = "https://mcp1.leadcm.com/mcp"
MAX_BODY = 16 * 1024


class KeyVerifier:
    def __init__(self, config: dict):
        self.digest = config["sha256"]
        self.expires = config["expires_at"]
        if not re.fullmatch(r"[a-f0-9]{64}", self.digest):
            raise ValueError("Invalid credential digest")
        if type(self.expires) is not int or self.expires <= time.time():
            raise ValueError("Credential must have a future expiration")

    async def verify_token(self, token: str) -> AccessToken | None:
        if len(token) > 256 or self.expires <= time.time():
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not hmac.compare_digest(digest, self.digest):
            return None
        return AccessToken(
            token=token, client_id="docs-reader", scopes=["docs:read"],
            expires_at=self.expires, resource=RESOURCE,
        )


class RequestGate:
    """Exact public authority, no cross-origin requests, no URL credentials or GET stream."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = HTTPConnection(scope).headers
        status = None
        if headers.get("host") != "mcp1.leadcm.com":
            status = 421
        elif headers.get("origin") not in (None, "https://mcp1.leadcm.com"):
            status = 403
        elif scope["query_string"] or len(headers.getlist("authorization")) > 1:
            status = 400
        elif scope["path"] != "/mcp":
            status = 404
        if status:
            await Response(status_code=status)(scope, receive, send)
            return
        await self.app(scope, receive, send)


class HTTPAuth(RequireAuthMiddleware):
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            await super().__call__(scope, receive, send)
        else:
            await self.app(scope, receive, send)


def create_app(credential: dict | None = None):
    if credential is None:
        credential = json.loads(Path(os.environ["MCP_AUTH_FILE"]).read_text())
    verifier = KeyVerifier(credential)
    manager = StreamableHTTPSessionManager(
        server, stateless=True, json_response=True, max_request_body_size=MAX_BODY,
        security_settings=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["mcp1.leadcm.com"],
            allowed_origins=["https://mcp1.leadcm.com"],
        ),
    )

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    # Authenticate before method dispatch, including GET/HEAD requests.
    app = Starlette(
        routes=[Route("/mcp", manager.asgi_app, methods=["POST"])], lifespan=lifespan
    )
    app = HTTPAuth(app, ["docs:read"])
    app = AuthenticationMiddleware(
        app, backend=BearerAuthBackend(verifier, resource_server_url=AnyHttpUrl(RESOURCE))
    )
    return RequestGate(app)


def production_app():
    audit.setLevel(logging.INFO)
    audit.propagate = False
    for handler in audit.handlers[:]:
        audit.removeHandler(handler)
        handler.close()
    for handler in (
        logging.StreamHandler(),
        RotatingFileHandler(ROOT / "logs/http.jsonl", maxBytes=1024 * 1024, backupCount=2),
    ):
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit.addHandler(handler)
    return create_app()
