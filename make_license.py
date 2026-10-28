# -*- coding: utf-8 -*-
"""
访问授权配置：管理员账号 + 授权码签发。

最常用的两条命令：
    python3 make_license.py --init                       # 首次开启：建管理员 + 签 5 个码
    python3 make_license.py --days 30 --count 10         # 再签 10 个 30 天的码（追加）

有效期单位（任选其一，不写默认是天）：
    --days 7        7 天
    --weeks 2       2 周
    --months 3      3 个月
    --years 1       1 年

其他：
    --expire 2027-12-31          直接指定到期日（优先于上面的单位）
    --count 20                   本次签几个（默认 1）
    --no-admin                   不改动管理员账号
    --admin-user wren            改管理员用户名
    --admin-pass xxxx            改管理员密码（不给就随机生成并打印）
    --off                        彻底关闭访问限制

产物：
    license.json       构建时内嵌进页面（只存散列，不存明文码）
    授权码名单.txt      明文码，你自己留底
    管理员账号.txt      管理员用户名/密码，务必单独保存

页面内也能签发（管理员登录后「生成授权码」），签发结果不用重新构建页面，
对方拿到码直接激活即可——码自带到期日。

边界说明（务必看清）：
    这是纯前端校验。能做到「没码进不去、到期自动失效、签发入口有密码」，
    做不到「别人不能自己造码」：验证用的密钥和算法都在 HTML 里，
    懂技术的人扒开源码就能绕过。要真正不可伪造必须上后端做非对称签名。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lic_hash import licH          # noqa: E402
from lic_code import make_code, add_days   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LIC_JSON = os.path.join(HERE, "license.json")
NAMES_TXT = os.path.join(HERE, "授权码名单.txt")
ADMIN_TXT = os.path.join(HERE, "管理员账号.txt")

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_salt():
    import random
    return "".join(random.choice(ALPHABET) for _ in range(16))


def load():
    if os.path.exists(LIC_JSON):
        try:
            return json.load(open(LIC_JSON, encoding="utf-8"))
        except Exception:      # noqa
            pass
    return {}


def save(cfg):
    json.dump(cfg, open(LIC_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="首次开启：建管理员 + 签 5 个码")
    ap.add_argument("--days", type=int)
    ap.add_argument("--weeks", type=int)
    ap.add_argument("--months", type=int)
    ap.add_argument("--years", type=int)
    ap.add_argument("--expire", default="", help="到期日 YYYY-MM-DD")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--no-admin", action="store_true")
    ap.add_argument("--admin-user", default="")
    ap.add_argument("--admin-pass", default="")
    ap.add_argument("--off", action="store_true")
    ap.add_argument("--init-registry", action="store_true",
                    help="创建云端登记表（一码一机），需本机联网")
    ap.add_argument("--provider", default="jsonblob",
                    choices=["jsonblob", "pantry"], help="登记表服务商")
    ap.add_argument("--reg-url", default="", help="直接指定登记表地址（GET 读 / PUT 写）")
    ap.add_argument("--reg-off", action="store_true", help="停用云端登记，退回纯本机绑定")
    ap.add_argument("--dev", default="", help="设备码（4 位）：生成只认该设备的绑定码")
    a = ap.parse_args()

    # ---- 云端登记表 ----
    if a.init_registry:
        import lic_reg
        try:
            url, _ = lic_reg.create(a.provider)
        except Exception as e:      # noqa
            print("创建失败：%s" % e)
            print("可能是被网络拦截。可手动创建后改用 --reg-url 填入地址。")
            return
        cfg = load()
        cfg["regUrl"] = url
        save(cfg)
        print("登记表已创建：%s" % url)
        print("已写入 license.json，请重新构建页面（python3 build_single.py --no-refresh）")
        return
    if a.reg_url:
        cfg = load()
        cfg["regUrl"] = a.reg_url
        save(cfg)
        print("已设置登记表：%s" % a.reg_url)
        print("请重新构建页面（python3 build_single.py --no-refresh）")
        return
    if a.reg_off:
        cfg = load()
        cfg.pop("regUrl", None)
        save(cfg)
        print("已停用云端登记：退回「仅本机绑定」，同一码可在多台设备各激活一次。")
        return

    if a.off:
        if os.path.exists(LIC_JSON):
            os.remove(LIC_JSON)
        print("已关闭访问授权：license.json 已删除，重新构建后页面无需授权码。")
        return

    cfg = load()
    if a.init:
        a.count = max(a.count, 5)
        if not (a.days or a.weeks or a.months or a.years):
            a.days = 30

    # ---- 管理员 ----
    admin = cfg.get("admin") or {}
    if not a.no_admin and (a.init or not admin or a.admin_user or a.admin_pass):
        import random
        user = a.admin_user or admin.get("user") or "admin"
        pwd = a.admin_pass or "".join(random.choice(ALPHABET) for _ in range(10))
        admin = {"user": user, "hash": licH("LCADMIN|" + user + "|" + pwd)}
        cfg["admin"] = admin
        with open(ADMIN_TXT, "w", encoding="utf-8") as f:
            f.write("彩票统计页面 · 管理员账号\n")
            f.write("-" * 40 + "\n")
            f.write("用户名：%s\n" % user)
            f.write("密　码：%s\n" % pwd)
            f.write("-" * 40 + "\n")
            f.write("用它在页面菜单 →「管理员」里登录，登录后可生成授权码。\n")
            f.write("这个文件只在本地，不要上传到公开仓库。\n")
        print("管理员账号：%s / %s（已写入 管理员账号.txt）" % (user, pwd))
    elif admin:
        cfg["admin"] = admin

    # ---- 自校验码密钥 ----
    if not cfg.get("sigSalt"):
        cfg["sigSalt"] = new_salt()
    if not cfg.get("salt"):
        cfg["salt"] = new_salt()

    # ---- 签发 ----
    expire = a.expire
    if not expire:
        for k, u in (("days", "day"), ("weeks", "week"),
                     ("months", "month"), ("years", "year")):
            v = getattr(a, k)
            if v:
                expire = add_days(v, u).isoformat()
                break
    if not expire:
        if cfg.get("expire"):
            expire = cfg["expire"]
        else:
            expire = add_days(30, "day").isoformat()
    cfg["expire"] = expire

    n = max(1, a.count) if (a.init or a.expire or a.days or a.weeks
                            or a.months or a.years) else 0
    plain = []
    for _ in range(n):
        plain.append(make_code(cfg["sigSalt"], expire, a.dev))
    print("已签发 %d 个%s，到期日 %s" % (len(plain),
          ("设备绑定码（只认设备 " + a.dev + "）") if a.dev else "授权码", expire))

    json.dump(cfg, open(LIC_JSON, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    old = []
    if os.path.exists(NAMES_TXT):
        import re
        for line in open(NAMES_TXT, encoding="utf-8"):
            m = re.match(r"^\s*\d+\.\s*([0-9A-Z]{4}-[0-9A-Z]{4}-[0-9A-Z]{4})\s*$",
                         line.rstrip())
            if m:
                old.append(m.group(1))
    with open(NAMES_TXT, "w", encoding="utf-8") as f:
        f.write("彩票统计页面 · 授权码名单\n")
        f.write("本次到期日：%s\n" % expire)
        f.write("-" * 46 + "\n")
        for i, c in enumerate(old + plain, 1):
            f.write("%2d. %s\n" % (i, c))
        f.write("-" * 46 + "\n")
        f.write("更多授权码不必重跑本脚本：页面菜单 → 管理员 → 生成授权码。\n")
        f.write("关闭授权：python3 make_license.py --off\n")
    if plain:
        for c in plain:
            print("   " + c)


if __name__ == "__main__":
    main()
