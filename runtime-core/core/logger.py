"""
MCP Logger Utilities
提供统一的日志设置方法
"""

import logging
import sys
import time
from pathlib import Path


def _get_main_project_root() -> Path:
    """获取整个项目的顶级根目录 (alphaplus)
    
    向上遍历寻找包含 .opencode 或 scripts/deploy_all.sh 的顶层目录。
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".opencode").exists() or (current / "scripts" / "deploy_all.sh").exists():
            return current
        current = current.parent
    # 退而求其次：找含 .git 的最高层目录
    current = Path(__file__).resolve().parent
    best = current
    while current != current.parent:
        if (current / ".git").exists():
            best = current
        current = current.parent
    return best


def setup_logger(name: str, log_to_file: bool = True, log_to_console: bool = True):
    """
    设置日志 - 输出到控制台和文件

    Args:
        name: logger名称
        log_to_file: 是否输出到文件
        log_to_console: 是否输出到控制台（MCP服务器应设为False）

    Returns:
        配置好的logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # 清除现有处理器
    logger.handlers.clear()

    # 控制台处理器 - 只在非MCP服务器模式下启用
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # 设置控制台处理器使用UTF-8编码
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except Exception:
                pass
        if hasattr(sys.stderr, 'reconfigure'):
            try:
                sys.stderr.reconfigure(encoding='utf-8')
            except Exception:
                pass
        
        logger.addHandler(console_handler)

    # 文件处理器 - 统一写入项目根目录 (alphaplus) 的 logs/
    if log_to_file:
        project_root = _get_main_project_root()
        log_dir = project_root / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f'{name.lower().replace("-", "_")}_{int(time.time())}.log'

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # 使用临时 logger 记录日志文件路径 - 只在控制台输出启用时
        if log_to_console:
            temp_logger = logging.getLogger('temp')
            temp_logger.addHandler(logging.StreamHandler(sys.stderr))
            temp_logger.info(f"{name} 日志将写入: {log_file}")
        else:
            # MCP服务器模式 - 只记录到文件，不输出到stdout
            logger.info(f"{name} 日志将写入: {log_file}")

    return logger


def get_logger(name: str):
    """
    获取或创建指定名称的logger

    Args:
        name: logger名称

    Returns:
        logger实例
    """
    return logging.getLogger(name)
