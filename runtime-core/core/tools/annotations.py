startup_tasks = []
shutdown_tasks = []

def startup_before(priority=100):
    """标记在启动前执行的函数，并指定优先级"""

    def decorator(func):

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._is_startup_task = True
        wrapper.__annotations__['startup_before'] = True
        wrapper._original_function = func
        wrapper._priority = priority
        return wrapper
    return decorator

def shutdown_before(priority=100):
    """标记在关闭前执行的函数，并指定优先级"""

    def decorator(func):
        """---
    tags:
      - API
    summary: /api/platform/list
    description: 自动生成的 API 文档
    parameters: []
    responses:
      200:
        description: 成功响应
      400:
        description: 错误请求"""

        def wrapper(*args, **kwargs):
            """---
    tags:
      - API
    summary: /api/youtube/auth/init
    description: 自动生成的 API 文档
    parameters: []
    responses:
      200:
        description: 成功响应
      400:
        description: 错误请求"""
            return func(*args, **kwargs)
        wrapper._is_shutdown_task = True
        wrapper.__annotations__['shutdown_before'] = True
        wrapper._original_function = func
        wrapper._priority = priority
        return wrapper
    return decorator

def json_api_wrapper(func):
    """
    Decorator to wrap Flask route functions for consistent JSON response formatting.
    Handles both successful responses and errors.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        """---
    tags:
      - API
    summary: /api/feature/status
    description: 自动生成的 API 文档
    parameters: []
    responses:
      200:
        description: 成功响应
      400:
        description: 错误请求"""
        from flask import jsonify
        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict) and 'success' in result:
                return jsonify(result)
            from flask import Response
            if isinstance(result, Response):
                return result
            if isinstance(result, tuple):
                return result
            return jsonify({'success': True, 'data': result, 'message': 'Operation completed successfully'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return (jsonify({'success': False, 'error': str(e), 'message': 'An error occurred'}), 500)
    return wrapper