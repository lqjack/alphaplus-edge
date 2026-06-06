import os
try:
    import librosa
except ImportError:
    import logging
    logging.warning("librosa module not found. Audio processing features will not work.")
    librosa = None
from core.tools.files import get_file_name, find_audio_files, read_file
import soundfile as sf
try:
    from mcp_legacy.servers.youtube.youtube_mp3_download import youtube_to_mp3
except ImportError:
    from servers.youtube.youtube_mp3_download import youtube_to_mp3
from PIL import Image
from urllib.parse import urlparse
import tempfile
from pathlib import Path
from typing import List, Dict
from core.audio.whisper_impl import _transcribe_audio
import logging
import random
import string
import shutil
from core.videos.youtube_downloader import YouTubeDownloader
from core.videos.youtube_info import YouTubeInfoFetcher

logger = logging.getLogger(__name__)

def summarize_youtube_video(youtube_url, outputs_dir, progress_bar, progress_text, summarization_function, no_summary=True):
    raw_audio_dir = f"{outputs_dir}/raw_audio/"
    segment_length = 10 * 60  # 10 minutes

    os.makedirs(outputs_dir, exist_ok=True)

    file_name = get_file_name(youtube_url)
    chunks_dir = f"{outputs_dir}/{file_name}/chunks/"
    transcripts_file = f"{outputs_dir}/{file_name}/transcripts.txt"
    summary_file = f"{outputs_dir}/{file_name}/summary.txt"

    # 检查本地文件是否存在
    if os.path.exists(audio_filename := f"{raw_audio_dir}/{file_name}.mp3"):
        progress_text.text(("Reading local audio file..."))
        chunked_audio_files = chunk_audio(audio_filename, segment_length=segment_length, output_dir=chunks_dir)
    elif os.path.exists(chunked_audio_files_path := f"{chunks_dir}/"):
        progress_text.text(("Reading local chunked audio files..."))
        chunked_audio_files = find_audio_files(chunked_audio_files_path)
    elif os.path.exists(transcripts_file):
        progress_text.text(("Reading local transcripts file..."))
        transcriptions = [read_file(transcripts_file)]
        chunked_audio_files = None
    elif os.path.exists(summary_file):
        progress_text.text(("Reading local summary file..."))
        summaries = [read_file(summary_file)]
        chunked_audio_files = None
    else:
        progress_text.text(("Downloading video..."))
        audio_filename = youtube_to_mp3(youtube_url, output_dir=raw_audio_dir)
        progress_bar.progress(0.25)

        progress_text.text(("Chunking audio..."))
        chunked_audio_files = chunk_audio(audio_filename, segment_length=segment_length, output_dir=chunks_dir)
        progress_bar.progress(0.5)

        progress_text.text(("Transcribing audio..."))
        transcriptions = _transcribe_audio(chunked_audio_files)
        progress_bar.progress(0.75)
        if not no_summary:
            progress_text.text(("Generating summary..."))
            system_prompt = ("You are a helpful assistant that summarizes and distills YouTube videos. You are provided chunks of raw audio that were transcribed from the video's audio. Summarize and distill the current chunk to succinct and clear bullet points of its contents.")
            summaries = summarization_function(transcriptions, system_prompt=system_prompt, output_file=summary_file)
            if summaries is not None:
                system_prompt_tldr = ("You are a helpful assistant that summarizes YouTube videos. Someone has already summarized the video to key points. Summarize the key points to one or two sentences that capture the essence of the video.")
                long_summary = "\n".join(summaries)
                short_summary = summarization_function([long_summary], system_prompt=system_prompt_tldr, output_file=summary_file)[0]
            progress_bar.progress(1.0)
            progress_text.text(("Summary complete."))
            return long_summary, short_summary
        
        else:
            return transcriptions, transcriptions

