"""
LLM Task Planner

Intelligent core enabling full autonomy:
- Goal Decomposition: Converts high-level goals into executable step-by-step plans
- Dynamic Planning: Adjusts plans based on current UI state, historical performance, and environmental factors
- Context Maintenance: Preserves conversation history with LLM for task progression awareness
- Tool Integration: Utilizes existing MCP-based LLM protocol for screen analysis and decision making
"""

import time
import logging
from typing import Dict, List, Optional, Any
from .interfaces import ILLMTaskPlanner, AutomationPlan, ExecutionContext
from .dependency_types import LLM_TASK_PLANNER


class LLMTaskPlanner(ILLMTaskPlanner):
    """LLM-driven task planning component"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.llm_task_planner")
        self._planning_context: Dict[str, Any] = {}
        self._conversation_history: List[Dict[str, Any]] = []
        self._initialize_planning_context()

    def _initialize_planning_context(self):
        """Initialize the planning context with system information"""
        self._planning_context = {
            "system_capabilities": self._get_system_capabilities(),
            "supported_operations": [
                "click",
                "type_text",
                "press_key",
                "scroll_down",
                "close_tab",
                "capture_screenshot",
                "clear_input",
                "wait",
                "check_element_exists",
                "get_element_text",
            ],
            "planning_version": "1.0",
            "timestamp": time.time(),
        }

    def _get_system_capabilities(self) -> Dict[str, Any]:
        """Get system capabilities from available components"""
        capabilities = {
            "accessibility_api": False,
            "ui_automation": False,
            "ocr": True,  # Assume OCR is generally available
            "llm_vision": False,
        }

        # Check platform adapter capabilities
        try:
            # Try to get platform adapter to check its capabilities
            # In a real implementation, we would query the actual adapter
            pass
        except:
            pass

        return capabilities

    def decompose_goal(
        self, goal: str, current_state: Dict[str, Any]
    ) -> AutomationPlan:
        """Decompose a high-level goal into executable steps"""
        self.logger.info(f"Decomposing goal: {goal}")

        # Add to conversation history
        self._add_to_conversation_history(
            "goal_decomposition_request", {"goal": goal, "current_state": current_state}
        )

        # In a real implementation, this would:
        # 1. Construct a prompt for the LLM describing the goal and current state
        # 2. Send the prompt to the LLM via MCP protocol
        # 3. Parse the LLM response to extract the step-by-step plan
        # 4. Validate and refine the plan

        # For now, we'll implement a rule-based fallback for common goals
        plan = self._decompose_goal_rule_based(goal, current_state)

        # Add to conversation history
        self._add_to_conversation_history(
            "goal_decomposition_result",
            {
                "goal": goal,
                "plan": plan.__dict__ if hasattr(plan, "__dict__") else str(plan),
            },
        )

        self.logger.info(f"Decomposed goal into {len(plan.steps)} steps")
        return plan

    def adjust_plan(
        self, plan: AutomationPlan, execution_results: List[Dict[str, Any]]
    ) -> AutomationPlan:
        """Adjust plan based on execution results"""
        self.logger.info(
            f"Adjusting plan based on {len(execution_results)} execution results"
        )

        # Add to conversation history
        self._add_to_conversation_history(
            "plan_adjustment_request",
            {
                "original_plan": (
                    plan.__dict__ if hasattr(plan, "__dict__") else str(plan)
                ),
                "execution_results": execution_results,
            },
        )

        # In a real implementation, this would:
        # 1. Analyze execution results to see what worked and what didn't
        # 2. Construct a prompt for the LLM to suggest plan adjustments
        # 3. Get adjusted plan from LLM
        # 4. Validate the adjusted plan

        # For now, we'll implement a simple rule-based adjustment
        adjusted_plan = self._adjust_plan_rule_based(plan, execution_results)

        # Add to conversation history
        self._add_to_conversation_history(
            "plan_adjustment_result",
            {
                "adjusted_plan": (
                    adjusted_plan.__dict__
                    if hasattr(adjusted_plan, "__dict__")
                    else str(adjusted_plan)
                )
            },
        )

        return adjusted_plan

    def validate_plan_feasibility(self, plan: AutomationPlan) -> bool:
        """Validate that a plan is feasible to execute"""
        self.logger.debug(f"Validating plan feasibility for goal: {plan.goal}")

        # Basic validation
        if not plan.goal or not isinstance(plan.goal, str):
            self.logger.warning("Plan goal is missing or invalid")
            return False

        if not plan.steps or not isinstance(plan.steps, list):
            self.logger.warning("Plan steps are missing or invalid")
            return False

        # Check each step for basic validity
        for i, step in enumerate(plan.steps):
            if not isinstance(step, dict):
                self.logger.warning(f"Step {i} is not a dictionary: {step}")
                return False

            if "action" not in step or not isinstance(step["action"], str):
                self.logger.warning(f"Step {i} missing or invalid action: {step}")
                return False

        # In a real implementation, we would:
        # 1. Check if required capabilities are available
        # 2. Validate that locators can find the required elements
        # 3. Check resource constraints (time, memory, etc.)
        # 4. Validate sequence dependencies

        # For now, assume it's feasible if it passes basic validation
        self.logger.debug("Plan validation passed")
        self._add_to_conversation_history(
            "plan_validation_request",
            {"plan_goal": plan.goal, "plan_steps": len(plan.steps)},
        )

        return True

    def get_planning_context(self) -> Dict[str, Any]:
        """Get current planning context"""
        return self._planning_context.copy()

    # Private helper methods

    def _add_to_conversation_history(self, event_type: str, data: Dict[str, Any]):
        """Add an event to the conversation history"""
        self._conversation_history.append(
            {"timestamp": time.time(), "type": event_type, "data": data}
        )

        # Keep conversation history from growing too large
        max_history = 50
        if len(self._conversation_history) > max_history:
            self._conversation_history = self._conversation_history[-max_history:]

    def _decompose_goal_rule_based(
        self, goal: str, current_state: Dict[str, Any]
    ) -> AutomationPlan:
        """Rule-based goal decomposition (fallback when LLM unavailable)"""
        self.logger.debug(f"Using rule-based decomposition for goal: {goal}")

        goal_lower = goal.lower().strip()

        # Common goal patterns
        if "view latest articles" in goal_lower or "view latest article" in goal_lower:
            return self._plan_view_latest_articles(current_state)
        elif "search for" in goal_lower:
            return self._plan_search_for(goal, current_state)
        elif "open" in goal_lower and (
            "app" in goal_lower or "application" in goal_lower
        ):
            return self._plan_open_application(goal, current_state)
        else:
            # Generic fallback plan
            return AutomationPlan(
                goal=goal,
                steps=[
                    {
                        "action": "analyze_screen",
                        "description": "Analyze current screen to understand context",
                        "timeout": 5.0,
                    },
                    {
                        "action": "request_clarification",
                        "description": f"Need clarification on how to achieve goal: {goal}",
                        "timeout": 10.0,
                    },
                ],
                estimated_duration=15.0,
                success_criteria=[f"Goal achieved: {goal}"],
            )

    def _plan_view_latest_articles(
        self, current_state: Dict[str, Any]
    ) -> AutomationPlan:
        """Plan for viewing latest articles from an official account"""
        # Extract account name from current state or use default
        account_name = current_state.get("target_account", "official account")

        return AutomationPlan(
            goal=f"View latest articles from {account_name}",
            steps=[
                {
                    "action": "click",
                    "target": "search_box",
                    "description": "Click on the search box to initiate search",
                    "timeout": 3.0,
                },
                {
                    "action": "type_text",
                    "text": account_name,
                    "description": f"Type the account name: {account_name}",
                    "timeout": 2.0,
                },
                {
                    "action": "press_key",
                    "key": "enter",
                    "description": "Press Enter to search for the account",
                    "timeout": 3.0,
                },
                {
                    "action": "wait",
                    "description": "Wait for search results to load",
                    "timeout": 3.0,
                },
                {
                    "action": "click",
                    "target": "official_account_result",
                    "description": f"Click on the official account result for {account_name}",
                    "timeout": 3.0,
                },
                {
                    "action": "wait",
                    "description": "Wait for account page to load",
                    "timeout": 3.0,
                },
                {
                    "action": "click",
                    "target": "latest_article",
                    "description": "Click on the latest article",
                    "timeout": 3.0,
                },
                {
                    "action": "wait",
                    "description": "Wait for article to load",
                    "timeout": 5.0,
                },
            ],
            estimated_duration=25.0,
            success_criteria=[
                "Article content is visible",
                "Page indicates article has been loaded successfully",
            ],
        )

    def _plan_search_for(
        self, goal: str, current_state: Dict[str, Any]
    ) -> AutomationPlan:
        """Plan for searching for something"""
        # Extract search term from goal
        # Simple extraction: everything after "search for"
        search_term = goal.lower().split("search for", 1)[-1].strip()
        if not search_term:
            search_term = "search term"

        return AutomationPlan(
            goal=goal,
            steps=[
                {
                    "action": "click",
                    "target": "search_box",
                    "description": "Click on the search box",
                    "timeout": 3.0,
                },
                {
                    "action": "type_text",
                    "text": search_term,
                    "description": f"Type search term: {search_term}",
                    "timeout": 2.0,
                },
                {
                    "action": "press_key",
                    "key": "enter",
                    "description": "Press Enter to execute search",
                    "timeout": 3.0,
                },
                {
                    "action": "wait",
                    "description": "Wait for search results",
                    "timeout": 3.0,
                },
            ],
            estimated_duration=11.0,
            success_criteria=[
                "Search results are displayed",
                f"Results related to '{search_term}' are visible",
            ],
        )

    def _plan_open_application(
        self, goal: str, current_state: Dict[str, Any]
    ) -> AutomationPlan:
        """Plan for opening an application"""
        # Extract app name from goal
        # Simple approach: look for known app names
        known_apps = ["wechat", "chrome", "firefox", "safari", "notes", "calendar"]
        app_name = "application"

        goal_lower = goal.lower()
        for app in known_apps:
            if app in goal_lower:
                app_name = app
                break

        return AutomationPlan(
            goal=goal,
            steps=[
                {
                    "action": "press_key",
                    "key": "cmd+space",  # Spotlight on Mac, or Win+Space on Windows
                    "description": "Open application launcher",
                    "timeout": 2.0,
                },
                {
                    "action": "type_text",
                    "text": app_name,
                    "description": f"Type application name: {app_name}",
                    "timeout": 2.0,
                },
                {
                    "action": "press_key",
                    "key": "enter",
                    "description": f"Press Enter to open {app_name}",
                    "timeout": 5.0,
                },
            ],
            estimated_duration=9.0,
            success_criteria=[f"{app_name} application is open and ready for use"],
        )

    def _adjust_plan_rule_based(
        self, plan: AutomationPlan, execution_results: List[Dict[str, Any]]
    ) -> AutomationPlan:
        """Rule-based plan adjustment (fallback when LLM unavailable)"""
        self.logger.debug(f"Using rule-based adjustment for plan: {plan.goal}")

        # If no execution results, return original plan
        if not execution_results:
            return plan

        # Analyze execution results for failures
        failed_steps = []
        for i, result in enumerate(execution_results):
            if i < len(plan.steps):
                step = plan.steps[i]
                if not result.get("success", False):
                    failed_steps.append((i, step, result.get("error", "Unknown error")))

        # If no failures, return original plan
        if not failed_steps:
            return plan

        # For now, we'll just return the original plan but log the failures
        # In a real implementation, we would:
        # 1. Analyze patterns of failure
        # 2. Suggest alternative approaches
        # 3. Modify the plan to avoid known failure points
        # 4. Add retry logic or fallback steps

        self.logger.warning(
            f"Plan execution had {len(failed_steps)} failed steps: {failed_steps}"
        )
        return plan
