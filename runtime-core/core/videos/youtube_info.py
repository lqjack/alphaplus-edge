import tempfile
from pathlib import Path
from typing import Dict, Optional
import logging
import yt_dlp
from core.videos.browser_credentials import (
    apply_browser_credentials,
    browser_cookie_sources,
    describe_cookie_source,
)

logger = logging.getLogger(__name__)

class YouTubeInfoFetcher:
    """YouTube视频信息获取器，处理视频元数据获取和格式检查"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        
    def get_video_info(
        self,
        url: str,
        download_directory: Optional[str] = None
    ) -> Dict:
        """
        获取YouTube视频信息（不下载视频）
        
        Args:
            url: YouTube视频URL
            download_directory: 临时目录路径
            
        Returns:
            包含视频信息的字典
            
        Raises:
            RuntimeError: 当获取信息失败时抛出
        """
        _download_directory = Path(download_directory or tempfile.mkdtemp()).resolve()
        _download_directory.mkdir(parents=True, exist_ok=True)
        
        ydl_opts = {
            "outtmpl": str(_download_directory / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": False,
            "skip_download": True,
            
            # 字幕配置
            # "writesubtitles": True,
            # "allsubtitles": True,
            "listformats": True,
            # "writeautomaticsub": True,
            # "subtitlesformat": "best",
            
            # 改进的格式选择
            # "format": "bestvideo*+bestaudio/best",
            # "merge_output_format": "mp4",
            
            # 增强的兼容性设置
            "ignoreerrors": True,
            # "extract_flat": "in_playlist",
            # "compat_opts": ["no-youtube-unavailable-videos"],
            
            # 网络和验证设置：优先使用用户默认浏览器登录态
            # "referer": "https://www.youtube.com",
            # "socket_timeout": 10,
            
            # YouTube特定设置
            # "youtube_include_dash_manifest": False,
            # "youtube_include_hls_manifest": False,
            "subtitleslangs": ["zh", "en", "a.en", "a.zh"],
            # "subtitlesformat": "json3"
        }

        try:
            for cookie_source in browser_cookie_sources():
                current_opts = dict(ydl_opts)
                current_opts["cookiesfrombrowser"] = cookie_source
                try:
                    with yt_dlp.YoutubeDL(current_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        logger.info(
                            "YouTube info fetched with browser cookies: %s",
                            describe_cookie_source(cookie_source),
                        )
                        return info
                except yt_dlp.utils.DownloadError as exc:
                    logger.warning(
                        "YouTube info fetch failed with browser cookies %s: %s",
                        describe_cookie_source(cookie_source),
                        exc,
                    )

            with yt_dlp.YoutubeDL(apply_browser_credentials(ydl_opts, enabled=False)) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
                
        except yt_dlp.utils.DownloadError as e:
            if "Sign in to confirm you're not a bot" in str(e):
                # 尝试其他浏览器cookies
                for browser in browser_cookie_sources():
                    try:
                        ydl_opts["cookiesfrombrowser"] = browser
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            return ydl.extract_info(url, download=False)
                    except:
                        continue
                
            # 尝试更宽松的格式选择
            ydl_opts["format"] = "bestvideo+bestaudio/best"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
                
        except Exception as e:
            raise RuntimeError(f"获取视频信息失败: {e}")

# 示例用法
if __name__ == "__main__":
    fetcher = YouTubeInfoFetcher()
    test_url = "https://www.youtube.com/watch?v=9P8uuXc9iE8"
    
    try:
        info = fetcher.get_video_info(test_url)
        print(f"获取视频信息成功: {info['title']}")
    except Exception as e:
        print(f"获取视频信息失败: {e}")
