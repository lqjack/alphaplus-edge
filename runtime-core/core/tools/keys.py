# -*- coding: utf-8 -*-
# @File    : keys.py
import hashlib
import json

from core.exceptions import NoneKeyUinError
from api.rest.views import get_key, delete_key

def delete_key_uin(account_biz):
    # redis_server = redis.StrictRedis(connection_pool=redis.ConnectionPool(**WX_REDIS_CONFIG))
    hash_key = hashlib.md5(account_biz.encode("utf-8")).hexdigest()
    # redis_server.delete(hash_key)
    delete_key(hash_key)

def _get_key_uin(account_biz):
    # redis_server = redis.StrictRedis(connection_pool=redis.ConnectionPool(**WX_REDIS_CONFIG))
    hash_key = hashlib.md5(account_biz.encode("utf-8")).hexdigest()
    # return redis_server.get(hash_key)
    return get_key(hash_key)

def get_key_uin(account_biz):
    key_uin = _get_key_uin(account_biz)
    if not key_uin:
        raise NoneKeyUinError("NoneKeyUinError")
    return json.loads(key_uin, encoding="utf-8")

def get_pass_key_and_uin(article_url: str, account_biz: str):
    key_uin = _get_key_uin(account_biz)
    return json.loads(key_uin, encoding="utf-8")
