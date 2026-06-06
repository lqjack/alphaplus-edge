import ffmpeg
import random
import os
from typing import List, Dict
from core.settings import VIDEO_SETTINGS
class VideoComposer:
    def __init__(self):
        self.resolution = (1080, 1920)  # 竖屏分辨率
        
    def _select_background(self) -> str:
        """随机选择背景视频"""
        bg_dir = VIDEO_SETTINGS.assets_bg_videos
        videos = [f for f in os.listdir(bg_dir) if f.endswith('.mp4')]
        return os.path.join(bg_dir, random.choice(videos))
        
    def _select_music(self) -> str:
        """随机选择背景音乐"""
        music_dir = os.path.dirname(VIDEO_SETTINGS.assets_bg_music)
        tracks = [f for f in os.listdir(music_dir) if f.endswith('.mp3')]
        return os.path.join(music_dir, random.choice(tracks))
        
    def compose_video(
        self,
        audio_path: str,
        subtitles: List[Dict],
        output_path: str,
        duration: float
    ) -> bool:
        """合成最终视频"""
        try:
            # 1. 准备输入流
            bg_video = self._select_background()
            bg_music = self._select_music()
            
            # 2. 处理背景视频循环
            input_video = (
                ffmpeg
                .input(bg_video, stream_loop=-1)
                .filter('trim', duration=duration)
                .filter('scale', *self.resolution)
            )
            
            # 3. 添加字幕滤镜
            video_with_subtitles = input_video
            for sub in subtitles:
                video_with_subtitles = video_with_subtitles.drawtext(
                    text=sub['text'],
                    x=sub['position'][0],
                    y=sub['position'][1],
                    fontfile=VIDEO_SETTINGS.video_font,
                    fontsize=48,
                    fontcolor='white',
                    bordercolor='black',
                    borderw=2,
                    enable=f"between(t,{sub['start']},{sub['end']})"
                )
                
            # 4. 混合音频
            input_audio = ffmpeg.input(audio_path)
            bg_audio = (
                ffmpeg
                .input(bg_music)
                .filter('volume', 0.3)
                .filter('atrim', duration=duration)
            )
            
            mixed_audio = ffmpeg.filter([input_audio, bg_audio], 'amix')
            
            # 5. 输出合成视频
            (
                ffmpeg
                .output(
                    video_with_subtitles,
                    mixed_audio,
                    output_path,
                    vcodec='libx264',
                    acodec='aac',
                    shortest=None,
                    preset='fast'
                )
                .overwrite_output()
                .run()
            )
            
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"视频合成失败: {str(e)}")
            return False