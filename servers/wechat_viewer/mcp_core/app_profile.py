"""
App Profile System for Universal App Automation

Defines configurations and metadata for different applications to enable
universal control across various GUI environments.
"""
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class ElementSelector:
    """Strategy for locating a UI element"""
    value: Optional[str] = None # Name or identifier
    role: Optional[str] = None
    accessibility_id: Optional[str] = None
    description: Optional[str] = None
    ocr_text: Optional[str] = None
    relative_position: Optional[Dict[str, float]] = None # {"X": 0.5, "Y": 0.5} (normalized 0-1)
    fallback: Optional['ElementSelector'] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {k: v for k, v in self.__dict__.items() if v is not None}
        if self.fallback:
            result['fallback'] = self.fallback.to_dict()
        return result

@dataclass
class AppProfile:
    """Metadata and structural fingerprint for a specific application"""
    name: str
    bundle_id: str  # macOS Bundle ID
    process_names: List[str]  # e.g., ["WeChat", "微信"]
    window_titles: List[str]  # e.g., ["WeChat", "微信"]
    
    # Common UI elements defined for this app
    selectors: Dict[str, ElementSelector] = field(default_factory=dict)
    
    # App-specific behavioral config
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Recovery strategy
    recovery_strategies: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def get_selector(self, key: str) -> Optional[ElementSelector]:
        return self.selectors.get(key)

class AppRegistry:
    """Registry to manage and retrieve AppProfiles"""
    
    def __init__(self):
        self._profiles: Dict[str, AppProfile] = {}
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Initialize built-in profiles with enhanced WeChat selectors"""
        
        # WeChat Profile (MacOS Specific)
        wechat = AppProfile(
            name="WeChat",
            bundle_id="com.tencent.xinWeChat",
            process_names=["WeChat", "微信"],
            window_titles=["WeChat", "微信", "Weixin"],
            selectors={
                "search_bar": ElementSelector(
                    value="搜索",
                    description="Top search bar",
                    ocr_text="搜索",
                    fallback=ElementSelector(
                        value="搜索栏",
                        fallback=ElementSelector(relative_position={"X": 0.15, "Y": 0.08})
                    )
                ),
                "sidebar_chats": ElementSelector(
                    value="聊天",
                    description="Sidebar chat icon",
                    ocr_text="聊天"
                ),
                "sidebar_contacts": ElementSelector(
                    value="通讯录",
                    description="Sidebar contact list icon",
                    ocr_text="通讯录"
                ),
                "official_accounts_folder": ElementSelector(
                    value="订阅号",
                    description="Official account folder in contact list",
                    ocr_text="订阅号"
                ),
                "official_account_result": ElementSelector(
                    value="搜索结果",
                    description="Official account result in search dropdown",
                    role="cell"
                ),
                "message_input": ElementSelector(
                    value="输入框",
                    description="Chat message input area",
                    role="textarea"
                ),
                "menu_bar": ElementSelector(
                    value="菜单栏",
                    description="Bottom menu interaction bar in OA chat",
                    role="toolbar"
                ),
                "menu_item": ElementSelector(
                    description="Generic menu button/question",
                    role="button"
                ),
                "article_card": ElementSelector(
                    description="Article card in chat flow",
                    role="cell"
                )
            },
            recovery_strategies={
                "not_visible": [{"action": "bring_to_front"}],
                "not_running": [{"action": "launch_app"}],
                "stuck": [{"action": "press", "key": "escape"}]
            }
        )
        self.register_profile(wechat)

    def register_profile(self, profile: AppProfile):
        """Register a new app profile"""
        self._profiles[profile.name.lower()] = profile
        for alias in profile.process_names:
            self._profiles[alias.lower()] = profile

    def get_profile(self, app_name: str) -> Optional[AppProfile]:
        """Get profile by app name or alias"""
        return self._profiles.get(app_name.lower())

# Global registry instance
_app_registry = None

def get_app_registry() -> AppRegistry:
    global _app_registry
    if _app_registry is None:
        _app_registry = AppRegistry()
    return _app_registry
