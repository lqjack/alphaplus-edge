from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class VideoMeta:
    title: str
    description: str
    video_path: str
    cover_path: Optional[str] = None
    tags: List[str] = None
    publish_time: Optional[datetime] = None
    visibility: str = "public"  # public/private/friends

    def to_platform_format(self, platform: str):
        """转换为不同平台要求的格式"""
        formats = {
            "douyin": {
                "title": self.title[:30],  # 抖音标题限制
                "video": self.video_path,
                "cover": self.cover_path or ""
            },
            "bilibili": {
                "title": self.title,
                "desc": self.description,
                "tag": ",".join(self.tags)[:120]
            }
        }
        return formats.get(platform, {})