def chunk_audio(filename, segment_length: int, output_dir):
    if librosa is None:
        raise ImportError("librosa is required for audio chunking but is not installed")

    os.makedirs(output_dir, exist_ok=True)
    audio, sr = librosa.load(filename, sr=44100)
    duration = librosa.get_duration(y=audio, sr=sr)
    num_segments = int(duration / segment_length) + 1
    for i in range(num_segments):
        start = i * segment_length * sr
        end = (i + 1) * segment_length * sr
        segment = audio[start:end]
        sf.write(os.path.join(output_dir, f"segment_{i}.mp3"), segment, sr)
    chunked_audio_files = find_audio_files(output_dir)
    return sorted(chunked_audio_files)

def convert_webm_to_mp4(video_path: str) -> str:
    import ffmpeg
    r"""Convert a .webm video file to .mp4 format.

    Args:
        video_path (str): The path to the .webm video file.

    Returns:
        str: The path to the converted .mp4 file.

    Raises:
        RuntimeError: If the conversion fails.
    """
    import os
    # 检查文件是否存在
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # 检查文件是否为 .webm 格式
    if not video_path.lower().endswith(".webm"):
        raise ValueError(f"File is not a .webm video: {video_path}")

    # 生成输出文件路径
    output_path = video_path.rsplit('.', 1)[0] + ".mp4"

    # 如果输出文件已存在，直接返回
    if os.path.exists(output_path):
        return output_path

    try:
        # 使用 FFmpeg 转换格式
        (
            ffmpeg.input(video_path)
            .output(output_path, vcodec="libx264", acodec="aac")
            .run()
        )
        return output_path
    except ffmpeg.Error as e:
        raise RuntimeError(f"FFmpeg-Python failed: {e}")

def split_audio_segments(video_path, segment_duration=60 * 2, sample_rate=16000, force=False):
    """
    将视频中的音频拆分为多个大小相同的片段，并保存为 WAV 格式。

    Args:
        video_path (str): 视频文件路径。
        segment_duration (int): 每个音频片段的时长（秒）。
        sample_rate (int): 音频采样率（Hz）。

    Returns:
        List[str]: 生成的音频片段文件路径列表。
    """
    # 生成随机8位字符的目录名
    random_dir = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    output_dir = os.path.join(os.path.dirname(video_path), random_dir)
    
    # 创建随机目录
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 生成输出文件模板
        output_template = os.path.join(output_dir, "segment_%03d.wav")
        
        import ffmpeg
        # 使用 FFmpeg 拆分音频
        try:
            (
                ffmpeg.input(video_path)
                .output(
                    output_template,
                    f="segment",  # 使用 segment 过滤器
                    segment_time=segment_duration,  # 每个片段的时长
                    acodec="pcm_s16le",  # 使用 WAV 格式的编码器
                    ar=sample_rate,  # 设置采样率
                    ac=1,  # 单声道（可选）
                )
                .run()
            )
        except ffmpeg.Error as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"FFmpeg failed: {e.stderr}")

        # 获取生成的音频片段文件列表
        segment_files = sorted([os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.startswith("segment_")])
        
        return segment_files, output_dir
        
    finally:
        # 删除临时目录及其内容
        if force:
          shutil.rmtree(output_dir, ignore_errors=True)
        
def _extract_audio_from_video(video_path: str, output_format: str = "mp3"
) -> str:
    r"""Extract audio from the video.

    Args:
        video_path (str): The path to the video file.
        output_format (str): The format of the audio file to be saved.
            (default: :obj:`"mp3"`)

    Returns:
        str: The path to the audio file."""

    output_path = video_path.rsplit('.', 1)[0] + f".{output_format}"
    import os
    if os.path.exists(output_path):
        return output_path
    import ffmpeg
    try:
        (
            ffmpeg.input(video_path)
            .output(output_path, vn=None, acodec="libmp3lame")
            .run()
        )
        return output_path
    except ffmpeg.Error as e:
        raise RuntimeError(f"FFmpeg-Python failed: {e}")
    
