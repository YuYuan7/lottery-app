# -*- coding: utf-8 -*-
"""
生成「自包含单文件 HTML」到 dist/单文件版/彩票统计.html

特点：数据直接烤进 HTML，**不发起任何网络请求**。
     → 不依赖后端、不依赖 data/*.json
     → 双击就能看，也可以直接把这一个文件发给别人
     → 彻底避开云平台「非 HTML 请求被强制下载」的限制

用法:
    python3 build_single.py             # 用已有数据生成（快）
    python3 build_single.py --refresh   # 先重新抓取再生成
"""
import os
import sys
import json
import time
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(BASE, "dist", "单文件版")
DATA = os.path.join(BASE, "dist", "static_site", "data")
META_KEYS = ("name", "redMax", "blueMax", "redCount", "blueCount",
             "redLabel", "blueLabel")

refresh = "--refresh" in sys.argv


def log(m):
    print("[single] " + m)


def strip(o):
    return {k: v for k, v in o.items() if k in META_KEYS or k == "rows"}


def ensure_data():
    """确保 dist/static_site/data/*.json 存在"""
    os.makedirs(DATA, exist_ok=True)
    if refresh or not os.path.exists(os.path.join(DATA, "ssq.json")):
        log("抓取最新数据 ...")
        sys.path.insert(0, BASE)
        import crawler
        for lot in ("ssq", "dlt"):
            data, src = crawler.get_data_safe(lot, force=True)
            body = strip(data)
            body["source"] = src
            body["count"] = len(body["rows"])
            with open(os.path.join(DATA, lot + ".json"), "w",
                      encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
            log("  %s: %d 期 (%s)" % (lot, body["count"], src))


def build():
    html = open(os.path.join(BASE, "static", "index.html"),
                encoding="utf-8").read()

    payload = {}
    for lot in ("ssq", "dlt"):
        payload[lot] = json.load(
            open(os.path.join(DATA, lot + ".json"), encoding="utf-8"))

    # 补写 updatedAt / buildDate。
    # 这两个字段只有后端 main.py 会写，静态构建不会，
    # 缺了会让页面显示「数据更新于 Invalid Date」
    # （undefined*1000 = NaN → new Date(NaN)）。
    now = int(time.time())
    now_str = datetime.datetime.utcfromtimestamp(now + 8 * 3600) \
        .strftime("%Y-%m-%d %H:%M")
    for lot in ("ssq", "dlt"):
        d = payload[lot]
        d["updatedAt"] = int(d.get("updatedAt") or 0) or now
        d["buildDate"] = d.get("buildDate") or now_str
        d["embedded"] = True
        d["staticMode"] = True

    # 注入内嵌数据 + fetch 垫片（放在所有脚本之前）
    inject = ("<script>\n"
              "/* 内嵌数据：由 build_single.py 生成，页面无需任何网络请求 */\n"
              "var EMBEDDED_DATA = " +
              json.dumps(payload, ensure_ascii=False, separators=(",", ":")) +
              ";\n"
              "/* fetch 垫片：拦截一切数据请求，直接从内嵌数据返回。\n"
              "   这样即使浏览器在 file:// 下让 fetch 永久挂起，页面也能正常渲染。 */\n"
              "(function(){\n"
              "  if(typeof EMBEDDED_DATA==='undefined'||!EMBEDDED_DATA) return;\n"
              "  var realFetch = window.fetch ? window.fetch.bind(window) : null;\n"
              "  window.fetch = function(url, opt){\n"
              "    var s = String(url==null?'':url);\n"
              "    var m = /(ssq|dlt)/.exec(s);\n"
              "    if(m && EMBEDDED_DATA[m[1]]){\n"
              "      var d = EMBEDDED_DATA[m[1]];\n"
              "      return Promise.resolve({\n"
              "        ok:true, status:200,\n"
              "        headers:{get:function(){return 'application/json'}},\n"
              "        json:function(){return Promise.resolve(d)},\n"
              "        text:function(){return Promise.resolve(JSON.stringify(d))}\n"
              "      });\n"
              "    }\n"
              "    return realFetch ? realFetch(url, opt)\n"
              "                     : Promise.reject(new Error('offline'));\n"
              "  };\n"
              "})();\n"
              "</script>\n")

    marker = "<script>\nvar API ="
    if marker not in html:
        # 退而求其次：插到第一个 <script> 之前
        idx = html.index("<script>")
        html = html[:idx] + inject + html[idx:]
    else:
        html = html.replace(marker, inject + marker, 1)

    # 标记：内嵌模式 + 静态模式
    html = html.replace("var STATIC_BUILD = false;",
                        "var STATIC_BUILD = true;\nvar EMBEDDED_BUILD = true;", 1)

    # 让 load() 优先读内嵌数据
    old = """  /* 静态托管模式：优先读同目录 data/xx.json（无需后端，免备案可分享）
     读不到再回退到后端 /api/history（自建服务器 / 云函数部署时用） */
  return fetch('./data/'+lot+'.json', {cache:'no-store'}).then(function(r){"""
    new = """  /* 内嵌模式：数据已烤进本文件，直接返回，零网络请求 */
  if(typeof EMBEDDED_DATA!=='undefined' && EMBEDDED_DATA && EMBEDDED_DATA[lot]
     && EMBEDDED_DATA[lot].rows && EMBEDDED_DATA[lot].rows.length){
    var ed = EMBEDDED_DATA[lot]; ed.embedded = true; ed.staticMode = true;
    D[lot] = ed;                    /* 关键：必须写入 D，否则 render() 读不到 */
    return Promise.resolve(ed);
  }
  /* 静态托管模式：优先读同目录 data/xx.json（无需后端，免备案可分享）
     读不到再回退到后端 /api/history（自建服务器 / 云函数部署时用） */
  return fetch('./data/'+lot+'.json', {cache:'no-store'}).then(function(r){"""
    assert old in html, "未找到 load() 内的静态读取分支"
    html = html.replace(old, new, 1)

    old_tip = ('\'正在获取\'+n+\'最新开奖数据…<br><span style="font-size:12px;color:#aaa">'
               '首次加载需从官方接口抓取，请稍候</span>')
    new_tip = ('\'正在加载\'+n+\'开奖数据…<br><span style="font-size:12px;color:#aaa">'
               '\'+(typeof EMBEDDED_BUILD!==\'undefined\'&&EMBEDDED_BUILD'
               '?\'请稍候\':\'首次加载需从官方接口抓取，请稍候\')+\'</span>')
    if old_tip in html:
        html = html.replace(old_tip, new_tip, 1)
        log("  加载提示文案已改为自适应")
    else:
        log("  [警告] 未匹配到加载提示文案，保留原文")

    # loading 文案：内嵌版不再提示"从官方接口抓取"
    html = html.replace(
        "正在获取'+n+'最新开奖数据…<br><span style=\"font-size:12px;color:#aaa\">"
        "首次加载需从官方接口抓取，请稍候</span>",
        "正在加载'+n+'开奖数据…<br><span style=\"font-size:12px;color:#aaa\">"
        "请稍候</span>", 1)

    # 修「数据更新于 Invalid Date」：前端加兜底。
    # 任何情况下 updatedAt 缺失/非法，都退回用「最新一期的开奖日期」显示。
    old_upd = ("  var d=D[S.lot], t=new Date(d.updatedAt*1000);\n"
               "  var s='<div class=\"upd\">数据更新于 '+t.toLocaleString('zh-CN')\n"
               "    +(typeof EMBEDDED_BUILD!=='undefined'&&EMBEDDED_BUILD"
               "?'（数据已内置于本页面，无需联网）':(d.source==='live'?'（实时抓取）':'（缓存）'))+'</div>';")
    new_upd = ("  var d=D[S.lot];\n"
               "  var _ts=Number(d&&d.updatedAt)*1000;\n"
               "  var _t=(_ts>0)?new Date(_ts):null;\n"
               "  var _txt=_t?_t.toLocaleString('zh-CN')\n"
               "    :((d&&d.buildDate)?String(d.buildDate)\n"
               "      :((d&&d.rows&&d.rows.length)?String(d.rows[d.rows.length-1][1]):'未知'));\n"
               "  /* 当前时间：取访客本机时间，每次渲染刷新 */\n"
               "  var _n=new Date();\n"
               "  var _p=function(x){return (x<10?'0':'')+x;};\n"
               "  var _now=_p(_n.getMonth()+1)+'-'+_p(_n.getDate())+' '\n"
               "          +_p(_n.getHours())+':'+_p(_n.getMinutes())+':'+_p(_n.getSeconds());\n"
               "  var s='<div class=\"upd\">数据更新于 '+_txt+'（构建时刻）'\n"
               "    +' · 当前时间 '+_now+'</div>';")
    if old_upd in html:
        html = html.replace(old_upd, new_upd, 1)
        log("  已改为：构建时刻 + 当前时间")
    else:
        log("  [警告] 未匹配到 upd 区块，日期改动未注入")

    # 兜底：若 3 秒后仍停在 loading，直接用内嵌数据强制渲染
    html = html.replace(
        "</script>\n</body>",
        "</script>\n<script>\n"
        "(function(){\n"
        "  setTimeout(function(){\n"
        "    try{\n"
        "      var m = document.getElementById('main');\n"
        "      if(!m || !/正在加载|正在获取/.test(m.textContent)) return;\n"
        "      var lot = (typeof S!=='undefined'&&S.lot)||'ssq';\n"
        "      var d = EMBEDDED_DATA && EMBEDDED_DATA[lot];\n"
        "      if(!d || !d.rows || !d.rows.length) return;\n"
        "      D[lot] = d; render();\n"
        "    }catch(e){}\n"
        "  }, 3000);\n"
        "})();\n</script>\n</body>", 1)

    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, "彩票统计.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(path)
    log("生成: " + path)
    log("大小: %.0f KB" % (size / 1024))
    for lot in ("ssq", "dlt"):
        log("  内嵌 %s: %d 期，最新 %s (%s)"
            % (lot, payload[lot]["count"],
               payload[lot]["rows"][-1][0], payload[lot]["rows"][-1][1]))
    return path


if __name__ == "__main__":
    ensure_data()
    build()
    log("完成。这一个文件可以直接双击打开，也可以发给别人。")
