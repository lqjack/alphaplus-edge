import hashlib
import importlib
import json
import sys
import types


def _load_addons(monkeypatch):
    captured = {
        "set_keys": [],
        "save_account": [],
        "construct_article": [],
        "save_article": [],
        "schedule_sync_account": [],
        "ctx_logs": [],
        "persist_observed_cookies": [],
        "bridge_harvest_to_account": [],
    }

    mitmproxy_module = types.ModuleType("mitmproxy")
    mitmproxy_module.ctx = types.SimpleNamespace(
        log=types.SimpleNamespace(info=lambda message: captured["ctx_logs"].append(message))
    )
    mitmproxy_module.http = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "mitmproxy", mitmproxy_module)

    mongodb_module = types.ModuleType("api.rest.mongodb_adapter")
    mongodb_module.key_value_adapter = types.SimpleNamespace(
        set_key=lambda key, value: captured["set_keys"].append((key, value))
    )
    monkeypatch.setitem(sys.modules, "api.rest.mongodb_adapter", mongodb_module)

    article_check_module = types.ModuleType("core.tools.article_content_check")
    article_check_module.run_with_app = lambda fn: fn
    monkeypatch.setitem(sys.modules, "core.tools.article_content_check", article_check_module)

    save_module = types.ModuleType("api.rest.services.save")
    save_module.save_account = lambda **kwargs: captured["save_account"].append(kwargs) or 15
    save_module.construct_article = (
        lambda **kwargs: captured["construct_article"].append(kwargs) or {"article": kwargs}
    )
    save_module.save_article = lambda **kwargs: captured["save_article"].append(kwargs)
    monkeypatch.setitem(sys.modules, "api.rest.services.save", save_module)

    weixin_module = types.ModuleType("api.rest.services.weixin")
    weixin_module.schedule_sync_account = (
        lambda account_id: captured["schedule_sync_account"].append(account_id)
    )
    monkeypatch.setitem(sys.modules, "api.rest.services.weixin", weixin_module)

    key_module = types.ModuleType("api.rest.services.key")
    key_module.get_key_uin = lambda account_biz: {
        "biz": account_biz,
        "key": "stored-key",
        "uin": "stored-uin",
        "pass_ticket": "stored-pass-ticket",
        "appmsg_token": "stored-appmsg-token",
        "wap_sid2": "stored-wap",
    }
    monkeypatch.setitem(sys.modules, "api.rest.services.key", key_module)

    cookie_harvest_module = types.ModuleType("servers.wechat.cookie_harvest")
    cookie_harvest_module.persist_observed_cookies = (
        lambda cookies_dict, source="mitmproxy", path=None: captured["persist_observed_cookies"].append(
            {"cookies": dict(cookies_dict), "source": source, "path": path}
        )
        or {"source": source, "verification": {"ok": True}}
    )
    monkeypatch.setitem(sys.modules, "servers.wechat.cookie_harvest", cookie_harvest_module)

    import servers.wechat.cookie_bridge as real_cookie_bridge

    cookie_bridge_module = types.ModuleType("servers.wechat.cookie_bridge")
    cookie_bridge_module._extract_per_article_session_from_values = (
        real_cookie_bridge._extract_per_article_session_from_values
    )
    cookie_bridge_module.bridge_harvest_to_account = (
        lambda account_biz, user_id="my", history_count=1, cookies=None: captured["bridge_harvest_to_account"].append(
            {
                "account_biz": account_biz,
                "user_id": user_id,
                "history_count": history_count,
                "cookies": dict(cookies or {}),
            }
        )
        or {"ok": True, "mode": "history"}
    )
    monkeypatch.setitem(sys.modules, "servers.wechat.cookie_bridge", cookie_bridge_module)

    sys.modules.pop("core.tools.addons", None)
    import core.tools.addons as addons

    addons = importlib.reload(addons)
    return addons, captured


def _make_flow(*, path, url, cookie_header="", html_text=""):
    request = types.SimpleNamespace(
        host="mp.weixin.qq.com",
        path=path,
        url=url,
        pretty_url=url,
        headers={"Cookie": cookie_header},
    )
    response = types.SimpleNamespace(
        headers={},
        content=html_text.encode("utf-8"),
        text=html_text,
    )
    return types.SimpleNamespace(request=request, response=response)


