import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
from dotenv import load_dotenv
import logging

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__) 

class GoogleCredentialGetter:
    def __init__(self):
        self.driver = None
        self.credentials = {}
        
    def initialize_browser(self):
        """初始化浏览器"""
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        
        # 无头模式 (生产环境使用)
        # options.add_argument("--headless")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)
    
    def login_google(self, email, password):
        """登录Google账号"""
        logger.info("正在登录Google账号...")
        self.driver.get("https://accounts.google.com")
        
        # 输入邮箱
        email_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "identifierId"))
        )
        email_field.send_keys(email)
        email_field.send_keys(Keys.RETURN)
        
        # 输入密码
        password_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "Passwd"))
        )
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)
        
        # 等待登录完成
        time.sleep(3)
        logger.info("登录成功")
    
    def create_oauth_credentials(self, project_name, redirect_uri):
        """创建OAuth凭据"""
        logger.info("正在创建OAuth凭据...")
        
        # 导航到Google Cloud Console
        self.driver.get("https://console.cloud.google.com/apis/credentials")
        time.sleep(3)
        
        # 创建新项目
        try:
            self.driver.find_element(By.XPATH, "//button[contains(.,'创建项目')]").click()
            time.sleep(1)
            
            project_name_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@aria-label='项目名称']"))
            )
            project_name_field.send_keys(project_name)
            
            self.driver.find_element(By.XPATH, "//button[contains(.,'创建')]").click()
            WebDriverWait(self.driver, 20).until(
                EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), project_name)
            )
            logger.info(f"项目 '{project_name}' 创建成功")
        except Exception as e:
            logger.info(f"使用现有项目: {str(e)}")
        
        # 创建OAuth同意屏幕
        try:
            self.driver.get("https://console.cloud.google.com/apis/credentials/consent")
            time.sleep(2)
            
            # 选择用户类型 (外部)
            self.driver.find_element(By.XPATH, "//div[contains(text(),'外部')]").click()
            self.driver.find_element(By.XPATH, "//button[contains(.,'创建')]").click()
            time.sleep(1)
            
            # 填写应用信息
            app_name_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@aria-label='应用名称']"))
            )
            app_name_field.send_keys(f"{project_name} App")
            
            user_support_email = os.getenv("GOOGLE_ACCOUNT_EMAIL")
            self.driver.find_element(By.XPATH, "//input[@aria-label='用户支持电子邮件']").send_keys(user_support_email)
            
            developer_contact_email = os.getenv("GOOGLE_ACCOUNT_EMAIL")
            self.driver.find_element(By.XPATH, "//input[@aria-label='开发者联系电子邮件']").send_keys(developer_contact_email)
            
            # 保存并继续
            self.driver.find_element(By.XPATH, "//button[contains(.,'保存并继续')]").click()
            time.sleep(1)
            
            # 跳过范围页面
            self.driver.find_element(By.XPATH, "//button[contains(.,'保存并继续')]").click()
            time.sleep(1)
            
            # 跳过测试用户
            self.driver.find_element(By.XPATH, "//button[contains(.,'保存并继续')]").click()
            time.sleep(1)
            
            # 返回仪表板
            self.driver.find_element(By.XPATH, "//button[contains(.,'返回到仪表板')]").click()
            time.sleep(2)
            logger.info("OAuth同意屏幕配置完成")
        except Exception as e:
            logger.info(f"配置OAuth同意屏幕时出错: {str(e)}")
        
        # 创建OAuth客户端ID
        self.driver.get("https://console.cloud.google.com/apis/credentials")
        time.sleep(2)
        
        self.driver.find_element(By.XPATH, "//button[contains(.,'创建凭据')]").click()
        self.driver.find_element(By.XPATH, "//div[contains(text(),'OAuth 客户端 ID')]").click()
        time.sleep(1)
        
        # 填写应用类型和名称
        self.driver.find_element(By.XPATH, "//div[contains(text(),'Web 应用')]").click()
        
        name_field = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@aria-label='名称']"))
        )
        name_field.send_keys(f"{project_name} Web Client")
        
        # 添加授权重定向URI
        redirect_uris_field = self.driver.find_element(By.XPATH, "//input[@aria-label='已获授权的重定向 URI']")
        redirect_uris_field.send_keys(redirect_uri)
        self.driver.find_element(By.XPATH, "//button[contains(.,'添加 URI')]").click()
        time.sleep(1)
        
        # 创建客户端ID
        self.driver.find_element(By.XPATH, "//button[contains(.,'创建')]").click()
        time.sleep(2)
        
        # 获取客户端ID和密钥
        client_id = self.driver.find_element(By.XPATH, "//input[@aria-label='客户端 ID']").get_attribute("value")
        client_secret = self.driver.find_element(By.XPATH, "//input[@aria-label='客户端密钥']").get_attribute("value")
        
        logger.info(f"客户端ID: {client_id}")
        logger.info(f"客户端密钥: {client_secret}")
        
        self.credentials = {
            "GOOGLE_CLIENT_ID": client_id,
            "GOOGLE_CLIENT_SECRET": client_secret
        }
        
        # 下载JSON凭据
        self.driver.find_element(By.XPATH, "//button[contains(.,'下载 JSON')]").click()
        time.sleep(2)
        
        return self.credentials
    
    def save_to_env(self, env_file=".env"):
        """保存凭据到.env文件"""
        if not self.credentials:
            logger.info("没有可保存的凭据")
            return
        
        # 读取现有.env文件
        env_vars = {}
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        env_vars[key] = value
        
        # 更新凭据
        env_vars.update(self.credentials)
        
        # 写回文件
        with open(env_file, "w") as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        
        logger.info(f"凭据已保存到 {env_file}")
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")

if __name__ == "__main__":
    # 配置参数
    PROJECT_NAME = "YouTubeQRCodeAuth"  # 修改为您喜欢的项目名称
    REDIRECT_URI = "http://localhost:5050/api/youtube/auth/callback"  # 修改为您的重定向URI
    
    # 从环境变量获取Google账号凭据
    GOOGLE_EMAIL = os.getenv("GOOGLE_ACCOUNT_EMAIL") or 'lqjacklee@gmail.com'
    GOOGLE_PASSWORD = os.getenv("GOOGLE_ACCOUNT_PASSWORD") or 'lqjacklee1!Ab,./'
    
    if not GOOGLE_EMAIL or not GOOGLE_PASSWORD:
        logger.info("请在.env文件中设置GOOGLE_ACCOUNT_EMAIL和GOOGLE_ACCOUNT_PASSWORD")
        exit(1)
    
    # 执行自动化流程
    getter = GoogleCredentialGetter()
    try:
        getter.initialize_browser()
        getter.login_google(GOOGLE_EMAIL, GOOGLE_PASSWORD)
        credentials = getter.create_oauth_credentials(PROJECT_NAME, REDIRECT_URI)
        getter.save_to_env()
    except Exception as e:
        logger.info(f"自动化流程出错: {str(e)}")
    finally:
        getter.close()