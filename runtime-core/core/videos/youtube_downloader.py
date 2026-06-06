import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging
import yt_dlp
from core.videos.browser_credentials import (
    browser_cookie_sources,
    describe_cookie_source,
)

logger = logging.getLogger(__name__)


def _load_browser_cookie3():
    import browser_cookie3

    return browser_cookie3


class YouTubeDownloader:
    """YouTube视频下载器，处理下载和cookie重试逻辑"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        
    def _get_browser_cookies(self) -> Optional[Tuple[str]]:
        """获取浏览器cookies，优先使用用户默认浏览器"""
        try:
            browser_cookie3 = _load_browser_cookie3()
        except ImportError:
            return None
        for cookies_from_browser in browser_cookie_sources():
            browser = cookies_from_browser[0]
            try:
                browser_cookie3.load(browser)
                return cookies_from_browser
            except Exception:
                continue
        return None
    
    def download_video(
        self,
        url: str,
        download_directory: Optional[str] = None,
        info: Optional[Dict] = None,
        use_cookies: bool = False
    ) -> Tuple[str, str, Dict]:
        """
        下载YouTube视频
        
        Args:
            url: YouTube视频URL
            download_directory: 下载目录路径
            info: 预获取的视频信息
            use_cookies: 是否使用浏览器cookies
            
        Returns:
            tuple: (文件类型, 文件路径, 视频信息)
            
        Raises:
            RuntimeError: 下载失败时抛出
        """
        _download_directory = Path(download_directory or tempfile.mkdtemp()).resolve()
        _download_directory.mkdir(parents=True, exist_ok=True)
        
        video_id = url.split('=')[-1] if '=' in url else url.split('/')[-1]
        video_template = _download_directory / f"{video_id}.%(ext)s"
        
        ydl_opts = {
            "format": None,  # 自动选择最佳格式
            "outtmpl": str(video_template),
            "quiet": True,
            "ignoreerrors": False,
            "no_warnings": True,
            "retries": self.max_retries,
        }
        
        if use_cookies:
            cookies = self._get_browser_cookies()
            if cookies:
                ydl_opts["cookiesfrombrowser"] = cookies
                logger.info(
                    "Using YouTube browser credentials from %s",
                    describe_cookie_source(cookies),
                )
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = info or ydl.extract_info(url, download=False)
                ydl.extract_info(url, download=True)
                
                # 查找下载的文件
                video_file = None
                for ext in ['mp4', 'webm', 'mkv']:
                    potential_file = video_template.with_name(f"{video_id}.{ext}")
                    if potential_file.exists():
                        video_file = potential_file
                        break
                
                if not video_file:
                    # 检查临时文件
                    temp_files = list(_download_directory.glob(f"{video_id}.*.part*"))
                    if temp_files:
                        temp_files[0].rename(video_template.with_name(f"{video_id}.mp4"))
                        video_file = video_template.with_name(f"{video_id}.mp4")
                    else:
                        raise RuntimeError(f"下载的文件未找到: {video_template}")
                
                return 'mp4', str(video_file), info
                
        except yt_dlp.utils.DownloadError as e:
            if "Sign in to confirm you're not a bot" in str(e) and not use_cookies:
                logger.info("检测到机器人验证，尝试使用浏览器cookies重试...")
                return self.download_video(url, download_directory, info, use_cookies=True)
            
            error_msg = f"下载视频失败: {e}\n"
            error_msg += "可能的解决方案:\n"
            error_msg += "1. 稍后重试(YouTube可能有临时限制)\n"
            error_msg += "2. 安装browser-cookie3包自动处理cookies\n"
            error_msg += "3. 手动导出cookies并使用'cookiefile'选项\n"
            error_msg += "4. 检查磁盘空间和权限\n"
            raise RuntimeError(error_msg)
            
        except Exception as e:
            raise RuntimeError(f"下载过程中发生意外错误: {e}")

# 示例用法
if __name__ == "__main__":
    downloader = YouTubeDownloader()
    test_url = "https://www.youtube.com/watch?v=9P8uuXc9iE8"
    
    try:
        file_type, file_path, info = downloader.download_video(test_url)
        print(f"下载成功: {file_type}, {file_path}")
    except Exception as e:
        print(f"下载失败: {e}")
