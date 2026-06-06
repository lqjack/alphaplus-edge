import os
import random
import string
import shutil
import ffmpeg
from typing import List, Tuple, Optional
from pathlib import Path

class AudioProcessor:
    @staticmethod
    def split_audio_segments(
        input_path: str,
        segment_duration: int = 120,
        sample_rate: int = 16000,
        output_format: str = "wav",
        force_cleanup: bool = False,
        output_dir: Optional[str] = None
    ) -> Tuple[List[str], str]:
        """
        通用音频分割函数，支持视频和音频文件
        
        Args:
            input_path: 输入文件路径（支持视频或MP3等音频文件）
            segment_duration: 分段时长（秒）
            sample_rate: 输出采样率（Hz）
            output_format: 输出格式（wav/mp3）
            force_cleanup: 是否在处理后删除临时文件
            output_dir: 指定输出目录（None则自动创建随机目录）
            
        Returns:
            (segment_files, output_dir) 分段文件列表和输出目录
        """
        # 验证输入文件
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")
            
        # 设置输出目录
        if output_dir is None:
            random_dir = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            output_dir = os.path.join(os.path.dirname(input_path), f"segments_{random_dir}")
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # 根据格式确定输出参数
            if output_format.lower() == "wav":
                output_params = {
                    "acodec": "pcm_s16le",
                    "ar": sample_rate,
                    "ac": 1  # 单声道
                }
                ext = ".wav"
            elif output_format.lower() == "mp3":
                output_params = {
                    "acodec": "libmp3lame",
                    "audio_bitrate": "192k",
                    "ar": sample_rate
                }
                ext = ".mp3"
            else:
                raise ValueError(f"Unsupported output format: {output_format}")

            # 生成输出模板
            output_template = os.path.join(output_dir, f"segment_%03d{ext}")
            
            # 执行FFmpeg分割
            try:
                (
                    ffmpeg.input(input_path)
                    .output(
                        output_template,
                        f="segment",
                        segment_time=segment_duration,
                        **output_params
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error as e:
                raise RuntimeError(f"FFmpeg processing failed: {e.stderr.decode('utf-8')}")

            # 获取生成的分段文件
            segment_files = sorted([
                os.path.join(output_dir, f) 
                for f in os.listdir(output_dir) 
                if f.startswith("segment_") and f.endswith(ext)
            ])
            
            return segment_files, output_dir
            
        except Exception as e:
            # 发生错误时清理临时目录
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            raise
        finally:
            # 根据参数清理临时文件
            if force_cleanup and os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)

    @staticmethod
    def convert_to_wav(
        input_path: str,
        output_path: Optional[str] = None,
        sample_rate: int = 16000
    ) -> str:
        """
        将音频文件转换为WAV格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（None则自动生成）
            sample_rate: 目标采样率
            
        Returns:
            输出文件路径
        """
        if output_path is None:
            output_path = os.path.splitext(input_path)[0] + ".wav"
            
        try:
            (
                ffmpeg.input(input_path)
                .output(
                    output_path,
                    acodec="pcm_s16le",
                    ar=sample_rate,
                    ac=1
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return output_path
        except ffmpeg.Error as e:
            raise RuntimeError(f"Audio conversion failed: {e.stderr.decode('utf-8')}")

    @staticmethod
    def process_mp3(
        mp3_path: str,
        segment_duration: int = 120,
        output_format: str = "wav",
        force_cleanup: bool = False
    ) -> Tuple[List[str], str]:
        """
        专门处理MP3文件的分割
        
        Args:
            mp3_path: MP3文件路径
            segment_duration: 分段时长（秒）
            output_format: 输出格式（wav/mp3）
            force_cleanup: 是否清理临时文件
            
        Returns:
            (segment_files, output_dir) 分段文件列表和输出目录
        """
        # 验证MP3文件
        if not mp3_path.lower().endswith('.mp3'):
            raise ValueError("Input file must be an MP3 file")
            
        return AudioProcessor.split_audio_segments(
            input_path=mp3_path,
            segment_duration=segment_duration,
            output_format=output_format,
            force_cleanup=force_cleanup
        )