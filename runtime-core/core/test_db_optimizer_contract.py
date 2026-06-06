import sys
from pathlib import Path

from sqlalchemy import String, Text


PROJECT_SRC = Path(__file__).resolve().parents[1]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from core.db_optimizer import DatabaseOptimizer


def test_article_url_column_resize_plan_targets_legacy_varchar_columns():
    plan = DatabaseOptimizer._article_url_column_resize_plan(
        {
            "article_content_url": {"name": "article_content_url", "type": String(500)},
            "article_source_url": {"name": "article_source_url", "type": String(255)},
        }
    )

    assert plan == ["article_content_url", "article_source_url"]


def test_article_url_column_resize_plan_skips_existing_text_columns():
    plan = DatabaseOptimizer._article_url_column_resize_plan(
        {
            "article_content_url": {"name": "article_content_url", "type": Text()},
            "article_source_url": {"name": "article_source_url", "type": Text()},
        }
    )

    assert plan == []


def test_resolve_database_config_falls_back_to_settings(monkeypatch):
    class _App:
        config = {}

    monkeypatch.setattr("core.settings.DB_TYPE", "postgresql")
    monkeypatch.setattr("core.settings.DATABASE_URL", "postgresql+psycopg://demo")

    db_type, database_url = DatabaseOptimizer._resolve_database_config(_App())

    assert db_type == "postgresql"
    assert database_url == "postgresql+psycopg://demo"


def test_get_db_prefers_existing_flask_extension():
    sentinel = object()

    class _App:
        extensions = {"sqlalchemy": sentinel}

    assert DatabaseOptimizer._get_db(_App()) is sentinel
