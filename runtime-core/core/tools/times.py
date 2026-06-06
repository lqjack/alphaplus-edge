
from datetime import datetime,timezone
import re

def format_datetime(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc).isoformat()  # 明确标记为UTC时间

def is_valid_timestamp(timestamp_str):
    # 先检查是否为纯数字
    if not isinstance(timestamp_str, (int, float)) and not timestamp_str.isdigit():
        return False
    try:
        timestamp = float(timestamp_str)
        min_timestamp = 0  # 1970-01-01 00:00:00 UTC
        max_timestamp = 4102444800000  # 2100-01-01 00:00:00 UTC，毫秒级
        return min_timestamp <= timestamp <= max_timestamp
    except (ValueError, TypeError):
        return False

def timestamp_to_time(input_value, format="%H:%M"):
    """
    将 Unix 时间戳或日期字符串转换为 "小时:分钟" 格式的时间。
    如果输入不是合法的时间戳或日期字符串，则不进行处理。

    :param input_value: Unix 时间戳（整数）或日期字符串（如 '20250225'）
    :return: 时间字符串，例如 "14:30" 或错误提示
    """
    try:
        # 尝试将输入值转换为整数（假设是 Unix 时间戳）
        timestamp = int(input_value)
        # 将时间戳转换为 datetime 对象
        dt = datetime.fromtimestamp(timestamp)
    except (ValueError, TypeError):
        # 如果转换失败，尝试将输入值解析为日期字符串
        try:
            # 假设输入的日期字符串格式为 'YYYYMMDD'
            dt = datetime.strptime(input_value, "%Y%m%d")
        except (ValueError, TypeError):
            # 如果无法解析为日期字符串，返回原始输入
            return input_value
    
    # 格式化为 "小时:分钟" 格式
    return dt.strftime(format)
 

def time_to_timestamp(input_str):
    """
    将 "小时:分钟" 格式的时间转换为时间戳。

    :param input_str: 时间字符串，例如 "14:30"。
    :return: Unix 时间戳。
    """
    time_pattern = r"^\d{1,2}:\d{2}$"  # 匹配格式如 "14:30"
    
    if re.match(time_pattern, input_str):
        # 如果匹配到时间格式
        today = datetime.now().date()
        # 将时间字符串与当前日期结合
        full_time = datetime.strptime(f"{today} {input_str}", "%Y-%m-%d %H:%M")
        # 转换为时间戳
        return int(full_time.timestamp())
    else:
        try:
            # 尝试将输入字符串作为日期格式解析
            try:
                date_obj = datetime.strptime(input_str, '%Y%m%d')  # 先尝试YYYYMMDD格式
            except ValueError:
                try:
                  date_obj = datetime.strptime(input_str, '%Y-%m-%d')  # 再尝试YYYY-MM-DD格式
                except:
                    if is_valid_timestamp(timestamp_str=input_str):
                      return int(input_str)
            # 将 datetime 对象转换为时间戳（timestamp），并转换为整数
            return int(date_obj.timestamp())
        except ValueError:
            # 如果输入格式不符合日期或时间格式，抛出错误
            raise ValueError("输入的字符串格式不正确，应为时间（如'14:30'）或日期（如'YYYYMMDD'或'YYYY-MM-DD'）")
        
def time_to_cron(notification_time):
    """
    将小时和分钟的时间字符串转换为 cron 表达式。
    
    参数:
        notification_time (str): 格式为 "hour:minute" 的时间字符串，例如 "14:30"
    
    返回:
        str: 对应的 cron 表达式
    """
    try:
        hour, minute = notification_time.split(':')
        # 验证小时和分钟是否有效
        if not (0 <= int(hour) <= 23) or not (0 <= int(minute) <= 59):
            raise ValueError("小时必须在 0-23 之间，分钟必须在 0-59 之间")
        # 构造 cron 表达式
        cron_expression = f"{minute} {hour} * * *"
        return cron_expression
    except ValueError as e:
        return f"输入格式错误：{e}"

