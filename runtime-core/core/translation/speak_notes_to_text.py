'''
pip install pydub SpeechRecognition
'''
import logging
from pydub import AudioSegment
import speech_recognition as sr

logger = logging.getLogger(__name__)

def convert_mp3_to_wav(mp3_file, wav_file):
    audio = AudioSegment.from_file(mp3_file, format='mp3')
    audio.export(wav_file, format='wav')

def recog_mp3(mp3_audio_file):
    wav_audio_file = mp3_audio_file.replace(".mp3", ".wav")
    txt_audio_file = mp3_audio_file.replace(".mp3", ".txt")
    convert_mp3_to_wav(mp3_audio_file, wav_audio_file)
    
    r = sr.Recognizer()
    with sr.AudioFile(wav_audio_file) as source:
        audio = r.record(source)
    
    logger.info('识别内容：\n')
    try:
        audio_text = r.recognize_google(audio, language='zh-CN')
        audio_text = audio_text.replace(" ", "")
        with open(txt_audio_file, 'w') as file:
            file.write(audio_text)
        return audio_text
    except sr.UnknownValueError:
        return "未能理解音频内容"
    except sr.RequestError as e:
        return f"无法连接至识别服务; {e}"

# 示例
mp3_path = "/Users/liu/codes/python/YoutubeGPTClaude/outputs/《重返三星堆》04 神启：三星堆青铜顶尊跪坐人像的神秘缺口 竟然意外重逢！【CCTV纪录】/chunks/segment_0.mp3"
text = recog_mp3(mp3_path)
logger.info(text)