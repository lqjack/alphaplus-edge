import hashlib

def generate_sha256_hash(text: str) -> str:
    """
    生成文本的 SHA-256 哈希值
    :param text: 输入文本
    :return: SHA-256 哈希值（十六进制字符串）
    """
    # 创建一个 SHA-256 哈希对象
    sha256_hash = hashlib.sha256()
    
    # 将文本编码为字节（SHA-256 需要字节输入）
    text_bytes = text.encode('utf-8')
    
    # 更新哈希对象
    sha256_hash.update(text_bytes)
    
    # 获取十六进制哈希值
    hex_digest = sha256_hash.hexdigest()
    
    return hex_digest