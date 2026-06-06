# -*- encoding: utf-8 -*-
# !/usr/bin/python3


class InvalidHandleError(Exception):
    """无效的句柄异常"""

    def __init__(self, *args):
        super(InvalidHandleError, self).__init__(*args)


class HandleDoseNotExistError(Exception):
    """不存在的句柄异常"""

    def __init__(self, *args):
        super(HandleDoseNotExistError, self).__init__(*args)
