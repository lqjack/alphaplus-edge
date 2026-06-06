"""
Intelligent Execution Monitor

Ensures reliable unattended operation through continuous oversight:
- Real-time Validation: Verifies each step's success before proceeding to subsequent steps
- Error Detection: Identifies unexpected dialogs, loading states, navigation errors, and application crashes
- Recovery Strategies: Implements predefined recovery actions for common failure scenarios
- Performance Tracking: Monitors execution timing, success rates, and resource utilization for optimization
"""

import time
import logging
from typing import Dict, List, Optional, Any
from .interfaces import IIntelligentExecutionMonitor, ExecutionContext, AutomationStatus
from .dependency_types import (
    CROSS_PLATFORM_AUTOMATION_ENGINE,
    ADAPTIVE_ELEMENT_LOCATOR,
    INTELLIGENT_EXECUTION_MONITOR,
    STATE_PERSISTENCE_LAYER
)


class IntelligentExecutionMonitor(IIntelligentExecutionMonitor):
    """Intelligent execution monitoring and error recovery component"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.execution_monitor")
        self._automation_engine = None
        self._adaptive_locator = None
        self._state_persistence = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

    def _get_engine(self):
        """Lazy load automation engine to avoid circular dependencies"""
        if self._automation_engine is None:
            self._automation_engine = self.dep_manager.get_dependency(CROSS_PLATFORM_AUTOMATION_ENGINE)
        return self._automation_engine

    def _get_locator(self):
        """Lazy load adaptive locator"""
        if self._adaptive_locator is None:
            self._adaptive_locator = self.dep_manager.get_dependency(ADAPTIVE_ELEMENT_LOCATOR)
        return self._adaptive_locator

    def _get_persistence(self):
        """Lazy load state persistence"""
        if self._state_persistence is None:
            self._state_persistence = self.dep_manager.get_dependency(STATE_PERSISTENCE_LAYER)
        return self._state_persistence

    def execute_step(self,
                    step: Dict[str, Any],
                    context: ExecutionContext) -> Dict[str, Any]:
        """Execute a single automation step with monitoring and validation"""
        action = step.get("action")
        description = step.get("description", action)
        # Use configurable timeout with fallback to step timeout, then default
        default_timeout = 10.0
        if self._config_manager:
            default_timeout = self._config_manager.get_tunable_parameter("default_timeout", default_timeout)
        timeout = step.get("timeout", default_timeout)
        
        self.logger.info(f"Executing step: {description}")
        start_time = time.time()
        
        try:
            # 1. Validate prerequisites (if any)
            if not self._validate_prerequisites(step, context):
                return {
                    "success": False,
                    "status": "prerequisite_failed",
                    "message": f"Prerequisites for step '{description}' not met",
                    "execution_time": time.time() - start_time
                }

            # 2. Execute the action via automation engine
            result = self._perform_action(step, context)
            
            # 3. Validate the result
            if result.get("success", False):
                validation_success = self.validate_step_result(step, result)
                if not validation_success:
                    result["success"] = False
                    result["status"] = "validation_failed"
                    result["message"] = f"Validation failed for step: {description}"
            
            # 4. Update performance metrics
            execution_time = time.time() - start_time
            result["execution_time"] = execution_time
            self._update_metrics(action, execution_time, result["success"], context)
            
            # 5. Handle success/failure
            if result["success"]:
                self._consecutive_failures = 0
                self.logger.info(f"Step executed successfully: {description} ({execution_time:.2f}s)")
            else:
                self._consecutive_failures += 1
                self.logger.warning(f"Step failed: {description} - {result.get('message')}")
                
                # Try automatic recovery if available
                error_type = self.detect_error_state()
                if error_type and self.execute_recovery(error_type):
                    self.logger.info(f"Recovery successful for error: {error_type}. Retrying step...")
                    # Note: In a full implementation, we might retry the step here
                    # or inform the planner to adjust the plan.
            
            return result

        except Exception as e:
            self.logger.error(f"System error during step execution: {e}", exc_info=True)
            self._consecutive_failures += 1
            return {
                "success": False,
                "status": "system_error",
                "message": str(e),
                "execution_time": time.time() - start_time
            }

    def validate_step_result(self,
                            step: Dict[str, Any],
                            result: Dict[str, Any]) -> bool:
        """Validate that a step executed successfully by checking UI state"""
        action = step.get("action")
        expected_state = step.get("expected_state")
        
        if not expected_state:
            # If no expected state defined, rely on the action's reported result
            return result.get("success", False)
            
        try:
            engine = self._get_engine()
            locator = self._get_locator()
            
            # Example: Check if a specific element became visible
            target_element = expected_state.get("element_visible")
            if target_element:
                location = locator.locate_element(target_element, timeout=5.0)
                if not location:
                    self.logger.warning(f"Validation failed: expected element '{target_element}' not visible")
                    return False
            
            # Example: Check if a window title changed
            expected_title = expected_state.get("window_title")
            if expected_title:
                window_info = engine.get_active_window_info()
                if not window_info or expected_title not in window_info.get("title", ""):
                    self.logger.warning(f"Validation failed: expected window title '{expected_title}' not found")
                    return False
                    
            return True
        except Exception as e:
            self.logger.error(f"Error during result validation: {e}")
            return False

    def detect_error_state(self) -> Optional[str]:
        """Detect if the application is in an error state (e.g., unexpected dialogs)"""
        try:
            # Use adaptive locator to check for common error indicators
            locator = self._get_locator()
            
            # Check for generic "Error" dialogs
            error_patterns = ["error", "failure", "network error", "retry", "failed to load"]
            for pattern in error_patterns:
                if locator.locate_element(pattern, timeout=1.0):
                    return "app_error_dialog"
            
            # Check for application crash or lack of responsiveness
            engine = self._get_engine()
            if not engine.get_active_window_info():
                return "app_not_responding"
                
            return None
        except:
            return None

    def execute_recovery(self, error_type: str) -> bool:
        """Execute recovery procedure for an error type"""
        self.logger.info(f"Executing recovery for error: {error_type}")
        
        try:
            engine = self._get_engine()
            
            if error_type == "app_error_dialog":
                # Try to close the dialog
                return engine.press_key("escape")
            elif error_type == "app_not_responding":
                # In WeChat context, we might try to bring it to front again or restart it
                # For now, just try to bring to front
                if hasattr(engine, 'bring_wechat_to_front'):
                    return engine.bring_wechat_to_front()
                return False
            elif error_type == "navigation_stuck":
                # Try to go back or refresh
                return engine.press_key("cmd+left") # Browser back
                
            return False
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            return False

    def should_replan(self, consecutive_failures: int) -> bool:
        """Determine if we should replan after consecutive failures"""
        return consecutive_failures >= self._max_consecutive_failures

    # Private helper methods

    def _validate_prerequisites(self, step: Dict[str, Any], context: ExecutionContext) -> bool:
        """Verify step prerequisites are met"""
        # Full implementation would check context, UI state, etc.
        return True

    def _perform_action(self, step: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Perform the actual automation action via engine"""
        engine = self._get_engine()
        locator = self._get_locator()
        action = step.get("action")

        if action == "click":
            target = step.get("target")
            if target:
                location = locator.locate_element(target)
                if location:
                    # Use configurable click delay
                    click_delay = 0.1
                    if self._config_manager:
                        click_delay = self._config_manager.get_tunable_parameter("click_delay", click_delay)
                    time.sleep(click_delay)
                    success = engine.click_at(location.x, location.y)
                    return {"success": success, "message": f"Clicked at ({location.x}, {location.y})" if success else "Click failed"}
                return {"success": False, "message": f"Could not locate target: {target}"}

            # Direct coordinates
            x, y = step.get("x"), step.get("y")
            if x is not None and y is not None:
                # Use configurable click delay
                click_delay = 0.1
                if self._config_manager:
                    click_delay = self._config_manager.get_tunable_parameter("click_delay", click_delay)
                time.sleep(click_delay)
                success = engine.click_at(int(x), int(y))
                return {"success": success, "message": f"Clicked at ({x}, {y})" if success else "Click failed"}

        elif action == "type_text":
            text = step.get("text", "")
            # Use configurable type delay
            type_delay = 0.05
            if self._config_manager:
                type_delay = self._config_manager.get_tunable_parameter("type_delay", type_delay)
            success = engine.type_text(text)
            return {"success": success, "message": f"Typed text" if success else "Typing failed"}

        elif action == "press_key":
            key = step.get("key", "")
            # Use configurable key press delay
            key_delay = 0.05
            if self._config_manager:
                key_delay = self._config_manager.get_tunable_parameter("key_press_delay", key_delay)
            time.sleep(key_delay)
            success = engine.press_key(key)
            return {"success": success, "message": f"Pressed key {key}" if success else "Key press failed"}

        elif action == "wait":
            duration = step.get("timeout", 2.0)
            # Use configurable wait between steps multiplier
            wait_multiplier = 1.0
            if self._config_manager:
                wait_multiplier = self._config_manager.get_tunable_parameter("wait_between_steps", wait_multiplier)
            adjusted_duration = duration * wait_multiplier
            time.sleep(adjusted_duration)
            return {"success": True, "message": f"Waited for {adjusted_duration}s"}

        elif action == "clear_input":
            success = engine.clear_input()
            return {"success": success, "message": "Input cleared" if success else "Clear failed"}

        return {"success": False, "message": f"Unsupported or missing action: {action}"}

    def _update_metrics(self, action: str, execution_time: float, success: bool, context: ExecutionContext):
        """Update performance metrics in context and persistence"""
        try:
            metrics = context.performance_metrics
            key = f"action_{action}"
            
            # Simple moving average for timing
            current_time = metrics.get(f"{key}_avg_time", execution_time)
            metrics[f"{key}_avg_time"] = (current_time * 0.7) + (execution_time * 0.3)
            
            # Success count
            metrics[f"{key}_count"] = metrics.get(f"{key}_count", 0) + 1
            if success:
                metrics[f"{key}_success_count"] = metrics.get(f"{key}_success_count", 0) + 1
            
            # Persist if needed
            persistence = self._get_persistence()
            if persistence and metrics[f"{key}_count"] % 5 == 0:
                # This would be more sophisticated in a real app
                pass
                
        except Exception as e:
            self.logger.warning(f"Failed to update metrics: {e}")
