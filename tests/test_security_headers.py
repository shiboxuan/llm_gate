"""Security response header regression tests."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.logging import SecurityHeadersMiddleware


@pytest.mark.asyncio
async def test_csp_allows_antd_inline_styles_and_iconify_api():
    """Production CSP must allow the frontend resources used by the login page."""
    test_app = FastAPI()
    test_app.add_middleware(SecurityHeadersMiddleware)

    @test_app.get("/")
    async def root():
        return {"status": "ok"}

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.headers["Content-Security-Policy"] == (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "connect-src 'self' https://api.iconify.design https://api.simplesvg.com https://api.unisvg.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:"
    )
