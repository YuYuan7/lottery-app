# -*- coding: utf-8 -*-
"""
生成「纯静态站点」到 dist/static_site/

特点：无需后端、无需数据库、无需 Serverless。
      前端 + 数据 JSON 一起上传到任何静态托管
      （推荐腾讯云 CloudBase 静态网站托管，免备案、国内 CDN）
      即可多人同时访问。

用法:
    python3 build_static.py            # 生成静态站点（数据已存在则复用）
    python3 build_static.py --refresh  # 重新抓取最新数据再生成
"""
import os
import re
import sys
import json
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "dist", "static_site")
DATA = os.path.join(OUT, "data")
META_KEYS = ("name", "redMax", "blueMax", "redCount", "blueCount",
             "redLabel", "blueLabel", "pool")

refresh = "--refresh" in sys.argv


LOTS = ("ssq", "dlt", "3d", "pls")


def load_license():
    """读取 license.json（由 make_license.py 生成）；不存在则不开启授权限制。"""
    p = os.path.join(BASE, "license.json")
    if not os.path.exists(p):
        return None
    try:
        cfg = json.load(open(p, encoding="utf-8"))
    except Exception as e:      # noqa
        log("[警告] license.json 解析失败，跳过授权: %s" % e)
        return None
    if not cfg.get("salt") or not cfg.get("codes"):
        return None
    out = {"salt": cfg["salt"], "expire": cfg.get("expire", ""),
           "codes": list(cfg["codes"])}
    if cfg.get("sigSalt"):
        out["sigSalt"] = cfg["sigSalt"]
    if cfg.get("admin"):
        out["admin"] = cfg["admin"]
    if cfg.get("regUrl"):
        out["regUrl"] = cfg["regUrl"]
    return out


def log(m):
    print("[static] " + m)


def strip(o):
    return {k: v for k, v in o.items() if k in META_KEYS or k == "rows"}


def fetch_data():
    sys.path.insert(0, BASE)
    import crawler
    os.makedirs(DATA, exist_ok=True)
    for lot in LOTS:
        data, src = crawler.get_data_safe(lot, force=True)
        body = strip(data)
        body["source"] = src
        body["count"] = len(body["rows"])
        import time as _t, datetime as _dt
        _n = int(_t.time())
        body["updatedAt"] = _n
        body["buildDate"] = _dt.datetime.utcfromtimestamp(_n + 8 * 3600).strftime("%Y-%m-%d %H:%M")
        with open(os.path.join(DATA, lot + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
        log("%s: %d 期 (%s)" % (lot, body["count"], src))


def build_html():
    src = os.path.join(BASE, "static", "index.html")
    html = open(src, encoding="utf-8").read()
    # 注入静态标记：关闭后端回退与「刷新数据」按钮
    html = html.replace("var STATIC_BUILD = false;",
                        "var STATIC_BUILD = true;", 1)

    # 访问授权：存在 license.json 就内嵌（只含散列，不含明文授权码）
    lic = load_license()
    if lic:
        html = html.replace("var LICENSE = null;",
                            "var LICENSE = " + json.dumps(lic, ensure_ascii=False,
                                                          separators=(",", ":")) + ";", 1)
        log("访问授权：已内嵌（到期 %s，%d 个授权码）"
            % (lic.get("expire"), len(lic.get("codes") or [])))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    assert "var STATIC_BUILD = true;" in html
    log("index.html 已注入 STATIC_BUILD=true")


def ensure_meta():
    """旧版生成的 data/*.json 没有 updatedAt，会让页面显示「最新一期日期」
       而不是构建时刻。这里统一补上（缺失时用文件修改时间）。"""
    import time as _t
    import datetime as _dt
    for lot in LOTS:
        p = os.path.join(DATA, lot + ".json")
        if not os.path.exists(p):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        changed = False
        if not d.get("updatedAt"):
            d["updatedAt"] = int(os.path.getmtime(p))
            changed = True
        if not d.get("buildDate"):
            d["buildDate"] = _dt.datetime.utcfromtimestamp(
                int(d["updatedAt"]) + 8 * 3600).strftime("%Y-%m-%d %H:%M")
            changed = True
        if changed:
            json.dump(d, open(p, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
            log("  补写 %s.json 的 updatedAt/buildDate" % lot)


def main():
    if refresh or not os.path.isdir(DATA) or \
            not os.path.exists(os.path.join(DATA, "ssq.json")):
        log("抓取最新数据 ...")
        fetch_data()
    else:
        log("复用已有数据（加 --refresh 可重新抓取）")
    ensure_meta()
    build_html()
    # 汇总信息
    info = {}
    for lot in LOTS:
        p = os.path.join(DATA, lot + ".json")
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding="utf-8"))
        rows = d.get("rows", [])
        info[lot] = {"count": len(rows),
                     "latest": (rows[-1][0] if rows else None),
                     "latestDate": (rows[-1][1] if rows else None),
                     "bytes": os.path.getsize(p)}
    log("输出目录: " + OUT)
    for k, v in info.items():
        log("  %s: %d 期, 最新 %s (%s), %.0f KB"
            % (k, v["count"], v["latest"], v["latestDate"], v["bytes"] / 1024))
    log("完成。把 dist/static_site/ 里所有文件上传到静态托管即可。")


if __name__ == "__main__":
    main()
