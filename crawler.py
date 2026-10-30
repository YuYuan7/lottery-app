# -*- coding: utf-8 -*-
"""
数据抓取：双色球（中国福彩网官方接口）+ 大乐透（中国体彩官方接口）
- 多 User-Agent 轮换 + 重试，应对体彩 WAF 概率性 403
- 内存 + 磁盘双级缓存，避免每次请求都打官方接口
"""
import json, os, time, random, urllib.request, urllib.error, tempfile

UA = [
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
]

CACHE_DIR = os.environ.get("LOTTERY_CACHE_DIR") or os.path.join(tempfile.gettempdir(), "lottery_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 缓存有效期（秒）：开奖日之外数据不会变，给 6 小时足够
TTL = int(os.environ.get("LOTTERY_TTL", "21600"))

# 并发页数：太高会触发体彩 WAF，6~8 较稳
MAX_WORKERS = int(os.environ.get("LOTTERY_WORKERS", "10"))

# 增量更新时抓取的页数（每页 100 期）
INCREMENT_PAGES = int(os.environ.get("LOTTERY_INC_PAGES", "3"))

_mem = {}


def _http(url, headers, timeout=25):
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout).read()


def _retry(fn, tries=8, base=0.25):
    """概率性 403 的重试封装"""
    last = None
    for i in range(tries):
        try:
            r = fn()
            if r is not None:
                return r
        except Exception as e:          # noqa
            last = e
        time.sleep(base + 0.15 * i + random.random() * 0.2)
    raise RuntimeError("抓取失败（已重试 %d 次）: %s" % (tries, last))


