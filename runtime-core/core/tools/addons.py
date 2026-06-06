# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import re
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from mitmproxy import ctx, http

from api.rest.mongodb_adapter import key_value_adapter
from core.tools.article_content_check import run_with_app

logger = logging.getLogger(__name__)


class WeiXinProxy():  # 继承自 mitmproxy.addons.Addon

    # redis_server = redis.StrictRedis(connection_pool=redis.ConnectionPool(**WX_REDIS_CONFIG))

    def __init__(self):
        pass

    def uin_md5(self, uin):
        value = str(uin or "")
        saw_percent = "%" in value
        # WeChat click URLs occasionally carry partially decoded tails like
        # `%253D%25`; keep decoding only while the value is actually changing.
        for _ in range(8):
            if "%" not in value:
                break
            decoded = unquote(value)
            if decoded == value:
                break
            value = decoded
        if saw_percent and "%" in value:
            value = value.rstrip("%")
            # UINs are base64-like; if a malformed trailing percent ate the
            # final padding marker, restore the missing `=` padding.
            if value.endswith("=") and len(value) % 4:
                value = value + ("=" * (4 - (len(value) % 4)))
        return value
    
    def cal_key_and_json(self, url_path, cookie_dict):
        try:
            biz_match = re.search(r"__biz=([^&]+)&?", url_path)
            key_match = re.search(r"key=([^&]+)&?", url_path)
            uin_match = re.search(r"uin=([^&]+)&?", url_path)
            pass_ticket_match = re.search(r"pass_ticket=([^&]+)&?", url_path)

            if not all([biz_match, key_match, uin_match, pass_ticket_match]):
                return None, None, None

            biz = self.uin_md5(biz_match.group(1))
            key = key_match.group(1)
            uin = self.uin_md5(uin_match.group(1))
            pass_ticket = pass_ticket_match.group(1)
            hash_key = hashlib.md5(biz.encode("utf-8")).hexdigest()
            appmsg_token = pass_ticket  # Corresponding to original code logic

            wap_sid2 = None
            if "wap_sid2" in cookie_dict:
                wap_sid2 = cookie_dict["wap_sid2"]
            data = {
                "uin": uin,
                "key": key,
                "pass_ticket": pass_ticket,
                "appmsg_token": appmsg_token,
                "wap_sid2": wap_sid2,
                "biz": biz,
            }
            json_data = json.dumps(data, ensure_ascii=False)

            return hash_key, data, json_data
        except Exception:
            return None, None, None

    def get_cookie(self, flow):
        raw_cookie = flow.request.headers.get("Cookie", "")
        cookie_dict: Dict[str, str] = {}
        if not raw_cookie:
            return cookie_dict

        jar = SimpleCookie()
        try:
            jar.load(raw_cookie)
        except Exception:
            jar = None

        if jar:
            for key, morsel in jar.items():
                cookie_dict[key] = morsel.value
            if cookie_dict:
                return cookie_dict

        # Some desktop/browser environments still emit malformed cookie strings.
        for chunk in re.split(r"[;,]\s*", raw_cookie):
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                cookie_dict[key] = value
        return cookie_dict

    def _response_cookies(self, flow: Any) -> Dict[str, str]:
        response = getattr(flow, "response", None)
        headers = getattr(response, "headers", None)
        if not headers:
            return {}

        raw_values = []
        getter = getattr(headers, "get_all", None)
        if callable(getter):
            try:
                raw_values = list(getter("Set-Cookie"))
            except Exception:
                raw_values = []

        if not raw_values:
            single = headers.get("Set-Cookie", "")
            if single:
                raw_values = [single]

        cookie_dict: Dict[str, str] = {}
        for raw_cookie in raw_values:
            if not raw_cookie:
                continue
            jar = SimpleCookie()
            try:
                jar.load(raw_cookie)
            except Exception:
                jar = None
            if jar:
                for key, morsel in jar.items():
                    cookie_dict[key] = morsel.value
        return cookie_dict

    def _persist_observed_operator_cookies(self, cookie_dict: Optional[Dict[str, str]], *, source: str) -> None:
        observed = {
            key: str(value)
            for key, value in (cookie_dict or {}).items()
            if key in {"slave_sid", "slave_user", "data_ticket", "bizuin", "uuid", "wap_sid2"}
            and value
        }
        if not observed:
            return

        try:
            try:
                from servers.wechat.cookie_harvest import persist_observed_cookies
            except ImportError:
                from cookie_harvest import persist_observed_cookies

            result = persist_observed_cookies(observed, source=source)
            verification = result.get("verification") or {}
            if verification.get("ok"):
                logger.info("persisted live WeChat operator cookies from %s", source)
            elif verification:
                logger.info(
                    "persisted WeChat cookies from %s but session is not live: %s",
                    source,
                    verification.get("reason") or "verification failed",
                )
        except Exception as exc:
            logger.warning("failed to persist observed WeChat cookies from %s: %s", source, exc)

    def _maybe_bridge_live_wechat_session(
        self,
        account_id: Any,
        session: Optional[Dict[str, Any]],
        cookie_dict: Optional[Dict[str, str]],
        *,
        user_id: str,
    ) -> None:
        account_biz = str((session or {}).get("biz") or "")
        operator_cookies = {
            key: str(value)
            for key, value in (cookie_dict or {}).items()
            if key in {"slave_sid", "slave_user", "data_ticket", "bizuin", "uuid", "wap_sid2"}
            and value
        }
        if not account_biz or not operator_cookies:
            return

        try:
            from servers.wechat.cookie_bridge import bridge_harvest_to_account

            result = bridge_harvest_to_account(
                account_biz,
                user_id=user_id,
                history_count=2,
                cookies=operator_cookies,
            )
            logger.info(
                "bridged live WeChat session for account %s via article click: mode=%s",
                account_id,
                result.get("mode"),
            )
        except Exception as exc:
            logger.info("live WeChat session bridge skipped for account %s: %s", account_id, exc)

    def _is_wechat_article_click(self, flow: Any) -> bool:
        if getattr(getattr(flow, "request", None), "host", "") != "mp.weixin.qq.com":
            return False
        path = str(getattr(getattr(flow, "request", None), "path", "") or "")
        return path.startswith("/s?") or bool(re.match(r"^/s/[\w-]+", path))

    def _persist_key_payload(self, data: Dict[str, Any]) -> Optional[str]:
        biz = self.uin_md5(str(data.get("biz") or ""))
        key = str(data.get("key") or "")
        uin = self.uin_md5(str(data.get("uin") or ""))
        pass_ticket = str(data.get("pass_ticket") or "")
        if not all([biz, key, uin, pass_ticket]):
            return None

        normalized = {
            "uin": uin,
            "key": key,
            "pass_ticket": pass_ticket,
            "appmsg_token": str(data.get("appmsg_token") or pass_ticket),
            "wap_sid2": str(data.get("wap_sid2") or ""),
            "biz": biz,
        }
        operator_cookies = data.get("operator_cookies")
        if isinstance(operator_cookies, dict):
            normalized["operator_cookies"] = {
                str(cookie_key): str(cookie_value)
                for cookie_key, cookie_value in operator_cookies.items()
                if cookie_key and cookie_value
            }
        hash_key = hashlib.md5(biz.encode("utf-8")).hexdigest()
        key_value_adapter.set_key(hash_key, json.dumps(normalized, ensure_ascii=False))
        logger.info(
            "persisted wechat article key payload for biz=%s uin=%s operator_cookies=%s",
            biz,
            uin,
            bool(normalized.get("operator_cookies")),
        )
        return hash_key

    def _extract_flow_session(
        self,
        flow: Any,
        *,
        cookie_dict: Optional[Dict[str, str]] = None,
        html_text: str = "",
    ) -> Optional[Dict[str, Any]]:
        if cookie_dict is None:
            cookie_dict = self.get_cookie(flow)

        request = getattr(flow, "request", None)
        response = getattr(flow, "response", None)
        values = [
            getattr(request, "url", ""),
            getattr(request, "pretty_url", ""),
            getattr(request, "path", ""),
            getattr(response, "headers", {}).get("Location", "") if response else "",
            html_text,
        ]

        try:
            from servers.wechat.cookie_bridge import _extract_per_article_session_from_values

            return _extract_per_article_session_from_values(values, cookies=cookie_dict)
        except Exception:
            fallback = self._fallback_session_from_stored_key(values, cookie_dict=cookie_dict)
            if fallback:
                return fallback
            hash_key, data, _ = self.cal_key_and_json(getattr(request, "path", "") or "", cookie_dict)
            if hash_key and data:
                return data
        return None

    def _fallback_session_from_stored_key(
        self,
        values: list[Any],
        *,
        cookie_dict: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        extracted: Dict[str, str] = {}
        for value in values:
            parsed = urlparse(str(value or ""))
            query = parse_qs(parsed.query or "")
            for key in ("__biz", "key", "uin", "pass_ticket", "appmsg_token", "wap_sid2"):
                if extracted.get(key):
                    continue
                vals = query.get(key) or []
                if vals:
                    extracted[key] = vals[0]

        biz = str(extracted.get("__biz") or "")
        if not biz:
            return None

        try:
            from api.rest.services.key import get_key_uin

            stored = dict(get_key_uin(unquote(biz)) or {})
        except Exception:
            stored = {}

        extracted_uin = self.uin_md5(str(extracted.get("uin") or ""))
        stored_uin = self.uin_md5(str(stored.get("uin") or ""))
        if not extracted_uin or "%" in extracted_uin:
            extracted_uin = stored_uin

        merged = {
            "biz": unquote(biz),
            "key": str(extracted.get("key") or stored.get("key") or ""),
            "uin": extracted_uin,
            "pass_ticket": str(extracted.get("pass_ticket") or stored.get("pass_ticket") or ""),
            "appmsg_token": str(
                extracted.get("appmsg_token")
                or stored.get("appmsg_token")
                or extracted.get("pass_ticket")
                or stored.get("pass_ticket")
                or ""
            ),
            "wap_sid2": str(
                (cookie_dict or {}).get("wap_sid2")
                or extracted.get("wap_sid2")
                or stored.get("wap_sid2")
                or ""
            ),
        }
        if not all([merged["biz"], merged["key"], merged["uin"], merged["pass_ticket"]]):
            return None
        return merged

    def _persist_wechat_article_session(
        self,
        flow: Any,
        *,
        cookie_dict: Optional[Dict[str, str]] = None,
        html_text: str = "",
    ) -> Optional[str]:
        session = self._extract_flow_session(flow, cookie_dict=cookie_dict, html_text=html_text)
        if not session:
            logger.info(
                "wechat article session not captured for url=%s path=%s",
                getattr(getattr(flow, "request", None), "url", ""),
                getattr(getattr(flow, "request", None), "path", ""),
            )
            return None
        if cookie_dict:
            session["operator_cookies"] = {
                str(cookie_key): str(cookie_value)
                for cookie_key, cookie_value in cookie_dict.items()
                if cookie_key and cookie_value
            }
        logger.info(
            "captured wechat article session biz=%s key=%s uin=%s operator_cookies=%s",
            str(session.get("biz") or ""),
            bool(session.get("key")),
            bool(session.get("uin")),
            bool(session.get("operator_cookies")),
        )
        return self._persist_key_payload(session)

    def _response_text(self, flow: Any) -> str:
        response = getattr(flow, "response", None)
        if response is None:
            return ""
        text = getattr(response, "text", None)
        if isinstance(text, str) and text:
            return text
        content = getattr(response, "content", b"")
        if not content:
            return ""
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore")
        return str(content)

    @run_with_app
    def request(self, flow):
        # Only process requests that match our specific criteria
        if self._is_wechat_article_click(flow):
            cookie_dict = self.get_cookie(flow=flow)
            self._persist_observed_operator_cookies(cookie_dict, source="mitmproxy_request")
            hash_key = self._persist_wechat_article_session(flow, cookie_dict=cookie_dict)
            if hash_key:
                ctx.log.info("sync redis account meta info: " + hash_key)
            # Note: We don't return early here to allow all mp.weixin.qq.com requests to pass through
            # This ensures CSS, JS, images, and other resources load properly for page rendering

    @run_with_app
    def response(self, flow):
        # Only process responses that match our specific criteria
        if self._is_wechat_article_click(flow):
            cookie_dict = self.get_cookie(flow=flow)
            cookie_dict.update(self._response_cookies(flow))
            self._persist_observed_operator_cookies(cookie_dict, source="mitmproxy_response")
            html_text = self._response_text(flow)
            hash_key = self._persist_wechat_article_session(
                flow,
                cookie_dict=cookie_dict,
                html_text=html_text,
            )
            session = self._extract_flow_session(flow, cookie_dict=cookie_dict, html_text=html_text)
            from api.rest.services.save import save_account

            user_id = str((session or {}).get("uin") or "my")
            id = save_account(wx_uri=flow.request.url, html_text=html_text, user_id=user_id)
            if id is not None:
                from api.rest.services.save import construct_article, save_article

                article = construct_article(
                    article_content_url=flow.request.url,
                    article_html=html_text,
                    account_id=id,
                )
                save_article(article=article, article_html=html_text)
                if hash_key:
                    ctx.log.info("sync database account meta info: " + hash_key)
                self._maybe_bridge_live_wechat_session(
                    id,
                    session,
                    cookie_dict,
                    user_id=user_id,
                )
                from api.rest.services.weixin import schedule_sync_account

                schedule_sync_account(id)
            else:
                self._maybe_bridge_live_wechat_session(
                    "unknown",
                    session,
                    cookie_dict,
                    user_id=user_id,
                )
                logger.info("account not found")
            # Note: We don't return early here to allow all mp.weixin.qq.com responses to pass through
            # This ensures CSS, JS, images, and other resources load properly for page rendering
