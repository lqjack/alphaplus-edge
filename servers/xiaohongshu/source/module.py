from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
from contextlib import suppress
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import aiosqlite
import httpx
from pydantic import BaseModel, Field
from yaml import dump, safe_load

ROOT = Path(__file__).resolve().parent.parent
PROJECT = "XHS-Downloader"
REPOSITORY = "https://github.com/JoeanAmier/XHS-Downloader"
RELEASES = f"{REPOSITORY}/releases/latest"
LICENCE = "GNU General Public License v3.0"
VERSION_MAJOR = 2
VERSION_MINOR = 7
VERSION_BETA = False
__VERSION__ = f"{VERSION_MAJOR}.{VERSION_MINOR}{'-beta' if VERSION_BETA else ''}"

MASTER = "bold bright_white"
PROMPT = "bold cyan"
GENERAL = "bright_white"
ERROR = "bold bright_red"
WARNING = "bold bright_yellow"
INFO = "bold bright_green"

MAX_WORKERS = 4
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
FILE_SIGNATURES = (
    (0, b"\xff\xd8\xff", "jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "png"),
    (0, b"RIFF", "webp"),
    (4, b"ftyp", "mp4"),
    (4, b"ftypheic", "heic"),
    (4, b"ftypavif", "avif"),
)
FILE_SIGNATURES_LENGTH = max(offset + len(signature) for offset, signature, _ in FILE_SIGNATURES)


class ExtractParams(BaseModel):
    url: str = Field(description="Xiaohongshu note URL or share text")
    download: bool = False
    index: list[int | str] | None = None
    cookie: str | None = None
    proxy: str | None = None
    skip: bool = True


class ExtractData(BaseModel):
    message: str
    params: ExtractParams
    data: Any | None = None


def logging(print_: Any, text: str, style: str = INFO) -> None:
    writer = getattr(print_, "func", print_)
    try:
        writer(text, style=style)
    except TypeError:
        with suppress(Exception):
            writer(text)


async def sleep_time(delay: float = 0.2) -> None:
    await asyncio.sleep(delay)


def retry(function: Callable):
    @wraps(function)
    async def inner(self, *args, **kwargs):
        attempts = max(1, int(getattr(self, "retry", 1) or 1))
        last_error = None
        for _ in range(attempts):
            try:
                return await function(self, *args, **kwargs)
            except Exception as error:
                last_error = error
                await asyncio.sleep(0.2)
        if last_error:
            raise last_error
        return None

    return inner


class Manager:
    SEPARATE = "_"
    INVALID_NAME = re.compile(r"[^\u4e00-\u9fffa-zA-Z0-9-_！？，。；：“”（）《》\\[\\]()]")

    def __init__(
        self,
        root: Path,
        work_path: str,
        folder_name: str,
        name_format: str,
        chunk: int,
        user_agent: str | None,
        cookie: str,
        proxy: str | dict | None,
        timeout: int,
        max_retry: int,
        record_data: bool,
        image_format: str,
        image_download: bool,
        video_download: bool,
        live_download: bool,
        download_record: bool,
        folder_mode: bool,
        author_archive: bool,
        write_mtime: bool,
        script_server: bool,
        cleaner: Any,
        print_: Any,
    ):
        self.root = Path(root)
        self.path = Path(work_path).expanduser() if work_path else self.root.joinpath("Volume")
        self.temp = self.path.joinpath("Temp")
        self.data = self.path.joinpath("Data")
        self.folder = self.path.joinpath(folder_name or "Download")
        self.chunk = chunk if isinstance(chunk, int) and chunk > 0 else 1024 * 1024
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.cookie = cookie or ""
        self.proxy = proxy
        self.timeout = timeout if isinstance(timeout, int) and timeout > 0 else 10
        self.retry = max_retry if isinstance(max_retry, int) and max_retry > 0 else 5
        self.record_data = bool(record_data)
        self.image_format = (image_format or "PNG").lower()
        self.image_download = bool(image_download)
        self.video_download = bool(video_download)
        self.live_download = bool(live_download)
        self.download_record = bool(download_record)
        self.folder_mode = bool(folder_mode)
        self.author_archive = bool(author_archive)
        self.write_mtime = bool(write_mtime)
        self.script_server = bool(script_server)
        self.cleaner = cleaner
        self.print = print_
        self.name_format = name_format or "发布时间 作者昵称 作品标题"
        self.headers = {
            "User-Agent": self.user_agent,
            "Referer": "https://www.xiaohongshu.com/",
            "Cookie": self.cookie,
        }
        self.blank_headers = {"User-Agent": self.user_agent}
        self._create_directories()
        client_args = {
            "timeout": self.timeout,
            "follow_redirects": True,
            "trust_env": False,
        }
        if isinstance(proxy, str) and proxy:
            client_args["proxy"] = proxy
        self.request_client = httpx.AsyncClient(**client_args)
        self.download_client = httpx.AsyncClient(**client_args)

    def _create_directories(self) -> None:
        self.temp.mkdir(parents=True, exist_ok=True)
        self.data.mkdir(parents=True, exist_ok=True)
        self.folder.mkdir(parents=True, exist_ok=True)

    def filter_name(self, name: str, default: str = "") -> str:
        if not name:
            return default
        value = self.INVALID_NAME.sub("_", str(name))
        value = re.sub(r"_+", "_", value).strip("_. ")
        return value or default

    def archive(self, folder: Path, filename: str, folder_mode: bool) -> Path:
        if folder_mode:
            return folder.joinpath(self.filter_name(filename, "untitled"))
        return folder

    def move(self, temp: Path, target: Path, mtime: int | None = None, write_mtime: bool = False) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        shutil.move(str(temp.resolve()), str(target.resolve()))
        if write_mtime and mtime:
            with suppress(Exception):
                Path(target).touch()
                timestamp = int(mtime / 1000) if mtime > 10_000_000_000 else int(mtime)
                import os

                os.utime(target, (timestamp, timestamp))

    @staticmethod
    def delete(path: Path) -> None:
        if path.exists():
            path.unlink()

    def print_proxy_tip(self) -> None:
        if self.proxy:
            logging(self.print, f"Proxy enabled: {self.proxy}", INFO)

    async def close(self) -> None:
        await self.request_client.aclose()
        await self.download_client.aclose()


class _SQLiteStore:
    table = ""
    schema = ""

    def __init__(self, manager: Manager):
        self.manager = manager
        self.file = manager.data.joinpath("XHSDownloader.db")
        self.database = None
        self.cursor = None

    async def __aenter__(self):
        await self._connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.cursor is not None:
            await self.cursor.close()
            self.cursor = None
        if self.database is not None:
            await self.database.close()
            self.database = None

    async def _connect(self) -> None:
        if self.database is not None:
            return
        self.manager.data.mkdir(parents=True, exist_ok=True)
        self.database = await aiosqlite.connect(self.file)
        self.cursor = await self.database.cursor()
        await self.database.execute(self.schema)
        await self.database.commit()


class IDRecorder(_SQLiteStore):
    table = "download_ids"
    schema = "CREATE TABLE IF NOT EXISTS download_ids (id TEXT PRIMARY KEY)"

    async def add(self, id_: str) -> None:
        if not self.manager.download_record:
            return
        await self._connect()
        await self.database.execute("INSERT OR IGNORE INTO download_ids (id) VALUES (?)", (id_,))
        await self.database.commit()

    async def select(self, id_: str):
        if not self.manager.download_record:
            return None
        await self._connect()
        cursor = await self.database.execute("SELECT id FROM download_ids WHERE id = ?", (id_,))
        return await cursor.fetchone()

    async def delete(self, ids: list[str]) -> None:
        await self._connect()
        await self.database.executemany("DELETE FROM download_ids WHERE id = ?", [(i,) for i in ids])
        await self.database.commit()


class DataRecorder(_SQLiteStore):
    table = "note_data"
    schema = """
    CREATE TABLE IF NOT EXISTS note_data (
        id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        created_at INTEGER NOT NULL
    )
    """

    async def add(self, **data) -> None:
        await self._connect()
        note_id = str(data.get("作品ID") or data.get("noteId") or int(time.time() * 1000))
        await self.database.execute(
            "REPLACE INTO note_data (id, payload, created_at) VALUES (?, ?, ?)",
            (note_id, json.dumps(data, ensure_ascii=False), int(time.time())),
        )
        await self.database.commit()


class MapRecorder(_SQLiteStore):
    table = "author_mapping"
    schema = """
    CREATE TABLE IF NOT EXISTS author_mapping (
        author_id TEXT PRIMARY KEY,
        alias TEXT NOT NULL
    )
    """

    async def get(self, author_id: str):
        await self._connect()
        cursor = await self.database.execute(
            "SELECT alias FROM author_mapping WHERE author_id = ?",
            (author_id,),
        )
        return await cursor.fetchone()

    async def set(self, author_id: str, alias: str) -> None:
        await self._connect()
        await self.database.execute(
            "REPLACE INTO author_mapping (author_id, alias) VALUES (?, ?)",
            (author_id, alias),
        )
        await self.database.commit()


class Mapping:
    def __init__(self, manager: Manager, recorder: MapRecorder):
        self.manager = manager
        self.recorder = recorder

    async def update_cache(self, author_id: str, alias: str) -> None:
        if self.manager.author_archive:
            await self.recorder.set(author_id, alias)


class Settings:
    DEFAULT = {
        "mapping_data": {},
        "work_path": "",
        "folder_name": "Download",
        "name_format": "发布时间 作者昵称 作品标题",
        "user_agent": DEFAULT_USER_AGENT,
        "cookie": "",
        "proxy": None,
        "timeout": 10,
        "chunk": 1024 * 1024,
        "max_retry": 5,
        "record_data": False,
        "image_format": "PNG",
        "image_download": True,
        "video_download": True,
        "live_download": False,
        "folder_mode": False,
        "download_record": True,
        "author_archive": False,
        "write_mtime": False,
        "language": "zh_CN",
        "read_cookie": None,
        "script_server": False,
        "script_host": "0.0.0.0",
        "script_port": 5558,
    }

    def __init__(self, root: Path):
        self.root = Path(root)
        self.file = self.root.joinpath("settings.yaml")

    def run(self) -> dict[str, Any]:
        if not self.file.exists():
            self.update(self.DEFAULT)
            return dict(self.DEFAULT)
        with self.file.open("r", encoding="utf-8") as file:
            data = safe_load(file) or {}
        result = dict(self.DEFAULT) | data
        if result != data:
            self.update(result)
        return result

    def update(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.file.open("w", encoding="utf-8") as file:
            dump(data, file, allow_unicode=True, sort_keys=False)


class ScriptServer:
    def __init__(self, app: Any, host: str, port: int):
        self.app = app
        self.host = host
        self.port = port

    async def __aenter__(self):
        logging(self.app.print, f"Script server disabled in API process: {self.host}:{self.port}", INFO)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None
