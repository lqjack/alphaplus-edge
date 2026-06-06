# -*- encoding: utf-8 -*-
# !/usr/bin/python3
from dotenv import load_dotenv
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

VERSION = "0.1.0"

from core.tools.files import get_project_root, get_cache_directory

path = os.path.join(get_project_root(), ".env")
# Process/supervisor env wins; .env only fills unset keys (avoids stale mysql overrides).
load_dotenv(dotenv_path=path, override=False)


def _csv_env_or_list(value):
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []

# 从环境变量中读取配置
MONITOR_ERROR = os.getenv("MONITOR_ERROR", "False").lower() == "true"
SLEEP_TIME = int(os.getenv("SLEEP_TIME", 5))
DEV_SLEEP_TIME = int(os.getenv("DEV_SLEEP_TIME", 10))
UPDATE_DELAY = int(os.getenv("UPDATE_DELAY", 10))
UPDATE_STOP = int(os.getenv("UPDATE_STOP", 60))

TEXT_PROCESSOR_FONT_PATH = os.getenv("TEXT_PROCESSOR_FONT_PATH", "arial.ttf")
TEXT_PROCESSOR_MAX_WIDTH = int(os.getenv("TEXT_PROCESSOR_MAX_WIDTH", 100))
TTS_VOICE = os.getenv("TTS_VOICE", "zh-CN-YunxiNeural")
TTS_OUTPUT_DIR = os.getenv("TTS_OUTPUT_DIR", get_cache_directory())

DOUYIN_ACCESS_TOKEN = os.getenv("DOUYIN_ACCESS_TOKEN")
DOUYIN_APP_ID = os.getenv("DOUYIN_APP_ID")

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "lqjacklee@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "lqjacklee1!ABcd../")

USER_AGENT_WECHAT = os.getenv(
    "USER_AGENT_WECHAT",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.116 Safari/537.36 QBCore/3.53.1159.400 QQBrowser/9.0.2524.400 Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 MicroMessenger/6.5.2.501 NetType/WIFI WindowsWechat",
)
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
)

CHECK_HEADER = {
    "User-Agent": os.getenv(
        "CHECK_HEADER_USER_AGENT",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0",
    ),
    "Accept": os.getenv("CHECK_HEADER_ACCEPT", "*/*"),
    "Connection": os.getenv("CHECK_HEADER_CONNECTION", "keep-alive"),
    "Accept-Language": os.getenv("CHECK_HEADER_ACCEPT_LANGUAGE", "zh-CN,zh;q=0.8"),
}
RESOLUTION = os.getenv("resolution", "1080x1920")
DEV_MODE = os.getenv("DEV_MODE", "pro")
SERVER_TYPE = os.getenv("SERVER_TYPE", "simple")
PERFORMANCE_MODE = os.getenv("PERFORMANCE_MODE", "True").lower() == "true"
TRIAL_MODEL = os.getenv("TRIAL_MODEL", "False").lower() == "true"
DB_TYPE = os.getenv("DB_TYPE", "postgresql")  # postgresql, sqlite, or mongo
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/dataproai")

from core.database_url import (
    resolve_database_url,
    is_postgresql_url,
    is_sqlite_url,
    infer_db_type_from_url,
    ensure_sql_driver,
)

# Back-compat alias — historically MYSQL_CONFIG held any SQLAlchemy URL.
DATABASE_URL = resolve_database_url()
MYSQL_CONFIG = DATABASE_URL

if DB_TYPE == "mongo":
    MYSQL_CONFIG = None
elif os.getenv("TRIAL_MODEL", "False").lower() == "true":
    MYSQL_CONFIG = "sqlite:///:memory:"
    DATABASE_URL = MYSQL_CONFIG
elif DB_TYPE == "sqlite":
    from core.tools.files import find_root_directory

    current_script_path = Path(__file__).resolve()
    root_directory = find_root_directory(current_script_path)
    db_path = os.path.join(root_directory, "data", "dataproai.db")
    DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("MYSQL_CONFIG") or f"sqlite:///{db_path}"
    MYSQL_CONFIG = DATABASE_URL
elif not is_postgresql_url(DATABASE_URL) and not is_sqlite_url(DATABASE_URL):
    # Legacy mysql URL in env until migrate completes — still accepted via resolve_database_url().
    pass

# Keep DB_TYPE aligned with the resolved URL (PostgreSQL deploys must not stay on mysql).
if DB_TYPE != "mongo":
    inferred = infer_db_type_from_url(DATABASE_URL)
    if inferred != DB_TYPE:
        DB_TYPE = inferred

