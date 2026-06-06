import os
import json
import time
from datetime import datetime
import re
import base64
import hashlib
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def encode_directory_name(directory_string, method='sha256'):
    # 将目录字符串编码为 Base64
    if method == 'base64':
        encoded_bytes = base64.b64encode(directory_string.encode('utf-8'))
        encoded_string = encoded_bytes.decode('utf-8')
        return encoded_string
    elif method == 'sha256':
        hash_object = hashlib.sha256(directory_string.encode('utf-8'))
        encoded_string = hash_object.hexdigest()
        return encoded_string
    else:
        raise Exception(f'method : {method} unsupported')

def get_file_name(file_path):
    file_name_with_extension = os.path.basename(file_path)
    file_name, _ = os.path.splitext(file_name_with_extension)
    return file_name

# Common Functions
def find_audio_files(path, extension=".mp3"):
    audio_files = []
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(extension):
                audio_files.append(os.path.join(root, f))
    return audio_files

def read_file(file_path):
    with open(file_path, "r") as file:
        content = file.read()
    return content

def get_user_directory():
    """获取用户目录路径"""
    return os.path.expanduser("~")

def get_upload_folder():
    from core.settings import UPLOAD_FOLDER
    from core.tools.files import get_cache_directory
    upload_folder = os.path.join(get_cache_directory(), UPLOAD_FOLDER)
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    return upload_folder

def get_cache_directory():
    """获取缓存目录路径，如果不存在则创建"""
    cache_dir = os.path.join(get_user_directory(), ".cache", "dataproai")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_static_dir(uid='my'):
    dir = os.path.join("webapp", "static", uid)
    os.makedirs(dir, exist_ok=True)
    return dir

def get_file_path(pre='youtube-subscription', file_type='json', dir=get_cache_directory(), now=datetime.now()):
    """生成以 'youtube-subscription-年月日.json' 命名的文件路径"""
    if isinstance(now ,str):
        now = datetime.strptime(now, '%Y-%m-%d')
    file_name = now.strftime(f"{pre}-%Y%m%d.{file_type}")  # 例如：youtube-subscription-20231015.json
    return os.path.join(dir, file_name)

def is_file_recent(file_path, hours=3):
    """判断文件是否在指定小时内创建"""
    if not os.path.exists(file_path):
        return False
    file_creation_time = os.path.getctime(file_path)
    current_time = time.time()
    return (current_time - file_creation_time) <= hours * 3600

def write_to_file(file_path, data, file_type='json'):
    """将数据写入文件，支持 JSON 和纯文本格式
    
    Args:
        file_path (str): 文件路径
        data: 要写入的数据（JSON 可序列化对象或字符串）
        file_type (str): 文件类型，'json' 或 'text'
    
    Raises:
        ValueError: 文件类型不支持
        IOError: 文件写入失败
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if file_type == 'json':
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
        elif file_type == 'text':
            with open(file_path, "w", encoding="utf-8") as file:
                if not isinstance(data, str):
                    raise TypeError("Text file requires string data")
                file.write(data)
        else:
            raise ValueError(f"Unsupported file type: {file_type}. Use 'json' or 'text'.")
    except (IOError, OSError) as e:
        raise IOError(f"Failed to write to file {file_path}: {str(e)}")

def read_from_file(file_path, file_type='json'):
    """从文件中读取数据，支持 JSON 和纯文本格式
    
    Args:
        file_path (str): 文件路径
        file_type (str): 文件类型，'json' 或 'text'
    
    Returns:
        解析后的数据（JSON 返回 dict/list，text 返回 str）
    
    Raises:
        ValueError: 文件类型不支持
        IOError: 文件读取失败
        json.JSONDecodeError: JSON 解析失败
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            if file_type == 'json':
                try:
                    return json.load(file)
                except json.JSONDecodeError as e:
                    # 尝试读取文件内容用于调试
                    file.seek(0)
                    content = file.read()
                    raise json.JSONDecodeError(
                        f"Invalid JSON in {file_path}. Error at line {e.lineno}, column {e.colno} (char {e.pos}). "
                        f"Near: '{content[max(0, e.pos-20):e.pos+20]}'",
                        e.doc, e.pos
                    )
            elif file_type == 'text':
                return file.read()
            else:
                raise ValueError(f"Unsupported file type: {file_type}. Use 'json' or 'text'.")
    except UnicodeDecodeError:
        # 尝试其他编码
        with open(file_path, "r", encoding="utf-8-sig") as file:
            if file_type == 'json':
                return json.load(file)
            return file.read()
    
def path_to_valid_filename(path, max_length=255, unique=False):
    """
    将文件路径转化为有效的文件名称。

    :param path: 文件路径。
    :param max_length: 文件名最大长度，默认为 255。
    :param unique: 是否确保文件名唯一，默认为 False。
    :return: 有效的文件名称。
    """
    # 替换无效字符为下划线
    valid_name = re.sub(r'[\\/:*?"<>|]', '_', path)

    # 限制文件名长度
    if len(valid_name) > max_length:
        valid_name = valid_name[:max_length]

    # 确保文件名唯一
    if unique:
        base_name, ext = os.path.splitext(valid_name)
        counter = 1
        while os.path.exists(valid_name):
            valid_name = f"{base_name}_{counter}{ext}"
            counter += 1

    return valid_name

