import os
import datetime, time
import hashlib
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import threading
import asyncio
from pydub import AudioSegment
from pydub.playback import play
from core.tools.files import get_file_path
import logging

logger = logging.getLogger(__name__)

try:
    import pyttsx4
    engine = pyttsx4.init()
except Exception as e:
    import pyttsx3
    engine = pyttsx3.init()
    if not engine:
        raise RuntimeError("语音引擎初始化失败")

def text_to_speech_with_gtts(text, lang='en', save_path='output.mp3', play=True):
    try:
        from gtts import gTTS
        import playsound
        tts = gTTS(text=text, lang=lang)
        tts.save(save_path)
        logger.info(f"语音文件已保存到 {save_path}")
        if play:
            playsound.playsound(save_path)
    except Exception as e:
        logger.info(f"生成语音时发生错误: {e}")
        os.remove(save_path)

def text_to_speech_with_pyttsx3(text, lang='cn', rate=150, volume=1.0, save_path='output.mp3'):
    start = time.time()
    res = asyncio.run(text_to_speech_with_pyttsx3_async(text, lang=lang, rate=rate, volume=volume, save_path=save_path))
    logger.info(f'text to speech cost : {time.time() - start}')
    return res

def _run_engine(text, save_path):
    engine.save_to_file(text, save_path)
    engine.runAndWait()

def is_voice_valid(engine, voice_id, text='你好'):
    """
    检查语音 ID 是否有效
    :param engine: pyttsx3 引擎
    :param voice_id: 语音 ID
    :return: 如果语音有效，返回 True；否则返回 False
    """
    # with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
    #     temp_path = temp_file.name
    # save_path = temp_path
    try:
        engine.setProperty('voice', voice_id)
        engine.say(text)
        engine.runAndWait()
        # if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
        #     return True
        return True
    except Exception as e:
        logger.info(f"语音 ID {voice_id} 无效: {e}")
        return False

async def text_to_speech_with_pyttsx3_async(text, lang='zh_CN', rate=150, volume=1.0, save_path='output.mp3'):
    engine.setProperty('rate', rate)
    engine.setProperty('volume', volume)

    # 设置语言
    voices = engine.getProperty('voices')
    vid = voices[0].id  # 默认语音 ID
    for voice in voices:
        if lang in voice.languages:
            vid = voice.id
            logger.info(f"ID: {voice.id}, Name: {voice.name}, Languages: {voice.languages}")

    # 检查语音 ID 是否有效
    if not is_voice_valid(engine, vid):
        logger.info("使用默认语音")
        vid = voices[0].id

    engine.setProperty('voice', vid)
    try:
        thread = threading.Thread(target=_run_engine, args=(text, save_path))
        thread.start()
        thread.join()
        # _run_engine(text, save_path)
    except RuntimeError as e:
        engine.setProperty('voice', voices[0].id)
        # thread = threading.Thread(target=_run_engine, args=(text, save_path))
        # thread.start()
        # thread.join()
        _run_engine(text, save_path)
    except Exception as e:
        engine.setProperty('voice', voices[0].id)
        # thread = threading.Thread(target=_run_engine, args=(text, save_path))
        # thread.start()
        # thread.join()
        _run_engine(text, save_path)
    return save_path

# 创建线程安全的队列
task_queue = queue.Queue()

def worker():
    import pyttsx3
    engine = pyttsx3.init()
    engine.startLoop(False)  # 启动异步模式
    while True:
        text, temp_file, rate, volume, lang = task_queue.get()
        if text is None:  # 退出信号
            break
        engine.setProperty('rate', rate)
        engine.setProperty('volume', volume)
        if not set_language(engine, lang):
            logger.info(f"Unsupported language: {lang}")
        engine.save_to_file(text, temp_file)
        engine.iterate()  # 处理语音合成任务
        task_queue.task_done()

def set_language(engine, lang):
    voices = engine.getProperty('voices')
    for voice in voices:
        if lang in voice.languages:
            engine.setProperty('voice', voice.id)
            return True
    return False

