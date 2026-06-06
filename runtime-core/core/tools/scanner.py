# scanner.py
import importlib
import pkgutil
import os
import sys
from pathlib import Path
from core.tools.files import get_project_root
from typing import Optional, Callable, Any, Dict, List
import ast
import inspect
import logging

logger = logging.getLogger(__name__)

def dynamic_import(package_name: str, max_retries: int = 2, start_module=None):
    """
    动态导入模块，自动处理路径问题
    
    参数:
        package_name: 要导入的模块名 (如 'webapp.wxapp')
        max_retries: 最大重试次数
        
    返回:
        成功则返回模块对象，失败返回None
    """
    retry_count = 0
    last_error = None
    
    while retry_count <= max_retries:
        try:
            return importlib.import_module(package_name)
        except ModuleNotFoundError as e:
            last_error = e
            if f"No module named '{package_name}'" in str(e):
                # 尝试修复路径问题
                from core.tools.files import get_project_root
                base_dir = get_project_root()
                possible_paths = [
                    os.path.join(base_dir, "src"),  # 假设项目结构为 .../src/webapp/...
                    base_dir,                     # 直接项目根目录
                ]
                
                for path in possible_paths:
                    if path not in sys.path and os.path.exists(path):
                        sys.path.insert(0, path)
                        logger.info(f"⚠️ 添加路径到sys.path: {path}")
                        break
                
                original_sys_path = sys.path.copy()
                try:
                    # 尝试常见项目结构路径
                    base_paths_to_try = [
                        os.path.dirname(os.path.abspath(__file__)),  # 当前文件所在目录
                        os.getcwd(),                                 # 当前工作目录
                        os.path.join(os.getcwd(), "src"),             # 常见的src目录
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")  # 上两级目录
                    ]
                    
                    for base_path in base_paths_to_try:
                        if not os.path.exists(base_path):
                            continue
                            
                        # 尝试将路径添加到sys.path
                        potential_path = os.path.normpath(os.path.join(base_path, *start_module.split('/')[:-1]))
                        if potential_path not in sys.path and os.path.exists(potential_path):
                            sys.path.insert(0, potential_path)
                            logger.info(f"⚠️ 尝试添加模块路径: {potential_path}")
                            
                            try:
                                package = importlib.import_module(package_name.split('.')[-1])
                                logger.info(f"✅ 成功从 {potential_path} 导入模块")
                                return package
                            except ImportError:
                                sys.path.remove(potential_path)
                                continue
                        
                finally:
                    # 恢复原始sys.path
                    sys.path = original_sys_path
                
                if 'webapp.wxapp.' == package_name:
                    package_name = 'webapp.wxapp'
                
                retry_count += 1
            else:
                break  # 其他类型的导入错误直接退出
    
    logger.info(f"❌ 导入失败 {package_name}: {last_error}")
    logger.info(f"当前sys.path: {sys.path}")
    return None