# PyMySQL is optional — only required for mysql+pymysql URLs.
if DB_TYPE != "mongo":
    ensure_sql_driver(DATABASE_URL)

WX_UPDATE_TIME = 60 * 60 * 24 * 1  # 对文章数据更新的频次， 默认一天更新一轮
WX_NOT_UPDATE_TIME = (
    60 * 60 * 24 * 3
)  # 停止文章数据更新的最大时间期限， 默认更新三天内的数据

PROXY_LISTEN_HOST = os.getenv("PROXY_LISTEN_HOST", "0.0.0.0")
PROXY_PORT = os.getenv("PROXY_PORT", 10500)
PROXY_LOCAL_TARGET = os.getenv("PROXY_LOCAL_TARGET", f"127.0.0.1:{PROXY_PORT}")

SHELL_PATH = os.getenv("SHELL_PATH", "/bin/zsh")
CUSTOM_CA_PATH = os.getenv("CUSTOM_CA_PATH", "conf/.mitmproxy")

WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
REQUEST_HOST = os.getenv("REQUEST_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", 10000))
WEB_SOCKETIO_PORT = int(os.getenv("WEB_SOCKETIO_PORT", 5001))

WEB_UWSGI_PROCESSES = int(os.getenv("WEB_UWSGI_PROCESSES", "1"))
WEB_UWSGI_THREAD = int(os.getenv("WEB_UWSGI_THREAD", "2"))
WEB_UWSGI_LOG_PATH = os.getenv("WEB_UWSGI_LOG_PATH", "logs/uwsgi/app.log")

ENABLE_MONITOR_SERVICE = os.getenv("ENABLE_MONITOR_SERVICE", "False").lower() == "true"
ENABLE_PROXY_SERVICE = os.getenv("ENABLE_PROXY_SERVICE", "False").lower() == "true"
ENABLE_SOCKETIO = os.getenv("ENABLE_SOCKETIO", "False").lower() == "true"
ENABLE_THREAD = os.getenv("ENABLE_THREAD", "True").lower() == "true"

USER_ACCOUNT_DAILY_READ_LIMIT = int(os.getenv("USER_ACCOUNT_DAILY_READ_LIMIT", 5000))
USER_ACCOUNT_DAILY_TOTAL_READ_LIMIT = int(
    os.getenv("USER_ACCOUNT_DAILY_TOTAL_READ_LIMIT", 50000)
)

PROXY_HEALTH_CHECK_TARGET_URL = os.getenv(
    "PROXY_HEALTH_CHECK_TARGET_URL", "http://www.baidu.com"
)
FETCH_REMOTE_IP_PROXY_URL = os.getenv(
    "FETCH_REMOTE_IP_PROXY_URL", "http://127.0.0.1:5010/get/"
)

VERIFY_TIMEOUT = int(os.getenv("VERIFY_TIMEOUT", 10))
USE_PROXY = os.getenv("USE_PROXY", "False").lower() == "true"
THREAD_POOL_MAX_WORKER = int(os.getenv("THREAD_POOL_MAX_WORKER", 6))
CUSTOM_UWSGI_PATH = os.getenv("CUSTOM_UWSGI_PATH", "conf/uwsgi.ini")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

TELEGRAM_BOT_API_TOKEN = os.getenv(
    "TELEGRAM_BOT_API_TOKEN", "7603720247:AAHOVnl5T_KGHO74OHXCrKWpb6C3AFEAWMo"
)

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
WHITELISTED_FILE_TYPES = os.getenv(
    "WHITELISTED_FILE_TYPES",
    [
        ".csv",
        ".doc",
        ".docx",
        ".epub",
        ".image",
        ".md",
        ".msg",
        ".odt",
        ".org",
        ".pdf",
        ".ppt",
        ".pptx",
        ".rtf",
        ".rst",
        ".tsv",
        ".xlsx",
    ],
)
WHITELISTED_FILE_TYPES = _csv_env_or_list(WHITELISTED_FILE_TYPES)

SKIP_CHECK = os.getenv("SKIP_CHECK", "True").lower() == "true"

AI_MODEL = os.getenv("AI_MODEL", "deepseek")

# Web Server Configuration
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", 10000))
CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5050,http://127.0.0.1:5050,http://localhost:8000,http://127.0.0.1:8000,http://localhost:10000,http://127.0.0.1:10000",
).split(",")
ENABLE_SOCKETIO = os.getenv("ENABLE_SOCKETIO", "True").lower() == "true"
AI_REQUEST_MODEL = os.getenv("AI_REQUEST_MODEL", "deepseek-chat")
# AI_KEY must come from the environment. Earlier versions shipped a real
# DeepSeek-style fallback ("sk-...") which leaked the credential through
# git history — that key has been rotated and removed (see issue #90).
AI_KEY = os.getenv("AI_KEY", "")

