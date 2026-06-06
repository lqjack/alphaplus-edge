# -*- encoding: utf-8 -*-
# !/usr/bin/python3
import re
import json
from urllib.request import Request
import html
import time
from urllib.request import urlopen
from ssl import _create_unverified_context
from core.settings import USER_AGENT_WECHAT
from bs4 import BeautifulSoup, NavigableString
import logging

logger = logging.getLogger(__name__) 

def parse_youtube_html(html_content):
    soup = BeautifulSoup(html_content, 'lxml')


    selector_path = "div#upload-info ytd-channel-name div#container yt-formatted-string a"
    channel_name = soup.select_one(selector_path)

    if channel_name:
        channel_name = channel_name.get_text(strip=True)
    else:
        channel_name = None

    # 使用select_one方法提取<a>标签的href属性
    a_tag = soup.select_one("yt-button-shape a[href*='/channel/'][href$='/videos']")

    # 输出结果
    if a_tag:
        channel_id = a_tag['href'].split('/channel/')[1].split('/')[0]
    else:
        channel_id = None
    return channel_id , channel_name

def get_platform_info_from_url(info_uri:str=None, cookies = None, html=None):
    html_content= None
    if html is not None:
        html_content = html
    else:
        if cookies is not None:
            request = Request(info_uri, headers={
                "User-Agent": USER_AGENT_WECHAT,
                "Cookie": cookies ,
            })
        else:
            request = Request(info_uri, headers={
                "User-Agent": USER_AGENT_WECHAT
            })
        req_resp = urlopen(request, context=_create_unverified_context())
        html_content = req_resp.read().decode()
    return parse_account_html(html_content, info_uri=info_uri)

def parse_account_html(raw, info_uri):
    html_content = html.unescape(raw)

    match = re.search(r"user_name = \"([\w-]+)\";", html_content)

    if not match:
        logger.info("No match found. Handling the absence of the pattern.")
        wx_id_unique = None  # 或者设置一个默认值

        from core.tools.article_exception import contains_keyword, get_keyword, get_reason
        if contains_keyword(html_content):
            keyword = get_keyword(html_content)
            reason = get_reason(html_content)
            return {
                "keyword" : keyword,
                "reason" : reason,
                "status": 1
            }
        raise Exception(f'parse account info missing')
    

    wx_id_unique = match.group(1)
    meta_values = re.findall(r"<span class=\"profile_meta_value\">(.*?)</span>", html_content)
    #wx_bizs = re.search(r"var biz = \"([\w=]*)\"\|\|\"([\w=]*)\";", html_content).groups()
    wx_bizs = re.search(r"var biz = \"([\w=]*)\" \|\| \"([\w=]*)\";", html_content).groups()
    account_desc = re.search(r'var profile_signature = "([^"]+)"', html_content).group(1)
    account_name = re.search(r"var nickname\s*=\s*htmlDecode\(\"([^\"]+)\"\)", html_content).group(1),
    if isinstance(account_name, tuple) and len(account_name) > 0:
        account_name = account_name[0]
    return {
        "account_name": account_name,
        # "account_name": re.search(r"nickname = \"([\w-]+)\"", html_content).group(1),
        "account_id":  meta_values[0] if meta_values and len(meta_values) > 0 and meta_values[0] else wx_id_unique,
        "account_biz": wx_bizs[0] if wx_bizs[0] else wx_bizs[1],
        "account_id_unique": wx_id_unique,
        "account_logo": re.search(r"head_?img = \"(https?:\/\/wx.qlogo.cn/mmhead/[\w\/]+)\"", html_content).group(1),
        "account_desc": meta_values[1] if meta_values and len(meta_values) > 1 and meta_values[1] else account_desc,
        "account_url": info_uri,
        "created": f"{int(time.time())}",
        "status": 0
    }

def parse_article_html(raw):
    
    if raw is None:
        return ""

    html_content = html.unescape(raw)

    if len(html_content) == 0:
        return ''
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    # 假设 doc 是 BeautifulSoup 对象
    article_title = ''
    meta_tag = soup.find('meta', attrs={'property': 'og:title'})
    if meta_tag:
        article_title = meta_tag.get('content')

    # article_author
    article_author = ''
    meta_tag = soup.find('meta', attrs={'property': 'author'})
    if meta_tag:
        article_author = meta_tag.get('content')
    desc = ''
    meta_tag = soup.find('meta', attrs={'property': 'description'})
    if meta_tag:
        desc =  meta_tag.get('content')
    # article_publish_time
    # article_publish_time = re.search(r'var createTime ="([^"]+)"', html_content).group(1)
    # article_copy_right 
    # article_digest 

    # article_cover_url 
    article_cover_url = ''
    meta_tag = soup.find('meta', attrs={'property': 'og:image'})
    if meta_tag:
        article_cover_url = meta_tag.get('content')
    # article_source_url 
    article_source_url = ''
    meta_tag = soup.find('meta', attrs={'property': 'og:url'})
    if meta_tag:
        article_source_url = meta_tag.get('content')

    return {
        "article_author": article_author,
        "article_title": article_title,
        # "description": desc,
        # "article_publish_time": article_publish_time,
        "article_cover_url": article_cover_url,
        "article_source_url": article_source_url
    }