def check_video_corruption(video_path: str) -> bool:
    r"""Check if a video file is corrupted.

    Args:
        video_path (str): The path to the video file.

    Returns:
        bool: True if the video is not corrupted, False otherwise.
    """
    import ffmpeg
    try:
        # 使用 FFmpeg 检查文件是否可读取
        ffmpeg.probe(video_path)
        return True
    except ffmpeg.Error as e:
        logger.info(f"Video file is corrupted or cannot be read: {video_path}")
        logger.info(f"Error: {e.stderr.decode()}")
        return False
    
def _extract_keyframes(video_path: str, num_frames: int, threshold: float = 25.0
    ) -> List[Image.Image]:
    from scenedetect import (  # type: ignore[import-untyped]
        SceneManager,
        VideoManager,
    )
    from scenedetect.detectors import (  # type: ignore[import-untyped]
        ContentDetector,
    )
    r"""Extract keyframes from a video based on scene changes
    and return them as PIL.Image.Image objects.

    Args:
        video_path (str): Path to the video file.
        num_frames (int): Number of keyframes to extract.
        threshold (float): The threshold value for scene change detection.

    Returns:
        list: A list of PIL.Image.Image objects representing
            the extracted keyframes.
    """
    from scenedetect import open_video
    video_stream = None
    keyframes: List[Image.Image] = []
    try:
        # 先检查视频文件是否存在
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        # 检查视频是否损坏
        if not check_video_corruption(video_path):
            raise RuntimeError(f"Video file is corrupted: {video_path}")
        
        # 尝试打开视频
        try:
            video_stream = open_video(video_path)
        except Exception as e:
            # 如果是webm格式，尝试转换为mp4
            if str(video_path).lower().endswith('.webm'):
                video_path = convert_webm_to_mp4(video_path)
                video_stream = open_video(video_path)
            else:
                raise
        
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=threshold))
        scene_manager.detect_scenes(video_stream)

        scenes = scene_manager.get_scene_list()

        for start_time, _ in scenes:
            if len(keyframes) >= num_frames:
                break
            try:
                frame = _capture_screenshot(video_path, start_time)
                keyframes.append(frame)
            except Exception as e:
                logger.warning(f"Failed to capture frame at {start_time}: {e}")
                continue

        logger.info(f"Extracted {len(keyframes)} keyframes from {video_path}")
    except Exception as e:
        logger.warn(f"Failed to extract keyframes from {video_path}: {e}")
        logger.warn(
            f"Failed to process video {video_path}. Possible solutions:\n"
            "1. Ensure file is a valid video format (MP4, MOV, AVI)\n"
            "2. Try converting the video to MP4 format\n"
            "3. Check file permissions and disk space\n"
            f"Original error: {e}"
        )
    finally:
        if video_stream:
            video_stream.close()
    return keyframes

def youtube_video_info(url: str, download_directory: str = None) -> Dict:
    """
    获取YouTube视频信息（不下载视频）
    
    Args:
        url: YouTube视频URL
        download_directory: 临时目录路径（可选）
    
    Returns:
        包含视频信息的字典
        
    Raises:
        RuntimeError: 当获取信息失败时抛出
    """
    fetcher = YouTubeInfoFetcher()
    try:
        return fetcher.get_video_info(url, download_directory)
    except Exception as e:
        raise RuntimeError(f"获取视频信息失败: {e}")

def get_first_subtitles(url: str, download_directory: str = None, info=None, keep_temp_files=True):
    from core.videos.youtube_subtitle_fetcher import YouTubeContentFetcher
    fetcher = YouTubeContentFetcher(keep_temp_files=keep_temp_files)
    return fetcher.get_first_subtitles(url, download_directory, info)
    
