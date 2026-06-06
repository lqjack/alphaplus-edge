from webvtt import WebVTT
from io import StringIO
from pathlib import Path
import json
from typing import List, Dict, Union

class VTTSubtitleParser:
    def __init__(self):
        self.supported_formats = ['.vtt', '.srt']

    def parse_from_file(self, file_path: Union[str, Path]) -> List[Dict]:
        """
        从VTT文件解析字幕
        :param file_path: 字幕文件路径
        :return: 解析后的字幕列表 [{'start': float, 'end': float, 'text': str}, ...]
        """
        try:
            captions = WebVTT().read(file_path)
            return self._convert_captions(captions)
        except Exception as e:
            print(f"Error parsing VTT file: {str(e)}")
            return []

    def parse_from_string(self, content: str) -> List[Dict]:
        """
        从VTT字符串内容解析字幕
        :param content: VTT格式字符串
        :return: 解析后的字幕列表
        """
        try:
            captions = WebVTT().read(StringIO(content))
            return self._convert_captions(captions)
        except Exception as e:
            print(f"Error parsing VTT content: {str(e)}")
            return []

    def _convert_captions(self, captions: WebVTT) -> List[Dict]:
        """将WebVTT对象转换为标准格式"""
        subtitles = []
        for caption in captions:
            subtitles.append({
                'start': self._time_to_seconds(caption.start),
                'end': self._time_to_seconds(caption.end),
                'text': self._clean_text(caption.text),
                'raw_text': caption.text  # 保留原始文本
            })
        return subtitles

    def _time_to_seconds(self, time_str: str) -> float:
        """
        将时间字符串(00:00:00.000)转换为秒数
        :param time_str: VTT格式时间字符串
        :return: 秒数(float)
        """
        h, m, s = time_str.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)

    def _clean_text(self, text: str) -> str:
        """
        清理字幕文本（移除多余空格/换行）
        :param text: 原始文本
        :return: 清理后的文本
        """
        return ' '.join(text.replace('\n', ' ').split())

    def export_to_json(self, subtitles: List[Dict], output_path: Union[str, Path]) -> bool:
        """
        将解析结果导出为JSON文件
        :param subtitles: 解析后的字幕列表
        :param output_path: 输出路径
        :return: 是否成功
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(subtitles, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error exporting to JSON: {str(e)}")
            return False

# 使用示例
if __name__ == "__main__":
    parser = VTTSubtitleParser()
    
    # 示例1：从文件解析
    vtt_file = "subtitles.vtt"
    if Path(vtt_file).exists():
        subtitles = parser.parse_from_file(vtt_file)
        print(f"从文件解析到 {len(subtitles)} 条字幕")
        parser.export_to_json(subtitles, "output.json")
    
    # 示例2：从字符串内容解析
    vtt_content = """
WEBVTT

1
00:00:01.000 --> 00:00:04.000
这是第一句字幕

2
00:00:05.000 --> 00:00:08.000
这是第二句字幕
"""
    subtitles = parser.parse_from_string(vtt_content)
    print("\n从字符串解析结果:")
    for sub in subtitles:
        print(f"{sub['start']:.1f}s - {sub['end']:.1f}s: {sub['text']}")