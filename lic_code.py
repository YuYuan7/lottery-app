# -*- coding: utf-8 -*-
"""自校验授权码：码里自带到期日，页面无需重新构建即可签发与验证。

码结构（12 字符，显示为 XXXX-XXXX-XXXX）：
    payload(4)  = 到期日距 EPOCH 的天数，Crockford Base32
    rand(4)     = 随机串
    sig(4)      = licH(salt|payload|rand) 前 20 bit，Base32

三组字符交错排列（下标 i%3 → 0:payload 1:rand 2:sig），
让整串看起来是随机码，但实际可反解校验。

重要边界（务必看清）：
    验证用的 salt 明文内嵌在页面里，所以这个机制只能做到
    「拿到码才能进、到期自动失效、签发入口有密码」，
    做不到「别人不能自己造码」——算法和 salt 都在 HTML 里。
    要真正做到不可伪造，必须用非对称签名（私钥留在签发端），
    那需要后端或额外的密码学依赖，本项目刻意保持零依赖。
"""
import datetime
import random

from lic_hash import licH

# Crockford Base32：去掉 I / L / O / U，避免手抄看错
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
IDX = {c: i for i, c in enumerate(ALPHABET)}
EPOCH = datetime.date(2020, 1, 1)


def b32enc(val, width):
    """整数 → 定长 Base32 字符串（高位在前）"""
    s = ""
    for _ in range(width):
        s = ALPHABET[val & 31] + s
        val >>= 5
    return s


def b32dec(s):
    """Base32 字符串 → 整数"""
    v = 0
    for ch in s:
        v = (v << 5) | IDX.get(ch, 0)
    return v


def _sig(salt, payload, rand):
    """取散列前 5 个十六进制字符（20 bit）→ 4 个 Base32 字符"""
    h = licH(salt + "|" + payload + "|" + rand)
    return b32enc(int(h[:5], 16), 4)


def _interleave(payload, rand, sig):
    out = [""] * 12
    for i in range(12):
        j = i // 3
        out[i] = payload[j] if i % 3 == 0 else (rand[j] if i % 3 == 1 else sig[j])
    return "".join(out)


def _deinterleave(code):
    p = code[0] + code[3] + code[6] + code[9]
    r = code[1] + code[4] + code[7] + code[10]
    s = code[2] + code[5] + code[8] + code[11]
    return p, r, s


def _rand4():
    return "".join(random.choice(ALPHABET) for _ in range(4))


def norm(code):
    """归一：去横线、转大写、纠正常见抄写错误"""
    if not code:
        return ""
    s = str(code).upper().replace("-", "").replace(" ", "")
    s = s.replace("O", "0").replace("I", "1").replace("L", "1")
    return "".join(c for c in s if c in IDX)


def fmt(code):
    return "-".join(code[i:i + 4] for i in range(0, 12, 4))


def make_code(salt, expire_date):
    """按到期日签一个码。expire_date: datetime.date 或 'YYYY-MM-DD'"""
    if isinstance(expire_date, str):
        expire_date = datetime.date(*[int(x) for x in expire_date.split("-")])
    payload = b32enc((expire_date - EPOCH).days, 4)
    rand = _rand4()
    sig = _sig(salt, payload, rand)
    return fmt(_interleave(payload, rand, sig))


def parse_code(salt, code):
    """校验并取回到期日。返回 (ok, expire_str, reason)"""
    c = norm(code)
    if len(c) != 12:
        return False, "", "格式不对"
    p, r, s = _deinterleave(c)
    if _sig(salt, p, r) != s:
        return False, "", "校验不通过"
    d = EPOCH + datetime.timedelta(days=b32dec(p))
    return True, d.isoformat(), ""


def add_days(n, unit):
    """把 (数量, 单位) 换算成天数的增量。
    月/年按日历推进（1 月 31 日 + 1 月 = 2 月 28/29 日），不是固定 30/365 天。"""
    n = int(n)
    u = {"day": "day", "week": "week", "month": "month", "year": "year"}.get(unit, "day")
    today = datetime.date.today()
    if u == "day":
        return today + datetime.timedelta(days=n)
    if u == "week":
        return today + datetime.timedelta(weeks=n)
    if u == "month":
        y, m = today.year, today.month + n
        y += (m - 1) // 12
        m = (m - 1) % 12 + 1
        d = min(today.day, [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
                            else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
        return datetime.date(y, m, d)
    y, m = today.year + n, today.month
    d = min(today.day, [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
                        else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return datetime.date(y, m, d)
