# -*- encoding: utf-8 -*-
# !/usr/bin/python3

import requests
import time
from .proxy import Proxy
from .validator import ProxyValidator
import logging

logger = logging.getLogger(__name__)

from core.settings import FETCH_REMOTE_IP_PROXY_URL

validator = ProxyValidator()

class ProxyPool:
    def __init__(self):
        self.proxies = []
        self.refresh_interval = 60  # 1分钟刷新一次
        # self.init_proxy_db()
        # self.refresh_proxy_pool()

    # def init_proxy_db(self):
    #     init_proxy_db()

    def validte_proxy(self, proxy):
        return validator.test_proxy(proxy=proxy.ip + ":" + str(proxy.port))
    
    def refresh_proxy_pool(self, api_url = FETCH_REMOTE_IP_PROXY_URL, max_retries: int = 3):
        """
        刷新代理池，支持重试逻辑。
        """
        retries = 0
        while retries < max_retries:
            logger.info(f"Fetching external proxies (Attempt {retries + 1}/{max_retries})...")
            external_proxies = self.fetch_external_proxies(api_url)
            if external_proxies:
                logger.info(f"Successfully fetched {len(external_proxies)} proxies.")
                valid_proxies = validator.validate_proxies(proxy_list=[external_proxies])
                self.proxies = [Proxy(ip=proxy.split(":")[0], port=int(proxy.split(":")[1])) for proxy in valid_proxies]

                for proxy in self.proxies:
                    self.add_proxy_to_db(proxy.ip, proxy.port, proxy.delay)
                
                if len(valid_proxies) > 0:
                    break
            else:
                logger.info("Failed to fetch external proxies. Retrying...")
                retries += 1
                time.sleep(2)  # 等待2秒后重试

        if not external_proxies:
            logger.info("All retries exhausted. No proxies fetched.")
            return


    def add_proxy_to_db(self, ip: str, port: int, delay: float = 0.0):
        """
        将代理添加到数据库。
        """
        # 假设这是你的数据库添加逻辑
        logger.info(f"Adding proxy {ip}:{port} to database with delay {delay}.")
        

    def get_best_proxy(self) -> Proxy:
        if not self.proxies:
            self.refresh_proxy_pool()
        self.proxies.sort(key=lambda p: p.delay)
        if len(self.proxies) == 0:
            return None
    
        # self.update_proxy_delay(self.proxies[0], self.proxies[0].delay)
        return self.proxies[0]

    def update_proxy_delay(self, proxy: Proxy, delay: float):
        proxy.delay = delay
        proxy.last_used = time.time()
    
    from typing import List

    def fetch_external_proxies(self, api_url: str) -> List[str]:
        response = requests.get(api_url, proxies=None)
        if response.status_code == 200:
            return response.json().get("proxy")
        else:
            return None
        
    def delete_proxy(self, proxy):
        requests.get(FETCH_REMOTE_IP_PROXY_URL + "/delete/?proxy={}".format(proxy))
        ip, port = validator.parse_proxy(proxy=proxy)
        # delete_proxy_from_db(ip=ip, port=port)

# def refresh_proxies_periodically():
#     import time
#     proxy_pool = ProxyPool()
#     while True:
#         time.sleep(proxy_pool.refresh_interval)
#         proxy_pool.refresh_proxy_pool()
#         logger.info("Proxy pool refreshed.")

# # 启动定时刷新线程
# import threading
# refresh_thread = threading.Thread(target=refresh_proxies_periodically, daemon=True)
# refresh_thread.start()

