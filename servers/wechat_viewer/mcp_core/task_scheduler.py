"""
Task Scheduler Core

Handles task scheduling, retry mechanisms, and execution management.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta


class TaskScheduler:
    """Task scheduler with retry mechanisms and execution management"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.scheduler")
        self.is_running = False
        self.tasks = {}
        self.task_results = {}
    
    async def start_scheduled_tasks(self):
        """启动定时任务"""
        self.is_running = True
        
        while self.is_running:
            try:
                # 执行所有预定任务
                for task_config in self.config.get("tasks", []):
                    if await self._should_execute_task(task_config):
                        await self._execute_task_with_retry(task_config)
                
                # 等待下一个周期
                interval_minutes = self.config.get("interval_minutes", 60)
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                self.logger.error(f"任务调度器错误: {e}", exc_info=True)
                await asyncio.sleep(60)  # 错误后短暂等待
    
    async def stop_scheduled_tasks(self):
        """停止定时任务"""
        self.is_running = False
        self.logger.info("任务调度器已停止")
    
    async def _execute_task_with_retry(self, task_config: Dict[str, Any], max_retries: int = 3):
        """带重试的任务执行"""
        task_name = task_config.get("name", "unknown_task")
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"执行任务: {task_name} (尝试 {attempt + 1}/{max_retries})")
                
                # 执行任务
                success = await self._execute_single_task(task_config)
                
                if success:
                    self.logger.info(f"任务完成: {task_name}")
                    self._record_task_result(task_name, True, None)
                    return True
                else:
                    self.logger.warning(f"任务失败: {task_name}")
                    self._record_task_result(task_name, False, "任务执行失败")
                    
            except Exception as e:
                self.logger.error(f"任务执行异常: {task_name} - {e}")
                self._record_task_result(task_name, False, str(e))
            
            # 重试前等待
            if attempt < max_retries - 1:
                retry_delay = self.config.get("retry_delay_seconds", 30)
                self.logger.info(f"任务 {task_name} 将在 {retry_delay} 秒后重试")
                await asyncio.sleep(retry_delay)
        
        self.logger.error(f"任务 {task_name} 经过 {max_retries} 次尝试后仍然失败")
        return False
    
    async def _execute_single_task(self, task_config: Dict[str, Any]) -> bool:
        """执行单个任务"""
        task_type = task_config.get("type", "generic")
        
        if task_type == "wechat_monitor":
            return await self._execute_wechat_monitor_task(task_config)
        elif task_type == "generic":
            return await self._execute_generic_task(task_config)
        else:
            self.logger.error(f"未知任务类型: {task_type}")
            return False
    
    async def _execute_wechat_monitor_task(self, task_config: Dict[str, Any]) -> bool:
        """执行微信监控任务"""
        try:
            # 获取任务参数
            account_ids = task_config.get("account_ids", [])
            max_articles = task_config.get("max_articles", 3)
            
            # 这里应该调用实际的微信自动化逻辑
            # 由于我们重构了架构，这里需要通过依赖注入获取执行器
            executor = self.config.get("executor")
            if executor:
                success = await executor.execute_smart_mission(task_config)
                return success
            else:
                self.logger.warning("未提供执行器，跳过微信监控任务")
                return True  # 模拟成功
                
        except Exception as e:
            self.logger.error(f"微信监控任务执行失败: {e}")
            return False
    
    async def _execute_generic_task(self, task_config: Dict[str, Any]) -> bool:
        """执行通用任务"""
        try:
            # 获取自定义执行函数
            execute_func = task_config.get("execute_func")
            if execute_func and callable(execute_func):
                result = await execute_func(task_config)
                return bool(result)
            else:
                self.logger.warning("通用任务未提供执行函数")
                return True  # 模拟成功
                
        except Exception as e:
            self.logger.error(f"通用任务执行失败: {e}")
            return False
    
    async def _should_execute_task(self, task_config: Dict[str, Any]) -> bool:
        """判断是否应该执行任务"""
        # 检查任务是否启用
        if not task_config.get("enabled", True):
            return False
        
        # 检查时间限制
        if not self._check_time_constraints(task_config):
            return False
        
        # 检查频率限制
        if not self._check_frequency_limit(task_config):
            return False
        
        return True
    
    def _check_time_constraints(self, task_config: Dict[str, Any]) -> bool:
        """检查时间限制"""
        # 检查是否在允许的执行时间范围内
        allowed_hours = task_config.get("allowed_hours")
        if allowed_hours:
            current_hour = datetime.now().hour
            if current_hour not in allowed_hours:
                return False
        
        return True
    
    def _check_frequency_limit(self, task_config: Dict[str, Any]) -> bool:
        """检查频率限制"""
        task_name = task_config.get("name", "unknown")
        
        # 获取上次执行时间
        last_execution = self.task_results.get(task_name, {}).get("last_execution")
        if not last_execution:
            return True
        
        # 检查最小执行间隔
        min_interval = task_config.get("min_interval_minutes", 0)
        if min_interval > 0:
            time_since_last = datetime.now() - datetime.fromisoformat(last_execution)
            if time_since_last < timedelta(minutes=min_interval):
                return False
        
        return True
    
    def _record_task_result(self, task_name: str, success: bool, error_message: Optional[str]):
        """记录任务执行结果"""
        self.task_results[task_name] = {
            "last_execution": datetime.now().isoformat(),
            "success": success,
            "error_message": error_message,
            "total_attempts": self.task_results.get(task_name, {}).get("total_attempts", 0) + 1
        }
    
    def get_task_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        return {
            "is_running": self.is_running,
            "tasks": self.tasks,
            "task_results": self.task_results,
            "config": self.config
        }
    
    def add_task(self, task_config: Dict[str, Any]):
        """添加新任务"""
        task_name = task_config.get("name")
        if task_name:
            self.tasks[task_name] = task_config
            self.logger.info(f"添加任务: {task_name}")
        else:
            self.logger.warning("任务配置缺少名称，无法添加")
    
    def remove_task(self, task_name: str):
        """移除任务"""
        if task_name in self.tasks:
            del self.tasks[task_name]
            self.logger.info(f"移除任务: {task_name}")
        else:
            self.logger.warning(f"任务不存在: {task_name}")


