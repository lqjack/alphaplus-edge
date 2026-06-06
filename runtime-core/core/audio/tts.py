# tts_engine.py
import edge_tts
import asyncio
import os
from pathlib import Path
from hashlib import md5
import platform
import subprocess
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging
from core.tools.files import get_cache_directory
# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TTSConfig:
    """
    TTS 配置数据类
    默认值对应微软Edge TTS的推荐配置
    """
    voice: str = "zh-CN-YunxiNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    cache_dir: str = os.path.join(get_cache_directory(), "tts_cache")
    timeout: int = 30
    proxy: Optional[str] = None
    max_text_length: int = 5000
    auto_play: bool = False
    allowed_voices: tuple = (
        "zh-CN-YunxiNeural",  # 男声
        "zh-CN-XiaoxiaoNeural",  # 女声
        "zh-CN-YunyangNeural",  # 新闻播音
    )

    def validate(self):
        """验证配置有效性"""
        if self.voice not in self.allowed_voices:
            raise ValueError(f"不支持的语音: {self.voice}，可选: {self.allowed_voices}")
        if not -100 <= int(self.rate.strip('%+')) <= 100:
            raise ValueError("语速调整范围应在 -100% 到 +100% 之间")
        if not -100 <= int(self.volume.strip('%+')) <= 100:
            raise ValueError("音量调整范围应在 -100% 到 +100% 之间")
        if not -100 <= int(self.pitch.strip('Hz+')) <= 100:
            raise ValueError("音调调整范围应在 -100Hz 到 +100Hz 之间")
        if self.timeout < 0:
            raise ValueError("超时时间必须为正数")
        if self.max_text_length <= 0:
            raise ValueError("最大文本长度必须为正数")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'voice': self.voice,
            'rate': self.rate,
            'volume': self.volume,
            'pitch': self.pitch,
            'cache_dir': self.cache_dir,
            'timeout': self.timeout,
            'proxy': self.proxy,
            'max_text_length': self.max_text_length,
            'auto_play': self.auto_play
        }

class TTSEngine:
    """
    基于微软Edge TTS的语音合成引擎
    支持配置管理、本地缓存和音频播放
    
    示例用法:
    >>> config = TTSConfig(voice="zh-CN-XiaoxiaoNeural")
    >>> engine = TTSEngine(config)
    >>> asyncio.run(engine.generate_audio("你好世界"))
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        """
        初始化TTS引擎
        
        :param config: 可选的TTS配置，如为None则使用默认配置
        """
        self.config = config if config else TTSConfig()
        self.config.validate()
        self._init_cache_dir()
        
    def _init_cache_dir(self):
        """初始化缓存目录"""
        try:
            cache_path = Path(self.config.cache_dir)
            cache_path.mkdir(exist_ok=True, parents=True)
            logger.info(f"TTS缓存目录已初始化: {cache_path.absolute()}")
        except Exception as e:
            logger.error(f"创建缓存目录失败: {str(e)}")
            raise RuntimeError(f"无法创建缓存目录: {self.config.cache_dir}") from e
    
    def _get_cache_path(self, text: str) -> Path:
        """
        获取文本对应的缓存路径
        使用MD5哈希作为文件名保证唯一性
        """
        text_hash = md5(text.encode('utf-8')).hexdigest()
        return Path(self.config.cache_dir) / f"{text_hash}.mp3"
    
    async def generate_audio(
        self,
        text: str,
        output_file: Optional[str] = None,
        use_cache: bool = True
    ) -> Path:
        """
        生成语音音频文件
        
        :param text: 要合成的文本内容
        :param output_file: 自定义输出路径，None则使用缓存路径
        :param use_cache: 是否检查缓存
        :return: 生成的音频文件路径
        :raises: ValueError, RuntimeError
        """
        # 参数验证
        if not text.strip():
            raise ValueError("输入文本不能为空")
        
        if len(text) > self.config.max_text_length:
            raise ValueError(f"文本长度超过限制 ({self.config.max_text_length} 字符)")
        
        # 检查缓存
        cache_path = self._get_cache_path(text)
        if use_cache and cache_path.exists():
            logger.info(f"使用缓存语音: {cache_path}")
            if output_file:
                return self._copy_file(cache_path, Path(output_file))
            return cache_path
        
        # 确定输出路径
        output_path = Path(output_file) if output_file else cache_path
        
        try:
            # 调用Edge TTS生成语音
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.config.voice,
                rate=self.config.rate,
                volume=self.config.volume,
                pitch=self.config.pitch,
                proxy=self.config.proxy,
                timeout=self.config.timeout
            )
            
            logger.info(f"生成语音: voice={self.config.voice}, text_length={len(text)}")
            await communicate.save(str(output_path))
            
            # 如果使用了自定义路径，也保存到缓存
            if output_file and output_path != cache_path:
                self._copy_file(output_path, cache_path)
            
            # 自动播放
            if self.config.auto_play:
                await self.play_audio(output_path)
                
            return output_path
            
        except edge_tts.exceptions.NoAudioReceived:
            logger.error("未接收到音频数据")
            raise RuntimeError("TTS服务未返回音频数据")
        except Exception as e:
            logger.error(f"语音生成失败: {str(e)}")
            raise RuntimeError(f"语音生成失败: {str(e)}") from e
    
    def _copy_file(self, src: Path, dst: Path) -> Path:
        """复制音频文件"""
        import shutil
        try:
            shutil.copy(src, dst)
            return dst
        except Exception as e:
            logger.warning(f"文件复制失败: {src} -> {dst}, {str(e)}")
            return src
    
    async def play_audio(self, file_path: Path) -> bool:
        """
        播放音频文件
        
        :param file_path: 音频文件路径
        :return: 是否播放成功
        """
        if not file_path.exists():
            logger.error(f"音频文件不存在: {file_path}")
            return False
            
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.run(["afplay", str(file_path)])
            else:
                subprocess.run(["aplay", str(file_path)], check=True)
            return True
        except Exception as e:
            logger.error(f"播放音频失败: {str(e)}")
            return False
    
    async def text_to_speech(
        self,
        text: str,
        play: Optional[bool] = None
    ) -> Path:
        """
        文本转语音 (简化接口)
        
        :param text: 要合成的文本
        :param play: 是否播放，None则使用配置的auto_play设置
        :return: 音频文件路径
        """
        should_play = self.config.auto_play if play is None else play
        audio_path = await self.generate_audio(text)
        
        if should_play:
            await self.play_audio(audio_path)
            
        return audio_path


# 使用示例
async def demo():
    # 自定义配置
    config = TTSConfig(
        voice="zh-CN-XiaoxiaoNeural",
        rate="+10%",
        auto_play=True
    )
    
    # 创建引擎
    engine = TTSEngine(config)
    
    # 生成语音
    try:
        audio_path = await engine.text_to_speech("你好，这是一个语音合成演示")
        print(f"语音已生成: {audio_path}")
    except Exception as e:
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(demo())