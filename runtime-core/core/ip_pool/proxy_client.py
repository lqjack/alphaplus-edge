# -*- encoding: utf-8 -*-
# !/usr/bin/python3
from .pool import ProxyPool
import logging
logger = logging.getLogger(__name__)
proxy_pool = ProxyPool()
from requests.exceptions import SSLError
def do_req(url, timeout=10, method="get",headers=None, data=None, json=None):
    # proxy = get_proxy()
    proxy = None
    if proxy is None:
        # logger.info("get proxy failed, fallback to no proxy")
        proxies = None
    else:
        proxies = {
            "http": f"{proxy.ip}:{proxy.port}",
            "https": f"{proxy.ip}:{proxy.port}"
        }

    # 定义一个包装函数，用于执行 requests.get
    def request_fun(url, proxies=None, timeout=10, json=None,
                    max_retries=3, method='get',headers=None, data=None):
        import requests

        retry_count = 0
        response = None
        while retry_count < max_retries:
            try:
                if proxies is not None:
                    response = requests.request(method=method, url=url, json=json,verify=True,
                                                proxies=proxies, timeout=timeout, headers=headers, data=data)
                else:
                    response = requests.request(method=method, url=url, json=json,verify=True,
                                                headers=headers, data=data)

                if response.status_code == 404:
                    logger.info(f"Request failed with status code 404. Retrying... ({retry_count + 1}/{max_retries})")
                    retry_count += 1
                else:
                    return response  # 如果状态码不是404，直接返回响应
            except SSLError as e:
                logger.error(f"SSL 错误详情: {e}")
                proxy_pool.proxies.remove(proxy)
            except Exception as e:
                if proxies is not None:
                    logger.error(f"Request failed with proxy {proxies}: {e}")
                    # 这里可以添加逻辑，例如从代理池中移除无效代理
                    # proxy_pool.proxies.remove(proxies)
                    proxy_pool.proxies.remove(proxy)
                retry_count += 1
                logger.error(f"Request failed with exception: {e}. Retrying... ({retry_count}/{max_retries})")

        # 如果重试次数用完，仍然失败，抛出异常或返回None
        logger.info(f"Request url : {url} failed after {max_retries} retries.")
        return response
    if proxies is not None:
        return request_fun(url=url, proxies= proxies, timeout=10, max_retries=3, method=method, headers=headers, data=data, json=json)
    else:
        return request_fun(url=url,timeout=timeout, max_retries=3, method=method, headers=headers, data=data, json=json)

def get_proxy():
    # 最大重试次数
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        proxy = proxy_pool.get_best_proxy()
        if proxy is not None:
            logger.info(f"Successfully obtained proxy: {proxy}")
            return proxy
        else:
            retry_count += 1
            logger.info(f"Current proxy is unavailable. Retrying... ({retry_count}/{max_retries})")
            # 如果需要，可以在这里删除无效的代理
            # proxy_pool.delete_proxy(proxy)

    # 如果重试次数用完，仍然没有获取到代理，抛出异常或返回 None
    logger.info("Failed to obtain a valid proxy after maximum retries.")
    return None

if __name__ == "__main__":
    proxy = get_proxy()
    logger.info(proxy)