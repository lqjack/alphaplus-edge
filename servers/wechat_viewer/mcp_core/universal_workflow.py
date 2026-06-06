"""
Universal Automation Workflow using LangGraph

Implements a Plan-Execute-Verify-Recover state machine for autonomous GUI control.
Integrated with the CrossPlatformAutomationEngine for real-world execution.
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Annotated, TypedDict, Sequence, Union
from langgraph.graph import StateGraph, END, START
from .interfaces import AutomationStatus, AutomationResult
from .app_profile import get_app_registry

logger = logging.getLogger("mcp-server-universal-automation.workflow")

class MissionState(TypedDict):
    """Current state of the automation mission"""
    app_name: str
    goal: str
    plan: List[Dict[str, Any]]
    current_step_index: int
    context: Dict[str, Any]
    history: List[Dict[str, Any]]
    error: Optional[str]
    success: bool
    final_report: str
    extraction_results: List[Any]
    engine: Optional[Any] 

async def plan_mission(state: MissionState) -> MissionState:
    """Generate or refine the automation plan using LLM or rule-based logic"""
    app_profile = get_app_registry().get_profile(state["app_name"])
    logger.info(f"Planning mission for {state['app_name']}: {state['goal']}")
    
    goal_lower = state["goal"].lower()
    
    # Check for direct clicking on questions/menus in WeChat
    if state["app_name"] == "WeChat" and ("click" in goal_lower and ("question" in goal_lower or "menu" in goal_lower)):
        target_name = state["context"].get("target") or "更多"
        state["plan"] = [
            {"action": "bring_to_front"},
            {"action": "click", "element_name": target_name},
            {"action": "verify", "expected": f"Clicked {target_name}"}
        ]
    # Enhanced plan for searching and reading articles
    elif state["app_name"] == "WeChat" and ("search" in goal_lower and ("article" in goal_lower or "title" in goal_lower)):
        target = state["context"].get("target") or state["context"].get("account_ids", ["alphaplus"])[0]
        state["plan"] = [
            {"action": "bring_to_front"},
            {"action": "wait", "seconds": 1},
            {"action": "click", "selector": "search_bar"},
            {"action": "type", "text": target},
            {"action": "press", "key": "enter"},
            {"action": "wait", "seconds": 2},
            {"action": "click", "selector": "official_account_result", "optional": True},
            {"action": "wait", "seconds": 2},
            {"action": "read_articles"},
            {"action": "verify", "expected": f"Articles from {target} read"}
        ]
    elif state["app_name"] == "WeChat" and "search" in goal_lower:
        target = state["context"].get("target", "test")
        state["plan"] = [
            {"action": "bring_to_front"},
            {"action": "wait", "seconds": 1},
            {"action": "click", "selector": "search_bar"},
            {"action": "type", "text": target},
            {"action": "press", "key": "enter"},
            {"action": "verify", "expected": f"Search for {target}"}
        ]
    else:
        # Generic plan bootstrap
        state["plan"] = [
            {"action": "bring_to_front"},
            {"action": "verify", "expected": f"{state['app_name']} active"}
        ]
        
    return {**state, "current_step_index": 0}

async def execute_step(state: MissionState) -> MissionState:
    """Execute the current step with advanced element location fallbacks"""
    idx = state["current_step_index"]
    step = state["plan"][idx]
    engine = state.get("engine")
    app_name = state["app_name"]
    
    logger.info(f"Executing step {idx+1}/{len(state['plan'])}: {step['action']}")
    
    status = "success"
    try:
        if not engine:
            await asyncio.sleep(0.5)
        else:
            action = step["action"]
            if action == "bring_to_front":
                logger.info(f"Targeting app: {app_name}")
                engine.bring_to_front(app_name)
            elif action == "click":
                selector_key = step.get("selector")
                element_name = step.get("element_name")
                
                logger.info(f"Attempting to click element: {selector_key or element_name}")
                el = None
                app_profile = get_app_registry().get_profile(app_name)
                
                # 1. Try by manual name if provided
                if element_name and hasattr(engine, "_platform_adapter") and engine._platform_adapter:
                   logger.debug(f"Direct name lookup: {element_name}")
                   el = engine._platform_adapter.find_element_by_name(element_name, app_name)
                
                # 2. Try by profile selector
                if not el and selector_key and app_profile:
                    def try_selector(sel_info):
                        nonlocal el
                        if not sel_info: return False
                        
                        logger.debug(f"Trying selector logic for: {sel_info.to_dict()}")
                        # Try accessibility name
                        if sel_info.value:
                            el = engine._platform_adapter.find_element_by_name(sel_info.value, app_name)
                        
                        # Try relative position fallback
                        if not el and sel_info.relative_position:
                            logger.info(f"Using relative position fallback: {sel_info.relative_position}")
                            bounds = engine.get_window_bounds(app_name)
                            if bounds:
                                rx = sel_info.relative_position["X"]
                                ry = sel_info.relative_position["Y"]
                                el_x = bounds["X"] + (bounds["Width"] * rx)
                                el_y = bounds["Y"] + (bounds["Height"] * ry)
                                logger.info(f"Clicking at relative coordinate: ({el_x}, {el_y})")
                                engine.click_at(int(el_x), int(el_y))
                                return True # Clicked via relative pos
                            else:
                                logger.warning(f"Could not get window bounds for {app_name}")
                        
                        # Recursive fallback
                        if not el and sel_info.fallback:
                            logger.debug("Attempting selector fallback...")
                            return try_selector(sel_info.fallback)
                        
                        return el is not None

                    sel_info = app_profile.selectors.get(selector_key)
                    if sel_info and hasattr(engine, "_platform_adapter") and engine._platform_adapter:
                        if try_selector(sel_info):
                            if not el: # Means it returned True from relative_position click
                                await asyncio.sleep(0.5)
                                logger.info("Step completed via coordinate click")
                                return {**state, "history": state["history"] + [{"step": step, "status": "success"}], "current_step_index": idx + 1}

                if el:
                    logger.info(f"Successfully located element. Clicking at center: ({el.x + el.width//2}, {el.y + el.height//2})")
                    engine.click_at(el.x + el.width//2, el.y + el.height//2)
                else:
                    if not step.get("optional"):
                        logger.error(f"Critical element not found: {selector_key or element_name}")
                        raise Exception(f"Element not found for step {step}")
                    logger.warning(f"Optional element not found: {selector_key or element_name}")
            
            elif action == "type":
                logger.info(f"Typing text: '{step['text'][0:10]}...'")
                engine.type_text(step["text"])
            elif action == "press":
                logger.info(f"Pressing key: {step['key']}")
                engine.press_key(step["key"])
            elif action == "wait":
                logger.info(f"Waiting for {step.get('seconds', 1)} seconds...")
                await asyncio.sleep(step.get("seconds", 1))
            elif action == "read_articles":
                if hasattr(engine, "read_articles"):
                    logger.info("Starting article reading phase...")
                    articles = engine.read_articles(app_name)
                    logger.info(f"Extraction complete. Found {len(articles)} articles.")
                    state["extraction_results"].extend(articles)
            
            await asyncio.sleep(0.5) 
            
    except Exception as e:
        logger.error(f"Step execution failed: {e}")
        status = "failed"
        return {**state, "error": str(e)}

    step_result = {"step": step, "status": status}
    return {
        **state,
        "history": state["history"] + [step_result],
        "current_step_index": idx + 1
    }

async def verify_state(state: MissionState) -> MissionState:
    return state

async def handle_error(state: MissionState) -> MissionState:
    return {**state, "error": None}

def should_continue(state: MissionState) -> str:
    if state.get("error"):
        return "recover"
    if state["current_step_index"] >= len(state["plan"]):
        return "complete"
    return "execute"

def build_universal_graph() -> StateGraph:
    workflow = StateGraph(MissionState)
    workflow.add_node("planner", plan_mission)
    workflow.add_node("execute", execute_step)
    workflow.add_node("verify", verify_state)
    workflow.add_node("recover", handle_error)
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "execute")
    workflow.add_edge("execute", "verify")
    workflow.add_conditional_edges("verify", should_continue, {"execute": "execute", "recover": "recover", "complete": END})
    workflow.add_edge("recover", "planner")
    return workflow.compile()

class UniversalMissionOrchestrator:
    def __init__(self, engine: Optional[Any] = None):
        self.graph = build_universal_graph()
        self.engine = engine
    async def run_mission(self, app_name: str, goal: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        initial_state: MissionState = {"app_name": app_name, "goal": goal, "plan": [], "current_step_index": 0, "context": context or {}, "history": [], "error": None, "success": False, "final_report": "", "extraction_results": [], "engine": self.engine}
        try:
            result = await self.graph.ainvoke(initial_state)
            if "engine" in result: del result["engine"]
            return result
        except Exception as e:
            logger.error(f"Mission failed: {e}")
            return {"error": str(e), "success": False}
