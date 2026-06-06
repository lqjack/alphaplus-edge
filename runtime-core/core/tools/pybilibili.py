import requests
import json
import time
import hashlib

class Bilibili:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.qrcode_key = None
        self.cookies = None
    
    def get_qrcode_url(self):
        """获取登录二维码"""
        url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
        response = self.session.get(url)
        data = response.json()
        if data['code'] == 0:
            self.qrcode_key = data['data']['qrcode_key']
            return data['data']['url']
        raise Exception("Failed to get QR code")
    
    def check_qrcode(self):
        """检查二维码状态"""
        if not self.qrcode_key:
            raise Exception("QR code not generated")
        
        url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={self.qrcode_key}"
        response = self.session.get(url)
        data = response.json()
        
        if data['code'] == 0:
            if data['data']['code'] == 0:  # 登录成功
                self.cookies = response.cookies.get_dict()
                return 'success'
            elif data['data']['code'] == 86038:  # 二维码过期
                return 'expired'
            else:  # 等待扫码
                return 'waiting'
        raise Exception("Failed to check QR code status")
    
    def get_user_info(self):
        """获取用户信息"""
        if not self.cookies:
            raise Exception("Not logged in")
        
        url = "https://api.bilibili.com/x/web-interface/nav"
        response = self.session.get(url, cookies=self.cookies)
        data = response.json()
        if data['code'] == 0:
            return data['data']
        raise Exception("Failed to get user info")
    
    def get_subscriptions(self, page=1, page_size=50):
        """获取用户订阅列表"""
        if not self.cookies:
            raise Exception("Not logged in")
        
        url = "https://api.bilibili.com/x/relation/followings"
        params = {
            'vmid': self.get_user_info()['mid'],
            'pn': page,
            'ps': page_size
        }
        response = self.session.get(url, params=params, cookies=self.cookies)
        data = response.json()
        if data['code'] == 0:
            return data['data']['list']
        raise Exception("Failed to get subscriptions")
    
    def get_latest_videos(self, mid, page=1, page_size=10):
        """获取UP主最新视频"""
        url = "https://api.bilibili.com/x/space/arc/search"
        params = {
            'mid': mid,
            'pn': page,
            'ps': page_size,
            'order': 'pubdate'
        }
        response = self.session.get(url, params=params)
        data = response.json()
        if data['code'] == 0:
            return data['data']['list']['vlist']
        raise Exception("Failed to get latest videos")