def _num(v):
    """把 '1,056,837,777' / 1056837777 / '' 统一转成 int，失败返回 None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).replace(",", "").replace("，", "").strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:          # noqa
        return None


def _ssq_pool(d):
    """双色球：取最新一期的奖池金额 + 一/二等奖实际奖金"""
    res = d.get("result") or []
    if not res:
        return None
    it = res[0]
    pool = _num(it.get("poolmoney"))
    if not pool:
        return None
    top = {}
    for g in (it.get("prizegrades") or []):
        m = _num(g.get("typemoney"))
        if not m:
            continue
        t = str(g.get("type"))
        if t == "1":
            top["p1"] = m
        elif t == "2":
            top["p2"] = m
    # 福运奖相关说明：优先取提到「福运」或「特别规定」的最近一条
    fyj_note = ""
    for x in d.get("result", []):
        s = (x.get("specialRuleInfo") or "").strip()
        if s and ("福运" in s or "特别规定" in s):
            fyj_note = s
            break
    return {"issue": it.get("code"), "date": (it.get("date") or "")[:10],
            "amount": pool, "sales": _num(it.get("sales")), "top": top,
            "fyj": {"count": _num(it.get("fyjCount")), "money": _num(it.get("fyjMoney"))},
            "fyjNote": fyj_note}


def _dlt_pool(lst):
    """大乐透：取最新一期的奖池金额 + 一/二等奖实际奖金"""
    if not lst:
        return None
    it = lst[0]
    pool = _num(it.get("poolBalance"))
    if not pool:
        return None
    top = {}
    for g in (it.get("prizeLevelList") or []):
        lv = str(g.get("prizeLevel") or "")
        m = _num(g.get("stakeAmount"))
        if not m:
            continue
        if "一等奖" in lv:
            top.setdefault("p1", m)
        elif "二等奖" in lv:
            top.setdefault("p2", m)
    return {"issue": it.get("lotteryDrawNum"), "date": (it.get("lotteryDrawTime") or "")[:10],
            "amount": pool, "sales": _num(it.get("totalSaleAmount")), "top": top}


def fetch_ssq():
    """双色球：福彩官方，一次可取全部历史"""
    url = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=ssq&issueCount=3000"

    def go():
        raw = _http(url, {
            "User-Agent": random.choice(UA),
            "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        return json.loads(raw.decode("utf-8", "ignore"))

    d = _retry(go, tries=6)
    rows = []
    for it in d.get("result", []):
        code = it.get("code")
        red = it.get("red", "")
        blue = it.get("blue")
        if not code or not red or not blue:
            continue
        reds = [int(x) for x in red.split(",") if x.strip()]
        if len(reds) != 6:
            continue
        rows.append([code, (it.get("date") or "")[:10], sorted(reds), [int(blue)]])
    rows.sort(key=lambda r: r[0])
    return {
        "name": "双色球", "redMax": 33, "blueMax": 16,
        "redCount": 6, "blueCount": 1,
        "redLabel": "红球", "blueLabel": "蓝球",
        "rows": rows,
        "pool": _ssq_pool(d),
    }


def _dlt_page(page, size):
    url = ("https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?"
           "gameNo=85&provinceId=0&pageSize=%d&isVerify=1&pageNo=%d" % (size, page))

    def go():
        raw = _http(url, {
            "User-Agent": random.choice(UA),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.sporttery.cn/",
            "Origin": "https://www.sporttery.cn",
        })
        d = json.loads(raw.decode("utf-8", "ignore"))
        v = d.get("value") or {}
        if v.get("list"):
            return v
        return None

    return _retry(go, tries=8)


def _parse_dlt_item(it):
    num = it.get("lotteryDrawNum")
    res = (it.get("lotteryDrawResult") or "").split()
    if not num or len(res) != 7:
        return None
    try:
        nums = [int(x) for x in res]
    except ValueError:
        return None
    front = sorted(nums[:5])
    back = sorted(nums[5:])
    if len(set(front)) != 5 or len(set(back)) != 2:
        return None
    if max(front) > 35 or max(back) > 12:
        return None
    return [num, (it.get("lotteryDrawTime") or "")[:10], front, back]


def _plan_pages(first, size, max_pages):
    """决定要抓多少页：默认不设上限，抓到官方给的全部历史为止。

    - 接口返回 total：直接按 total 算页数（不再被 max_pages 截断）
    - 接口没给 total：向后逐页探测，直到某页为空为止
    - max_pages 传了具体数字才生效（仅调试用）
    """
    if max_pages:
        return max_pages
    total = 0
    try:
        total = int(first.get("total") or 0)
    except Exception:          # noqa
        total = 0
    if total > 0:
        return (total + size - 1) // size
    return 1                   # 交给调用方做"抓到空页为止"的探测


def _scan_pages(page_fn, size, first, parse_fn, hard_cap=2000):
    """不限页数地抓取：并发铺一遍 + 缺页串行重试 + 末尾继续探测到空页。

    返回 (got, pages)，got 为 {页号: [行]}。
    """
    from concurrent.futures import ThreadPoolExecutor

    def job(p):
        try:
            v = first if p == 1 else page_fn(p, size)
            return [parse_fn(x) for x in (v.get("list") or [])]
        except Exception:      # noqa
            return []

    got = {}
    end = _plan_pages(first, size, None)
    # total 已知时页数是准的，不必再往后探测；只有接口没给 total 才继续扫
    probe = False
    try:
        probe = not int(first.get("total") or 0)
    except Exception:          # noqa
        probe = True

    def sweep(lo, hi):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for p, lst in zip(range(lo, hi + 1), ex.map(job, range(lo, hi + 1))):
                got[p] = lst

    sweep(1, end)

    # 接口没给 total 时：只要最后一批还有数据，就继续往后扫，直到空页
    more = 0
    while probe and got.get(end) and end < hard_cap and more < 40:
        lo, end = end + 1, end + 20
        sweep(lo, end)
        more += 1
        if not any(got.get(p) for p in range(lo, end + 1)):
            break

    # 补抓：并发中被 WAF 拒掉的页，串行重试 5 轮
    for _ in range(5):
        missing = [p for p in range(1, end + 1) if not got.get(p)]
        if not missing:
            break
        still = []
        for p in missing:
            lst = job(p)
            if lst:
                got[p] = lst
            else:
                still.append(p)
            time.sleep(0.2)
        got = {k: v for k, v in got.items() if v}
        for p in still:
            got.pop(p, None)
    missing = [p for p in range(1, end + 1) if not got.get(p)]
    if missing:
        print("[warn] 缺页（可能丢失部分历史）: %s" % missing)
    return got, end


def fetch_dlt(max_pages=None):
    """大乐透：体彩官方分页抓取（WAF 概率放行；并发 + 逐页重试）

    默认不限页数，抓到官方给的全部历史为止。
    """
    size = 100
    # 先探首页拿总页数
    first = _dlt_page(1, size)
    got, pages = _scan_pages(_dlt_page, size, first, _parse_dlt_item)

    seen, all_rows = set(), []
    for p in range(1, pages + 1):
        for r in (got.get(p) or []):
            if r and r[0] not in seen:
                seen.add(r[0])
                all_rows.append(r)
    all_rows.sort(key=lambda r: (len(r[0]), r[0]))
    return {
        "name": "大乐透", "redMax": 35, "blueMax": 12,
        "redCount": 5, "blueCount": 2,
        "redLabel": "前区", "blueLabel": "后区",
        "rows": all_rows,
        "pool": _dlt_pool(first.get("list") or []),
    }


def fetch_dlt_recent(pages=3):
    """只抓最近 N 页（新期号在前面），用于增量更新"""
    from concurrent.futures import ThreadPoolExecutor

    first_raw = []      # 首页原始数据，用于取奖池（_dlt_pool 需要接口原始结构）

    def job(p):
        try:
            v = _dlt_page(p, 100)
            return v
        except Exception:      # noqa
            return None

    got, raw1 = {}, {}
    with ThreadPoolExecutor(max_workers=min(pages, 4)) as ex:
        for p, v in zip(range(1, pages + 1), ex.map(job, range(1, pages + 1))):
            if p == 1 and v:
                raw1 = v
            got[p] = [_parse_dlt_item(x) for x in (v or {}).get("list", [])] \
                if v else []

    seen, rows = set(), []
    for p in range(1, pages + 1):
        for r in (got.get(p) or []):
            if r and r[0] not in seen:
                seen.add(r[0])
                rows.append(r)
    if not rows:
        raise RuntimeError("增量抓取为空")
    rows.sort(key=lambda r: (len(r[0]), r[0]))
    return {
        "name": "大乐透", "redMax": 35, "blueMax": 12,
        "redCount": 5, "blueCount": 2,
        "redLabel": "前区", "blueLabel": "后区",
        "rows": rows,
        "pool": _dlt_pool(raw1.get("list") or []),
    }



def fetch_3d():
    """福彩 3D：福彩官方接口，一次可取全部历史（约 4791 期）
    玩法特点：3 位数字、每位 0-9、可重复、有顺序（百/十/个）
    """
    url = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=3d&issueCount=8000"

    def go():
        raw = _http(url, {
            "User-Agent": random.choice(UA),
            "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/sd/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        return json.loads(raw.decode("utf-8", "ignore"))

    d = _retry(go, tries=6)
    rows = []
    for it in d.get("result", []):
        code = it.get("code")
        red = it.get("red") or ""
        if not code or not red:
            continue
        nums = [int(x) for x in str(red).split(",") if x.strip() != ""]
        if len(nums) != 3 or any(n < 0 or n > 9 for n in nums):
            continue
        rows.append([code, (it.get("date") or "")[:10], nums, []])
    rows.sort(key=lambda r: r[0])
    return _pack_positional("3d", "福彩3D", rows, _pos_pool(d))


def fetch_pls(max_pages=None):
    """体彩排列三：体彩官方分页抓取
    玩法同福彩 3D：3 位数字、每位 0-9、可重复、有顺序

    默认不限页数，抓到官方给的全部历史为止。
    """
    size = 100
    first = _pls_page(1, size)
    got, pages = _scan_pages(_pls_page, size, first, _parse_pls_item)

    seen, rows = set(), []
    for p in range(1, pages + 1):
        for r in (got.get(p) or []):
            if r and r[0] not in seen:
                seen.add(r[0])
                rows.append(r)
    rows.sort(key=lambda r: (len(r[0]), r[0]))
    pool = None
    try:
        pool = _dlt_pool(first.get("list") or [])
    except Exception:      # noqa
        pool = None
    return _pack_positional("pls", "排列三", rows, pool)


def _pls_page(page, size):
    url = ("https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry?"
           "gameNo=35&provinceId=0&pageSize=%d&isVerify=1&pageNo=%d" % (size, page))

    def go():
        raw = _http(url, {
            "User-Agent": random.choice(UA),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.sporttery.cn/",
            "Origin": "https://www.sporttery.cn",
        })
        d = json.loads(raw.decode("utf-8", "ignore"))
        v = d.get("value") or {}
        if v.get("list"):
            return v
        return None

    return _retry(go, tries=8)


def _parse_pls_item(it):
    num = it.get("lotteryDrawNum")
    res = (it.get("lotteryDrawResult") or "").split()
    if not num or len(res) != 3:
        return None
    try:
        nums = [int(x) for x in res]
    except ValueError:
        return None
    if any(n < 0 or n > 9 for n in nums):
        return None
    return [num, (it.get("lotteryDrawTime") or "")[:10], nums, []]


def _pos_pool(d):
    """福彩 3D 奖池/销量（3D 无固定奖池，取当期销售额）"""
    res = d.get("result") or []
    if not res:
        return None
    it = res[0]
    return {"issue": it.get("code"), "date": (it.get("date") or "")[:10],
            "amount": None, "sales": _num(it.get("sales")), "top": {}}


def _pack_positional(key, name, rows, pool):
    """3D / 排列三 的统一数据结构：positional=True 表示按位、可重复"""
    return {
        "name": name, "redMax": 9, "blueMax": 0,
        "redCount": 3, "blueCount": 0,
        "redLabel": "号码", "blueLabel": "",
        "positional": True,
        "posLabels": ["百位", "十位", "个位"],
        "minNum": 0,
        "rows": rows,
        "pool": pool,
    }


FETCHERS = {"ssq": fetch_ssq, "dlt": fetch_dlt, "3d": fetch_3d, "pls": fetch_pls}


def _save(lot, data):
    data["_t"] = time.time()
    _mem[lot] = (data["_t"], data)
    try:
        with open(os.path.join(CACHE_DIR, "%s.json" % lot), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    except Exception:          # noqa
        pass


def _load_disk(lot):
    fp = os.path.join(CACHE_DIR, "%s.json" % lot)
    if not os.path.exists(fp):
        return None
    try:
        with open(fp, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if obj.get("rows") else None
    except Exception:          # noqa
        return None


def _merge(old, new):
    """把新抓到的期号合并进旧数据（按最新期号去重）"""
    base = {r[0]: r for r in (old or {}).get("rows", [])}
    for r in new["rows"]:
        base[r[0]] = r
    rows = sorted(base.values(), key=lambda r: (len(r[0]), r[0]))
    new["rows"] = rows
    if not new.get("pool") and (old or {}).get("pool"):
        new["pool"] = old["pool"]
    new["_t"] = time.time()
    return new


def get_data(lot, force=False):
    """带缓存取数：内存 -> 磁盘 -> 官方接口（增量）"""
    now = time.time()

    if not force:
        hit = _mem.get(lot)
        if hit and now - hit[0] < TTL:
            return hit[1], "cache"
        disk = _load_disk(lot)
        if disk and now - disk.get("_t", 0) < TTL:
            _mem[lot] = (disk["_t"], disk)
            return disk, "disk"

    old = _load_disk(lot) if not force else None

    # 增量：已有全量缓存时，只抓最新几页（大乐透全量很慢）
    if old and len(old["rows"]) > 500 and lot == "dlt":
        try:
            head = fetch_dlt_recent(pages=INCREMENT_PAGES)
            merged = _merge(old, head)
            _save(lot, merged)
            return merged, "live"
        except Exception:      # noqa
            pass               # 增量失败则退回全量

    data = FETCHERS[lot]()
    if old and len(data["rows"]) < len(old["rows"]):
        data = _merge(old, data)
    _save(lot, data)
    return data, "live"


def get_data_safe(lot, force=False):
    """优先实时；失败则回落到过期缓存，绝不因抓取失败而整体报错"""
    try:
        return get_data(lot, force=force)
    except Exception as e:     # noqa
        fp = os.path.join(CACHE_DIR, "%s.json" % lot)
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                obj["_stale"] = True
                return obj, "stale"
            except Exception:  # noqa
                pass
        raise e


if __name__ == "__main__":
    for k in ("ssq", "dlt"):
        t = time.time()
        d, src = get_data_safe(k, force=True)
        print("%s: %d 期 [%s] %.1fs  %s ~ %s" % (
            d["name"], len(d["rows"]), src, time.time() - t,
            d["rows"][0][0], d["rows"][-1][0]))
