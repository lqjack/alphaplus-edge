import importlib
import inspect
# 动态加载函数并执行
def execute_function(fun_path, task_args):
    module_name, function_name = fun_path.rsplit('.', 1)
    module = importlib.import_module(module_name)
    function = getattr(module, function_name)
    return function(**task_args)


def get_function_path(func):
    module_name = inspect.getmodule(func).__name__
    function_name = func.__name__
    return f"{module_name}.{function_name}"