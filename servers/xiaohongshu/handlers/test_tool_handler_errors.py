import pytest

from servers.xiaohongshu.handlers.tool_handler import XiaohongshuToolHandler


class FailingXiaohongshuClient:
    async def sync_notes(self, user_id, limit):
        raise RuntimeError("0 notes returned by live API")


@pytest.mark.asyncio
async def test_xiaohongshu_tool_errors_are_structured():
    handler = XiaohongshuToolHandler(dep_manager=None, api_client=FailingXiaohongshuClient())

    result = await handler.execute_tool(
        "sync_notes",
        {"user_id": "https://xhslink.com/example", "limit": 20},
    )

    assert result["success"] is False
    assert result["error_code"] == "EMPTY_RESULT"
    assert result["message"] == "0 notes returned by live API"
    assert result["source_url"] == "https://xhslink.com/example"
    assert result["next_action"]
