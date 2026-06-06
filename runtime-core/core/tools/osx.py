

def detect_os(user_agent):
    """从 User-Agent 中检测操作系统类型"""
    if "Windows" in user_agent:
        return "windows"
    elif "Mac OS" in user_agent or "Macintosh" in user_agent:
        return "mac"
    elif "Linux" in user_agent:
        return "linux"
    else:
        return "unknown"