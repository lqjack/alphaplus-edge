import yt_dlp
from pathlib import Path
import tempfile
from typing import Dict, Optional, List, Union, Tuple
import logging
from core.videos.subtitle_parser import SubtitleParser
# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class YouTubeContentFetcher:
    """YouTube内容获取器（格式+字幕）"""
    
    SUBTITLE_EXTS = ['vtt', 'srt', 'ass', 'ssa', 'ttml', 'dfxp']
    
    def __init__(self, keep_temp_files: bool = False):
        self.keep_temp_files = keep_temp_files
    
    def _get_video_info(self, url: str) -> Dict:
        """获取视频元数据"""
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "ignoreerrors": False,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    
    def get_available_formats(self, url: str) -> List[Dict[str, Union[str, int]]]:
        """获取所有可用格式信息"""
        info = self._get_video_info(url)
        return info.get('formats', []) if info else []
    
    def _get_available_languages(self, info: Dict) -> List[str]:
        """获取可用字幕语言"""
        auto_subs = info.get('automatic_captions', {})
        manual_subs = info.get('subtitles', {})
        return sorted(set(auto_subs.keys()).union(set(manual_subs.keys())))
    
    def _cleanup_temp_files(self, temp_dir: Path):
        """清理临时文件"""
        if not self.keep_temp_files and temp_dir.exists():
            for f in temp_dir.glob("*"):
                try:
                    f.unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {f} - {e}")
            try:
                temp_dir.rmdir()
            except Exception as e:
                logger.warning(f"删除临时目录失败: {temp_dir} - {e}")
    
    def get_first_subtitles(
        self,
        url: str,
        download_directory: Optional[str] = None,
        info: Optional[Dict] = None
    ):
        """
        获取第一个可用的字幕内容并保存为txt文件
        
        Args:
            url: YouTube视频URL
            download_directory: 临时目录路径（可选）
            info: 预获取的视频信息（可选）
            
        Returns:
            第一个可用的字幕内容字符串
            
        Raises:
            RuntimeError: 当获取字幕失败时抛出
        """
        temp_dir = Path(download_directory or tempfile.mkdtemp()).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            info = info or self._get_video_info(url)
            if not info:
                raise RuntimeError(f"无法从 {url} 获取视频信息")
            
            available_langs = self._get_available_languages(info)
            if not available_langs:
                raise RuntimeError("没有可用的字幕语言")
            
            # 下载字幕
            ydl_opts = {
                "writesubtitles": True,
                "subtitleslangs": available_langs,
                "subtitlesformat": "best",
                "skip_download": True,
                "quiet": True,
                "outtmpl": str(temp_dir / "%(id)s.%(lang)s.txt"),
                "writeautomaticsub": True,
                "no_warnings": True,
            }
            video_id = info.get('id', 'unknown')
            subs = None
            if 'zh' in info.get('subtitles', {}):
                parser = SubtitleParser()
                subs = parser.get_best_subtitle(info['subtitles']['zh'])
                subs['language'] = 'zh'
                
            if 'en' in info.get('subtitles', {}):
                parser = SubtitleParser()
                subs = parser.get_best_subtitle(info['subtitles']['en'])  
                subs['language'] = 'en'
            if subs:
                return subs['format'],subs['language'], subs['content']
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"下载字幕失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"处理字幕时发生错误: {e}")
            return None
        finally:
            self._cleanup_temp_files(temp_dir)
    
    def get_first_playable_content_with_subtitles(
        self,
        url: str,
        download_directory: Optional[str] = None,
        info: Optional[Dict] = None
    ) -> Tuple[Optional[str], str]:
        """
        获取第一个可播放格式的内容及其第一个字幕
        
        Args:
            url: YouTube视频URL
            download_directory: 临时目录路径（可选）
            info: 预获取的视频信息（可选）
            
        Returns:
            tuple: (格式内容文本, 第一个字幕内容)
        """
        temp_dir = Path(download_directory or tempfile.mkdtemp()).resolve()
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 获取视频信息
            info = info or self._get_video_info(url)
            if not info:
                raise RuntimeError(f"无法从 {url} 获取视频信息")
            
            # 获取字幕
            format, lang, subtitle_content = self.get_first_subtitles(url, temp_dir, info)
            return subtitle_content
        except Exception as e:
            raise RuntimeError(f"获取内容失败: {e}")
        finally:
            self._cleanup_temp_files(temp_dir)

# 示例用法
if __name__ == "__main__":
    fetcher = YouTubeContentFetcher(keep_temp_files=False)
    
    # 示例URL
    test_url = "https://www.youtube.com/watch?v=9P8uuXc9iE8"
    
    try:
        # 获取第一个字幕
        _, _, subtitle = fetcher.get_first_subtitles(test_url)
        print(f"\n获取到的第一个字幕长度: {len(subtitle)}")
        print("字幕预览:")
        print(subtitle[:200] + "...")
        
        # 获取内容和字幕
        subtitle = fetcher.get_first_playable_content_with_subtitles(test_url)
        print(f"\n获取到的内容长度: {len(subtitle) if subtitle else 0}")
        print(f"获取到的字幕长度: {len(subtitle)}")
        
    except Exception as e:
        print(f"错误: {e}")