# -*- coding: utf-8 -*-
"""
multi_layer_locator.py - 多层级元素定位系统
解决：坐标依赖脆弱性、缺乏元素定位策略
"""

import logging
from typing import Optional, Tuple, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import time
from pathlib import Path
import tempfile
import os

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV2_AVAILABLE = False

if TYPE_CHECKING:
    import numpy as np

class LocatorStrategy(Enum):
    """定位策略优先级"""
    TEMPLATE_MATCH = "template"      # 图像模板匹配（最稳定）
    UI_AUTOMATION = "ui_automation"  # 系统UI自动化接口
    OCR_SEMANTIC = "ocr_semantic"    # OCR+语义匹配
    HEURISTIC = "heuristic"          # 启发式坐标（兜底）
    LEARNED = "learned"              # 机器学习预测位置


@dataclass
class LocationResult:
    """定位结果"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    strategy: LocatorStrategy
    element_hash: Optional[str] = None  # 元素特征哈希，用于追踪
    metadata: Dict[str, Any] = None


class TemplateLibrary:
    """模板库管理 - 存储关键UI元素的图像模板"""
    
    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(exist_ok=True)
        self.templates: Dict[str, Dict] = {}
        self._load_templates()
        
    def _load_templates(self):
        """加载所有模板"""
        for template_file in self.template_dir.glob("*.json"):
            with open(template_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.templates[data['name']] = data
                
    def save_template(self, name: str, image: "np.ndarray", 
                      relative_pos: Dict[str, float],
                      description: str = ""):
        """
        保存新模板
        relative_pos: 相对窗口的位置比例 {x_ratio, y_ratio, w_ratio, h_ratio}
        """
        template_path = self.template_dir / f"{name}.png"
        cv2.imwrite(str(template_path), image)
        
        # 计算图像特征哈希
        feature_hash = self._compute_image_hash(image)
        
        template_data = {
            'name': name,
            'image_path': str(template_path),
            'feature_hash': feature_hash,
            'relative_pos': relative_pos,
            'description': description,
            'created_at': time.time()
        }
        
        json_path = self.template_dir / f"{name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
            
        self.templates[name] = template_data
        
    def _compute_image_hash(self, image: "np.ndarray") -> str:
        """计算感知哈希，用于相似度比较"""
        # 缩放到8x8
        resized = cv2.resize(image, (8, 8), interpolation=cv2.INTER_AREA)
        # 转灰度
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized
        # 计算平均亮度
        avg = gray.mean()
        # 生成哈希：每个像素与平均值比较
        hash_bits = (gray > avg).flatten().astype(int)
        return ''.join(map(str, hash_bits))
        
    def get_template(self, name: str) -> Optional["np.ndarray"]:
        """获取模板图像"""
        if name not in self.templates:
            return None
        path = self.templates[name]['image_path']
        return cv2.imread(path) if Path(path).exists() else None


class MultiLayerLocator:
    """多层级元素定位器"""
    
    def __init__(self, ocr_processor, window_manager, template_dir: str = "templates"):
        self.ocr = ocr_processor
        self.window = window_manager
        self.templates = TemplateLibrary(template_dir)
        self.logger = logging.getLogger("locator")
        
        # 截图保存目录
        self.screenshot_dir = Path("temp_screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        
        # 定位历史，用于学习
        self.location_history: List[LocationResult] = []
        
        # 策略成功率统计
        self.strategy_stats = {s: {'success': 0, 'fail': 0} for s in LocatorStrategy}
        
    async def locate(self, target: str, 
                     screenshot: Optional["np.ndarray"] = None,
                     context: Optional[Dict] = None) -> Optional[LocationResult]:
        """
        多层级定位入口
        按优先级尝试不同策略
        """
        # 获取当前窗口信息
        window_info = self.window.get_window_bounds()
        if not window_info:
            self.logger.error("无法获取窗口信息")
            return None
            
        # 获取截图
        if screenshot is None:
            screenshot, path = self._capture_screenshot()
            
        # 按优先级尝试各策略
        strategies = [
            (LocatorStrategy.TEMPLATE_MATCH, self._template_match),
            (LocatorStrategy.OCR_SEMANTIC, self._ocr_semantic_match),
            (LocatorStrategy.LEARNED, self._learned_position),
            (LocatorStrategy.HEURISTIC, self._heuristic_position),
        ]
        
        for strategy, method in strategies:
            try:
                self.logger.debug(f"尝试 {strategy.value} 策略定位 '{target}'")
                result = await method(target, screenshot, path, window_info, context)
                
                if result and result.confidence > 0.7:
                    self.logger.info(f"{strategy.value} 成功定位 '{target}' "
                                   f"置信度 {result.confidence:.2f}")
                    self.strategy_stats[strategy]['success'] += 1
                    self.location_history.append(result)
                    return result
                else:
                    self.strategy_stats[strategy]['fail'] += 1
                    
            except Exception as e:
                self.logger.warning(f"{strategy.value} 策略失败: {e}")
                self.strategy_stats[strategy]['fail'] += 1
                
        self.logger.error(f"所有策略均无法定位 '{target}'")
        return None
        
    async def _template_match(self, target: str, screenshot: "PIL.PngImagePlugin.PngImageFile", path:str,
                              window_info: Dict, context: Optional[Dict]) -> Optional[LocationResult]:
        """图像模板匹配"""
        # 尝试精确模板名
        template = self.templates.get_template(target)
        
        # 如果没有精确匹配，尝试语义匹配
        if template is None:
            template = self._find_similar_template(target)
            
        if template is None:
            return None
            
        # 处理截图
        image = None
        if hasattr(screenshot, 'size') and hasattr(screenshot, 'width') and hasattr(screenshot, 'height'):
            # PIL Image对象
            import numpy as np
            image = np.array(screenshot)
        elif isinstance(screenshot, np.ndarray):
            image = screenshot
        elif isinstance(screenshot, str) and os.path.exists(screenshot):
            image = cv2.imread(screenshot)
        elif path and os.path.exists(path):
            image = cv2.imread(path)
        else:
            self.logger.error("无法处理截图，截图和路径都无效")
            return None
            
        # 多尺度模板匹配
        result = self._multi_scale_match(template, image)
        
        if result['confidence'] > 0.8:
            return LocationResult(
                x=result['x'],
                y=result['y'],
                width=result['width'],
                height=result['height'],
                confidence=result['confidence'],
                strategy=LocatorStrategy.TEMPLATE_MATCH,
                element_hash=self.templates._compute_image_hash(template)
            )
        return None
        
    def _multi_scale_match(self, template: "np.ndarray", 
                           screenshot: "np.ndarray") -> Dict:
        """多尺度模板匹配，处理不同分辨率/DPI"""
        # 模板和截图都转灰度
        if len(template.shape) == 3:
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template
            
        if len(screenshot.shape) == 3:
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        else:
            screenshot_gray = screenshot
            
        h, w = template_gray.shape
        
        # 尝试不同缩放比例
        scales = [0.8, 0.9, 1.0, 1.1, 1.2]
        best_match = {'confidence': 0, 'x': 0, 'y': 0, 'width': w, 'height': h}
        
        for scale in scales:
            resized_template = cv2.resize(template_gray, 
                                          (int(w * scale), int(h * scale)))
            
            result = cv2.matchTemplate(screenshot_gray, resized_template, 
                                       cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val > best_match['confidence']:
                best_match.update({
                    'confidence': max_val,
                    'x': max_loc[0],
                    'y': max_loc[1],
                    'width': int(w * scale),
                    'height': int(h * scale),
                    'scale': scale
                })
                
        return best_match
        
    def _find_similar_template(self, target: str) -> Optional["np.ndarray"]:
        """查找相似的模板"""
        # 基于目标名称查找相似的模板
        target_lower = target.lower()
        
        # 尝试查找包含目标关键词的模板
        for template_name in self.templates.templates.keys():
            template_lower = template_name.lower()
            if target_lower in template_lower or template_lower in target_lower:
                template = self.templates.get_template(template_name)
                if template is not None:
                    return template
        
        # 尝试模糊匹配
        from difflib import SequenceMatcher
        best_match = None
        best_score = 0
        
        for template_name in self.templates.templates.keys():
            score = SequenceMatcher(None, target_lower, template_name.lower()).ratio()
            if score > best_score and score > 0.6:  # 相似度阈值0.6
                best_score = score
                best_match = template_name
        
        if best_match:
            return self.templates.get_template(best_match)
            
        return None
        
    async def _ocr_semantic_match(self, target: str, screenshot: "PIL.PngImagePlugin.PngImageFile", path:str,
                                  window_info: Dict, context: Optional[Dict]) -> Optional[LocationResult]:
        """OCR语义匹配 - 改进版，解决中文相似字问题"""
        
        # 处理截图
        image = None
        if hasattr(screenshot, 'size') and hasattr(screenshot, 'width') and hasattr(screenshot, 'height'):
            # PIL Image对象
            import numpy as np
            image = np.array(screenshot)
        elif isinstance(screenshot, np.ndarray):
            image = screenshot
        elif isinstance(screenshot, str) and os.path.exists(screenshot):
            image = cv2.imread(screenshot)
        elif path and os.path.exists(path):
            image = cv2.imread(path)
        else:
            self.logger.error("OCR语义匹配失败：截图和路径都无效")
            return None
        
        # 验证图像有效性
        if image is None or image.size == 0:
            self.logger.error("OCR语义匹配失败：图像为空或无效")
            return None
        
        try:
            # OCR识别
            ocr_results = self.ocr.recognize(image)
            
            if not ocr_results:
                self.logger.debug("OCR识别结果为空")
                return None
            
            # 语义相似度匹配
            best_match = None
            best_score = 0
            
            for result in ocr_results:
                text = result.get('text', '')
                confidence = result.get('confidence', 0)
                
                # 跳过空文本或低置信度结果
                if not text or confidence < 50:
                    continue
                
                # 多维度相似度计算
                similarity = self._compute_text_similarity(target, text)
                
                # 结合OCR置信度
                final_score = similarity * (confidence / 100)
                
                if final_score > best_score and final_score > 0.6:
                    best_score = final_score
                    best_match = result
                    
            if best_match:
                pos = best_match['position']
                return LocationResult(
                    x=pos['x'],
                    y=pos['y'],
                    width=pos['width'],
                    height=pos['height'],
                    confidence=best_score,
                    strategy=LocatorStrategy.OCR_SEMANTIC,
                    metadata={'matched_text': best_match['text']}
                )
            return None
            
        except Exception as e:
            self.logger.error(f"OCR语义匹配过程中发生错误: {e}")
            return None
        
    def _compute_text_similarity(self, target: str, candidate: str) -> float:
        """计算文本相似度 - 处理中文相似字"""
        # 1. 精确匹配
        if target == candidate:
            return 1.0
            
        # 2. 包含匹配
        if target in candidate or candidate in target:
            return 0.9
            
        # 3. 编辑距离
        from difflib import SequenceMatcher
        base_similarity = SequenceMatcher(None, target, candidate).ratio()
        
        # 4. 处理中文相似字
        similar_chars = {
            '公': ['公', '厶', '八'],
            '众': ['众', '从', '人'],
            '号': ['号', '日', '曰'],
            '官': ['官', '宫', '官'],
            '方': ['方', '万', '文'],
            '订': ['订', '钉', '丁'],
            '阅': ['阅', '闰', '门'],
            '搜': ['搜', '叟', '搜'],
            '索': ['索', '素', '索'],
        }
        
        # 将相似字视为相同
        normalized_target = self._normalize_similar_chars(target, similar_chars)
        normalized_candidate = self._normalize_similar_chars(candidate, similar_chars)
        
        normalized_similarity = SequenceMatcher(None, normalized_target, 
                                                normalized_candidate).ratio()
        
        # 取最高相似度
        return max(base_similarity, normalized_similarity)
        
    def _normalize_similar_chars(self, text: str, similar_map: Dict) -> str:
        """将相似字归一化"""
        result = []
        for char in text:
            # 找到该字所属的相似组
            normalized = char
            for standard, similars in similar_map.items():
                if char in similars:
                    normalized = standard
                    break
            result.append(normalized)
        return ''.join(result)
        
    async def _learned_position(self, target: str, screenshot: "PIL.PngImagePlugin.PngImageFile", path:str,
                                window_info: Dict, context: Optional[Dict]) -> Optional[LocationResult]:
        """基于历史学习的预测位置"""
        # 查找该目标的历史成功定位
        relevant_history = [
            h for h in self.location_history 
            if h.metadata and h.metadata.get('target') == target
        ]
        
        if len(relevant_history) < 3:
            return None
            
        # 处理截图
        image = None
        if hasattr(screenshot, 'size') and hasattr(screenshot, 'width') and hasattr(screenshot, 'height'):
            # PIL Image对象
            import numpy as np
            image = np.array(screenshot)
        elif isinstance(screenshot, np.ndarray):
            image = screenshot
        elif isinstance(screenshot, str) and os.path.exists(screenshot):
            image = cv2.imread(screenshot)
        elif path and os.path.exists(path):
            image = cv2.imread(path)
        else:
            self.logger.error("学习预测定位失败：截图和路径都无效")
            return None
        
        # 验证图像有效性
        if image is None or image.size == 0:
            self.logger.error("学习预测定位失败：图像为空或无效")
            return None
        
        # 使用正确的键名，兼容不同的窗口信息格式
        width_key = 'width' if 'width' in window_info else 'Width'
        height_key = 'height' if 'height' in window_info else 'Height'
        
        # 计算平均位置（相对窗口）
        avg_x_ratio = np.mean([h.x / window_info[width_key] for h in relevant_history])
        avg_y_ratio = np.mean([h.y / window_info[height_key] for h in relevant_history])
        
        # 预测当前位置
        predicted_x = int(avg_x_ratio * window_info[width_key])
        predicted_y = int(avg_y_ratio * window_info[height_key])
        
        # 在预测位置附近验证
        verification_region = image[
            max(0, predicted_y - 50):predicted_y + 100,
            max(0, predicted_x - 100):predicted_x + 200
        ]
        
        # 使用OCR验证
        ocr_results = self.ocr.recognize(verification_region)
        for result in ocr_results:
            if self._compute_text_similarity(target, result['text']) > 0.7:
                return LocationResult(
                    x=predicted_x + result['position']['x'],
                    y=predicted_y + result['position']['y'],
                    width=result['position']['width'],
                    height=result['position']['height'],
                    confidence=0.75,  # 学习预测的置信度较低
                    strategy=LocatorStrategy.LEARNED
                )
                
        return None
        
    async def _heuristic_position(self, target: str, screenshot: "PIL.PngImagePlugin.PngImageFile", path:str,
                                  window_info: Dict, context: Optional[Dict]) -> Optional[LocationResult]:
        """启发式位置 - 基于常见UI模式"""
        # 预定义的常见元素位置模式
        heuristics = {
            '搜索': {'x_ratio': 0.5, 'y_ratio': 0.08, 'w_ratio': 0.3, 'h_ratio': 0.05},
            '搜索框': {'x_ratio': 0.5, 'y_ratio': 0.08, 'w_ratio': 0.3, 'h_ratio': 0.05},
            '通讯录': {'x_ratio': 0.25, 'y_ratio': 0.95, 'w_ratio': 0.2, 'h_ratio': 0.08},
            '发现': {'x_ratio': 0.5, 'y_ratio': 0.95, 'w_ratio': 0.2, 'h_ratio': 0.08},
            '我': {'x_ratio': 0.75, 'y_ratio': 0.95, 'w_ratio': 0.2, 'h_ratio': 0.08},
        }
        
        # 处理截图
        image = None
        if hasattr(screenshot, 'size') and hasattr(screenshot, 'width') and hasattr(screenshot, 'height'):
            # PIL Image对象
            import numpy as np
            image = np.array(screenshot)
        elif isinstance(screenshot, np.ndarray):
            image = screenshot
        elif isinstance(screenshot, str) and os.path.exists(screenshot):
            image = cv2.imread(screenshot)
        elif path and os.path.exists(path):
            image = cv2.imread(path)
        else:
            self.logger.error("启发式定位失败：截图和路径都无效")
            return None
        
        # 验证图像有效性
        if image is None or image.size == 0:
            self.logger.error("启发式定位失败：图像为空或无效")
            return None
        
        # 查找匹配或相似的启发式规则
        best_rule = None
        best_match = 0
        for key, rule in heuristics.items():
            similarity = self._compute_text_similarity(target, key)
            if similarity > best_match:
                best_match = similarity
                best_rule = rule
                
        if best_rule and best_match > 0.6:
            # 使用正确的键名，兼容不同的窗口信息格式
            width_key = 'width' if 'width' in window_info else 'Width'
            height_key = 'height' if 'height' in window_info else 'Height'
            
            x = int(best_rule['x_ratio'] * window_info[width_key])
            y = int(best_rule['y_ratio'] * window_info[height_key])
            w = int(best_rule['w_ratio'] * window_info[width_key])
            h = int(best_rule['h_ratio'] * window_info[height_key])
            
            return LocationResult(
                x=x, y=y, width=w, height=h,
                confidence=best_match * 0.6,  # 启发式的置信度更低
                strategy=LocatorStrategy.HEURISTIC
            )
            
        return None
        
    def _capture_screenshot(self) -> "np.ndarray":
        """捕获屏幕截图并保存到项目目录"""
        try:
            # 使用window_manager获取窗口截图
            screenshot = self.window.capture_screenshot()
            if screenshot is None:
                self.logger.error("无法捕获窗口截图")
                return None
            
            # 保存截图到项目目录
            screenshot_path = self._save_screenshot_to_project(screenshot, "window_capture")
            if screenshot_path:
                self.logger.debug(f"截图已保存到: {screenshot_path}")
            
            return screenshot, screenshot_path
        except Exception as e:
            self.logger.error(f"捕获截图失败: {e}")
            return None
    
    def _save_screenshot_to_project(self, screenshot, prefix: str = "screenshot") -> Optional[str]:
        """将截图保存到项目目录"""
        try:
            # 生成唯一文件名
            timestamp = int(time.time() * 1000)  # 毫秒级时间戳
            filename = f"{prefix}_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            # 确保图像是numpy数组格式
            if hasattr(screenshot, 'shape'):
                # 已经是numpy数组
                image_array = screenshot
            else:
                # PIL Image对象，转换为numpy数组
                import numpy as np
                image_array = np.array(screenshot)
            
            # 保存截图
            cv2.imwrite(str(filepath), image_array)
            
            self.logger.debug(f"截图已保存到: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"保存截图失败: {e}")
            return None
    
    def _cleanup_screenshot(self, filepath: str):
        """清理截图文件"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                self.logger.debug(f"已删除截图: {filepath}")
        except Exception as e:
            self.logger.warning(f"删除截图失败: {e}")
    
    def cleanup_all_screenshots(self):
        """清理所有截图文件"""
        try:
            for screenshot_file in self.screenshot_dir.glob("*.png"):
                os.remove(screenshot_file)
            self.logger.info(f"已清理所有截图文件")
        except Exception as e:
            self.logger.error(f"清理截图文件失败: {e}")
        
    def get_strategy_stats(self) -> Dict:
        """获取各策略成功率统计"""
        stats = {}
        for strategy, counts in self.strategy_stats.items():
            total = counts['success'] + counts['fail']
            if total > 0:
                stats[strategy.value] = {
                    'success_rate': counts['success'] / total,
                    'total_attempts': total
                }
        return stats