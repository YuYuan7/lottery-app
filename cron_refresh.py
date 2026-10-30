# -*- coding: utf-8 -*-
"""
cron 刷新脚本：抓取最新开奖数据 → 生成静态产物 + 单文件 HTML

核心设计：轮询等数据（poll）
----------------------------------------------------------------
为什么不"掐点"抓？因为有两个延迟源，任何一个都会让掐点落空：

  1. GitHub Actions 的 schedule 只是"排队时间"，官方明确说明
     高负载期（尤其整点）会延迟 5~30 分钟，极端时 job 会被直接丢弃。
  2. 更关键：官方接口本身也不是开奖瞬间就有数据，通常要晚几分钟。

所以正确的做法不是"掐准某一秒"，而是：
     job 什么时候启动都行，启动后一直轮询官方接口，
     直到「最新期号」真的变了为止。

这样 cron 早到就多等一会儿，晚到也无所谓，两种情况都能拿到新数据。

特性：
  * 内容哈希比对：数据真的变了才写文件，避免 CI 空提交
  * 开奖日识别：非开奖日不做无谓轮询
  * 同时产出静态站 + 单文件版

用法：
    python3 cron_refresh.py                    # 抓一次
    python3 cron_refresh.py --poll-minutes 12  # 开奖后轮询最多 12 分钟
"""
import os
import sys
import json
import time
import argparse
import hashlib
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

STATIC = os.path.join(BASE, "dist", "static_site")
SINGLE = os.path.join(BASE, "dist", "单文件版")
META_KEYS = ("name", "redMax", "blueMax", "redCount", "blueCount",
             "redLabel", "blueLabel", "source",
             # 福彩3D / 排列三：按位玩法标记与位名，缺了前端会按双色球渲染
             "positional", "posLabels", "minNum",
             # 奖池 / 销量 / 浮动奖实际奖金 / 福运奖
             "pool")

# 开奖日（Python weekday: 周一=0 ... 周日=6），已用历史数据反推验证
DRAW_DAYS = {
    "ssq": {1, 3, 6},   # 周二、周四、周日
    "dlt": {0, 2, 5},   # 周一、周三、周六
    "3d": {0, 1, 2, 3, 4, 5, 6},   # 福彩3D 每天开奖
    "pls": {0, 1, 2, 3, 4, 5, 6},  # 排列三 每天开奖
}
# 开奖时刻（北京时间），用于判断现在是否已过开奖时间
LOTS = ("ssq", "dlt", "3d", "pls")
DRAW_HOUR = {"ssq": 21, "dlt": 20, "3d": 21, "pls": 21}
DRAW_MIN = {"ssq": 15, "dlt": 30, "3d": 15, "pls": 25}


def log(m):
    print("[cron] " + m, flush=True)


