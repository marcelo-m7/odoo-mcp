"""ASGI factory for Coolify: uvicorn --factory odoo_mcp.hosted:create_hosted_app."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.applications import Starlette


def create_hosted_app(server: FastMCP | None = None) -> Starlette:
    if os.environ.get("ODOO_MCP_TRANSPORT") != "streamable-http":
        raise RuntimeError("Hosted MCP requires ODOO_MCP_TRANSPORT=streamable-http with OAuth configured")
    if server is None:
        from .server import mcp

        server = mcp

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        # Process liveness, not a public credential/IdP diagnostic endpoint.
        return JSONResponse({"status": "ok"})

    return server.streamable_http_app()