def extract_var_name_value(html_content):
    # 定义正则表达式模式，匹配形如 var name = value; 的语句
    pattern = r"var\s+(\w{3,})\s*=\s*(\w+);"
    matches = re.findall(pattern, html_content)
    
    # 初始化一个空字典来存储变量名和值
    result = {}
    
    # 遍历匹配结果
    for name, value in matches:
        # 去掉值两边的引号（如果存在）
        var_value = value.strip().strip('"').strip("'")
        # 将变量名和值存入字典
        result[name] = var_value
    
    return result

# 提取昵称
def extract_nickname(html_content):
    match = re.search(r"var nickname\s*=\s*htmlDecode\(\"([^\"]+)\"\)", html_content)
    return match.group(1) if match else None

# 提取wx_id_unique
def extract_wx_id_unique(html_content):
    match = re.search(r"var wx_id_unique\s*=\s*\'([^\']+)\'", html_content)
    return match.group(1) if match else None

# 提取head_img
def extract_head_img(html_content):
    match = re.search(r"var\s+head_?img\s*=\s*\"(https?:\/\/wx.qlogo.cn/mmhead/[\w\/]+)\"", html_content)
    return match.group(1) if match else None

# 提取profile_signature
def extract_profile_signature(html_content):
    match = re.search(r"var profile_signature\s*=\s*\"([^\"]+)\"", html_content)
    return match.group(1) if match else None

# 提取meta_values
def extract_meta_values(html_content):
    # 假设meta_values是一个包含两个元素的列表
    meta_values = [None, None]
    nickname_match = re.search(r"var nickname\s*=\s*htmlDecode\(\"([^\"]+)\"\)", html_content)
    profile_signature_match = re.search(r"var profile_signature\s*=\s*\"([^\"]+)\"", html_content)
    if nickname_match:
        meta_values[0] = nickname_match.group(1)
    if profile_signature_match:
        meta_values[1] = profile_signature_match.group(1)
    return meta_values

def parse_cookies(cookie_header):
    cookies = {}
    for cookie in cookie_header.split("; "):
        name, value = cookie.split("=", 1)
        cookies[name] = value
    return cookies

def urldecoder(str):
    import html
    from urllib.parse import unquote

    # 原始字符串
    url_str = str
    # 替换转义的 HTML 实体
    url_str = url_str.replace("\\x26amp;", "&")

    # 提取 URL 部分
    start_tag = url_str.find('">') + 2
    end_tag = url_str.find('</url>')
    base_url = url_str[start_tag:end_tag]

    # 拼接完整的 URL
    full_url = base_url + url_str[end_tag + 6:]  # 跳过 '</url> '

    # 对 URL 进行解码
    decoded_url = unquote(full_url)
    return decoded_url

def extract_comment_id(html_content):
    match = re.search(r"comment_id = .*?\"([\d]+)\"", html_content)
    return match.group(1) if match else None

def get_content_from_html(res_html):
    from pyquery import PyQuery
    from api.rest.services.crawler import get_html_api
    content = str(PyQuery(res_html)("#js_content")).replace("\n", "").strip()

    if len(content) == 0:
        # 示例 HTML 内容
        html_content = res_html
        # 
        if 'target_url' in html_content:
            pattern = r'target_url\s*:\s*"([^"]+)"'
            match = re.search(pattern, html_content)
            if match:
                # 提取匹配的内容
                target_url = match.group(1)
                
                # 替换转义的 HTML 实体
                import html
                target_url = html.unescape(target_url)
                
                from urllib.parse import unquote
                # 解码 URL
                target_url = unquote(target_url)
                try:
                    article_html = get_html_api(target_url)

                    return article_html
                except Exception as e:
                    raise e    
            else:
                logger.info("No target_url found in the text.")
                return html_content
        else:
            from bs4 import BeautifulSoup

            # 使用 BeautifulSoup 解析 HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 查找 <meta property="og:url"> 标签
            meta_tag = soup.find('meta', property='og:url')

            # 提取 content 属性值
            if meta_tag and 'content' in meta_tag.attrs:
                content_value = meta_tag['content']
                article_html = get_html_api(content_value)
                return article_html
            else:
                logger.info("No og:url meta tag found or content attribute missing.")
                return content
    else:
        return content

if __name__ == "__main__":
    path = 'resources/article.html'

    with open(path, 'r', encoding='utf-8') as file:
        html_text =  file.read()

    article_info = parse_article_html(raw=html_text)
    import json
    logger.info(json.dumps(article_info))