def scan_modules(start_module='callback', annotation=None, containers=[], env=False, 
                wrap_routes=False, route_decorator=None):
    """
    Scan specified package for modules and parse annotations.
    Optionally wrap Flask route functions with a decorator.
    
    Args:
        start_module (str): Base module to scan (default: 'callback')
        annotation: Annotation to look for in functions
        containers (list): List to store found functions
        env (bool): Whether to check environment variables
        wrap_routes (bool): Whether to wrap Flask route functions
        route_decorator: Decorator to apply to route functions
        
    Returns:
        list: Sorted list of functions by priority
    """
    root_directory = get_project_root()
    callback_directory = root_directory / start_module
    
    # Try to find the callback directory
    if not callback_directory.exists():
        callback_directory = root_directory / 'src' / start_module
    if not callback_directory.exists():
        raise FileNotFoundError(f"{start_module} directory not found: {callback_directory}")
    logger.info(f"Scanning directory: {callback_directory}")

    # Add to Python path if needed
    import sys
    if str(callback_directory) not in sys.path:
        sys.path.append(str(callback_directory))

    package_name = start_module.replace('/', '.').rstrip('.')
    
    try:
        package = dynamic_import(package_name, start_module=start_module)
    except ImportError as e:
        raise ImportError(f"Failed to import package {package_name}: {e}")

    # Determine package path
    if not hasattr(package, "__file__") or package.__file__ is None:
        package_path = callback_directory
    else:
        package_path = Path(package.__file__).parent
    

    # Walk through all modules in package
    for _, module_name, _ in pkgutil.walk_packages([str(package_path)], prefix=f"{package_name}."):
        try:
            module = importlib.import_module(module_name)
            logger.info(f"Scanning module: {module_name}")
            import inspect
            # Check all members of the module
            for name, obj in inspect.getmembers(module):
                if not inspect.isfunction(obj) and not inspect.ismethod(obj):
                    continue
                
                # Handle annotation scanning
                if annotation and hasattr(obj, "__annotations__") and annotation in obj.__annotations__:
                    original_function = getattr(obj, "_original_function", obj)
                    priority = getattr(obj, "_priority", 100)
                    name = getattr(obj, "_name", None)
                    
                    if env:
                        if not name:
                            name = original_function.__name__
                        envname = getattr(obj, "_env", None)
                        env_default = getattr(obj, "_env_default", None)
                        
                        if envname:
                            env_val = os.environ.get(envname, '')
                            if env_val:
                                containers.append((priority, original_function))
                                logger.info(f"Registered {annotation} task: {original_function}")
                        elif env_default:
                            containers.append((priority, original_function))
                            logger.info(f"Registered {annotation} task: {original_function}")
                    else:
                        containers.append((priority, original_function))
                        logger.info(f"Registered {annotation} task: {original_function}")
                
                if wrap_routes:
                    _process_module(module=module, wrap_routes=wrap_routes,route_decorator=route_decorator)

        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.info(f"Failed to scan module {module_name}: {e}")

    # Sort by priority if containers were populated
    if containers:
        containers.sort(key=lambda x: x[0])
        return [func for _, func in containers]
    
    return []

def _is_route_decorator(decorator: ast.Call) -> bool:
    """检查AST节点是否是路由装饰器"""
    if not isinstance(decorator, ast.Call):
        return False
        
    # 检查装饰器形式: @app.route 或 @wx_app.route
    if (isinstance(decorator.func, ast.Attribute) and \
        isinstance(decorator.func.value, ast.Name) and \
        (decorator.func.value.id == 'app' or decorator.func.value.id == 'wx_app') and \
        decorator.func.attr in ['route']):
        return True
        
    # 检查直接装饰器形式: @route
    if isinstance(decorator.func, ast.Name) and \
        decorator.func.id in ['route']:
        return True
        
    return False

def _extract_route_path(decorator: ast.Call) -> Optional[str]:
    """从装饰器AST节点提取路由路径"""
    if not decorator.args:
        return None
    if isinstance(decorator.args[0], ast.Str):
        return decorator.args[0].s
    if isinstance(decorator.args[0], ast.Constant):  # Python 3.8+
        return decorator.args[0].value
    return None

def _analyze_module(filepath: str) -> Dict[str, Any]:
    """通过AST分析模块文件中的路由"""
    module_routes = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
        
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
            
        # 检查函数装饰器
        for decorator in node.decorator_list:
            if _is_route_decorator(decorator):
                route_path = _extract_route_path(decorator)
                if route_path and route_path.startswith('/api'):
                    module_routes[route_path] = node.name
                break
                
    return module_routes

def _process_module(module: Any, wrap_routes,route_decorator) -> None:
    """处理模块中的路由"""
    filepath = inspect.getfile(module)
    if filepath.endswith('.py'):
        module_routes = _analyze_module(filepath)
        
        # 动态加载路由函数
        for route_path, func_name in module_routes.items():
            func = getattr(module, func_name, None)
            if func:
                # 自定义包装逻辑
                if wrap_routes and not hasattr(func, "_wrapped"):
                    wrapped = route_decorator(func)
                    setattr(module, func_name, wrapped)
                    setattr(wrapped, "_wrapped", True)
                    logger.info(f"🎁 包装路由: {route_path}")