def download_video_and_subtitles(url: str, download_directory: str = None, info=None):
    """下载YouTube视频和字幕，优先获取字幕，不存在时才下载视频"""
    # 设置下载目录
    _download_directory = Path(download_directory or tempfile.mkdtemp()).resolve()
    _download_directory.mkdir(parents=True, exist_ok=True)
    
    # 简化文件名模板
    video_id = url.split('=')[-1] if '=' in url else url.split('/')[-1]
    subtitles_template = _download_directory / f"{video_id}.%(lang)s.txt"
    
    # 1. 首先检查本地是否已有字幕文件
    for lang in ["en", "zh"]:
        sub_file = subtitles_template.with_name(f"{video_id}.{lang}.txt")
        if sub_file.exists():
            return 'txt', str(sub_file), info
    
    # 2. 检查视频文件是否已存在
    video_file = _download_directory / f"{video_id}.mp4"
    if video_file.exists():
        return 'mp4', str(video_file), info
    
    if not info:
        info = youtube_video_info(url, download_directory)
    
    # 3. 获取字幕
    try:
        ext,lang, subtitles = get_first_subtitles(url, download_directory, info)
        if subtitles:
            filename = f"{video_id}.{lang}.txt"
            file_path = _download_directory / filename
            with open(file_path, 'w', encoding='utf-8') as f:
              f.write(subtitles)
            return 'txt', str(file_path), info
    except Exception as e:
        print(f'e')
        pass
    
    # 使用YouTubeDownloader下载视频
    downloader = YouTubeDownloader()
    try:
        return downloader.download_video(url, download_directory, info)
    except Exception as e:
        raise RuntimeError(f"下载视频失败: {e}")

def get_video_screenshots(video_path: str, amount: int
) -> List[Image.Image]:
    r"""Capture screenshots from the video at specified timestamps or by
    dividing the video into equal parts if an integer is provided.

    Args:
        video_url (str): The URL of the video to take screenshots.
        amount (int): the amount of evenly split screenshots to capture.

    Returns:
        List[Image.Image]: A list of screenshots as Image.Image.
    """
    import ffmpeg

    parsed_url = urlparse(video_path)
    is_url = all([parsed_url.scheme, parsed_url.netloc])
    if is_url:
        file_type, video_path = download_video_and_subtitles(video_path)
    video_file = video_path

    # Get the video length
    try:
        probe = ffmpeg.probe(video_file)
        video_length = float(probe['format']['duration'])
    except ffmpeg.Error as e:
        raise RuntimeError(f"Failed to determine video length: {e.stderr}")

    interval = video_length / (amount + 1)
    timestamps = [i * interval for i in range(1, amount + 1)]

    images = [_capture_screenshot(video_file, ts) for ts in timestamps]

    return images

