# -*- coding: utf-8 -*-
from .process import AudioProcessor
from .whisper_impl import _transcribe_audio
import os


def transcript():
    try:
        mp3_path = "/Users/liu/Desktop/立邦漆(4008851687)_20250905130729.mp3"
        # 生成同名的txt文件路径
        txt_path = os.path.splitext(mp3_path)[0] + ".txt"
        
        segments, output_dir = AudioProcessor.process_mp3(
            mp3_path,
            segment_duration=60,  # 1分钟分段
            output_format="wav",
            force_cleanup=False
        )
        print(f"{len(segments)}, dir ：{output_dir}")
        audio_transcript = _transcribe_audio(segments)
        transcript = ''.join(audio_transcript)
        print(transcript)
        
        # 将转录文本写入txt文件
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(transcript)
        print(f" save path: {txt_path}")
        
        return transcript
    except Exception as e:
        print(f"error : {str(e)}")
        raise  # 可以选择重新抛出异常或返回None