def sig(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def strip(o):
    return {k: v for k, v in o.items() if k in META_KEYS or k == "rows"}


def beijing_now():
    """当前北京时间（CI 环境通常是 UTC，统一换算到 UTC+8）"""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def baseline_issue(lot):
    """仓库里已存的最新期号，作为"是否出新期"的基准"""
    p = os.path.join(STATIC, "data", lot + ".json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)["rows"][-1][0]
    except Exception:
        return None


def probe_latest(lot, crawler):
    """快速探测官方接口的最新期号（比全量抓取轻）"""
    try:
        if lot == "ssq":
            d = crawler.fetch_ssq()
        elif lot == "3d":
            d = crawler.fetch_3d()
        elif lot == "pls":
            d = crawler.fetch_pls(max_pages=3)
        else:
            # 体彩全量要数秒，探测时只取最近 1 页
            d = crawler.fetch_dlt_recent(pages=1)
        return (d["rows"][-1][0] if d.get("rows") else None), d
    except Exception as e:
        log("  探测 %s 失败: %s" % (lot, e))
        return None, None


def is_draw_day(lot, now=None):
    now = now or beijing_now()
    return now.weekday() in DRAW_DAYS[lot]


def past_draw_time(lot, now=None):
    now = now or beijing_now()
    return (now.hour, now.minute) >= (DRAW_HOUR[lot], DRAW_MIN[lot])


def should_poll(lot, now=None):
    """只有"今天是开奖日 且 已过开奖时刻"才值得轮询"""
    return is_draw_day(lot, now) and past_draw_time(lot, now)


def fetch_one(lot, crawler, poll_minutes=0, interval=90):
    """抓取单个彩种；如需轮询，则一直等到期号变化为止"""
    base = baseline_issue(lot)
    now = beijing_now()
    log("%s: 本地最新期号 %s，北京时间 %s" %
        (lot, base, now.strftime("%m-%d %H:%M")))

    want_poll = poll_minutes > 0 and should_poll(lot, now)
    if poll_minutes > 0 and not want_poll:
        log("%s: 非开奖窗口，跳过轮询（今天是%s，开奖%s:%s）" %
            (lot, "周" + "一二三四五六日"[now.weekday()],
             DRAW_HOUR[lot], DRAW_MIN[lot]))

    deadline = time.time() + poll_minutes * 60
    attempt = 0
    while True:
        attempt += 1
        latest, _ = probe_latest(lot, crawler)
        got_new = latest is not None and latest != base
        if got_new:
            log("%s: 官方已出新期 %s（本地 %s）" % (lot, latest, base))
            break
        if not want_poll or time.time() >= deadline:
            if latest:
                log("%s: 官方最新仍为 %s，与本地一致，无新数据" % (lot, latest))
            break
        log("%s: 第 %d 次探测，官方仍为 %s，%.0f 秒后重试…" %
            (lot, attempt, latest, interval))
        time.sleep(interval)

    # 完整抓取（保证历史全量而非只有最近一页）
    try:
        data, src = crawler.get_data_safe(lot, force=True)
    except Exception as e:
        log("%s 完整抓取失败: %s" % (lot, e))
        return None

    body = strip(data)
    # 期号倒退保护：抓到的比仓库里还旧，说明接口异常或解析出错，
    # 绝不能拿它覆盖好数据。
    if base and body["rows"] and \
            (len(body["rows"][-1][0]), body["rows"][-1][0]) < (len(base), base):
        log("%s: ⚠ 抓到的最新期号 %s 比仓库已有 %s 还旧，判定异常，放弃本次更新"
            % (lot, body["rows"][-1][0], base))
        return None
    body["source"] = src
    body["count"] = len(body["rows"])
    body["updatedAt"] = int(time.time())
    body["buildDate"] = datetime.datetime.utcfromtimestamp(
        time.time() + 8 * 3600).strftime("%Y-%m-%d %H:%M")
    if not body["rows"]:
        log("%s 返回空数据，跳过" % lot)
        return None
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll-minutes", type=int, default=0,
                    help="开奖后最多轮询多少分钟等官方出数据（0=不轮询）")
    ap.add_argument("--interval", type=int, default=90,
                    help="轮询间隔秒数")
    args = ap.parse_args()

    os.makedirs(os.path.join(STATIC, "data"), exist_ok=True)
    os.makedirs(SINGLE, exist_ok=True)

    before = {
        "ssq": sig(os.path.join(STATIC, "data", "ssq.json")),
        "dlt": sig(os.path.join(STATIC, "data", "dlt.json")),
        "3d": sig(os.path.join(STATIC, "data", "3d.json")),
        "pls": sig(os.path.join(STATIC, "data", "pls.json")),
        "single": sig(os.path.join(SINGLE, "彩票统计.html")),
    }

    import crawler
    ok = 0
    for lot in LOTS:
        body = fetch_one(lot, crawler, args.poll_minutes, args.interval)
        if not body:
            continue
        with open(os.path.join(STATIC, "data", lot + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, separators=(",", ":"))
        ok += 1
        log("%s: %d 期，最新 %s (%s)" % (lot, body["count"],
                                      body["rows"][-1][0], body["rows"][-1][1]))

    if ok == 0:
        log("两个彩种都抓取失败，不覆盖已有文件")
        print("CHANGED=no")
        return 1

    import build_single
    build_single.build()

    after = {
        "ssq": sig(os.path.join(STATIC, "data", "ssq.json")),
        "dlt": sig(os.path.join(STATIC, "data", "dlt.json")),
        "3d": sig(os.path.join(STATIC, "data", "3d.json")),
        "pls": sig(os.path.join(STATIC, "data", "pls.json")),
        "single": sig(os.path.join(SINGLE, "彩票统计.html")),
    }
    changed = before != after
    log("数据变化: %s" % ("是" if changed else "否"))
    print("CHANGED=" + ("yes" if changed else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
