# -*- encoding: utf-8 -*-
# !/usr/bin/python3

from core.exceptions import IPError, ArticleHasBeenDeleteError
from core.tools.article_exception import KEYWORD_MAP

import logging

logger = logging.getLogger(__name__)

def _safe_api(lambda_api):
    def _api(*args, **kwargs):
        try:
            api_result = lambda_api(*args, **kwargs)
            if isinstance(api_result, dict) and api_result.get("status", 500) == 200:
                return api_result
            
            error_msg = "API Execution Failed"
            if isinstance(api_result, dict):
                error_msg = api_result.get("message", error_msg)
                
            logger.warning(f"API Execution Failed. Result: {api_result}")
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Uncaught Exception in API: {e}")
            raise e

    return _api

def check_html_api(func):
    def __wrapper(*args, **kwargs):
        res_html = func(*args, **kwargs)

        # 检查内容是否包含关键字
        for keyword, reason in KEYWORD_MAP.items():
            if keyword in res_html:
                # 根据原因抛出对应的异常
                if "ip" in reason.lower():
                    raise IPError(reason)
                else:
                    raise ArticleHasBeenDeleteError(reason)
        
        return res_html
    return __wrapper

def run_with_app(func):
    def __wrapper(*args, **kwargs):
        from api.main import app
        # Ensure database is initialized for MCP server context
        if not hasattr(app, '_db_initialized'):
            from api.main import init_database
            init_database()
            app._db_initialized = True
        with app.app_context():
            return func(*args, **kwargs)
    return __wrapper