def extract_text_from_html_or_plain(text: str, text_enabled=True, image_enabled=True, link_enabled=True) -> str:
    """
    判断输入文本是否是HTML格式，如果是，则根据开关参数提取文本内容、图片链接和链接，并将它们合并为一个单一的字符串；
    如果不是，则直接返回原始文本。
    
    :param text: 输入文本
    :param text_enabled: 是否提取文本内容
    :param image_enabled: 是否提取图片链接
    :param link_enabled: 是否提取链接
    :return: 提取的内容的组合字符串
    """
    if not text:
        return ""

    # 使用正则表达式检测HTML标签
    html_pattern = re.compile(r'<[^>]+>')
    if html_pattern.search(text):
        # 如果文本是HTML格式，使用BeautifulSoup解析并提取内容
        soup = BeautifulSoup(text, 'html.parser')
        
        # 提取所有文本内容
        if text_enabled:
            text_parts = []
            for element in soup.descendants:
                if isinstance(element, NavigableString):
                    # 处理特殊符号，解码HTML实体
                    decoded_text = html.unescape(element)
                    cleaned_text = re.sub(r'\s+', ' ', decoded_text).strip()
                    if cleaned_text:
                        text_parts.append(cleaned_text)
            extracted_text = ' '.join(text_parts).strip()
        else:
            extracted_text = ""

        # 提取所有图片的链接
        if image_enabled:
            images = [img.get('src') for img in soup.find_all('img') if img.get('src')]
        else:
            images = []

        # 提取所有链接（包括图片链接和其他链接）
        if link_enabled:
            links = [a.get('href') for a in soup.find_all('a') if a.get('href')]
        else:
            links = []

        # 将文本、图片链接和链接合并为一个字符串
        combined_text = ""
        if extracted_text:
            combined_text += extracted_text + "\n\n"
        if images:
            combined_text += "Images:\n" + "\n".join(images) + "\n\n"
        if links:
            combined_text += "Links:\n" + "\n".join(links)

        return combined_text.strip()
    else:
        # 如果文本不是HTML格式，直接返回原始文本
        return text.strip()

def convert_to_html(text: str) -> str:
    import markdown
    """
    将用户输入的文本转换为HTML格式。如果输入文本是Markdown格式，则转换为HTML；
    如果不是Markdown格式，则直接返回原始文本。
    
    :param text: 用户输入的文本
    :return: 转换后的HTML格式文本
    """
    if not text:
        return ""

    # 检查是否包含Markdown特有的标记
    markdown_pattern = re.compile(r'^\s*[-*#>]|[`\[\]{}!_=+~^]+', re.MULTILINE)
    if markdown_pattern.search(text):
        # 如果包含Markdown标记，则将其转换为HTML
        return markdown.markdown(text, extensions=['extra'])
    else:
        # 如果不包含Markdown标记，则直接返回原始文本
        return text

def extract_and_validate_json(text):
    """
    从文本中提取 json 部分，并验证其是否为有效的 JSON 格式。

    :param text: 包含 json 部分的文本
    :return: 如果提取的 json 部分有效，返回解析后的 JSON 数据；否则，返回错误信息
    """
    # 正则表达式匹配 ```json 和 ``` 之间的内容
    json_pattern = r"```json(.*?)```"
    matches = re.findall(json_pattern, text, re.DOTALL)

    if not matches:
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            return None

    for match in matches:
        try:
            json.loads(match.strip())
            return match.strip()
        except json.JSONDecodeError as e:
            # 如果解析失败，返回错误信息
            return None

    # 如果没有找到匹配的 json 部分
    return None

def str_to_json(json_str):
    """
    Convert a JSON-formatted string to a Python object (dict or list).
    """
    try:
        validated_str = extract_and_validate_json(json_str)
        if validated_str:
            return json.loads(validated_str)
        else:
            return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.info(f"Error parsing JSON: {e}")
        return {}

def str_to_json_list(json_str):
    try:
        data = str_to_json(json_str)
        if isinstance(data, dict):
            return [data]  # Wrap dict in a list
        elif isinstance(data, list):
            return data  # Return list directly
        else:
            logger.info("JSON data must be a dict or a list.")
            return []
    except json.JSONDecodeError as e:
        # raise ValueError(f"Error parsing JSON: {e}")
        return []

def markdown_to_str(markdown_str):
    """
    Convert a Markdown-formatted string to a plain text string.
    Specifically, it removes Markdown code block formatting.
    """
    # Remove Markdown code block formatting
    plain_text = re.sub(r'^```json\s*$', '', markdown_str, flags=re.MULTILINE)
    plain_text = re.sub(r'^```$', '', plain_text, flags=re.MULTILINE)
    return plain_text.strip()
