# -*- encoding: utf-8 -*-
import os
from datetime import datetime
from typing import Optional

from storage import models
from api.main import db
from core.tools.times import format_datetime

# 全局缓存
_db_type = None

def get_db_type() -> str:
    global _db_type
    if _db_type is None:
        _db_type = os.getenv("DB_TYPE", "sqlite").lower()
    return _db_type

def get_account(account_id) -> Optional[models.Account]:
    return models.Account.get_account(account_id)

def get_article(article_id) -> Optional[models.Article]:
    with db.session.no_autoflush:
        return models.Article.query.get(article_id)

def save_task_status(task_id, status, result=None, commit=True):
    with db.session.no_autoflush:
        task = models.JobTask.query.get(task_id)
        if not task:
            return
        task.status = status
        if result is not None:
            task.result = result
        task.updated_at = datetime.utcnow()
        if commit:
            db.session.commit()

# ---------------- 删除与计数（SQL） ----------------
def delete_article_sql(article_id, account_id) -> int:
    with db.session.no_autoflush:
        deleted = models.Article.query.filter_by(id=article_id).delete()
        if deleted > 0:
            # 重新统计
            from sqlalchemy import func
            article_count = db.session.query(func.count(models.Article.id)).filter(
                models.Article.account_id == account_id
            ).scalar()
            account = models.Account.query.filter_by(id=account_id).first()
            if account:
                account.counts = article_count
                account.update = str(int(datetime.utcnow().timestamp()))
        db.session.commit()
        return deleted

def delete_articles_by_account_sql(account_id) -> int:
    with db.session.no_autoflush:
        deleted = models.Article.query.filter_by(account_id=account_id).delete()
        if deleted > 0:
            account = models.Account.query.filter_by(id=account_id).first()
            if account:
                account.counts = 0
                account.update = str(int(datetime.utcnow().timestamp()))
        db.session.commit()
        return deleted

def sync_account_counts_sql(account_id) -> bool:
    from sqlalchemy import func
    with db.session.no_autoflush:
        article_count = db.session.query(func.count(models.Article.id)).filter(
            models.Article.account_id == account_id
        ).scalar()
        account = models.Account.query.filter_by(id=account_id).first()
        if account:
            account.counts = article_count
            account.update = str(int(datetime.utcnow().timestamp()))
            db.session.commit()
            return True
        return False

# ---------------- Mongo 同步写入 ----------------
def _mongo_sync_article_delete(article_id: int, account_id: int):
    try:
        from mongoengine import connection
        if not connection.get_db():
            return
        MongoArticle.objects(id=article_id).delete()
    except Exception:
        pass

def _mongo_sync_articles_delete_by_account(account_id: int):
    try:
        from mongoengine import connection
        if not connection.get_db():
            return
        MongoArticle.objects(account_id=account_id).delete()
    except Exception:
        pass

def _mongo_sync_account_counts(account_id: int):
    try:
        from mongoengine import connection
        if not connection.get_db():
            return
        from storage.models_mongo import MongoAccount, MongoArticle
        cnt = MongoArticle.objects(account_id=account_id).count()
        MongoAccount.objects(account_id_unique=str(account_id)).update_one(
            set__counts=cnt, set__update_timestamp=str(int(datetime.utcnow().timestamp()))
        )
    except Exception:
        pass

def _mongo_sync_infosource(info_source: models.InfoSource):
    try:
        from mongoengine import connection
        if not connection.get_db():
            return
        from storage.models_mongo import MongoInfoSource
        MongoInfoSource(
            id=info_source.id,
            source_type=info_source.source_type,
            content=info_source.content,
            platform=info_source.platform,
            content_processed=info_source.content_processed,
            source_id=info_source.source_id,
            source_model=info_source.source_model,
            created_at=info_source.created_at,
            updated_at=info_source.updated_at
        ).save()
    except Exception:
        pass

def _mongo_sync_analysis_result(ar: models.AnalysisResult):
    try:
        from mongoengine import connection
        if not connection.get_db():
            return
        from storage.models_mongo import MongoAnalysisResult
        MongoAnalysisResult(
            id=ar.id,
            info_source_id=ar.info_source_id,
            related_info=ar.related_info,
            hot_degree=ar.hot_degree,
            bullish_sectors=ar.bullish_sectors,
            bearish_sectors=ar.bearish_sectors,
            summary=ar.summary,
            investment_plan=ar.investment_plan,
            investment_strategy=ar.investment_strategy,
            created_at=ar.created_at,
            updated_at=ar.updated_at,
            core_viewpoint=ar.core_viewpoint,
            detailed_summary=ar.detailed_summary,
            sentiment=ar.sentiment,
            related_industries=ar.related_indctries,
            impact_scope=ar.impact_scope,
            key_metrics=ar.key_metrics,
            ai_analysis_data=ar.ai_analysis_data
        ).save()
    except Exception:
        pass

# ---------------- 创建记录（SQL -> Mongo 同步） ----------------
def create_infosource_sql(info_source: models.InfoSource) -> int:
    with db.session.no_autoflush:
        db.session.add(info_source)
        db.session.commit()
        _mongo_sync_infosource(info_source)
        return info_source.id

def create_analysisresult_sql(ar: models.AnalysisResult) -> int:
    with db.session.no_autoflush:
        db.session.add(ar)
        db.session.commit()
        _mongo_sync_analysis_result(ar)
        return ar.id