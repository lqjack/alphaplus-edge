# import certifi
# import requests

from html_parser import parse_article_html, parse_account_html
import os
import logging

logger = logging.getLogger(__name__)

def load_html_file(file_path):
    """
    从指定路径加载HTML文件内容。

    :param file_path: HTML文件的路径
    :return: 文件内容
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        logger.info(f"文件 {file_path} 未找到。")
        return None
    except Exception as e:
        logger.info(f"读取文件时发生错误：{e}")
        return None

def process_html(path):
    # 加载HTML文件内容
    html_text = load_html_file(path)
    
    # 如果HTML文件内容加载成功，则调用函数获取平台信息
    import json
    if html_text:
        platform_info = parse_account_html(raw=html_text, info_uri="http://baidu.com")
        logger.info(json.dumps(platform_info))

def main():
    directory_path = "resources"
    # 遍历路径下的所有文件
    # for filename in os.listdir(directory_path):
        # process_html(filename)
    filename = 'resources/dabao_article.html'
    html = load_html_file(filename)
 
    article = parse_article_html(html)
    logger.info(article)


if __name__ == "__main__":
    main()
    pass