def test_get_cookie_parses_standard_semicolon_cookie_header(monkeypatch):
    addons, _ = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    flow = _make_flow(
        path="/s?id=test",
        url="https://mp.weixin.qq.com/s?id=test",
        cookie_header="wap_sid2=fresh-1; data_ticket=ticket-1; bizuin=abc",
    )

    cookie_dict = proxy.get_cookie(flow)

    assert cookie_dict["wap_sid2"] == "fresh-1"
    assert cookie_dict["data_ticket"] == "ticket-1"
    assert cookie_dict["bizuin"] == "abc"


def test_request_persists_wechat_click_session_from_query_url(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    flow = _make_flow(
        path="/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        url="https://mp.weixin.qq.com/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        cookie_header="wap_sid2=fresh-1; data_ticket=ticket-1",
    )

    proxy.request(flow)

    assert len(captured["set_keys"]) == 1
    persisted_key, raw_payload = captured["set_keys"][0]
    assert persisted_key == hashlib.md5("MzA1==".encode("utf-8")).hexdigest()
    payload = json.loads(raw_payload)
    assert payload["biz"] == "MzA1=="
    assert payload["key"] == "k-1"
    assert payload["uin"] == "12345"
    assert payload["pass_ticket"] == "pt-1"
    assert payload["wap_sid2"] == "fresh-1"
    assert payload["operator_cookies"]["wap_sid2"] == "fresh-1"
    assert payload["operator_cookies"]["data_ticket"] == "ticket-1"
    assert captured["persist_observed_cookies"] == [
        {
            "cookies": {
                "wap_sid2": "fresh-1",
                "data_ticket": "ticket-1",
            },
            "source": "mitmproxy_request",
            "path": None,
        }
    ]


def test_request_falls_back_to_stored_pass_ticket_when_click_url_is_incomplete(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    flow = _make_flow(
        path="/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=live-key&uin=live-uin",
        url="https://mp.weixin.qq.com/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=live-key&uin=live-uin",
        cookie_header="wap_sid2=fresh-3; data_ticket=ticket-3",
    )

    proxy.request(flow)

    assert len(captured["set_keys"]) == 1
    _, raw_payload = captured["set_keys"][0]
    payload = json.loads(raw_payload)
    assert payload["biz"] == "MzA1=="
    assert payload["key"] == "live-key"
    assert payload["uin"] == "live-uin"
    assert payload["pass_ticket"] == "stored-pass-ticket"
    assert payload["appmsg_token"] == "stored-appmsg-token"
    assert payload["wap_sid2"] == "fresh-3"


def test_request_stabilizes_partially_decoded_uin_without_recursing_forever(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    flow = _make_flow(
        path="/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=live-key&uin=MjQ2MDQ5ODMwNA%253D%25",
        url="https://mp.weixin.qq.com/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=live-key&uin=MjQ2MDQ5ODMwNA%253D%25",
        cookie_header="wap_sid2=fresh-4; data_ticket=ticket-4",
    )

    proxy.request(flow)

    assert len(captured["set_keys"]) == 1
    _, raw_payload = captured["set_keys"][0]
    payload = json.loads(raw_payload)
    assert payload["uin"] == "MjQ2MDQ5ODMwNA=="
    assert payload["pass_ticket"] == "stored-pass-ticket"


def test_response_persists_session_from_article_html_for_slash_click(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    html_text = """
    <html>
      <head><meta property="og:title" content="达里奥：黄金或成终极避险选项"></head>
      <body>
        <script>
          var biz = "MzA1==" || "";
          window.__INITIAL_STATE__ = {"key":"k-auto","uin":"98765","pass_ticket":"pt-2","appmsg_token":"app-2"};
        </script>
        <article>黄金和避险情绪持续升温。</article>
      </body>
    </html>
    """
    flow = _make_flow(
        path="/s/slug-click-article",
        url="https://mp.weixin.qq.com/s/slug-click-article",
        cookie_header="wap_sid2=fresh-2; data_ticket=ticket-2",
        html_text=html_text,
    )

    proxy.response(flow)

    assert len(captured["set_keys"]) == 1
    persisted_key, raw_payload = captured["set_keys"][0]
    assert persisted_key == hashlib.md5("MzA1==".encode("utf-8")).hexdigest()
    payload = json.loads(raw_payload)
    assert payload["key"] == "k-auto"
    assert payload["uin"] == "98765"
    assert payload["pass_ticket"] == "pt-2"
    assert payload["appmsg_token"] == "app-2"
    assert payload["wap_sid2"] == "fresh-2"
    assert payload["operator_cookies"]["wap_sid2"] == "fresh-2"

    assert captured["save_account"][0]["wx_uri"] == "https://mp.weixin.qq.com/s/slug-click-article"
    assert captured["save_account"][0]["user_id"] == "98765"
    assert captured["construct_article"][0]["account_id"] == 15
    assert captured["construct_article"][0]["article_content_url"] == "https://mp.weixin.qq.com/s/slug-click-article"
    assert captured["schedule_sync_account"] == [15]
    assert captured["bridge_harvest_to_account"] == [
        {
            "account_biz": "MzA1==",
            "user_id": "98765",
            "history_count": 2,
            "cookies": {
                "wap_sid2": "fresh-2",
                "data_ticket": "ticket-2",
            },
        }
    ]


def test_request_persists_operator_cookies_when_article_click_carries_backend_session(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    flow = _make_flow(
        path="/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        url="https://mp.weixin.qq.com/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        cookie_header="wap_sid2=fresh-1; slave_sid=sid-1; data_ticket=ticket-1; bizuin=123; uuid=uuid-1",
    )

    proxy.request(flow)

    assert captured["persist_observed_cookies"] == [
        {
            "cookies": {
                "wap_sid2": "fresh-1",
                "slave_sid": "sid-1",
                "data_ticket": "ticket-1",
                "bizuin": "123",
                "uuid": "uuid-1",
            },
            "source": "mitmproxy_request",
            "path": None,
        }
    ]


def test_response_merges_set_cookie_into_observed_operator_cookies(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    flow = _make_flow(
        path="/s/slug-click-article",
        url="https://mp.weixin.qq.com/s/slug-click-article",
        cookie_header="wap_sid2=old-wap; data_ticket=ticket-1",
        html_text="<html></html>",
    )
    flow.response.headers = types.SimpleNamespace(
        get_all=lambda name: [
            "wap_sid2=new-wap; Path=/; HttpOnly",
            "slave_sid=sid-2; Path=/; Secure",
        ],
        get=lambda name, default="": default,
    )

    proxy.response(flow)

    assert captured["persist_observed_cookies"][0]["source"] == "mitmproxy_response"
    assert captured["persist_observed_cookies"][0]["cookies"]["wap_sid2"] == "new-wap"
    assert captured["persist_observed_cookies"][0]["cookies"]["slave_sid"] == "sid-2"
    assert captured["persist_observed_cookies"][0]["cookies"]["data_ticket"] == "ticket-1"


def test_response_skips_live_bridge_without_operator_cookie_context(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    flow = _make_flow(
        path="/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        url="https://mp.weixin.qq.com/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        cookie_header="",
        html_text="<html></html>",
    )

    proxy.response(flow)

    assert captured["bridge_harvest_to_account"] == []


def test_response_attempts_live_bridge_even_when_save_account_cannot_parse_article(monkeypatch):
    addons, captured = _load_addons(monkeypatch)
    proxy = addons.WeiXinProxy()
    addons.save_account = None

    save_module = sys.modules["api.rest.services.save"]
    save_module.save_account = lambda **kwargs: captured["save_account"].append(kwargs) or None

    flow = _make_flow(
        path="/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        url="https://mp.weixin.qq.com/s?__biz=MzA1==&mid=1&idx=1&sn=abc&key=k-1&uin=12345&pass_ticket=pt-1",
        cookie_header="wap_sid2=fresh-1; slave_sid=sid-1; data_ticket=ticket-1",
        html_text="<html>captcha</html>",
    )

    proxy.response(flow)

    assert captured["save_account"][0]["wx_uri"] == flow.request.url
    assert captured["bridge_harvest_to_account"] == [
        {
            "account_biz": "MzA1==",
            "user_id": "12345",
            "history_count": 2,
            "cookies": {
                "wap_sid2": "fresh-1",
                "slave_sid": "sid-1",
                "data_ticket": "ticket-1",
            },
        }
    ]
