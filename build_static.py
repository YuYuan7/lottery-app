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
             "redLabel", "blueLabel")

refresh = "--refresh" in sys.argv


def log(m):
    print("[static] " + m)


def strip(o):
    return {k: v for k, v in o.items() if k in META_KEYS or k == "rows"}


def fetch_data():
    sys.path.insert(0, BASE)
    import crawler
    os.makedirs(DATA, exist_ok=True)
    for lot in ("ssq", "dlt"):
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
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    assert "var STATIC_BUILD = true;" in html
    log("index.html 已注入 STATIC_BUILD=true")


def main():
    if refresh or not os.path.isdir(DATA) or \
            not os.path.exists(os.path.join(DATA, "ssq.json")):
        log("抓取最新数据 ...")
        fetch_data()
    else:
        log("复用已有数据（加 --refresh 可重新抓取）")
    build_html()
    # 汇总信息
    info = {}
    for lot in ("ssq", "dlt"):
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