def get_output_path(text, root_dir, date_format="%Y%m%d", file_extension="mp3"):
    today = datetime.datetime.now().strftime(date_format)
    file_name = f"{hashlib.md5(text.encode()).hexdigest()}.{file_extension}"
    output_dir = os.path.join(root_dir, "data", today)
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, file_name)

def synthesize_to_temp_file(text_chunk, temp_dir, rate, volume, lang):
    temp_file = tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=".wav")
    temp_file.close()
    task_queue.put((text_chunk, temp_file.name, rate, volume, lang))
    return temp_file.name

def combine_audio_files(file_list, output_file):
    from pydub import AudioSegment
    combined_audio = AudioSegment.silent(duration=0)
    for file in file_list:
        audio = AudioSegment.from_wav(file)
        combined_audio += audio
        os.remove(file)
    combined_audio.export(output_file, format="mp3")

def text_to_speech_performance(text, impl='performance', lang='zh_CN',
                   num_chunks=5, rate=150, volume=1.0, root_dir='.'):
    save_path = get_output_path(text,root_dir=root_dir)
    logger.info(f"Output will be saved to: {save_path}")

    chunk_size = len(text) // num_chunks
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Using temporary directory: {temp_dir}")
        with ThreadPoolExecutor(max_workers=num_chunks) as executor:
            futures = [executor.submit(synthesize_to_temp_file, chunk, temp_dir, rate, volume, lang) for chunk in chunks]
            temp_files = [future.result() for future in as_completed(futures)]

        combine_audio_files(temp_files, save_path)
        logger.info(f"Audio synthesis completed. Output saved to: {save_path}")

    return save_path


def text_to_speech(text, impl='pyttsx3', lang = 'zh_CN',
                   num_chunks = 5,rate=150, volume=1.0, 
                   root_dir = get_file_path('daily-summary-speech', file_type='mp3')):
    try:
        import time
        start = time.time()
        if 'pyttsx3' == impl:
            path =  text_to_speech_with_pyttsx3(text=text, lang=lang, save_path=root_dir)
        elif 'gtts' == impl:
            path =  text_to_speech_with_gtts(text=text, lang=lang)
        elif 'performance' == impl:
            import threading
            worker_thread = threading.Thread(target=worker)
            worker_thread.start()
            path = text_to_speech_performance(text, lang=lang, num_chunks=num_chunks, root_dir=root_dir)
        logger.info(f'text_to_speech impl: {impl} cost {time.time() - start}')
        return path
    except Exception as e:
        import traceback 
        traceback.logger.info_exc()

        raise e
    finally:
        pass
        # task_queue.put((None, None, None, None, None))
        # worker_thread.join()


def text_to_speech_with_spark_tts():
    from huggingface_hub import snapshot_download
    from core.tools.files import get_cache_directory
    import time
    local_dir = os.path.join(get_cache_directory(),'Spark-TTS-0.5B')
    snapshot_download("SparkAudio/Spark-TTS-0.5B", local_dir=local_dir)
    from sparktts.cli.SparkTTS import SparkTTS
    model = SparkTTS(local_dir)

    # 输入文本和提示语音路径
    prompt_text = "吃燕窝就选燕之屋，本节目由26年专注高品质燕窝的燕之屋冠名播出。豆奶牛奶换着喝，营养更均衡，本节目由豆本豆豆奶特约播出。"
    prompt_speech_path = "sparktts/src/demos/liudehua/dehua_zh.wav"

    # 生成语音
    start = time.time()
    try:
        wav = model.inference(text=prompt_text, prompt_speech_path=prompt_speech_path, prompt_text=prompt_text)
    except RuntimeError as e:
        logger.info(f"运行时错误: {e}")
        raise
    except ValueError as e:
        logger.info(f"输入数据错误: {e}")
        raise
    end = time.time()

    # 保存语音文件
    file_name = "output_chinese.wav"
    with open(file_name, "wb") as f:
        f.write(wav)

    logger.info(f"中文语音已保存为 {file_name}, cost : {end - start}")