def get_data_with_last_hours(fetch_function=None, dir=get_cache_directory(),now=datetime.now(),
                             pre=None, hours=24, **kwargs):
    """
    获取订阅数据，如果本地文件在 3 小时内，则读取本地文件；否则调用远程函数获取数据并更新本地文件。

    :param last_n_days: 获取最近几天的数据，默认为 3 天。
    :param fetch_function: 远程获取数据的函数，必须接受 `last_n_days` 参数。
    :return: 订阅数据。
    """
    if fetch_function is None:
        raise ValueError("The 'fetch_function' parameter must be provided.")

    if not callable(fetch_function):
        raise TypeError("The 'fetch_function' parameter must be a callable function.")
    file_type = kwargs.pop('file_type', 'json')
    file_path = get_file_path(dir=dir, pre=pre, file_type=file_type, now=now)  # 获取文件路径

    if is_file_recent(file_path, hours=hours):
        logger.info(f"fun: {fetch_function.__name__} Reading from local file...")
        if 'mp3' == file_type:
            return file_path
        subscriptions = read_from_file(file_path, file_type)
    else:
        logger.info(f"fun : {fetch_function.__name__} Fetching from remote...")
        try:
            if fetch_function.__name__ == 'text_to_speech':
                kwargs['root_dir'] = file_path
            subscriptions = fetch_function(**kwargs)  # 调用远程函数获取数据
            if subscriptions:
                write_to_file(file_path, subscriptions, file_type)  # 将数据写入本地文件
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.info(f'invoke method : {str(fetch_function)} failed : {str(e)}')
            subscriptions =  None

    return subscriptions

def save_file(file):
    """
    保存上传的文件到指定目录
    :param file: 上传的文件对象
    :return: 保存后的文件路径
    """
    # 设置文件保存目录
    upload_folder = get_upload_folder()
    # 获取文件名
    filename = file.filename
    # 拼接保存路径
    file_path = os.path.join(upload_folder, filename)
    # 保存文件
    file.save(file_path)
    return file_path

def get_file_content_type(file, allowed_types=None):
    """
    根据文件扩展名获取文件的内容类型。
    :param file: 上传的文件对象（Flask 中的 FileStorage 对象）
    :return: 文件的内容类型（如 'text', 'image', 'video' 等）
    :raises ValueError: 如果文件扩展名不支持
    """
    if not file:
        return None

    file_ext = None
    from core.settings import ALLOWED_FILE_TYPES
    try:
        extension_groups = ALLOWED_FILE_TYPES if isinstance(ALLOWED_FILE_TYPES, dict) else {}
        allowed_content_types = allowed_types
        try:
            if allowed_content_types is None:
                allowed_content_types = set(extension_groups.keys())
        # 获取文件扩展名并转换为小写
            file_ext = os.path.splitext(file.filename)[1].lower()
        except Exception as e:
            file_ext = os.path.splitext(file)[1].lower()

        # if not file_ext in WHITLE_ALLOWED_FILE_TYPES:
        #     logger.info(f'{file_ext} ignore')
        #     return None
        # 根据扩展名判断内容类型
        if file_ext in extension_groups.get("video", []):
            content_type = "video"
        elif file_ext in extension_groups.get("image", []):
            content_type = "image"
        elif file_ext in extension_groups.get("text", []):
            content_type = "text"
        elif file_ext in extension_groups.get("pdf", []):
            content_type = "pdf"
        elif file_ext in extension_groups.get("word", []):
            content_type = "word"
        elif file_ext in extension_groups.get("excel", []):
            content_type = "excel"
        elif file_ext in extension_groups.get("powerpoint", []):
            content_type = "powerpoint"
        elif file_ext in extension_groups.get("archive", []):
            content_type = "archive"
        else:
            content_type = file_ext
        
        # 检查文件类型是否在白名单中
        if allowed_content_types and content_type not in allowed_content_types:
            logger.info(f'{content_type} ignore')
            return None

        return content_type
    except Exception as e:
        logger.error(f'get file content type error : {e}')
        return file_ext

def is_url(url):
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    is_url = all([parsed_url.scheme, parsed_url.netloc])
    return is_url

def get_project_root():
    from core.tools.files import find_root_directory
    from pathlib import Path
    current_script_path = Path(__file__).resolve()
    root_directory = find_root_directory(current_script_path)
    return root_directory

def find_root_directory(start_path):
    """
    从当前路径向上遍历，找到项目的根目录。
    :param start_path: 起始路径（通常是当前脚本的路径）
    :return: 根目录路径
    """
    current_path = Path(start_path).resolve()
    while current_path != current_path.parent:  # 遍历到根目录为止
        if (current_path / "requirements.txt").exists() or (current_path / ".git").exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError("Could not find project root directory.")

def get_main_root():
    """获取整个项目的顶级根目录 (alphaplus)"""
    from pathlib import Path
    current_path = Path(__file__).resolve().parent
    # 向上寻找包含 .opencode 或 scripts/deploy_all.sh 的顶级目录
    while current_path != current_path.parent:
        if (current_path / ".opencode").exists() or (current_path / "scripts" / "deploy_all.sh").exists():
            return str(current_path)
        current_path = current_path.parent
    
    # 如果找不到顶级标记，退而求其次寻找最上层的 .git
    current_path = Path(__file__).resolve().parent
    best_root = current_path
    while current_path != current_path.parent:
        if (current_path / ".git").exists():
            best_root = current_path
        current_path = current_path.parent
    return str(best_root)