LM_ANALYZE_UPPER_LIMIT = int(os.getenv("LM_ANALYZE_UPPER_LIMIT", 20000))
LOG_VERBOSE_ENABLED = os.getenv("LOG_VERBOSE_ENABLED", "True").lower() == "true"

PROXY_ALLOW_HOSTS = os.getenv("PROXY_ALLOW_HOSTS", "mp.weixin.qq.com").split(",")

creds_file = os.getenv("CREDS_FILE", "conf/google-auth/credentials.json")
token_file = os.getenv("TOKEN_FILE", "conf/google-auth/token.pickle")


class TTSConfig:
    """TTS 配置类"""

    @property
    def VOICE(self) -> str:
        return os.getenv("TTS_VOICE", "zh-CN-YunxiNeural")

    @property
    def OUTPUT(self) -> str:
        return os.getenv("OUTPUT", get_cache_directory() + "/tts")

    @property
    def RATE(self) -> str:
        return os.getenv("TTS_RATE", "+0%")

    @property
    def VOLUME(self) -> str:
        return os.getenv("TTS_VOLUME", "+0%")

    @property
    def PITCH(self) -> str:
        return os.getenv("TTS_PITCH", "+0Hz")

    @property
    def CACHE_DIR(self) -> Path:
        return Path(os.getenv("TTS_CACHE_DIR", "/tts_cache"))

    @property
    def TIMEOUT(self) -> int:
        return int(os.getenv("TTS_TIMEOUT", "30"))

    @property
    def PROXY(self) -> Optional[str]:
        return os.getenv("TTS_PROXY") or None

    @property
    def MAX_TEXT_LENGTH(self) -> int:
        return int(os.getenv("TTS_MAX_TEXT_LENGTH", "5000"))

    @property
    def AUTO_PLAY(self) -> bool:
        return os.getenv("TTS_AUTO_PLAY", "false").lower() == "true"

    def as_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "voice": self.VOICE,
            "rate": self.RATE,
            "volume": self.VOLUME,
            "pitch": self.PITCH,
            "cache_dir": str(self.CACHE_DIR),
            "timeout": self.TIMEOUT,
            "proxy": self.PROXY,
            "max_text_length": self.MAX_TEXT_LENGTH,
            "auto_play": self.AUTO_PLAY,
        }


# 实例化配置对象
TTS_SETTINGS = TTSConfig()