# if __name__ == '__main__':
    # with tempfile.NamedTemporaryFile(suffix=".mp3", delete=True) as temp_file:
    #     temp_path = temp_file.name
    #     text = text_to_speech(text='你好', root_dir=temp_path)
    #     logger.info(f'text : {text}')

    # voice_id = "com.apple.speech.synthesis.voice.tingting.premium"
    # engine.setProperty('voice', voice_id)
    # engine.say('你好世界')
    # engine.runAndWait()

    
    import asyncio


from funasr import AutoModel
from tortoise.api import TextToSpeech
# from tortoise.utils.audio import load_audio, save_audio
import soundfile as sf
try:
    import torch
    import pickle
    from tortoise.utils.audio import load_audio, load_voice, load_voices
except ImportError:
    import logging
    logging.warning("torch/tortoise modules not found. Advanced TTS features will not work.")
    torch = None
# 定义保存模型的路径
# 定义保存模型的路径
model_save_path = "local_model/sensevoice_small.pkl"
tts_save_path = "local_model/tortoise_tts.pth"

# 文字转语音
# 全局变量用于存储加载的模型
funasr_model = None
tortoise_tts_model = None

def text_to_speech(text, output_path, device='cpu', voice_path=None, preset='fast'):
    global funasr_model, tortoise_tts_model

    # 如果 FunASR 模型尚未加载，则加载模型
    if funasr_model is None:
        model_dir = "iic/SenseVoiceSmall"
        funasr_model = AutoModel(
            model=model_dir,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device=device,
        )

    # 如果 Tortoise\-TTS 模型尚未加载，则加载模型
    if tortoise_tts_model is None:
        tortoise_tts_model = TextToSpeech(device=device)

    # 如果提供了自定义语音文件路径，则加载自定义语音
    if voice_path:
        custom_voice = load_voice(voice_path)
        voice_samples = [custom_voice]
    else:
        voice_samples = None

    # 使用 Tortoise\-TTS 生成语音
    gen = tortoise_tts_model.tts_with_preset(text, num_autoregressive_samples=1, voice_samples=voice_samples, verbose=False, preset=preset)
    audio_data = gen.squeeze(0).cpu()
    sample_rate = 22050  # 根据生成的音频数据设置正确的采样率
    logger.info(f'audio data : {audio_data}')
    # 保存音频文件
    sf.write(output_path, audio_data, sample_rate)

async def main():
    text = "你好，介绍文字转音频相关工作, this is a test message from FunASR and Tortoise-TTS."
    output_path = "output.wav"
    
    # 调用文字转语音函数
    voice_path='sparktts/src/demos/liudehua/dehua_zh.wav'
    text_to_speech(text, output_path)
    logger.info(f"Generated audio saved to {output_path}")

# 运行主函数
if __name__ == "__main__":
    asyncio.run(main())




# server impl

# import asyncio
# import websockets
# import json

# async def ws_serve(websocket, path):
#     async for message in websocket:
#         data = json.loads(message)
#         text = data.get("text", "")
#         output_path = "output.wav"
        
#         # 调用文字转语音函数
#         await text_to_speech(text, output_path)
        
#         # 将生成的语音文件发送回客户端
#         with open(output_path, "rb") as f:
#             audio_data = f.read()
#             await websocket.send(audio_data)

# async def main():
#     async with websockets.serve(ws_serve, "localhost", 6789):
#         logger.info("Server started on ws://localhost:6789")
#         await asyncio.Future()  # 运行直到手动停止

# if __name__ == "__main__":
#     asyncio.run(main())



# client impl

# import asyncio
# import websockets
# import json

# async def ws_client():
#     uri = "ws://localhost:6789"
#     async with websockets.connect(uri) as websocket:
#         text = "Hello, this is a test message from the client."
#         await websocket.send(json.dumps({"text": text}))
#         audio_data = await websocket.recv()
#         with open("output.wav", "wb") as f:
#             f.write(audio_data)
#         logger.info("Received audio data and saved to output.wav")

# if __name__ == "__main__":
#     asyncio.run(ws_client())
