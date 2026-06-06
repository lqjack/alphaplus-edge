# -*- encoding: utf-8 -*-
import logging

logger = logging.getLogger(__name__)

def merge_dicts_with_non_empty_values(dict1, dict2):
    result = dict1.copy()  # 创建 dict1 的副本
    for key, value in dict2.items():
        if value:  # 只有非空值才更新
            result[key] = value
    return result

def unify_request_data():
    from flask import request
    from werkzeug.datastructures import FileStorage
    """
    将Flask request中的json、param、values、files统一到一个字典中。
    :return: dict
    """
    unified_data = {}

    try:
        # 获取JSON数据
        if request.is_json:
            json_data = request.get_json(silent=True) or {}
            if json_data:
                unified_data.update(json_data)

        # 获取查询参数和表单数据
        # request.args 是查询参数，request.form 是表单数据
        # request.values 是两者的组合
        for key, value in request.values.items():
            unified_data[key] = value

        # 获取文件数据
        if request.files:
            for key, file in request.files.items():
                if isinstance(file, FileStorage):
                    unified_data[key] = file
                else:
                    unified_data[key] = file.read()

    except Exception as e:
        # 异常处理
        logger.error(f"Error occurred while processing request data: {e}")
        return None

    return unified_data