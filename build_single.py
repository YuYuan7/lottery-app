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
             "redLabel", "blueLabel", "pool", "positional", "posLabels", "minNum")

refresh = "--refresh" in sys.argv


def log(m):
    print("[single] " + m)


LOTS = ("ssq", "dlt", "3d", "pls")


def load_license():
    """读取 license.json（由 make_license.py 生成）。
    不存在就返回 None —— 不开启授权限制，页面可直接打开。"""
    p = os.path.join(BASE, "license.json")
    if not os.path.exists(p):
        return None
    try:
        cfg = json.load(open(p, encoding="utf-8"))
    except Exception as e:      # noqa
        print("[single] [警告] license.json 解析失败，跳过授权: %s" % e)
        return None
    if not cfg.get("salt") or not cfg.get("codes"):
        return None
    out = {"salt": cfg["salt"], "expire": cfg.get("expire", ""),
           "codes": list(cfg["codes"])}
    if cfg.get("sigSalt"):
        out["sigSalt"] = cfg["sigSalt"]
    if cfg.get("admin"):
        out["admin"] = cfg["admin"]
    return out


def strip(o):
    return {k: v for k, v in o.items() if k in META_KEYS or k == "rows"}


def ensure_data():
    """确保 dist/static_site/data/*.json 存在"""
    os.makedirs(DATA, exist_ok=True)
    if refresh or not os.path.exists(os.path.join(DATA, "ssq.json")):
        log("抓取最新数据 ...")
        sys.path.insert(0, BASE)
        import crawler
        for lot in LOTS:
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
    for lot in LOTS:
        payload[lot] = json.load(
            open(os.path.join(DATA, lot + ".json"), encoding="utf-8"))

    # 补写 updatedAt / buildDate。
    # 这两个字段只有后端 main.py 会写，静态构建不会，
    # 缺了会让页面显示「数据更新于 Invalid Date」
    # （undefined*1000 = NaN → new Date(NaN)）。
    now = int(time.time())
    now_str = datetime.datetime.utcfromtimestamp(now + 8 * 3600) \
        .strftime("%Y-%m-%d %H:%M")
    for lot in LOTS:
        d = payload[lot]
        d["updatedAt"] = int(d.get("updatedAt") or 0) or now
        d["buildDate"] = d.get("buildDate") or now_str
        d["embedded"] = True
        d["staticMode"] = True

    # 内嵌数据：以「字符串」形式烤进页面。
    # 相比直接写对象字面量，字符串字面量 JS 引擎只需扫描、不必构造
    # 2080×7 层嵌套数组，首次解析明显更快；真正解析交给 JSON.parse，
    # 且结果会存进 localStorage，二次打开连 JSON.parse 都省不掉但
    # 不必再扫这段 227 KB 的文本。
    meta = {}
    for lot in LOTS:
        d = payload[lot]
        meta[lot] = {
            "n": len(d["rows"]),
            "last": d["rows"][0][0] if d["rows"] else "",
            "upd": int(d.get("updatedAt") or 0),
            "st": "%d_%s_%d" % (len(d["rows"]),
                                d["rows"][0][0] if d["rows"] else "",
                                int(d.get("updatedAt") or 0)),
        }
    src = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    inject = ("<script>\n"
              "/* 内嵌数据：由 build_single.py 生成，页面无需任何网络请求 */\n"
              "var EMBEDDED_META = " +
              json.dumps(meta, ensure_ascii=False, separators=(",", ":")) +
              ";\n"
              "var EMBEDDED_SRC = " +
              json.dumps(src, ensure_ascii=False) + ";\n"
              "var EMBEDDED_DATA = null;\n"
              "/* 取内嵌数据：优先读本机缓存（命中则不必解析 EMBEDDED_SRC），\n"
              "   未命中才解析一次并写回缓存 */\n"
              "function embeddedLoad(lot){\n"
              "  if(EMBEDDED_DATA) return EMBEDDED_DATA[lot];\n"
              "  var out={}, allHit=true, k;\n"
              "  if(typeof LC_OK!=='undefined' && LC_OK){\n"
              "    for(k in EMBEDDED_META){\n"
              "      var ok=false;\n"
              "      try{\n"
              "        if(localStorage.getItem('lcst_'+k)===EMBEDDED_META[k].st){\n"
              "          var s=localStorage.getItem('lcd_'+k);\n"
              "          if(s){ out[k]=JSON.parse(s); ok=true; }\n"
              "        }\n"
              "      }catch(e){}\n"
              "      if(!ok) allHit=false;\n"
              "    }\n"
              "  } else allHit=false;\n"
              "  if(allHit){ EMBEDDED_DATA=out; /* 命中本机缓存 */\n"
              "    try{ window.__lcHit=true; }catch(e){}\n"
              "    return EMBEDDED_DATA[lot]; }\n"
              "  EMBEDDED_DATA=JSON.parse(EMBEDDED_SRC);\n"
              "  try{ window.__lcHit=false; }catch(e){}\n"
              "  if(typeof LC_OK!=='undefined' && LC_OK){\n"
              "    for(k in EMBEDDED_META){\n"
              "      try{\n"
              "        localStorage.setItem('lcd_'+k, JSON.stringify(EMBEDDED_DATA[k]));\n"
              "        localStorage.setItem('lcst_'+k, EMBEDDED_META[k].st);\n"
              "      }catch(e){}\n"
              "    }\n"
              "  }\n"
              "  return EMBEDDED_DATA[lot];\n"
              "}\n"
              "/* fetch 垫片：拦截一切数据请求，直接从内嵌数据返回。\n"
              "   这样即使浏览器在 file:// 下让 fetch 永久挂起，页面也能正常渲染。 */\n"
              "(function(){\n"
              "  if(typeof EMBEDDED_META==='undefined'||!EMBEDDED_META) return;\n"
              "  var realFetch = window.fetch ? window.fetch.bind(window) : null;\n"
              "  window.fetch = function(url, opt){\n"
              "    var m = /(ssq|dlt|3d|pls)/.exec(String(url==null?'':url));\n"
              "    if(m && EMBEDDED_META[m[1]]){\n"
              "      var d = embeddedLoad(m[1]);\n"
              "      if(d) return Promise.resolve({\n"
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

    # 访问授权：存在 license.json 就内嵌（只含散列，不含明文授权码）
    lic = load_license()
    if lic:
        html = html.replace("var LICENSE = null;",
                            "var LICENSE = " + json.dumps(lic, ensure_ascii=False,
                                                          separators=(",", ":")) + ";", 1)
        log("访问授权：已内嵌（到期 %s，%d 个授权码）"
            % (lic.get("expire"), len(lic.get("codes") or [])))
    else:
        log("访问授权：未开启（无 license.json，页面可直接打开）")

    # 让 load() 优先读内嵌数据
    old = """  /* 静态托管模式：优先读同目录 data/xx.json（无需后端，免备案可分享）
     读不到再回退到后端 /api/history（自建服务器 / 云函数部署时用） */
  return fetch('./data/'+lot+'.json', {cache:'no-store'}).then(function(r){"""
    new = """  /* 内嵌模式：数据已烤进本文件，直接返回，零网络请求 */
  if(typeof EMBEDDED_META!=='undefined' && EMBEDDED_META && EMBEDDED_META[lot]
     && typeof embeddedLoad==='function'){
    var ed = embeddedLoad(lot);
    if(ed && ed.rows && ed.rows.length){
      ed.embedded = true; ed.staticMode = true;
      D[lot] = ed;                  /* 关键：必须写入 D，否则 render() 读不到 */
      return Promise.resolve(ed);
    }
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

    # 「数据更新于」时间格式：源码已内置 fmtDt 统一格式，这里只在旧版源码上补。
    if "function fmtDt(" in html:
        log("  时间格式：源码已统一为 YYYY-MM-DD，跳过注入")
    else:
        log("  [警告] 源码未含 fmtDt，时间格式可能仍不一致")

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
        "      var d = (typeof EMBEDDED_META!=='undefined' && EMBEDDED_META && EMBEDDED_META[lot]\n"
        "             && typeof embeddedLoad==='function') ? embeddedLoad(lot) : null;\n"
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
    for lot in LOTS:
        log("  内嵌 %s: %d 期，最新 %s (%s)"
            % (lot, payload[lot]["count"],
               payload[lot]["rows"][-1][0], payload[lot]["rows"][-1][1]))
    return path


if __name__ == "__main__":
    ensure_data()
    build()
    log("完成。这一个文件可以直接双击打开，也可以发给别人。")
