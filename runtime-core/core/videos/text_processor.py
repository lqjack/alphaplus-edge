import jieba
from PIL import ImageFont, ImageDraw
import numpy as np

class TextProcessor:
    def __init__(self, config):
        self.font_path = config['video']['font']
        self.max_chars_per_line = 20  # 每行最多字符数

    def split_text(self, text):
        """将长文案分割为适合字幕显示的多行"""
        words = jieba.lcut(text)
        lines, current_line = [], ""
        for word in words:
            if len(current_line + word) <= self.max_chars_per_line:
                current_line += word
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        return lines

    def generate_subtitle_frames(self, text_lines, duration):
        """生成字幕时间轴（每行显示时间）"""
        frames = []
        per_line_time = duration / len(text_lines)
        for i, line in enumerate(text_lines):
            frames.append({
                "text": line,
                "start": i * per_line_time,
                "end": (i + 1) * per_line_time
            })
        return frames