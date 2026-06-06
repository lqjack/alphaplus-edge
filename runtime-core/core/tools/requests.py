import requests
import logging

logger = logging.getLogger(__name__) 

def call_wx_add(wx_uri, html_text, server_url="http://127.0.0.1:5050/account"):
    """
    调用服务器的 /account 路由
    :param wx_uri: 微信 URI
    :param html_text: HTML 内容
    :param server_url: 服务器地址
    :return: 响应内容
    """
    # 构造请求数据
    data = {
        "wx_uri": wx_uri,
        "html_text": html_text
    }
    
    # 发送 POST 请求
    response = requests.post(server_url, data=data)
    
    # 检查响应状态
    if response.status_code == 200:
        return response.json()  # 返回 JSON 数据
    else:
        raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
    
def req(url, headers, params):
    import time
    import random
    import requests
    time.sleep(random.randint(20, 30))
    # 发送请求
    res = requests.get(url=url, headers=headers, params=params)
    # 获取json数据
    json_data = res.json()  

    if json_data['ret'] == -6:
        logger.info(json_data)
        logger.info('爬虫速度太快被封了...')
        time.sleep(20)
    elif json_data['ret'] == -3:
        logger.info(json_data)
        logger.info('会话过期了...')
    elif json_data['ret'] == 0:
        return json_data
    return json_data

def async_request(url, method, data=None, json=None, files=None, params=None, max_retries=3, timeout=60):
    retries = 0
    while retries < max_retries:
        try:
            response = requests.request(method, url, data=data, json=json, files=files, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            retries += 1
            logger.info(f"Request failed, retrying ({retries}/{max_retries}): {e}")
            if retries == max_retries:
                logger.info("Max retries reached, giving up.")
                return None