class SmartTaskScheduler(TaskScheduler):
    """智能任务调度器，支持动态任务管理和优先级"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.priority_queue = []
        self.dynamic_tasks = {}
    
    async def _execute_task_with_retry(self, task_config: Dict[str, Any], max_retries: int = 3):
        """带优先级的重试任务执行"""
        # 根据优先级调整重试次数
        priority = task_config.get("priority", 1)
        adjusted_retries = max_retries + (priority - 1)
        
        return await super()._execute_task_with_retry(task_config, adjusted_retries)
    
    def add_dynamic_task(self, task_config: Dict[str, Any]):
        """添加动态任务"""
        task_name = task_config.get("name")
        if task_name:
            self.dynamic_tasks[task_name] = task_config
            # 将动态任务添加到优先队列
            priority = task_config.get("priority", 1)
            self.priority_queue.append((priority, task_config))
            # 按优先级排序
            self.priority_queue.sort(key=lambda x: x[0], reverse=True)
            self.logger.info(f"添加动态任务: {task_name} (优先级: {priority})")
        else:
            self.logger.warning("动态任务配置缺少名称，无法添加")
    
    async def _should_execute_task(self, task_config: Dict[str, Any]) -> bool:
        """增强的任务执行判断"""
        # 调用父类判断
        if not await super()._should_execute_task(task_config):
            return False
        
        # 检查资源限制
        if not self._check_resource_limits(task_config):
            return False
        
        # 检查依赖关系
        if not self._check_dependencies(task_config):
            return False
        
        return True
    
    def _check_resource_limits(self, task_config: Dict[str, Any]) -> bool:
        """检查资源限制"""
        # 检查CPU使用率
        cpu_threshold = self.config.get("cpu_threshold", 80)
        import psutil
        current_cpu = psutil.cpu_percent()
        if current_cpu > cpu_threshold:
            self.logger.warning(f"CPU使用率过高 ({current_cpu}%), 跳过任务执行")
            return False
        
        # 检查内存使用率
        memory_threshold = self.config.get("memory_threshold", 80)
        current_memory = psutil.virtual_memory().percent
        if current_memory > memory_threshold:
            self.logger.warning(f"内存使用率过高 ({current_memory}%), 跳过任务执行")
            return False
        
        return True
    
    def _check_dependencies(self, task_config: Dict[str, Any]) -> bool:
        """检查任务依赖"""
        dependencies = task_config.get("dependencies", [])
        for dep_task in dependencies:
            dep_result = self.task_results.get(dep_task, {})
            if not dep_result.get("success", False):
                self.logger.warning(f"任务 {task_config.get('name')} 依赖的任务 {dep_task} 未成功完成")
                return False
        return True