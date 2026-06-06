
# -*- encoding: utf-8 -*-
# !/usr/bin/python3

from requests import head
import requests
import time
from urllib.request import Request, urlopen
from ssl import create_default_context, Purpose
from .proxy import Proxy
import logging
from typing import Tuple, List, Union

logger = logging.getLogger(__name__)

PROXY_HEALTH_CHECK_TARGET_URL = "http://www.baidu.com"
USER_AGENT_WECHAT = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.116 Safari/537.36 QBCore/3.53.1159.400 QQBrowser/9.0.2524.400 Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 MicroMessenger/6.5.2.501 NetType/WIFI WindowsWechat"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36"
VERIFY_TIMEOUT = 10

CHECK_HEADER ={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
          'Accept': '*/*',
          'Connection': 'keep-alive',
          'Accept-Language': 'zh-CN,zh;q=0.8'}

class ProxyValidator:
    def parse_proxy(self, proxy: str) -> Tuple[str, int]:
        """
        将代理字符串解析为 IP 和端口。
        :param proxy: 代理字符串，格式为 "ip:port"
        :return: 返回一个元组 (ip, port)
        """
        try:
            ip, port = proxy.split(":")
            port = int(port)  # 将端口转换为整数
            return ip, port
        except ValueError:
            raise ValueError(f"Invalid proxy format: {proxy}. Expected 'ip:port'.")

    def test_proxy(self, proxy: str) -> bool:
        # 格式化代理地址
        proxies = {
            "http": f"http://{proxy}",
            "https": f"https://{proxy}"
        }

        try:
            # 发起 HEAD 请求
            response = requests.head(PROXY_HEALTH_CHECK_TARGET_URL, 
                                    headers=CHECK_HEADER, 
                                    proxies=proxies, 
                                    verify=False,
                                    timeout=VERIFY_TIMEOUT)
            # 检查状态码
            return response.status_code == 200
        except requests.RequestException as e:
            # 捕获请求相关的异常
            logger.error(f"Request failed: {e}")
            return False
        except Exception as e:
            # 捕获其他未预期的异常
            logger.error(f"An unexpected error occurred: {e}")
            return False    
        
    def validate_proxies(self, proxy_list) -> List[str]:
        valid_proxies = []
        for _proxy in proxy_list:
            checked = self.test_proxy(proxy=_proxy)
            if checked:
                valid_proxies.append(_proxy)

        return valid_proxies


    # 检测代理网络可用性
    def check_proxy_availability(proxy: Proxy) -> bool:
        try:
            request = Request(PROXY_HEALTH_CHECK_TARGET_URL, headers={"User-Agent": USER_AGENT_WECHAT})
            start_time = time.time()
            urlopen(request, context=_create_unverified_context(), timeout=5)
            end_time = time.time()
            proxy.delay = end_time - start_time
            return True
        except Exception as e:
            logger.error(f"Proxy {proxy} failed: {e}")
            return False


# 假设 _create_unverified_context 是一个全局函数
def _create_unverified_context():
    return create_default_context(Purpose.CLIENT_AUTH)