def _capture_screenshot(video_file: str, timestamp: float) -> Image.Image:
    r"""Capture a screenshot from a video file at a specific timestamp.

    Args:
        video_file (str): The path to the video file.
        timestamp (float): The time in seconds from which to capture the
          screenshot.

    Returns:
        Image.Image: The captured screenshot in the form of Image.Image.
    """
    import ffmpeg

    try:
        out, _ = (
            ffmpeg.input(video_file, ss=timestamp)
            .filter('scale', 320, -1)
            .output('pipe:', vframes=1, format='image2', vcodec='png')
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        raise RuntimeError(f"Failed to capture screenshot: {e.stderr}")
    import io
    return Image.open(io.BytesIO(out))

def get_text_from_vtt(content:List[Dict[str, str]]):
    if not content:
        return None
    result = []
    for item in content:
        result.append(item['text'])
    
    return ','.join(result)

def parse_txt_file(txt_path:str) -> str:
    vtt_path = Path(txt_path)
    if not vtt_path.exists():
        raise FileNotFoundError(f"VTT file not found: {vtt_path}")

    lines = None
    with open(vtt_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    return ''.join(lines)

def parse_vtt_file(vtt_path: str) -> List[Dict[str, str]]:
    """
    Parse a VTT file into a list of subtitle segments.

    Args:
        vtt_path (str): Path to the VTT file.

    Returns:
        List[Dict[str, str]]: A list of subtitle segments, each containing
                              "start", "end", and "text" keys.
    """
    subtitles = []
    lines = parse_txt_file(vtt_path)

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("WEBVTT") or not line:
            i += 1
            continue
        if " --> " in line:
            start, end = line.split(" --> ")
            text = ""
            i += 1
            while i < len(lines) and lines[i].strip() and " --> " not in lines[i]:
                text += lines[i].strip() + " "
                i += 1
            subtitles.append({"start": start.strip(), "end": end.strip(), "text": text.strip()})
        else:
            i += 1

    return subtitles

def get_download_video_and_subtitles(video_path, download_directory, info):
    from urllib.parse import urlparse
    import time
    parsed_url = urlparse(video_path)
    is_url = all([parsed_url.scheme, parsed_url.netloc])
    if is_url:
        file_type , video_path, video_info = download_video_and_subtitles(
            url=video_path,download_directory=download_directory, info=info
        )
        return file_type , video_path, video_info
    
    from core.tools.files import get_file_content_type
    return get_file_content_type(video_path), video_path, None

def generate_video_summary(video_path, download_directory=None, info=None):
    video_type, path, info = get_download_video_and_subtitles(video_path, download_directory, info)
    if not path:
        return None
    return ask_question_about_video(video_path=path, file_type=video_type)

def ask_question_about_video(
        video_path: str,
        question: str = '总结核心内容',
        num_frames: int = 28,
        force_ai=False,
        file_type = None,
    ) -> str:
    video_frames = []
    from prompts import VIDEO_QA_PROMPT
    if file_type == 'mp4' or file_type == 'webm':
        if video_path.lower().endswith(".webm"):
            video_path = convert_webm_to_mp4(video_path=video_path)
        
        from scenedetect.video_stream import  VideoOpenFailure
        try:
            video_frames = _extract_keyframes(video_path, num_frames)
        except VideoOpenFailure as e:
            import traceback
            traceback.print_exc()
            pass
        out_dir = None
        try:
          segments, out_dir = split_audio_segments(video_path)
          audio_transcript = _transcribe_audio(segments)
          sub = ','.join(audio_transcript)
          prompt = VIDEO_QA_PROMPT.format(
              audio_transcription=sub,
              question=question,
          ) if force_ai else sub
        finally:
            if out_dir:
                # 先删除所有wav文件
                for f in Path(out_dir).glob("*.wav"):
                    try:
                        f.unlink()
                    except:
                        continue
                # 再删除目录
                # shutil.rmtree(out_dir, ignore_errors=True)
    elif file_type == 'vvt':
        list_dict = parse_vtt_file(video_path)
        sub = get_text_from_vtt(list_dict)
        prompt = VIDEO_QA_PROMPT.format(
            audio_transcription=sub,
            question=question,
        ) if force_ai else sub
    elif file_type == 'txt':
        sub = parse_txt_file(video_path)
        prompt = VIDEO_QA_PROMPT.format(
            audio_transcription=sub,
            question=question,
        ) if force_ai else sub
    else:
      raise Exception(f'file type : {file_type} not supported')
    if not force_ai:
        res = prompt
        return res
  
    from core.mcp_gateway import get_mcp_gateway
    import asyncio
    
    async def _chat_mcp():
        gateway = get_mcp_gateway()
        # Pass the extracted video details directly in text prompt because tool might not natively support Image arrays
        params = {"messages": [{"role": "user", "content": prompt}]}
        try:
            resp = await gateway.call("ai_mcp", "chat_analyze", params)
            if isinstance(resp, dict) and 'response' in resp:
                return resp['response']
            return str(resp)
        except Exception as e:
            return f"Analysis failed: {e}"
            
    return asyncio.run(_chat_mcp())

if __name__ == '__main__':
    url = 'https://www.youtube.com/watch?v=71Bcp4-Sj60'
    subtitile_dict= generate_video_summary(url=url)
    logger.info(subtitile_dict)
