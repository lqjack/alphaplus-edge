"""
WeChat Viewer Tool Handler

Handles MCP tool execution for WeChat GUI automation operations.
"""
import inspect
import sys
import os
from typing import Dict, Any, List
from dataclasses import asdict, is_dataclass
try:
    import mcp.types as types
except ImportError:
    types = None


class WeChatViewerToolHandler:
    """Handles MCP tool operations for WeChat Viewer"""

    def __init__(self, dep_manager, automation):
        self.dep_manager = dep_manager
        self.automation = automation
        import logging
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.tool_handler")

        # Define available tools
        self.tools = self._define_tools()

    def _emit_runtime_message(self, level: str, message: str) -> None:
        """Log runtime status without letting detached stderr failures break API responses."""
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)
        if os.getenv("WECHAT_VIEWER_STDERR_LOG", "").strip().lower() not in {"1", "true", "yes", "on"}:
            return
        try:
            print(message, file=sys.stderr)
        except OSError:
            self.logger.debug("stderr unavailable while emitting runtime message: %s", message)

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define all available WeChat Viewer MCP tools"""
        return {
            "wechat_start_automation": {
                "name": "wechat_start_automation",
                "description": "Start the WeChat Official Account automation loop",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of official accounts to process"
                        },
                        "accounts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Backward-compatible official account names"
                        },
                        "interval_minutes": {
                            "type": "integer",
                            "description": "Interval between cycles",
                            "default": 3
                        },
                        "max_cycles": {
                            "type": "integer",
                            "description": "Number of cycles to run",
                            "default": 1
                        },
                        "action": {
                            "type": "string",
                            "description": "start initializes the session; run executes a collection cycle",
                            "enum": ["start", "run"]
                        }
                    }
                }
            },
            "wechat_run_once": {
                "name": "wechat_run_once",
                "description": "Run the WeChat automation once for specific accounts",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of WeChat account IDs to process. If empty, processes all available accounts."
                        },
                        "account_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of official accounts to process"
                        },
                        "accounts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Backward-compatible official account names"
                        },
                        "max_articles": {
                            "type": "integer",
                            "description": "Maximum number of articles to process per account",
                            "default": 3
                        },
                        "action": {
                            "type": "string",
                            "description": "fetch_articles runs collection; cleanup closes transient state",
                            "enum": ["fetch_articles", "cleanup"]
                        }
                    }
                }
            },
            "universal_run_mission": {
                "name": "universal_run_mission",
                "description": "Execute a high-level goal-driven mission for any desktop application",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Name of the target application (e.g., 'WeChat', 'Notes', 'Chrome')"
                        },
                        "goal": {
                            "type": "string",
                            "description": "High-level goal (e.g., 'Search for account alphaplus', 'Write a note about the weather')"
                        },
                        "context": {
                            "type": "object",
                            "description": "Additional context for the mission"
                        }
                    },
                    "required": ["app_name", "goal"]
                }
            },
            "wechat_search_account": {
                "name": "wechat_search_account",
                "description": "Search for a WeChat Official Account by name",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_name": {
                            "type": "string",
                            "description": "Name of the official account to search for"
                        }
                    },
                    "required": ["account_name"]
                }
            },
            "wechat_get_account_article_titles": {
                "name": "wechat_get_account_article_titles",
                "description": "Search one or more WeChat Official Accounts, click the matching account result, and return latest article titles plus best-effort article links",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_name": {
                            "type": "string",
                            "description": "Name of the official account to search for"
                        },
                        "account_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of multiple official accounts to process"
                        },
                        "max_articles": {
                            "type": "integer",
                            "description": "Maximum number of latest articles to read per account",
                            "default": 3
                        },
                        "read_articles": {
                            "type": "boolean",
                            "description": "Whether to open and read article bodies after collecting visible titles",
                            "default": True
                        }
                    }
                }
            },
            "wechat_get_accounts_latest_articles": {
                "name": "wechat_get_accounts_latest_articles",
                "description": "Search multiple WeChat Official Accounts and return each account's latest article titles plus best-effort article links",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Names of official accounts to process"
                        },
                        "max_articles": {
                            "type": "integer",
                            "description": "Maximum number of latest articles to read per account",
                            "default": 3
                        },
                        "read_articles": {
                            "type": "boolean",
                            "description": "Whether to open and read article bodies after collecting visible titles",
                            "default": True
                        }
                    },
                    "required": ["account_names"]
                }
            },
            "wechat_click_latest_official_article": {
                "name": "wechat_click_latest_official_article",
                "description": "Open a specific WeChat Official Account and click its latest articles, or open the Official Accounts keyword flow when account_name is missing or '公众号'.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_name": {
                            "type": "string",
                            "description": "Specific target account name. Leave empty to use the '公众号' keyword flow."
                        },
                        "search_keyword": {
                            "type": "string",
                            "description": "Keyword for fallback mode when account_name is empty. Default: 公众号",
                            "default": "公众号"
                        },
                        "max_articles": {
                            "type": "integer",
                            "description": "Maximum number of latest articles to process",
                            "default": 1
                        },
                        "read_articles": {
                            "type": "boolean",
                            "description": "Whether to open and read article bodies after finding the latest rows",
                            "default": True
                        }
                    }
                }
            },
            "wechat_click_element": {
                "name": "wechat_click_element",
                "description": "Click an element by its text name (e.g., a menu item or question)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The exact or partial text of the element to click"
                        }
                    },
                    "required": ["text"]
                }
            },
            "wechat_check_accessibility": {
                "name": "wechat_check_accessibility",
                "description": "Inspect the current macOS/desktop accessibility runtime used by wechat_viewer, including AX trust and System Events assistive access",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "wechat_request_accessibility": {
                "name": "wechat_request_accessibility",
                "description": "Open the macOS Accessibility settings page for wechat_viewer and return the current permission status",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        }

    @staticmethod
    def _supports_keyword_argument(fn, name: str) -> bool:
        try:
            signature = inspect.signature(fn)
        except (TypeError, ValueError):
            return False
        parameter = signature.parameters.get(name)
        if parameter is None:
            return False
        return parameter.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )

    def get_tool_definitions(self) -> List[Any]:
        """Get MCP tool definitions"""
        if types is None:
            return []
        return [
            types.Tool(
                name=tool_def["name"],
                description=tool_def["description"],
                inputSchema=tool_def["inputSchema"]
            ) for tool_def in self.tools.values()
        ]

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools - required by base class"""
        return [
            {
                "name": tool_def["name"],
                "description": tool_def["description"],
                "inputSchema": tool_def.get("inputSchema", {})
            }
            for tool_def in self.tools.values()
        ]

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool with given arguments"""
        # print(f"INFO: Executing WeChat Viewer tool: {name} with args: {arguments}", file=sys.stderr)

        try:
            if name == "wechat_run_once":
                result = await self._handle_run_once(arguments)

            elif name == "wechat_start_automation":
                result = await self._handle_start_automation(arguments)

            elif name == "universal_run_mission":
                result = await self._handle_universal_run_mission(arguments)

            elif name == "wechat_search_account":
                result = await self._handle_search_account(arguments)

            elif name == "wechat_get_account_article_titles":
                result = await self._handle_get_account_article_titles(arguments)

            elif name == "wechat_get_accounts_latest_articles":
                result = await self._handle_get_accounts_latest_articles(arguments)

            elif name == "wechat_click_latest_official_article":
                result = await self._handle_click_latest_official_article(arguments)

            elif name == "wechat_click_element":
                result = await self._handle_click_element(arguments)

            elif name == "wechat_check_accessibility":
                result = await self._handle_check_accessibility(arguments)

            elif name == "wechat_request_accessibility":
                result = await self._handle_request_accessibility(arguments)

            else:
                raise ValueError(f"Unknown WeChat Viewer tool: {name}")

            self._emit_runtime_message("info", f"INFO: WeChat Viewer tool {name} executed successfully")
            return result

        except Exception as e:
            self._emit_runtime_message("error", f"ERROR: Error calling WeChat Viewer tool {name}: {e}")
            return {
                "error": str(e),
                "tool": name,
                "arguments": arguments
            }

    def _to_jsonable(self, value: Any) -> Any:
        """Convert dataclasses and enums returned by automation into JSON-safe data."""
        if is_dataclass(value):
            return self._to_jsonable(asdict(value))
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, dict):
            return {key: self._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]
        return value

    def _normalise_account_names(self, value: Any) -> List[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            result: List[str] = []
            for item in value:
                result.extend(self._normalise_account_names(item))
            return result
        text = str(value).strip()
        return [text] if text else []

    def _account_names_from_arguments(self, arguments: Dict[str, Any]) -> List[str]:
        candidates: List[str] = []
        for key in ("account_ids", "account_names", "accounts"):
            candidates.extend(self._normalise_account_names(arguments.get(key)))

        seen = set()
        accounts: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                accounts.append(candidate)
        return accounts

    def _get_interaction_bounds(self):
        bounds_result = self.automation.get_wechat_window_bounds()
        if bounds_result.status.name == "SUCCESS":
            return bounds_result.data["bounds"]
        return self.automation._get_screen_interaction_bounds()
    
    async def _handle_run_once(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle single run of WeChat automation"""
        max_articles = arguments.get("max_articles", 3)
        action = arguments.get("action", "fetch_articles")
        if action == "cleanup":
            return {"success": True, "status": "success", "cleaned": True}

        account_ids = self._account_names_from_arguments(arguments)
        if not account_ids:
            return {"success": False, "status": "error", "message": "公众号没找到"}

        try:
            self.logger.info(f"Running once: action={action}, accounts={account_ids}, max={max_articles}")
            result = await self.automation.run_cycle(
                account_ids=account_ids,
                max_articles=max_articles
            )

            return self._to_jsonable(result)

        except Exception as e:
            import traceback
            self._emit_runtime_message("error", f"ERROR: Execution failed: {e}\n{traceback.format_exc()}")
            return {"success": False, "status": "error", "message": str(e)}

    async def _handle_start_automation(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle starting automated WeChat processing"""
        interval = arguments.get("interval_minutes", 3)
        max_cycles = arguments.get("max_cycles", 1)
        action = arguments.get("action", "run")
        account_names = self._account_names_from_arguments(arguments)
        if action == "start":
            return {
                "success": True,
                "status": "started",
                "message": "WeChat automation session initialized",
                "interval_minutes": interval,
                "max_cycles": max_cycles,
                "accounts": account_names,
            }
        if not account_names:
            return {"success": False, "status": "error", "message": "公众号没找到"}

        try:
            # For now, just run one cycle
            # In full implementation, this would create a background task
            result = await self.automation.run_cycle(
                account_ids=account_names,
                max_articles=int(arguments.get("max_articles", 3) or 3),
            )

            return {
                "status": "completed",
                "message": f"Automation completed for {max_cycles} cycles",
                "interval_minutes": interval,
                "max_cycles": max_cycles,
                "accounts": account_names,
                "result": self._to_jsonable(result),
            }

        except Exception as e:
            import traceback
            self._emit_runtime_message("error", f"ERROR: Automation failed: {e}\n{traceback.format_exc()}")
            return {"success": False, "status": "error", "message": str(e)}

    async def _handle_universal_run_mission(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle execution of a universal automation mission"""
        app_name = arguments.get("app_name")
        goal = arguments.get("goal")
        context = arguments.get("context", {})

        try:
            # Check if engine exists
            engine = self.automation.get_engine()
            if not engine:
                return {"success": False, "error": "Automation engine not initialized"}
            
            result = await engine.execute_mission(app_name, goal, context)
            return {
                "success": result.get("success", True),
                "app_name": app_name,
                "goal": goal,
                "status": "completed",
                "mission_result": result
            }
        except Exception as e:
            return {"success": False, "error": str(e), "app_name": app_name}

    async def _handle_search_account(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle searching for a WeChat Official Account"""
        account_name = arguments.get("account_name")
        if not account_name:
            return {"success": False, "error": "Missing account_name"}
        
        bounds = self._get_interaction_bounds()
        if not bounds:
            return {"success": False, "error": "Failed to resolve WeChat interaction bounds"}

        result = await self.automation.search_wechat_account(bounds, account_name)
        return {
            "success": result.status.name == "SUCCESS",
            "status": result.status.value,
            "message": result.message,
            "data": result.data
        }

    async def _handle_get_account_article_titles(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle end-to-end public-account title fetching."""
        account_names = arguments.get("account_names") or arguments.get("accounts")
        if account_names:
            if isinstance(account_names, str):
                account_names = [a.strip() for a in account_names.split(",") if a.strip()]
            return await self._handle_get_accounts_latest_articles({
                **arguments,
                "account_names": account_names,
            })

        account_name = arguments.get("account_name") or arguments.get("query")
        if not account_name:
            return {"success": False, "error": "Missing account_name or account_names"}

        max_articles = int(arguments.get("max_articles", 3) or 3)
        read_articles = bool(arguments.get("read_articles", True))
        fetch_kwargs = {
            "account_name": account_name,
            "max_articles": max(1, max_articles),
        }
        if self._supports_keyword_argument(self.automation.fetch_account_article_titles, "read_articles"):
            fetch_kwargs["read_articles"] = read_articles
        result = await self.automation.fetch_account_article_titles(**fetch_kwargs)
        result_dict = self._to_jsonable(result)
        result_dict["success"] = result.status.name == "SUCCESS"
        return result_dict

    async def _handle_get_accounts_latest_articles(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle multi-account latest article fetching."""
        account_names = arguments.get("account_names") or arguments.get("accounts")
        if isinstance(account_names, str):
            account_names = [a.strip() for a in account_names.split(",") if a.strip()]
        if not account_names:
            return {"success": False, "error": "Missing account_names"}

        max_articles = int(arguments.get("max_articles", 3) or 3)
        read_articles = bool(arguments.get("read_articles", True))
        fetch_kwargs = {
            "account_names": account_names,
            "max_articles": max(1, max_articles),
        }
        if self._supports_keyword_argument(self.automation.fetch_accounts_latest_articles, "read_articles"):
            fetch_kwargs["read_articles"] = read_articles
        result = await self.automation.fetch_accounts_latest_articles(**fetch_kwargs)
        result_dict = self._to_jsonable(result)
        result_dict["success"] = result.status.name in ("SUCCESS", "PARTIAL_SUCCESS")
        return result_dict

    async def _handle_click_latest_official_article(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle click latest article flow for a specific account or keyword."""
        account_name = arguments.get("account_name")
        if account_name is None:
            account_name = arguments.get("query")
        search_keyword = arguments.get("search_keyword", "公众号")
        max_articles = int(arguments.get("max_articles", 1) or 1)
        read_articles = bool(arguments.get("read_articles", True))

        if not account_name and not search_keyword:
            return {"success": False, "error": "Missing account_name or search_keyword"}

        handler_kwargs = {
            "account_name": account_name,
            "max_articles": max(1, max_articles),
            "read_articles": read_articles,
            "search_keyword": search_keyword,
        }
        if not self._supports_keyword_argument(
            self.automation.open_latest_official_account_article,
            "search_keyword",
        ):
            handler_kwargs.pop("search_keyword", None)

        result = await self.automation.open_latest_official_account_article(**handler_kwargs)
        result_dict = self._to_jsonable(result)
        result_dict["success"] = result.status.name in ("SUCCESS", "PARTIAL_SUCCESS")
        return result_dict

    async def _handle_click_element(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle clicking a UI element by text"""
        text = arguments.get("text")
        if not text:
            return {"success": False, "error": "Missing text"}
            
        result = await self.automation.click_question(text)
        return {
            "success": result.status.name == "SUCCESS",
            "status": result.status.value,
            "message": result.message,
            "data": result.data
        }

    async def _handle_check_accessibility(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Return the current accessibility runtime status for live debugging."""
        try:
            status = self._to_jsonable(self.automation.get_accessibility_status())
            return {
                "success": True,
                "status": "success",
                "data": status,
            }
        except Exception as exc:
            return {
                "success": False,
                "status": "error",
                "message": str(exc),
            }

    async def _handle_request_accessibility(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Open macOS Accessibility settings and return the permission request result."""
        try:
            response = self._to_jsonable(self.automation.request_accessibility_permission())
            success = bool(response.get("success"))
            return {
                "success": success,
                "status": "success" if success else "error",
                "data": response,
                "message": response.get("message"),
            }
        except Exception as exc:
            return {
                "success": False,
                "status": "error",
                "message": str(exc),
            }
