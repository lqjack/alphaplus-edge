import httpx
import pytest

from core.protocol_client import APIProtocolClient


@pytest.mark.asyncio
async def test_api_protocol_client_prefers_api_tools_call_over_legacy_path():
    seen_paths = []

    def handler(request):
        seen_paths.append(request.url.path)
        if request.url.path == "/api/tools/call":
            return httpx.Response(200, json={"result": {"ok": True}})
        return httpx.Response(500, json={"error": "legacy path should not be called"})

    client = APIProtocolClient("http://platform-service")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        result = await client.call("sync_content", {"share_text": "valid"})
    finally:
        await client.close()

    assert result == {"ok": True}
    assert seen_paths == ["/api/tools/call"]
