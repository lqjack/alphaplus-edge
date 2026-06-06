import os
import wave
import json
from vosk import Model, KaldiRecognizer
import logging

logger = logging.getLogger(__name__)

def transcribe_audio_vosk(audio_path):
    # 加载 Vosk 模型
    model = Model("model")  # 下载并解压 Vosk 模型到当前目录
    wf = wave.open(audio_path, "rb")
    
    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() not in [8000, 16000]:
        raise ValueError("Audio file must be WAV format mono PCM.")
    
    rec = KaldiRecognizer(model, wf.getframerate())
    
    text = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text += result.get("text", "") + " "
    
    result = json.loads(rec.FinalResult())
    text += result.get("text", "")
    
    return text.strip()

# 使用示例
audio_path = "your_audio_file.wav"
transcription = transcribe_audio_vosk(audio_path)
logger.info(transcription)