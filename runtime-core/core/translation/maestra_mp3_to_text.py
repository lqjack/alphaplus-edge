import requests
import json
import logging
logger = logging.getLogger(__name__)
def mp3_to_text_maestra(mp3_path, api_key):
    # Maestra AI API 的 URL
    url = "https://api.maestra.ai/v1/audio/transcribe"
    
    # 读取 MP3 文件
    with open(mp3_path, 'rb') as audio_file:
        audio_data = audio_file.read()
    
    # 设置请求头
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 设置请求数据
    data = {
        "audio": audio_data,
        "language": "zh-CN",  # 指定语言为中文
        "model": "base"  # 选择模型
    }
    
    # 发送 POST 请求
    response = requests.post(url, headers=headers, data=json.dumps(data))
    
    # 处理响应
    if response.status_code == 200:
        result = response.json()
        text = result.get("text", "")
        return text
    else:
        return f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}"

# 示例
# mp3_path = "/Users/liu/codes/python/YoutubeGPTClaude/outputs/《重返三星堆》04 神启：三星堆青铜顶尊跪坐人像的神秘缺口 竟然意外重逢！【CCTV纪录】/chunks/segment_0.mp3"
# api_key = "YOUR_API_KEY"
# text = mp3_to_text_maestra(mp3_path, api_key)
# logger.info(text)