# -*- encoding: utf-8 -*-
# !/usr/bin/python3

import redis

r = redis.Redis(host="localhost", port=6379, db=0)

def add_proxy_to_redis(proxy: str):
    r.sadd("proxy_pool", proxy)

def get_random_proxy_from_redis():
    proxy = r.srandmember("proxy_pool")
    return proxy.decode("utf-8") if proxy else None