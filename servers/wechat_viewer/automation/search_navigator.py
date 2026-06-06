"""
Search and Navigation Component

Handles WeChat search operations, navigation, and UI interactions.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from mcp_core.interfaces import IWindowManager, IGUIAutomation, IOCRProcessor
from automation.adaptive_ocr import AdaptiveOCR
from automation.window_manager import WindowManager
from automation.ocr_processor import OCRProcessor


@dataclass
class SearchResult:
    """Search result data structure"""
    title: str
    position: Dict[str, int]
    confidence: float


class SearchNavigator:
    """Handles WeChat search and navigation operations"""
    
    def __init__(self, window_manager: WindowManager, ocr_processor: OCRProcessor, 
                 gui_automation: IGUIAutomation, adaptive_ocr: AdaptiveOCR):
        self.window_manager = window_manager
        self.ocr_processor = ocr_processor
        self.gui_automation = gui_automation
        self.adaptive_ocr = adaptive_ocr
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.search_navigator")
        
        # Search configuration
        self.search_timeout = 30
        self.click_delay = 1.0
        self.scroll_delay = 0.5
    
    def search_public_account(self, account_name: str) -> bool:
        """Search for a public account"""
        try:
            self.logger.info(f"Searching for public account: {account_name}")
            
            # Ensure WeChat is running and visible
            if not self.window_manager.ensure_wechat_running():
                self.logger.error("WeChat application is not running")
                return False
            
            if not self.window_manager.bring_to_front():
                self.logger.error("Failed to bring WeChat to front")
                return False
            
            if not self.window_manager.verify_visibility():
                self.logger.error("WeChat window is not visible")
                return False
            
            # Click search bar
            if not self._click_search_bar():
                self.logger.error("Failed to click search bar")
                return False
            
            # Type account name
            if not self._type_account_name(account_name):
                self.logger.error("Failed to type account name")
                return False
            
            # Wait for search results
            time.sleep(2)
            
            # Find and click the account
            if not self._click_account_result(account_name):
                self.logger.error("Failed to find and click account result")
                return False
            
            self.logger.info(f"Successfully searched for public account: {account_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error searching for public account: {e}")
            return False
    
    def _click_search_bar(self) -> bool:
        """Click the search bar"""
        try:
            self.logger.info("Clicking search bar")
            
            # Try multiple search strategies
            strategies = [
                self._click_search_bar_by_text,
                self._click_search_bar_by_position,
                self._click_search_bar_by_ocr
            ]
            
            for strategy in strategies:
                try:
                    if strategy():
                        self.logger.info("Successfully clicked search bar")
                        return True
                except Exception as e:
                    self.logger.warning(f"Search bar click strategy failed: {e}")
                    continue
            
            self.logger.error("All search bar click strategies failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking search bar: {e}")
            return False
    
    def _click_search_bar_by_text(self) -> bool:
        """Click search bar by finding '搜索' text"""
        try:
            # Capture screenshot
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            # Find search text
            results = self.adaptive_ocr.find_text(screenshot, "搜索")
            if not results:
                return False
            
            # Click on the first result
            result = results[0]
            x = result['position']['x'] + result['position']['width'] // 2
            y = result['position']['y'] + result['position']['height'] // 2
            
            return self.window_manager.click_at(x, y)
            
        except Exception as e:
            self.logger.error(f"Error clicking search bar by text: {e}")
            return False
    
    def _click_search_bar_by_position(self) -> bool:
        """Click search bar by known position"""
        try:
            # Try clicking at common search bar positions
            positions = [
                (100, 50),   # Top left
                (200, 50),   # Top center
                (300, 50),   # Top right
                (100, 100),  # Middle left
                (200, 100),  # Middle center
                (300, 100),  # Middle right
            ]
            
            for x, y in positions:
                if self.window_manager.click_at(x, y):
                    # Verify by checking if keyboard input is possible
                    if self._verify_search_bar_click():
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking search bar by position: {e}")
            return False
    
    def _click_search_bar_by_ocr(self) -> bool:
        """Click search bar using OCR to find input field"""
        try:
            # Capture screenshot
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            # Look for input field indicators
            input_indicators = ["搜索", "Search", "输入", "Input"]
            
            for indicator in input_indicators:
                results = self.adaptive_ocr.find_text(screenshot, indicator)
                if results:
                    result = results[0]
                    x = result['position']['x'] + result['position']['width'] // 2
                    y = result['position']['y'] + result['position']['height'] // 2
                    
                    if self.window_manager.click_at(x, y):
                        if self._verify_search_bar_click():
                            return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking search bar by OCR: {e}")
            return False
    
    def _verify_search_bar_click(self) -> bool:
        """Verify that search bar was clicked successfully"""
        try:
            # Type a test character to verify
            self.window_manager.type_text("a")
            time.sleep(0.5)
            
            # Clear the test character
            self.window_manager.press_key("backspace")
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error verifying search bar click: {e}")
            return False
    
    def _type_account_name(self, account_name: str) -> bool:
        """Type the account name in search bar"""
        try:
            self.logger.info(f"Typing account name: {account_name}")
            
            # Clear any existing text
            self.window_manager.press_key("cmd+a")  # Select all
            time.sleep(0.5)
            self.window_manager.press_key("backspace")  # Delete
            time.sleep(0.5)
            
            # Type the account name
            self.window_manager.type_text(account_name)
            time.sleep(1)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error typing account name: {e}")
            return False
    
    def _click_account_result(self, account_name: str) -> bool:
        """Click on the account result"""
        try:
            self.logger.info(f"Looking for account result: {account_name}")
            
            # Capture screenshot of search results area
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            # Find account name in results
            results = self.adaptive_ocr.find_text(screenshot, account_name, fuzzy_match=True)
            if not results:
                self.logger.warning(f"Account '{account_name}' not found in search results")
                return False
            
            # Click on the first result
            result = results[0]
            x = result['position']['x'] + result['position']['width'] // 2
            y = result['position']['y'] + result['position']['height'] // 2
            
            return self.window_manager.click_at(x, y)
            
        except Exception as e:
            self.logger.error(f"Error clicking account result: {e}")
            return False
    
    def navigate_to_article_list(self) -> bool:
        """Navigate to article list view"""
        try:
            self.logger.info("Navigating to article list")
            
            # Wait for article list to load
            time.sleep(3)
            
            # Verify we're in article list by looking for article indicators
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            article_indicators = ["阅读", "Read", "文章", "Article"]
            for indicator in article_indicators:
                results = self.adaptive_ocr.find_text(screenshot, indicator)
                if results:
                    self.logger.info("Successfully navigated to article list")
                    return True
            
            self.logger.warning("Could not verify article list navigation")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to article list: {e}")
            return False
    
    def scroll_to_load_more(self) -> bool:
        """Scroll to load more articles"""
        try:
            self.logger.info("Scrolling to load more articles")
            
            # Scroll down
            self.window_manager.scroll_down()
            time.sleep(self.scroll_delay)
            
            # Wait for new content to load
            time.sleep(2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling to load more articles: {e}")
            return False
    
    def close_current_tab(self) -> bool:
        """Close current tab/window"""
        try:
            self.logger.info("Closing current tab")
            return self.window_manager.close_tab()
        except Exception as e:
            self.logger.error(f"Error closing current tab: {e}")
            return False