import requests
from pathlib import Path
import json
from xml.etree import ElementTree as ET
import webvtt
from io import StringIO
from core.videos.vvt_parser import VTTSubtitleParser
class SubtitleParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_subtitle_content(self, url, ext):
        """获取字幕原始内容"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Failed to fetch subtitle ({ext}): {str(e)}")
            return None

    def parse_json3(self, content):
        """解析JSON3格式字幕"""
        try:
            data = json.loads(content)
            events = data.get('events', [])
            subtitles = []
            for event in events:
                if 'segs' in event:
                    for seg in event['segs']:
                        if 'utf8' in seg:
                            subtitles.append({
                                'start': event.get('tStartMs', 0) / 1000,
                                'end': (event.get('tStartMs', 0) + event.get('dDurationMs', 0)) / 1000,
                                'text': seg['utf8'].replace('\n', ' ')
                            })
            return subtitles
        except Exception as e:
            print(f"JSON3 parse error: {str(e)}")
            return []

    def parse_ttml(self, content):
        """解析TTML(XML)格式字幕"""
        try:
            root = ET.fromstring(content)
            namespaces = {'tt': 'http://www.w3.org/ns/ttml'}
            subtitles = []
            for p in root.findall('.//tt:p', namespaces):
                subtitles.append({
                    'start': float(p.attrib.get('begin', '0').replace('t', '').replace('s', '')),
                    'end': float(p.attrib.get('end', '0').replace('t', '').replace('s', '')),
                    'text': p.text.replace('\n', ' ') if p.text else ''
                })
            return subtitles
        except Exception as e:
            print(f"TTML parse error: {str(e)}")
            return []

    def parse_vtt(self, content):
        """解析WebVTT格式字幕"""
        try:
            subtitles = []
            parser = VTTSubtitleParser()
            subtitles = parser.parse_from_string(content)
            return subtitles
        except Exception as e:
            print(f"VTT parse error: {str(e)}")
            return []

    def parse_srv1(self, content):
        """解析SRV1格式字幕(类似JSON但结构不同)"""
        try:
            data = json.loads(content)
            subtitles = []
            for event in data.get('body', []):
                subtitles.append({
                    'start': event.get('time', 0) / 1000,
                    'end': (event.get('time', 0) + event.get('dur', 0)) / 1000,
                    'text': event.get('text', '').replace('\n', ' ')
                })
            return subtitles
        except Exception as e:
            print(f"SRV1 parse error: {str(e)}")
            return []

    def parse_subtitle(self, url, ext):
        """获取并解析字幕"""
        content = self.get_subtitle_content(url, ext)
        if not content:
            return []

        ext = ext.lower()
        if ext == 'json3':
            return self.parse_json3(content)
        elif ext == 'ttml':
            return self.parse_ttml(content)
        elif ext == 'vtt':
            return self.parse_vtt(content)
        elif ext == 'srv1':
            return self.parse_srv1(content)
        else:
            print(f"Unsupported subtitle format: {ext}")
            return []

    def get_best_subtitle(self, subtitle_infos, preferred_formats=['json3', 'vtt', 'ttml', 'srv1']):
        """获取最佳可用字幕"""
        for fmt in preferred_formats:
            for sub in subtitle_infos:
                if sub['ext'] == fmt:
                    parsed = self.parse_subtitle(sub['url'], sub['ext'])

                    plain_text = " ".join(
                        [item['text'] for item in parsed if item.get('text')]
                    ).strip()

                    if parsed:
                        return {
                            'format': sub['ext'],
                            'language': sub['name'],
                            'content': plain_text
                        }
        return None

# 使用示例
if __name__ == "__main__":
    # 示例数据
    subtitle_infos = [
        {'ext': 'json3', 'url': 'https://...', 'name': 'Chinese'},
        {'ext': 'vtt', 'url': 'https://...', 'name': 'Chinese'},
        {'ext': 'ttml', 'url': 'https://...', 'name': 'Chinese'}
    ]

    parser = SubtitleParser()
    result = parser.get_best_subtitle(subtitle_infos)
    
    if result:
        print(f"获取到 {result['language']} 字幕 ({result['format']} 格式):")
        for i, sub in enumerate(result['content'][:5]):  # 打印前5条
            print(f"{sub['start']:.1f}-{sub['end']:.1f}: {sub['text']}")
    else:
        print("未能获取有效字幕")