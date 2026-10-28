# -*- coding: utf-8 -*-
"""授权登记表（云端 KV）——让一个授权码只能绑定一台设备。

为什么必须有它：
    纯静态页面没有服务端，各设备的 localStorage 互不相通。
    光靠「码 + 本机指纹」只能做到换设备要重新激活，
    做不到「同一码不能在两台设备同时用」。
    所以需要一个所有设备都能读写的公共登记表。

登记表结构（存在第三方免费 JSON 存储里）：
    {"v":1,"bind":{"CODE":{"dev":"设备ID短号","at":"2026-10-28"}}}

支持的 provider：
    jsonblob  https://jsonblob.com/api/jsonBlob/{id}      POST 建 / GET 读 / PUT 写
    pantry    https://getpantry.cloud/apiv1/pantry/{id}/basket/{basket}
    custom    直接给完整 URL，GET 读、PUT 写

重要边界（务必看清）：
    登记表地址（含写入凭证）内嵌在页面里，所以这依然不是强加密方案。
    它能挡住「一个码发给多个人各自激活」——这是真实且常见的场景；
    挡不住懂技术的人扒源码清空登记表。要真正做到不可伪造 + 可吊销，
    必须有私有后端。
"""
import json
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (lottery-app registry client)"

PROVIDERS = {
    "jsonblob": {
        "create": "https://jsonblob.com/api/jsonBlob",
        "tmpl": "https://jsonblob.com/api/jsonBlob/{id}",
    },
    "pantry": {
        "create": "https://getpantry.cloud/apiv1/pantry/",
        "tmpl": "https://getpantry.cloud/apiv1/pantry/{id}/basket/lottery",
    },
}


def _req(url, method="GET", body=None, timeout=20):
    data = None
    headers = {"User-Agent": UA}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return json.loads(raw) if raw.strip() else {}
            except Exception:      # noqa
                return {}
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s" % e.code)
    except Exception as e:         # noqa
        raise RuntimeError(str(e))


def create(provider="jsonblob", timeout=20):
    """建一个空登记表，返回 (url, 备注)。"""
    if provider == "custom":
        raise ValueError("custom 不能自动创建，请直接给 URL")
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ValueError("未知 provider: %s" % provider)
    req = urllib.request.Request(
        cfg["create"],
        data=json.dumps({"v": 1, "bind": {}}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        loc = r.headers.get("Location") or r.headers.get("x-jsonblob") \
            or r.headers.get("X-jsonblob") or ""
        if provider == "jsonblob" and loc and "/api/jsonBlob/" not in loc:
            loc = "/api/jsonBlob/" + loc
        if not loc:
            raise RuntimeError("服务未返回登记表 ID（可能被拦截或改版）")
        if loc.startswith("/"):
            host = cfg["create"].split("/api")[0]
            url = host + loc
        else:
            url = loc
    return url, ""


def get(url, timeout=15):
    o = _req(url, "GET", timeout=timeout)
    if not isinstance(o, dict):
        return {"v": 1, "bind": {}}
    o.setdefault("bind", {})
    return o


def put(url, obj, timeout=20):
    return _req(url, "PUT", obj, timeout=timeout)


def url_for(provider, ident):
    """已知 ID 反推完整 URL。"""
    if provider == "custom":
        return ident
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ValueError("未知 provider: %s" % provider)
    return cfg["tmpl"].replace("{id}", ident)