class VideoSettings:
    def __init__(self):
        # TTS 配置
        self.tts_engine: str = os.getenv("TTS_ENGINE", "edge")
        self.tts_voice: str = os.getenv("TTS_VOICE", "zh-CN-YunxiNeural")
        self.tts_rate: str = os.getenv("TTS_RATE", "+10%")
        self.base = os.path.join(get_project_root(), "resources")
        # 视频参数
        self.video_resolution: str = os.getenv("VIDEO_RESOLUTION", "1080x1920")
        self.video_duration: int = int(os.getenv("VIDEO_DURATION", "15"))
        self.video_font: str = os.getenv(
            "VIDEO_FONT", self.base + "/fonts/Alibaba-PuHuiTi-Regular.ttf"
        )

        # 素材路径
        self.assets_bg_videos: str = os.getenv(
            "ASSETS_BG_VIDEOS", self.base + "/bg_videos/"
        )
        self.assets_bg_music: str = os.getenv(
            "ASSETS_BG_MUSIC", self.base + "/bg_music/default.mp3"
        )

        self.output: str = os.getenv("VIDEO_OUTPUT", get_cache_directory() + "/videos")

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式"""
        return {
            "tts": {
                "engine": self.tts_engine,
                "voice": self.tts_voice,
                "rate": self.tts_rate,
            },
            "video": {
                "resolution": self.video_resolution,
                "duration": self.video_duration,
                "font": self.video_font,
            },
            "assets": {
                "bg_videos": self.assets_bg_videos,
                "bg_music": self.assets_bg_music,
            },
        }


# 创建全局配置实例
VIDEO_SETTINGS = VideoSettings()

WHITLE_ALLOWED_FILE_TYPES = [
    ".csv",
    ".doc",
    ".docx",
    ".epub",
    ".image",
    ".md",
    ".msg",
    ".odt",
    ".org",
    ".pdf",
    ".ppt",
    ".pptx",
    ".rtf",
    ".rst",
    ".tsv",
    ".xlsx",
]

ALLOWED_FILE_TYPES = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"],
    "video": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
    "text": [".txt", ".csv", ".log"],
    "pdf": [".pdf"],
    "word": [".doc", ".docx"],
    "excel": [".xls", ".xlsx"],
    "powerpoint": [".ppt", ".pptx"],
    "archive": [".zip", ".rar", ".tar", ".gz"],
}


TASK_TYPE_MAP = {
    "weixin": ["History", "Article", "AIAnalysis"],
    "youtube": ["YouTubeSync", "AIAnalysis"],
    "bilibili": ["BilibiliSync", "AIAnalysis"],
    "telegram": ["TelegramSync", "AIAnalysis"],
    "douyin": ["DouyinSync", "AIAnalysis"],
    "cls": ["CLSSync", "AIAnalysis"],
}

SINGLE_TASK_TYPE_MAP = {
    "weixin": "Article",
    "youtube": "YouTubeSync",
    "bilibili": "BilibiliSync",
    "telegram": "TelegramSync",
    "douyin": "DouyinSync",
    "cls": "CLSSync",
    "file": "FileSync",
    "ai": "AIAnalysis",
}

plugin_map = {
    "history": "History",
    "article": "Article",
    "weixin": "Article",
    "comment": "Comment",
    "subtitles_generator": "subtitles_generator",
    "douyin_publisher": "douyin_publisher",
    "video_editor": "video_editor",
    "video_generator": "video_generator",
    "tts_engine": "tts_engine",
    "read_like": "ReadLike",
    "youtube": "YouTubeSync",
    "telegram": "TelegramSync",
    "cls": "CLSSync",
    "file": "FileSync",
    "key_manager": "KeyManager",
    "ai_analysis": "AIAnalysis",
    "ai": "AIAnalysis",
}

model_configs = {
    "o1": {
        "model_path": "openai/o1",
        "kwargs": {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "temperature": 1.0,
            "top_p": 0.9,
            "max_tokens": 8192,
        },
    },
    "gpt-4o": {
        "model_path": "openai/gpt-4o",
        "kwargs": {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "temperature": 1.0,
            "top_p": 0.9,
        },
    },
    "deepseek-reasoner": {
        "model_path": "openai/deepseek-reasoner",
        "kwargs": {
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "temperature": 1.0,
            "top_p": 0.9,
        },
    },
    "deepseek": {
        "model_path": "deepseek/deepseek-chat",
        "kwargs": {
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "temperature": 1.0,
            "max_tokens": 3000,
            "api_base": "https://api.deepseek.com/v1",
            "top_p": 0.9,
        },
    },
    "openrouter": {
        "model_path": "openrouter/deepseek/deepseek-r1",
        "kwargs": {
            "api_key": os.getenv("OPENROUTER_API_KEY"),
            "temperature": 1.0,
            "top_p": 0.9,
        },
    },
    "kim_web": {
        "model_path": "kim_web/kim",
        "kwargs": {
            "api_key": os.getenv("MOONSHOT_API_KEY"),
            "temperature": 1.0,
            "top_p": 0.9,
        },
    },
    "deepseek_web": {
        "model_path": "deepseek-r1",
        "kwargs": {
            "api_key": os.getenv("MOONSHOT_API_KEY"),
            "temperature": 1.0,
            "top_p": 0.9,
        },
    },
    "chain": {
        "model_path": "deepseek/deepseek-chat",
        "kwargs": {
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "temperature": 1.0,
            "max_tokens": 3000,
            "api_base": "https://api.deepseek.com/v1",
            "top_p": 0.9,
        },
    },
}

# WeChat monitoring configuration
WECHAT_MONITORING_INTERVAL_SECONDS = int(
    os.getenv("WECHAT_MONITORING_INTERVAL_SECONDS", 3)
)
WECHAT_MONITORING_MAX_ARTICLES = int(os.getenv("WECHAT_MONITORING_MAX_ARTICLES", 3))
WECHAT_MONITORING_ENABLED = (
    os.getenv("WECHAT_MONITORING_ENABLED", "True").lower() == "true"
)
WECHAT_MONITORING_EXPIRED_ACCOUNT_IDS = (
    os.getenv("WECHAT_MONITORING_EXPIRED_ACCOUNT_IDS", "").split(",")
    if os.getenv("WECHAT_MONITORING_EXPIRED_ACCOUNT_IDS")
    else []
)

# CORS 配置
CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5050,http://127.0.0.1:5050,http://localhost:8000,http://127.0.0.1:8000,http://localhost:10000,http://127.0.0.1:10000,*",
).split(",")
