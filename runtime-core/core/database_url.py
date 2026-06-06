# -*- coding: utf-8 -*-
"""Resolve SQLAlchemy database URL for dataproai (PostgreSQL default)."""

from __future__ import annotations

import os
from urllib.parse import quote_plus


DEFAULT_PG_PORT = os.getenv("DATAPROAI_PG_PORT", "5432")
DEFAULT_PG_HOST = os.getenv("DATAPROAI_PG_HOST", "127.0.0.1")
DEFAULT_PG_USER = os.getenv("DATAPROAI_PG_USER", "postgres")
DEFAULT_PG_PASSWORD = os.getenv("DATAPROAI_PG_PASSWORD", "postgres")
DEFAULT_PG_DATABASE = os.getenv("DATAPROAI_PG_DATABASE", "dataproai")

DEFAULT_DATABASE_URL = (
    f"postgresql+psycopg://{quote_plus(DEFAULT_PG_USER)}:{quote_plus(DEFAULT_PG_PASSWORD)}"
    f"@{DEFAULT_PG_HOST}:{DEFAULT_PG_PORT}/{DEFAULT_PG_DATABASE}"
)


def normalize_database_url(url: str) -> str:
    """Normalize legacy driver names to psycopg v3."""
    if not url:
        return url
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url and "+psycopg2" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def resolve_database_url() -> str:
    """Primary SQLAlchemy URL (PostgreSQL). Legacy MYSQL_CONFIG still accepted."""
    for key in ("DATABASE_URL", "DATAPROAI_DATABASE_URL", "MYSQL_CONFIG"):
        value = os.getenv(key, "").strip()
        if value:
            return normalize_database_url(value)
    return DEFAULT_DATABASE_URL


def is_postgresql_url(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres://")


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite://")


def is_mysql_url(url: str) -> bool:
    return url.startswith("mysql")


def infer_db_type_from_url(url: str) -> str:
    """Infer canonical DB_TYPE from a SQLAlchemy URL."""
    if not url:
        return "postgresql"
    if is_postgresql_url(url):
        return "postgresql"
    if is_sqlite_url(url):
        return "sqlite"
    if is_mysql_url(url):
        return "mysql"
    return os.getenv("DB_TYPE", "postgresql")


def requires_mysql_driver(url: str) -> bool:
    """True when the configured URL needs the PyMySQL DBAPI."""
    return is_mysql_url(url)


def ensure_sql_driver(database_url: str) -> None:
    """Validate optional SQL drivers only when the URL needs them."""
    if not requires_mysql_driver(database_url):
        return
    try:
        import pymysql  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "MySQL is configured (mysql+pymysql URL) but pymysql is not installed. "
            "Install with: uv pip install pymysql  — or switch to PostgreSQL "
            "(DB_TYPE=postgresql, DATABASE_URL=postgresql+psycopg://...)."
        ) from exc
