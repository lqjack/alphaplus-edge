import signal
import sys
import time
from core.tools.annotations import startup_tasks, shutdown_tasks
from core.tools.llm_finders import llms, registered_llms
import logging

logger = logging.getLogger(__name__)

class Command:
    def __init__(self, name="command", **kwargs):
        self.name = name
        self.kwargs = kwargs
        logger.info(f"Initializing {self.name}...")
        from core.tools.scanner import scan_modules
        scan_modules(start_module='core/callback', annotation='startup_before', containers=startup_tasks)
        scan_modules(start_module='core/callback', annotation='shutdown_before', containers=shutdown_tasks)
    def start(self):
        """启动时执行的任务"""
        logger.info(f"{self.name} is running...")
        self._execute_tasks(startup_tasks, "Startup")
        # LLM initialization is now handled by AI MCP server on demand
        # self._execute_tasks(llms, "llm")

    def stop(self):
        """关闭时执行的任务"""
        logger.info(f"{self.name} is shutting down...")
        self._execute_tasks(shutdown_tasks, "Shutdown")

    def _execute_tasks(self, tasks, task_type):
        """执行任务列表"""
        logger.info(f"Executing {task_type} tasks...")
        tasks.sort(key=lambda x: x[0])

        for priority, task in tasks:
            task_start_time = time.perf_counter()
            logger.info(f"Executing {task_type} task: {task.__name__} (Priority: {priority})")
            if 'llm' == task_type:
                registered_llms.append(task(**self.kwargs))
            else:
                task(**self.kwargs)
            duration = time.perf_counter() - task_start_time
            logger.info(f"Task {task.__name__} completed in {duration:.4f}s")
    
tool = Command('command')
# 信号处理函数
def handle_shutdown(signum, frame):
    try:
        logger.info("\nReceived shutdown signal. Cleaning up...")
    except:
        # Ignore logging errors during shutdown
        pass
    if tool:
        try:
            tool.stop()
        except:
            # Ignore errors during shutdown
            pass
    sys.exit(0)

# 注册信号处理
signal.signal(signal.SIGINT, handle_shutdown)  # Ctrl+C
signal.signal(signal.SIGTERM, handle_shutdown)  # 系统终止信号

if __name__ == "__main__":
    # 启动时执行所有启动任务
    tool.start()

    try:
        # 模拟长时间运行的任务
        while True:
            logger.info("Working...")
            time.sleep(1)
    except KeyboardInterrupt:
        # 捕获Ctrl+C，执行关闭任务
        handle_shutdown(signal.SIGINT, None)
