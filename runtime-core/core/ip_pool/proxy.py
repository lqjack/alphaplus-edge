# -*- encoding: utf-8 -*-
# !/usr/bin/python3

import time

# 代理类
class Proxy:
    def __init__(self, ip: str, port: int, delay: float = 0.0):
        self.ip = ip
        self.port = port
        self.delay = delay
        self.last_used = time.time()

    def __repr__(self):
        return f"Proxy(ip={self.ip}, port={self.port}, delay={self.delay})"