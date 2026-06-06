"""Adapter: OpenCLIWeixinToolHandler API backed by LocalToolExecutor."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.local_exec.executor import LocalToolExecutor


class OpenCLIExecutorAdapter:
    """Drop-in replacement for OpenCLIClient in MCP handlers."""

    def __init__(self, executor: LocalToolExecutor):
        self._executor = executor

    async def run(self, *args: str, fmt: Optional[str] = None, timeout: Optional[int] = None) -> Dict[str, Any]:
        tool_name = args[0] if args else "opencli_invoke"
        return await self._executor.opencli_run(*args, fmt=fmt, timeout=timeout, tool_name=tool_name)

    async def doctor(self) -> Dict[str, Any]:
        return await self._executor.opencli_run("doctor", fmt="", tool_name="opencli_doctor")

    async def weixin_search(self, query: str, *, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        return await self._executor.opencli_run(
            "weixin",
            "search",
            query,
            "-p",
            str(page),
            "-n",
            str(limit),
            tool_name="weixin_search",
        )

    async def weixin_download(
        self,
        url: str,
        output: str = ".",
        download_images: bool = True,
    ) -> Dict[str, Any]:
        args: List[str] = ["weixin", "download", url, "-o", output]
        if download_images:
            args.append("--images")
        return await self._executor.opencli_run(*args, tool_name="weixin_download")

    async def weixin_drafts(self, limit: int = 10) -> Dict[str, Any]:
        return await self._executor.opencli_run(
            "weixin",
            "drafts",
            "-n",
            str(limit),
            tool_name="weixin_drafts",
        )

    async def weixin_create_draft(self, **kwargs: Any) -> Dict[str, Any]:
        args = ["weixin", "create-draft"]
        for key in ("title", "content", "author", "summary"):
            if kwargs.get(key):
                args.extend([f"--{key.replace('_', '-')}", str(kwargs[key])])
        if kwargs.get("cover_image"):
            args.extend(["--cover", str(kwargs["cover_image"])])
        return await self._executor.opencli_run(*args, tool_name="weixin_create_draft")

    async def browser_open(self, url: str, session: Optional[str] = None) -> Dict[str, Any]:
        args = ["browser", session or "dataproai", "open", url]
        return await self._executor.opencli_run(*args, tool_name="browser_open")

    async def browser_state(self, session: Optional[str] = None) -> Dict[str, Any]:
        args = ["browser", session or "dataproai", "state"]
        return await self._executor.opencli_run(*args, tool_name="browser_state")

    async def browser_click(self, ref: str, session: Optional[str] = None) -> Dict[str, Any]:
        args = ["browser", session or "dataproai", "click", ref]
        return await self._executor.opencli_run(*args, tool_name="browser_click")

    async def browser_fill(self, ref: str, text: str, session: Optional[str] = None) -> Dict[str, Any]:
        args = ["browser", session or "dataproai", "fill", ref, text]
        return await self._executor.opencli_run(*args, tool_name="browser_fill")

    async def browser_extract(self, session: Optional[str] = None) -> Dict[str, Any]:
        args = ["browser", session or "dataproai", "extract"]
        return await self._executor.opencli_run(*args, tool_name="browser_extract")

    async def browser_screenshot(self, path: str, session: Optional[str] = None) -> Dict[str, Any]:
        args = ["browser", session or "dataproai", "screenshot", path]
        return await self._executor.opencli_run(*args, tool_name="browser_screenshot")
