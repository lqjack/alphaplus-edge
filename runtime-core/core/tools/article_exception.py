# -*- encoding: utf-8 -*-
# !/usr/bin/python3
import logging
logger = logging.getLogger(__name__)
# 关键字与原因的关联关系
KEYWORD_MAP = {
    "该内容已被发布者删除": "该文章链接已被删除",
    "此内容因违规无法查看": "该文章链接因违规无法查看",
    "此内容被投诉且经审核涉嫌侵权": "此内容被投诉且经审核涉嫌侵权，无法查看。",
    "访问过于频繁，请用微信扫描二维码进行访问": "当前ip已无法访问",
    "此内容因涉嫌违反相关法律法规": "此内容因涉嫌违反相关法律法规，无法查看。",
    "相关的内容无法进行查看": "此内容被多人投诉，相关的内容无法进行查看。",
    "你暂无权限查看此页面内容": "你暂无权限查看此页面内容"
}

# ID 与关键字的映射关系
ID_KEYWORD_MAP = {
    1: "该内容已被发布者删除",
    2: "此内容因违规无法查看",
    3: "此内容被投诉且经审核涉嫌侵权",
    4: "访问过于频繁，请用微信扫描二维码进行访问",
    5: "此内容因涉嫌违反相关法律法规",
    6: "相关的内容无法进行查看",
    7: "你暂无权限查看此页面内容"
}

def contains_keyword(content):
    """
    检测传入的内容是否包含关键字之一。
    如果存在，返回 True；否则返回 False。
    """
    for keyword in KEYWORD_MAP.keys():
        if keyword in content:
            return True
    return False

def get_keyword(content):
    for keyword in KEYWORD_MAP.keys():
        if keyword in content:
            return keyword
    return None

def get_reason(content):
    """
    检测传入的内容是否包含关键字之一，并返回对应的原因。
    如果存在，返回对应的原因；否则返回 None。
    """
    for keyword, reason in KEYWORD_MAP.items():
        if keyword in content:
            return reason
    return None

def get_keyword_by_id(keyword_id):
    """
    根据 ID 查找对应的关键字。
    如果找到，返回关键字；否则返回 None。
    """
    return ID_KEYWORD_MAP.get(keyword_id, None)

def get_reason_by_id(keyword_id):
    """
    根据 ID 查找对应的关键字，并返回对应的原因。
    如果找到，返回原因；否则返回 None。
    """
    keyword = get_keyword_by_id(keyword_id)
    if keyword:
        return KEYWORD_MAP.get(keyword, None)
    return None

def get_ids():
    return ID_KEYWORD_MAP.keys()

# 测试代码
if __name__ == "__main__":
    # 测试内容
    test_contents = [
        "该内容已被发布者删除",
        "此内容因违规无法查看",
        "此内容被投诉且经审核涉嫌侵权",
        "访问过于频繁，请用微信扫描二维码进行访问",
        "此内容因涉嫌违反相关法律法规",
        "相关的内容无法进行查看",
        "这是一个普通的内容，没有关键字",
    ]

    # 测试 ID
    test_ids = [1, 2, 3, 4, 5, 6, 7]

    # 测试内容检测
    for content in test_contents:
        logger.info(f"内容: {content}")
        logger.info(f"是否包含关键字: {contains_keyword(content)}")
        reason = get_reason(content)
        if reason:
            logger.info(f"对应原因: {reason}")
        else:
            logger.info("未找到对应原因")
        logger.info("-" * 40)

    # 测试 ID 查找
    for keyword_id in test_ids:
        logger.info(f"ID: {keyword_id}")
        keyword = get_keyword_by_id(keyword_id)
        if keyword:
            logger.info(f"找到关键字: {keyword}")
            reason = get_reason_by_id(keyword_id)
            if reason:
                logger.info(f"对应原因: {reason}")
            else:
                logger.info("未找到对应原因")
        else:
            logger.info("未找到关键字")
        logger.info("-" * 40)