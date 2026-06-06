"""
Article Reading Component

Handles article reading, content extraction, and text processing operations.
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
class ArticleContent:
    """Article content data structure"""
    title: str
    content: str
    author: Optional[str]
    publish_time: Optional[str]
    read_count: Optional[str]


@dataclass
class ArticleMetadata:
    """Article metadata data structure"""
    title: str
    author: Optional[str]
    publish_time: Optional[str]
    read_count: Optional[str]
    position: Dict[str, int]


class ArticleReader:
    """Handles article reading and content extraction operations"""
    
    def __init__(self, window_manager: WindowManager, ocr_processor: OCRProcessor,
                 gui_automation: IGUIAutomation, adaptive_ocr: AdaptiveOCR):
        self.window_manager = window_manager
        self.ocr_processor = ocr_processor
        self.gui_automation = gui_automation
        self.adaptive_ocr = adaptive_ocr
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.article_reader")
        
        # Reading configuration
        self.read_timeout = 60
        self.scroll_delay = 1.0
        self.click_delay = 0.5
    
    def read_article(self, article_title: str) -> Optional[ArticleContent]:
        """Read an article by title"""
        try:
            self.logger.info(f"Reading article: {article_title}")
            
            # Find and click the article
            if not self._click_article_by_title(article_title):
                self.logger.error(f"Failed to find and click article: {article_title}")
                return None
            
            # Wait for article to load
            time.sleep(3)
            
            # Extract article metadata
            metadata = self._extract_article_metadata()
            if not metadata:
                self.logger.warning("Could not extract article metadata")
            
            # Extract article content
            content = self._extract_article_content()
            if not content:
                self.logger.warning("Could not extract article content")
            
            # Close article
            self._close_article()
            
            # Return article content
            return ArticleContent(
                title=article_title,
                content=content or "",
                author=metadata.author if metadata else None,
                publish_time=metadata.publish_time if metadata else None,
                read_count=metadata.read_count if metadata else None
            )
            
        except Exception as e:
            self.logger.error(f"Error reading article: {e}")
            return None
    
    def _click_article_by_title(self, article_title: str) -> bool:
        """Click on article by title"""
        try:
            self.logger.info(f"Looking for article: {article_title}")
            
            # Capture screenshot
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            # Find article title
            results = self.adaptive_ocr.find_text(screenshot, article_title, fuzzy_match=True)
            if not results:
                self.logger.warning(f"Article '{article_title}' not found")
                return False
            
            # Click on the first result
            result = results[0]
            x = result['position']['x'] + result['position']['width'] // 2
            y = result['position']['y'] + result['position']['height'] // 2
            
            return self.window_manager.click_at(x, y)
            
        except Exception as e:
            self.logger.error(f"Error clicking article by title: {e}")
            return False
    
    def _extract_article_metadata(self) -> Optional[ArticleMetadata]:
        """Extract article metadata (title, author, publish time, read count)"""
        try:
            self.logger.info("Extracting article metadata")
            
            # Capture screenshot of article header
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return None
            
            # Find title
            title_results = self.adaptive_ocr.find_text(screenshot, "title", fuzzy_match=True)
            title = title_results[0]['text'] if title_results else None
            
            # Find author
            author_results = self.adaptive_ocr.find_text(screenshot, "author", fuzzy_match=True)
            author = author_results[0]['text'] if author_results else None
            
            # Find publish time
            time_results = self.adaptive_ocr.find_text(screenshot, "time", fuzzy_match=True)
            publish_time = time_results[0]['text'] if time_results else None
            
            # Find read count
            read_results = self.adaptive_ocr.find_text(screenshot, "read", fuzzy_match=True)
            read_count = read_results[0]['text'] if read_results else None
            
            # Get position information
            position = {}
            if title_results:
                position = title_results[0]['position']
            
            return ArticleMetadata(
                title=title or "",
                author=author,
                publish_time=publish_time,
                read_count=read_count,
                position=position
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting article metadata: {e}")
            return None
    
    def _extract_article_content(self) -> Optional[str]:
        """Extract article content by scrolling and capturing text"""
        try:
            self.logger.info("Extracting article content")
            
            content_parts = []
            max_scrolls = 10
            scroll_count = 0
            
            while scroll_count < max_scrolls:
                # Capture screenshot of current view
                screenshot = self.ocr_processor.capture_screenshot()
                if screenshot is None:
                    break
                
                # Extract text from current view
                ocr_results = self.adaptive_ocr.recognize(screenshot)
                if ocr_results:
                    for result in ocr_results:
                        content_parts.append(result.text)
                
                # Scroll down to load more content
                self.window_manager.scroll_down()
                time.sleep(self.scroll_delay)
                
                scroll_count += 1
            
            # Combine all content parts
            full_content = "\n".join(content_parts)
            
            if full_content.strip():
                self.logger.info(f"Extracted article content ({len(full_content)} characters)")
                return full_content
            else:
                self.logger.warning("No content extracted from article")
                return None
            
        except Exception as e:
            self.logger.error(f"Error extracting article content: {e}")
            return None
    
    def _close_article(self) -> bool:
        """Close the current article"""
        try:
            self.logger.info("Closing article")
            
            # Try multiple close methods
            close_methods = [
                self._close_by_back_button,
                self._close_by_keyboard_shortcut,
                self._close_by_menu
            ]
            
            for method in close_methods:
                try:
                    if method():
                        self.logger.info("Successfully closed article")
                        return True
                except Exception as e:
                    self.logger.warning(f"Close method failed: {e}")
                    continue
            
            self.logger.warning("All close methods failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error closing article: {e}")
            return False
    
    def _close_by_back_button(self) -> bool:
        """Close article using back button"""
        try:
            # Look for back button
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            back_indicators = ["返回", "Back", "返回上一页", "Back to list"]
            
            for indicator in back_indicators:
                results = self.adaptive_ocr.find_text(screenshot, indicator)
                if results:
                    result = results[0]
                    x = result['position']['x'] + result['position']['width'] // 2
                    y = result['position']['y'] + result['position']['height'] // 2
                    
                    return self.window_manager.click_at(x, y)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error closing by back button: {e}")
            return False
    
    def _close_by_keyboard_shortcut(self) -> bool:
        """Close article using keyboard shortcut"""
        try:
            # Try common close shortcuts
            shortcuts = ["esc", "cmd+w", "ctrl+w"]
            
            for shortcut in shortcuts:
                try:
                    self.window_manager.press_key(shortcut)
                    time.sleep(0.5)
                    
                    # Verify if article is closed by checking for article indicators
                    if self._verify_article_closed():
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error closing by keyboard shortcut: {e}")
            return False
    
    def _close_by_menu(self) -> bool:
        """Close article using menu options"""
        try:
            # Look for menu button
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            menu_indicators = ["菜单", "Menu", "更多", "More"]
            
            for indicator in menu_indicators:
                results = self.adaptive_ocr.find_text(screenshot, indicator)
                if results:
                    result = results[0]
                    x = result['position']['x'] + result['position']['width'] // 2
                    y = result['position']['y'] + result['position']['height'] // 2
                    
                    if self.window_manager.click_at(x, y):
                        time.sleep(1)
                        
                        # Look for close option in menu
                        menu_screenshot = self.ocr_processor.capture_screenshot()
                        if menu_screenshot is None:
                            return False
                        
                        close_results = self.adaptive_ocr.find_text(menu_screenshot, "关闭", fuzzy_match=True)
                        if close_results:
                            close_result = close_results[0]
                            close_x = close_result['position']['x'] + close_result['position']['width'] // 2
                            close_y = close_result['position']['y'] + close_result['position']['height'] // 2
                            
                            return self.window_manager.click_at(close_x, close_y)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error closing by menu: {e}")
            return False
    
    def _verify_article_closed(self) -> bool:
        """Verify that article has been closed"""
        try:
            # Check if we're back to article list
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False
            
            # Look for article list indicators
            list_indicators = ["阅读", "Read", "文章", "Article", "列表", "List"]
            
            for indicator in list_indicators:
                results = self.adaptive_ocr.find_text(screenshot, indicator)
                if results:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error verifying article closed: {e}")
            return False
    
    def extract_text_from_region(self, region: Tuple[int, int, int, int]) -> Optional[str]:
        """Extract text from a specific screen region"""
        try:
            self.logger.info(f"Extracting text from region: {region}")
            
            # Capture screenshot of specific region
            screenshot = self.ocr_processor.capture_screenshot(region)
            if screenshot is None:
                return None
            
            # Extract text from region
            ocr_results = self.adaptive_ocr.recognize(screenshot)
            if not ocr_results:
                return None
            
            # Combine all text results
            extracted_text = " ".join([result.text for result in ocr_results])
            
            self.logger.info(f"Extracted text from region: {extracted_text[:100]}...")
            return extracted_text
            
        except Exception as e:
            self.logger.error(f"Error extracting text from region: {e}")
            return None