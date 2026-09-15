"""Integration tests for FastAPI REST and SSE endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from src.api.app import app


@pytest.mark.asyncio
async def test_api_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["indexed_documents"] > 0


@pytest.mark.asyncio
async def test_api_chat_sync():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "三菱UFJフィナンシャル・グループの2024年3月期純利益は？",
            "session_id": "test-sync-api",
            "force_verify": True,
        }
        res = await client.post("/api/v1/chat/sync", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "8306" in data["target_tickers"]
        assert len(data["answer"]) > 20
        assert data["audit_report"]["attribution_consistency_rate"] > 0.5


@pytest.mark.asyncio
async def test_api_chat_stream_sse():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "日銀の追加利上げと政策金利について教えてください",
            "session_id": "test-stream-api",
        }
        async with client.stream("POST", "/api/v1/chat/stream", json=payload) as response:
            assert response.status_code == 200
            body = await response.aread()
            body_str = body.decode("utf-8")
            assert "event: session_start" in body_str
            assert "event: retrieval_done" in body_str
            assert "event: done" in body_str
