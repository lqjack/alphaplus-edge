import ffmpeg
import os
import random

class VideoEditor:
    def __init__(self, config):
        self.resolution = config['video']['resolution']
        self.bg_videos_path = config['assets']['bg_videos']

    def get_random_bg_video(self):
        """随机选择背景视频片段"""
        videos = os.listdir(self.bg_videos_path)
        return os.path.join(self.bg_videos_path, random.choice(videos))

    def compose_video(self, audio_file, subtitles, output_file):
        """合成最终视频"""
        bg_video = self.get_random_bg_video()
        
        # 步骤1：加载背景视频和音频
        input_video = ffmpeg.input(bg_video)
        input_audio = ffmpeg.input(audio_file)
        
        # 步骤2：添加字幕滤镜
        video_with_subtitles = input_video
        for sub in subtitles:
            video_with_subtitles = video_with_subtitles.drawtext(
                text=sub['text'],
                x='(w-tw)/2',  # 水平居中
                y='h-th-50',   # 底部上方
                fontfile='config/fonts/STHeiti.ttf',
                fontsize=48,
                fontcolor='white',
                shadowcolor='black',
                shadowx=2,
                shadowy=2,
                enable=f"between(t,{sub['start']},{sub['end']})"
            )
        
        # 步骤3：合并音频视频
        output = ffmpeg.output(
            video_with_subtitles,
            input_audio,
            output_file,
            vcodec='libx264',
            acodec='aac',
            shortest=None,
            format='mp4'
        )
        output.run(overwrite_output=True)