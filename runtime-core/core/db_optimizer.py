# -*- coding: utf-8 -*-
"""
Database Initialization Optimizer
Optimizes database initialization performance by avoiding redundant operations.
"""

import logging
import time
import os
from typing import Dict, List, Any
from sqlalchemy import inspect, text

try:
    from alembic.config import Config
except Exception:
    Config = None
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from loguru import logger


class DatabaseOptimizer:
    """Database initialization performance optimizer"""

    def __init__(self):
        self._migration_cache: Dict[str, bool] = {}
        self._table_cache: Dict[str, bool] = {}
        self._init_times: Dict[str, float] = {}

    def get_alembic_config(self, bind_key=None):
        """获取alembic配置"""
        alembic_cfg = Config()
        from core.tools.files import get_cache_directory

        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        script_location = os.path.join(project_root, "migrations")
        alembic_cfg.set_main_option("script_location", script_location)
        if bind_key:
            from core.settings import MYSQL_CONFIG
            from flask import current_app

            alembic_cfg.set_main_option(
                "sqlalchemy.url", current_app.config["SQLALCHEMY_BINDS"][bind_key]
            )
        else:
            # For single database mode
            from core.settings import DATABASE_URL

            alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        return alembic_cfg

    def needs_upgrade_cached(self, engine, bind_key=None):
        """检查是否需要升级数据库（带缓存）"""
        cache_key = f"upgrade_check_{bind_key or 'default'}"

        # 检查缓存
        if cache_key in self._migration_cache:
            return self._migration_cache[cache_key]

        try:
            alembic_cfg = self.get_alembic_config(bind_key)
            script = ScriptDirectory.from_config(alembic_cfg)
            with engine.connect() as conn:
                context = MigrationContext.configure(conn)
                needs_upgrade = (
                    context.get_current_revision() != script.get_current_head()
                )

                # 缓存结果
                self._migration_cache[cache_key] = needs_upgrade
                return needs_upgrade
        except Exception as e:
            logger.warning(f"Migration check failed for {bind_key}: {e}")
            return False

    def has_table_cached(self, engine, table_name):
        """检查表是否存在（带缓存）"""
        cache_key = f"table_exists_{table_name}"

        # 检查缓存
        if cache_key in self._table_cache:
            return self._table_cache[cache_key]

        try:
            inspector = inspect(engine)
            has_table = inspector.has_table(table_name)

            # 缓存结果
            self._table_cache[cache_key] = has_table
            return has_table
        except Exception as e:
            logger.warning(f"Table check failed for {table_name}: {e}")
            return False

    def batch_init_database(self, app):
        """批量数据库初始化 - 避免重复检查"""
        start_time = time.time()

        db_type, database_url = self._resolve_database_config(app)
        from core.database_url import ensure_sql_driver

        ensure_sql_driver(database_url or "")
        if db_type == "mongo":
            logger.info("MongoDB mode - skipping SQL database initialization")
            return

        if not database_url:
            logger.info("No SQL config - skipping database initialization")
            return

        with app.app_context():
            if database_url.startswith("sqlite://"):
                # 为SQLite创建数据库目录
                from core.tools.files import get_cache_directory

                db_dir = os.path.join(get_cache_directory(), "dbs")
                os.makedirs(db_dir, exist_ok=True)

                # 批量初始化所有绑定的数据库
                self._batch_init_sqlite_databases(app)
            else:
                # Single-database mode (PostgreSQL / legacy MySQL)
                self._batch_init_relational_database(app)

        elapsed = time.time() - start_time
        logger.info(f"Batch database initialization completed in {elapsed:.2f}s")
        self._init_times["batch_init"] = elapsed

    def _batch_init_sqlite_databases(self, app):
        """批量初始化SQLite数据库"""
        db = self._get_db(app)

        # 获取所有模型
        models = self._get_all_models(db)
        logger.info(f"Found {len(models)} models to initialize")

        # 按数据库分组
        model_groups = {}
        for model in models:
            bind_key = model.__name__
            if bind_key not in model_groups:
                model_groups[bind_key] = []
            model_groups[bind_key].append(model)

        # 批量处理每个数据库
        for bind_key, model_group in model_groups.items():
            try:
                engine = db.get_engine(app, bind=bind_key)
                self._init_single_database(engine, model_group, bind_key)
            except Exception as e:
                logger.error(f"Failed to initialize database {bind_key}: {e}")

    def _batch_init_relational_database(self, app):
        """Batch-init PostgreSQL/MySQL/SQLite from SQLAlchemy models."""
        db = self._get_db(app)

        # 获取所有模型
        models = self._get_all_models(db)
        logger.info(f"Found {len(models)} models to initialize")

        try:
            engine = db.get_engine()

            # 导入模型以确保注册
            try:
                from storage import models
            except ImportError as e:
                logger.warning(f"Could not import storage.models: {e}")
            except Exception as e:
                logger.error(f"Error importing models: {e}")

            # 只执行一次迁移检查
            if self.needs_upgrade_cached(engine):
                logger.info("Database schema upgrade needed, running migrations...")
                from alembic import command

                alembic_cfg = self.get_alembic_config()
                command.upgrade(alembic_cfg, "head")
                logger.info("Database schema upgraded successfully")
            else:
                logger.info("Database schema is up-to-date")

            self._ensure_article_url_columns(engine)

            # 缓存迁移状态
            self._migration_cache["default"] = False

        except Exception as e:
            logger.warning(
                f"Database migration check failed, falling back to basic init: {e}"
            )
            # Fallback to create tables that don't exist
            try:
                db.create_all()
                self._ensure_article_url_columns(db.get_engine())
                logger.info("Fallback database initialization completed")
            except Exception as fallback_error:
                logger.error(f"Fallback initialization also failed: {fallback_error}")

    def _init_single_database(self, engine, models, bind_key):
        """初始化单个数据库"""
        start_time = time.time()

        for model in models:
            table_name = model.__tablename__

            # 使用缓存检查表是否存在
            if not self.has_table_cached(engine, table_name):
                try:
                    # 表不存在，直接创建
                    model.__table__.create(bind=engine)
                    logger.info(f"Created table: {table_name}")
                except Exception as e:
                    logger.error(f"Failed to create table {table_name}: {e}")
            else:
                # 表已存在，检查是否需要升级
                if self.needs_upgrade_cached(engine, bind_key):
                    try:
                        from alembic import command

                        alembic_cfg = self.get_alembic_config(bind_key)
                        command.upgrade(alembic_cfg, "head")
                        logger.info(f"Upgraded table: {table_name}")
                    except Exception as e:
                        logger.error(f"Failed to upgrade table {table_name}: {e}")
                else:
                    logger.info(f"Table already exists and up-to-date: {table_name}")

        elapsed = time.time() - start_time
        logger.info(f"Database {bind_key} initialization completed in {elapsed:.2f}s")
        self._init_times[bind_key] = elapsed

    def _get_all_models(self, db):
        """获取所有注册的模型类"""
        models = []
        # 获取所有SQLAlchemy模型
        for mapper in db.Model.registry.mappers:
            model = mapper.class_
            if hasattr(model, "__tablename__"):
                models.append(model)
        return models

    @staticmethod
    def _get_db(app):
        db = app.extensions.get("sqlalchemy")
        if db is not None:
            return db
        from api.main import db as app_db

        return app_db

    @staticmethod
    def _resolve_database_config(app):
        db_type = app.config.get("DB_TYPE")
        database_url = app.config.get("DATABASE_URL") or app.config.get("MYSQL_CONFIG")
        if db_type and database_url is not None:
            return db_type, database_url
        from core.settings import DB_TYPE as SETTINGS_DB_TYPE, DATABASE_URL as SETTINGS_DATABASE_URL

        return db_type or SETTINGS_DB_TYPE, database_url if database_url is not None else SETTINGS_DATABASE_URL

    @staticmethod
    def _article_url_column_resize_plan(columns):
        def _needs_text(column_name):
            column = columns.get(column_name)
            if not isinstance(column, dict):
                return False
            col_type = column.get("type")
            if col_type is None:
                return False
            length = getattr(col_type, "length", None)
            type_name = str(col_type).upper()
            if any(token in type_name for token in ("TEXT", "MEDIUMTEXT", "LONGTEXT")):
                return False
            if "VARCHAR" in type_name:
                return length is None or length < 2048
            return False

        planned = []
        for column_name in ("article_content_url", "article_source_url"):
            if _needs_text(column_name):
                planned.append(column_name)
        return planned

    def _ensure_article_url_columns(self, engine):
        try:
            inspector = inspect(engine)
            if not inspector.has_table("tb_article"):
                return
            columns = {
                column.get("name"): column
                for column in inspector.get_columns("tb_article")
                if isinstance(column, dict)
            }
            planned = self._article_url_column_resize_plan(columns)
            if not planned:
                return

            dialect_name = engine.dialect.name
            if dialect_name == "postgresql":
                statements = [
                    text(f'ALTER TABLE tb_article ALTER COLUMN {column_name} TYPE TEXT')
                    for column_name in planned
                ]
            else:
                statements = [
                    text(f"ALTER TABLE tb_article MODIFY COLUMN {column_name} TEXT NULL")
                    for column_name in planned
                ]
            with engine.begin() as conn:
                for statement in statements:
                    conn.execute(statement)
            logger.info(
                "Expanded tb_article URL columns to TEXT: {}".format(", ".join(planned))
            )
        except Exception as exc:
            logger.warning(f"Failed to expand tb_article URL columns: {exc}")

    def get_performance_stats(self):
        """获取性能统计信息"""
        return {
            "migration_cache_size": len(self._migration_cache),
            "table_cache_size": len(self._table_cache),
            "init_times": self._init_times.copy(),
            "total_init_time": sum(self._init_times.values()),
        }

    def clear_cache(self):
        """清除缓存"""
        self._migration_cache.clear()
        self._table_cache.clear()
        self._init_times.clear()
        logger.info("Database optimizer cache cleared")


# 全局优化器实例
db_optimizer = DatabaseOptimizer()


def init_database_optimized(app):
    """优化的数据库初始化函数"""
    return db_optimizer.batch_init_database(app)
