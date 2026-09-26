"""Private single-principal HTTP boundary; service credential is not end-user auth."""

import hmac
import os
import re
from dataclasses import dataclass, field

from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse, Response

from flamoris_ai_agent.server import create_server


@dataclass(frozen=True)
class HTTPSettings:
    token: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 8768
    allowed_hosts: tuple[str, ...] = ("localhost:8768", "127.0.0.1:8768", "[::1]:8768")

    def __post_init__(self):
        if (
            not isinstance(self.token, str)
            or not 32 <= len(self.token) <= 512
            or not self.token.isascii()
            or any(ord(c) < 33 or ord(c) > 126 for c in self.token)
        ):
            raise ValueError("invalid_http_credential")
        if self.host not in ("127.0.0.1", "::1", "0.0.0.0"):
            raise ValueError("invalid_http_bind")
        if not 1 <= self.port <= 65535:
            raise ValueError("invalid_http_port")
        if not 1 <= len(self.allowed_hosts) <= 16 or any(
            not re.fullmatch(r"(?:[a-zA-Z0-9.-]+|\[::1\])(?::[0-9]{1,5})?", h) or len(h) > 255
            for h in self.allowed_hosts
        ):
            raise ValueError("invalid_http_hosts")

    @classmethod
    def from_env(cls):
        try:
            port = int(os.getenv("AGENT_HTTP_PORT", "8768"))
            hosts = os.getenv(
                "AGENT_HTTP_ALLOWED_HOSTS", f"localhost:{port},127.0.0.1:{port},[::1]:{port}"
            )
            return cls(
                os.getenv("AGENT_MCP_TOKEN", ""),
                os.getenv("AGENT_HTTP_HOST", "127.0.0.1"),
                port,
                tuple(h.strip() for h in hosts.split(",")),
            )
        except (ValueError, TypeError):
            raise ValueError("invalid_http_configuration") from None


class ServiceAuth:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["path"] == "/healthz" and scope["method"] == "GET":
            return await JSONResponse({"alive": True})(scope, receive, send)
        headers = scope.get("headers", [])
        auth = [v for k, v in headers if k.lower() == b"authorization"]
        hosts = [v for k, v in headers if k.lower() == b"host"]
        if len(auth) != 1 or not hmac.compare_digest(
            auth[0], ("Bearer " + self.settings.token).encode("ascii")
        ):
            return await Response(
                "Unauthorized", status_code=401, headers={"WWW-Authenticate": "Bearer"}
            )(scope, receive, send)
        if len(hosts) != 1 or hosts[0].decode("latin-1") not in self.settings.allowed_hosts:
            return await Response("Invalid host", status_code=421)(scope, receive, send)
        if any(k.lower() == b"origin" for k, v in headers):
            return await Response("Browser access forbidden", status_code=403)(scope, receive, send)
        if any(k.lower() == b"content-encoding" for k, v in headers):
            return await Response("Encoded body forbidden", status_code=415)(scope, receive, send)
        return await self.app(scope, receive, send)


def create_http_app(settings, service=None):
    server = create_server(service)
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        max_request_body_size=131072,
        host=settings.host,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.allowed_hosts),
            allowed_origins=[],
        ),
    )
    app.add_middleware(ServiceAuth, settings=settings)
    return app


def run_http():
    import uvicorn

    settings = HTTPSettings.from_env()
    uvicorn.run(
        create_http_app(settings),
        host=settings.host,
        port=settings.port,
        workers=1,
        access_log=False,
        log_level="warning",
        proxy_headers=False,
        timeout_graceful_shutdown=30,
        timeout_keep_alive=5,
        limit_concurrency=32,
    )
