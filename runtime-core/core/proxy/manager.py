import requests
import platform
import subprocess
import logging
from core.settings import PROXY_LOCAL_TARGET

logger = logging.getLogger(__name__) 

import abc
from abc import ABC, abstractmethod

class BaseProxyManager(ABC):
    @abstractmethod
    def set_proxy(self): pass
    @abstractmethod
    def unset_proxy(self): pass
    @abstractmethod
    def check_proxy(self): pass

class ProxyManager(BaseProxyManager):
    def __init__(self, target):
        self.target = target
        self.http_proxy = f"http://{target}"
        self.https_proxy = f"https://{target}"
    
    def set_proxy(self):
        """设置全局代理"""
        system = platform.system()
        if system == "Windows":
            self._set_windows_proxy(enable=True, target=self.target)
        elif system == "Darwin":
            self._set_macos_proxy(enable=True, target=self.target)
        elif system == "Linux":
            self._set_linux_proxy(enable=True, target=self.target)
        else:
            logger.warning(f"Unsupported system for proxy setting: {system}. Skipping.")

    def unset_proxy(self):
        """取消全局代理"""
        system = platform.system()
        if system == "Windows":
            self._set_windows_proxy(enable=False, target=self.target)
        elif system == "Darwin":
            self._set_macos_proxy(enable=False, target=self.target)
        elif system == "Linux":
            self._set_linux_proxy(enable=False, target=self.target)
        else:
            logger.warning(f"Unsupported system for proxy unsetting: {system}. Skipping.")

    def check_proxy(self):
        """检测代理是否设置成功"""
        system = platform.system()
        if system == "Linux":
            return self._check_linux_proxy()
        elif system == "Windows":
            return self._check_windows_proxy()
        elif system == "Darwin":
            return self._check_macos_proxy()
        else:
            logger.info(f"不支持的操作系统: {system}")
            return False

    def _check_linux_proxy(self):
        """检查 Linux 系统的代理设置"""
        try:
            mode = subprocess.run(
                ["gsettings", "get", "org.gnome.system.proxy", "mode"],
                capture_output=True, text=True
            ).stdout.strip().strip("'")
            if mode == "manual":
                http_host = subprocess.run(
                    ["gsettings", "get", "org.gnome.system.proxy.http", "host"],
                    capture_output=True, text=True
                ).stdout.strip().strip("'")
                http_port = subprocess.run(
                    ["gsettings", "get", "org.gnome.system.proxy.http", "port"],
                    capture_output=True, text=True
                ).stdout.strip()
                return http_host and http_port
            return False
        except Exception as e:
            logger.info(f"检查 Linux 代理时发生错误: {e}")
            return False

    def _check_windows_proxy(self):
        """检查 Windows 系统的代理设置"""
        try:
            import winreg
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                0, winreg.KEY_READ,
            )
            proxy_enable, _ = winreg.QueryValueEx(reg_key, "ProxyEnable")
            proxy_server, _ = winreg.QueryValueEx(reg_key, "ProxyServer")
            winreg.CloseKey(reg_key)
            return proxy_enable == 1 and proxy_server
        except Exception as e:
            logger.info(f"检查 Windows 代理时发生错误: {e}")
            return False

    def _check_macos_proxy(self):
        """检查 macOS 系统的代理设置"""
        try:
            active_services = self._get_active_network_services()
            if not active_services:
                logger.info("未找到活跃的 Wi-Fi 或 Ethernet 网络服务")
                return False

            for service in active_services:
                web_proxy_state = subprocess.run(
                    ['sudo',"networksetup", "-getwebproxy", service],
                    capture_output=True, text=True
                ).stdout.strip()
                secure_web_proxy_state = subprocess.run(
                    ['sudo',"networksetup", "-getsecurewebproxy", service],
                    capture_output=True, text=True
                ).stdout.strip()
                web_proxy_enabled = "Enabled: Yes" in web_proxy_state
                secure_web_proxy_enabled = "Enabled: Yes" in secure_web_proxy_state

                if web_proxy_enabled or secure_web_proxy_enabled:
                    return True
            return False
        except Exception as e:
            logger.info(f"检查 macOS 代理时发生错误: {e}")
            return False
        
    def _set_linux_proxy(self, enable=True, target=PROXY_LOCAL_TARGET):
        """Linux 系统设置/取消代理（GNOME 桌面环境）"""
        host, port = target.split(":")
        if enable:
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"])
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http", "host", host])
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http", "port", port])
        else:
            subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "none"])

    def _set_windows_proxy(self, enable=True, target=PROXY_LOCAL_TARGET):
        import winreg
        import ctypes
        """Windows 系统设置/取消代理"""
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0, winreg.KEY_WRITE,
        )
        winreg.SetValueEx(reg_key, "ProxyServer", 0, winreg.REG_SZ, target)
        winreg.SetValueEx(reg_key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enable else 0)
        winreg.CloseKey(reg_key)
        ctypes.windll.Wininet.InternetSetOptionW(0, 39, 0, 0)
        ctypes.windll.Wininet.InternetSetOptionW(0, 37, 0, 0)

    def _get_active_network_services(self):
        """获取所有活跃的 Wi-Fi 或 Ethernet 网络服务"""
        try:
            result = subprocess.run(
                ["networksetup", "-listallnetworkservices"],
                capture_output=True, text=True,
                timeout=10  # Add timeout to prevent hanging
            )

            if result.returncode != 0:
                logger.error(f"Failed to list network services: {result.stderr}")
                return []

            services = result.stdout.split("\n")

            active_services = []
            for service in services:
                if service and service.strip() and not service.startswith("An asterisk"):
                    service = service.strip()
                    try:
                        # 检查服务状态是否正常
                        status_result = subprocess.run(
                            ["networksetup", "-getnetworkserviceenabled", service],
                            capture_output=True, text=True,
                            timeout=5
                        )

                        if status_result.returncode == 0:
                            status = status_result.stdout.strip()
                            if "Enabled" in status and ("Wi-Fi" in service or "Ethernet" in service):
                                active_services.append(service)
                    except subprocess.TimeoutExpired:
                        logger.warning(f"Timeout checking service status for: {service}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error checking service {service}: {e}")
                        continue

            return active_services

        except subprocess.TimeoutExpired:
            logger.error("Timeout listing network services")
            return []
        except Exception as e:
            logger.error(f"Error getting active network services: {e}")
            return []

    def _set_macos_proxy(self, enable=True, target=PROXY_LOCAL_TARGET):
            """macOS 系统设置/取消代理"""
            try:
                if not target or ":" not in str(target):
                    raise ValueError("代理地址格式不正确，应为 'host:port'")
                host, port = str(target).split(":", 1)  # Split only on first colon

                active_services = self._get_active_network_services()
                if active_services is None:
                    active_services = []
                if not isinstance(active_services, list) or len(active_services) == 0:
                    raise ValueError("未找到活跃的 Wi-Fi 或 Ethernet 网络服务")

                logger.info(f"Found {len(active_services)} active network services: {active_services}")

                success_count = 0
                for service in active_services:
                    if service is None or not isinstance(service, str) or service.strip() == "":
                        logger.warning(f"Skipping invalid service: {service}")
                        continue

                    service = service.strip()
                    try:
                        if enable:
                            # Use subprocess with input=None to avoid password prompts if sudo is configured properly
                            logger.info(f"Setting web proxy for {service} to {host}:{port}")
                            subprocess.run(["sudo", "networksetup", "-setwebproxy", service, host, port], check=True, input=b'', text=False, timeout=30)
                            subprocess.run(["sudo", "networksetup", "-setsecurewebproxy", service, host, port], check=True, input=b'', text=False, timeout=30)
                            logger.info(f"{service} 代理已设置为 {host}:{port}")
                        else:
                            logger.info(f"Disabling web proxy for {service}")
                            subprocess.run(["sudo", "networksetup", "-setwebproxystate", service, "off"], check=True, input=b'', text=False, timeout=30)
                            subprocess.run(["sudo", "networksetup", "-setsecurewebproxystate", service, "off"], check=True, input=b'', text=False, timeout=30)
                            logger.info(f"{service} 代理已取消")

                        # Restart network service to apply changes
                        logger.info(f"Restarting network service {service}")
                        subprocess.run(["sudo", "networksetup", "-setnetworkserviceenabled", service, "off"], check=True, input=b'', text=False, timeout=30)
                        subprocess.run(["sudo", "networksetup", "-setnetworkserviceenabled", service, "on"], check=True, input=b'', text=False, timeout=30)

                        success_count += 1

                    except subprocess.TimeoutExpired:
                        logger.error(f"Timeout setting proxy for service {service}")
                        continue
                    except subprocess.CalledProcessError as cmd_error:
                        logger.error(f"Command failed for service {service}: {cmd_error}")
                        continue
                    except Exception as service_error:
                        logger.error(f"Error setting proxy for service {service}: {service_error}")
                        continue

                if success_count == 0:
                    raise Exception("Failed to configure proxy for any network service")

                logger.info(f"Successfully configured proxy for {success_count} out of {len(active_services)} services")

            except ValueError as e:
                # Re-raise ValueError for configuration errors
                raise e
            except subprocess.CalledProcessError as e:
                logger.error(f"代理设置命令执行失败 (exit code: {e.returncode}): {e}")
                raise Exception(f"代理设置失败，请检查sudo权限配置: {e}")
            except Exception as e:
                logger.error(f"设置代理失败: {e}")
                raise
           
# 示例用法
if __name__ == "__main__":
    proxy_manager = ProxyManager()

    # 设置代理
    proxy_manager.set_proxy()

    # 检测代理是否设置成功
    if proxy_manager.check_proxy():
        logger.info("代理已成功设置为 %s", PROXY_LOCAL_TARGET)
    else:
        logger.info("代理设置失败，请检查代理服务器是否运行。")

    # 取消代理
    proxy_manager.unset_proxy()
