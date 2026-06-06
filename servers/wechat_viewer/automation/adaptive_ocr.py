# -*- coding: utf-8 -*-
"""
adaptive_ocr.py - 自适应OCR处理器
解决：OCR识别不稳定、中文相似字问题
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
import time

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    CV2_AVAILABLE = False

from mcp_core.interfaces import TextResult

if TYPE_CHECKING:
    import numpy as np

@dataclass
class OCRConfig:
    """OCR配置"""
    confidence_threshold: float = 0.3
    enable_preprocessing: bool = True
    use_gpu: bool = False
    language: str = "ch_sim+en"  # 简体中文+英文


class ImagePreprocessor:
    """图像预处理 - 提升OCR识别率"""
    
    def __init__(self):
        self.logger = logging.getLogger("ocr_preprocessor")
        
    def preprocess(self, image: "np.ndarray", 
                   text_type: str = "general") -> List["np.ndarray"]:
        """
        生成多种预处理图像，提高识别率
        """
        if not CV2_AVAILABLE:
            self.logger.warning("cv2 not available, returning original image only")
            return [image]
            
        variants = [image]  # 原始图像
        
        # 确保图像是numpy数组格式
        if hasattr(image, 'shape'):
            # 已经是numpy数组
            img_array = image
        else:
            # PIL Image对象，转换为numpy数组
            import numpy as np
            img_array = np.array(image)
        
        # 灰度化
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_array
            
        variants.append(gray)
        
        # 二值化 - 多种阈值
        for threshold in [127, 150, 180]:
            _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
            variants.append(binary)
            
        # 自适应二值化
        adaptive = cv2.adaptiveThreshold(gray, 255, 
                                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 11, 2)
        variants.append(adaptive)
        
        # 去噪
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        variants.append(denoised)
        
        # 锐化（针对小文字）
        if text_type == "small":
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(gray, -1, kernel)
            variants.append(sharpened)
            
        # 对比度增强
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        variants.append(enhanced)
        
        # 缩放（针对不同DPI）
        for scale in [0.8, 1.2]:
            resized = cv2.resize(gray, None, fx=scale, fy=scale, 
                                interpolation=cv2.INTER_CUBIC)
            variants.append(resized)
            
        return variants


class AdaptiveOCR:
    """自适应OCR处理器"""
    
    def __init__(self, base_ocr_engine, config: OCRConfig = None):
        self.ocr = base_ocr_engine
        self.config = config or OCRConfig()
        self.preprocessor = ImagePreprocessor()
        self.logger = logging.getLogger("adaptive_ocr")
        
        # 中文相似字映射
        self.similar_chars = {
            '公': ['公', ],
            '众': ['众', ],
            '号': ['号', ],
            '官': ['官', ],
            '方': ['方', ],
            '订': ['订', ],
            '阅': ['阅', ],
            '搜': ['搜', ],
            '索': ['索', ],
            '信': ['信', ],
            '微': ['微', ],
            '信': ['信', ],
        }
        
        # 识别历史，用于自适应
        self.recognition_history: List[Dict] = []
        
    def recognize(self, image: "np.ndarray", 
                  target_hint: Optional[str] = None) -> List[Dict]:
        """
        自适应OCR识别
        
        Args:
            image: 输入图像
            target_hint: 预期文本提示（用于后处理优化）
        """
        base_size = self._get_image_size(image)

        # 1. 生成多种预处理图像. Native macOS Vision is already a full-page
        # recognizer and becomes very slow if invoked for every variant, so use
        # a single pass when tesseract is not available.
        if self._base_ocr_prefers_single_pass():
            variants = [image]
        else:
            variants = self.preprocessor.preprocess(image)
        
        all_results = []
        
        # 2. 对每种预处理图像进行识别
        for variant in variants:
            try:
                # 检查OCR引擎是否有recognize方法，如果没有则使用recognize_text
                if hasattr(self.ocr, 'recognize'):
                    results = self.ocr.recognize(variant)
                elif hasattr(self.ocr, 'recognize_text'):
                    # 使用OCRProcessor的recognize_text方法
                    try:
                        text = self.ocr.recognize_text(variant)
                        if text:
                            results = [{'text': text, 'confidence': 80, 'position': {'x': 0, 'y': 0, 'width': 100, 'height': 20}}]
                        else:
                            results = []
                    except Exception as e:
                        self.logger.warning(f"OCR识别失败，使用空结果: {e}")
                        results = []
                else:
                    self.logger.error("OCR引擎既没有recognize方法也没有recognize_text方法")
                    results = []
                all_results.extend(
                    self._normalize_variant_coordinates(results, base_size, self._get_image_size(variant))
                )
            except Exception as e:
                self.logger.debug(f"某种预处理识别失败: {e}")
                
        # 3. 合并和去重结果
        merged = self._merge_results(all_results)
        
        # 4. 如果有目标提示，进行语义校正
        if target_hint:
            merged = self._semantic_correction(merged, target_hint)
            
        # 5. 置信度过滤、排序并包装为TextResult
        final_results = []
        for r in merged:
            if r.get('confidence', 0) >= self.config.confidence_threshold * 100:
                final_results.append(TextResult(
                    text=r.get('text', ''),
                    confidence=r.get('confidence', 0),
                    position=r.get('position', {})
                ))
        
        final_results.sort(key=lambda x: -x.confidence)
        
        # 6. 记录历史
        self.recognition_history.append({
            'timestamp': time.time(),
            'results_count': len(final_results),
            'target_hint': target_hint
        })
        
        return final_results

    def _base_ocr_prefers_single_pass(self) -> bool:
        """Avoid expensive variant loops for OCR engines that already preprocess internally."""
        if not hasattr(self.ocr, "_is_tesseract_available"):
            return False
        try:
            dep_manager = getattr(self.ocr, "dep_manager", None)
            pytesseract = dep_manager.get_dependency("pytesseract") if dep_manager else None
            return not self.ocr._is_tesseract_available(pytesseract)
        except Exception:
            return False

    def _get_image_size(self, image) -> Tuple[int, int]:
        """Return image size as (width, height) for PIL or numpy-like images."""
        if image is None:
            return (0, 0)
        if hasattr(image, "size") and not hasattr(image, "shape"):
            return image.size
        if hasattr(image, "shape"):
            height, width = image.shape[:2]
            return (int(width), int(height))
        width = getattr(image, "width", 0)
        height = getattr(image, "height", 0)
        return (int(width or 0), int(height or 0))

    def _normalize_variant_coordinates(
        self,
        results: List[Dict],
        base_size: Tuple[int, int],
        variant_size: Tuple[int, int],
    ) -> List[Dict]:
        """Map OCR boxes from a preprocessed variant back to the original image coordinates."""
        base_width, base_height = base_size
        variant_width, variant_height = variant_size
        if (
            not results
            or base_width <= 0
            or base_height <= 0
            or variant_width <= 0
            or variant_height <= 0
            or (base_width == variant_width and base_height == variant_height)
        ):
            return results

        scale_x = base_width / variant_width
        scale_y = base_height / variant_height
        normalized = []
        for result in results:
            item = dict(result)
            position = dict(item.get("position") or {})
            if position:
                for key in ("x", "left"):
                    if key in position:
                        position[key] = position[key] * scale_x
                for key in ("y", "top"):
                    if key in position:
                        position[key] = position[key] * scale_y
                for key in ("width", "w"):
                    if key in position:
                        position[key] = position[key] * scale_x
                for key in ("height", "h"):
                    if key in position:
                        position[key] = position[key] * scale_y
                item["position"] = position

            for key in ("x", "left"):
                if key in item:
                    item[key] = item[key] * scale_x
            for key in ("y", "top"):
                if key in item:
                    item[key] = item[key] * scale_y
            for key in ("width", "w"):
                if key in item:
                    item[key] = item[key] * scale_x
            for key in ("height", "h"):
                if key in item:
                    item[key] = item[key] * scale_y

            normalized.append(item)
        return normalized
        
    def _merge_results(self, results: List[Dict]) -> List[Dict]:
        """合并多个识别结果，去重"""
        # 按位置聚类
        position_tolerance = 10  # 像素
        
        clusters = []
        
        for result in results:
            pos = result.get('position', {})
            x, y = pos.get('x', 0), pos.get('y', 0)
            
            # 查找匹配的聚类
            matched_cluster = None
            for cluster in clusters:
                cx, cy = cluster['center']
                if abs(x - cx) < position_tolerance and abs(y - cy) < position_tolerance:
                    matched_cluster = cluster
                    break
                    
            if matched_cluster:
                matched_cluster['results'].append(result)
                # 更新中心
                matched_cluster['center'] = (
                    (matched_cluster['center'][0] * len(matched_cluster['results']) + x) 
                    / (len(matched_cluster['results']) + 1),
                    (matched_cluster['center'][1] * len(matched_cluster['results']) + y)
                    / (len(matched_cluster['results']) + 1)
                )
            else:
                clusters.append({
                    'center': (x, y),
                    'results': [result]
                })
                
        # 从每个聚类中选择最佳结果
        merged = []
        for cluster in clusters:
            # 选择置信度最高的结果
            best = max(cluster['results'], key=lambda x: x.get('confidence', 0))
            merged.append(best)
            
        return merged
        
    def _semantic_correction(self, results: List[Dict], 
                             target_hint: str) -> List[Dict]:
        """基于目标提示进行语义校正"""
        corrected = []
        
        for result in results:
            text = result.get('text', '')
            confidence = result.get('confidence', 0)
            
            # 计算与目标的相似度
            similarity = self._compute_similarity(text, target_hint)
            
            # 如果相似度高，提升置信度
            if similarity > 0.8:
                confidence = min(100, confidence + 10)
                result['confidence'] = confidence
                result['semantic_boost'] = True
                
            # 处理相似字
            normalized_text = self._normalize_similar_chars(text)
            normalized_target = self._normalize_similar_chars(target_hint)
            
            if normalized_text == normalized_target:
                confidence = min(100, confidence + 15)
                result['confidence'] = confidence
                result['similar_char_match'] = True
                
            corrected.append(result)
            
        return corrected
        
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        from difflib import SequenceMatcher
        
        # 精确匹配
        if text1 == text2:
            return 1.0
            
        # 包含匹配 (仅针对有意义且长度足够的字符串)
        if (len(text1) > 1 and text1 in text2) or (len(text2) > 1 and text2 in text1):
            return 0.9
            
        # 编辑距离
        return SequenceMatcher(None, text1, text2).ratio()
        
    def _normalize_similar_chars(self, text: str) -> str:
        """归一化相似字"""
        result = []
        for char in text:
            # 查找该字的标准形式
            standard = char
            for std, similars in self.similar_chars.items():
                if char in similars:
                    standard = std
                    break
            result.append(standard)
        return ''.join(result)
        
    def find_text(self, image: "np.ndarray", target: str,
                  fuzzy_match: bool = True) -> List[Dict]:
        """
        在图像中查找特定文本
        
        Args:
            image: 输入图像
            target: 目标文本
            fuzzy_match: 是否使用模糊匹配
        """
        results = self.recognize(image, target_hint=target if fuzzy_match else None)
        
        matches = []
        for result in results:
            text = result.get('text', '')
            
            # 精确匹配
            if target == text:
                matches.append({**result, 'match_type': 'exact'})
                continue
                
            # 模糊匹配
            if fuzzy_match:
                similarity = self._compute_similarity(text, target)
                if similarity > 0.7:
                    matches.append({**result, 'match_type': 'fuzzy', 
                                   'similarity': similarity})
                    
        # 按匹配质量排序
        matches.sort(key=lambda x: (
            x.get('match_type') == 'exact',
            x.get('similarity', 0),
            x['confidence']
        ), reverse=True)
        
        return matches
        
    def get_adaptive_threshold(self) -> float:
        """基于历史识别情况获取自适应阈值"""
        if len(self.recognition_history) < 10:
            return self.config.confidence_threshold
            
        recent = self.recognition_history[-10:]
        avg_results = sum(r['results_count'] for r in recent) / len(recent)
        
        # 如果平均结果数太少，降低阈值
        if avg_results < 3:
            return max(0.5, self.config.confidence_threshold - 0.1)
            
        # 如果结果数正常，保持阈值
        return self.config.confidence_threshold
