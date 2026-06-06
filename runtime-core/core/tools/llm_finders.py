# 全局任务列表
llms = []

registered_llms = []

# 启动前注解
def llm(priority=100, name='', env=''):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._is_startup_task = True  
        wrapper.__annotations__["llm"] = True
        wrapper._original_function = func
        wrapper._priority = priority
        wrapper._name = name
        wrapper._env = env
        return wrapper
    return decorator