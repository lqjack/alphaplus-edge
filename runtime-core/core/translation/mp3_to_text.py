import os
import whisper
import logging

logger = logging.getLogger(__name__)

"""
pip install --upgrade git+https://github.com/openai/whisper.git
"""
'''
whisper 提供了不同大小的模型，您可以根据需要选择合适的模型：
tiny： 最小的模型，速度最快，但准确性较低。
base：较小的模型，速度较快，准确性适中。
small：中等大小的模型，速度适中，准确性较高。
medium：较大的模型，速度较慢，准确性更高。
large：最大的模型，速度最慢，准确性最高。
'''
def mp3_to_text(mp3_path, model_path:str= "tiny："):
    # 定义 Whisper 模型路径
    # 初始化 Whisper 模型
    model = whisper.load_model(model_path)

    # 遍历文件夹中的所有子文件夹和文件
    if mp3_path.endswith('.mp3'):
        # 构建 mp3 文件的完整路径
        # mp3_path = os.path.join(root, file)
        # 构建文本文件的完整路径
        text_path = os.path.splitext(mp3_path)[0] + '.txt'
        # 使用 Whisper 模型识别音频并生成文本
        try:
            result = model.transcribe(mp3_path)
            # 保存文本到文件
            # with open(text_path, 'w', encoding='utf-8') as f:
            #     f.write(result["text"])
            # logger.info(f'Transcription saved: {text_path}')
            return result["text"]
        except Exception as e:
            logger.info(f'Error transcribing audio from {mp3_path}: {e}')

if __name__ == "__main__":
    mp3_to_text("segment_0.mp3", model_path="medium")