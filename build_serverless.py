# -*- coding: utf-8 -*-
"""
打包 Serverless 部署包
用法:
    python3 build_serverless.py aliyun   # 生成 dist/aliyun-fc.zip
    python3 build_serverless.py tencent  # 生成 dist/tencent-scf.zip
    python3 build_serverless.py          # 两个都生成

包内包含: 应用代码 + 依赖(third_party/) + 启动脚本
"""
import os
import sys
import shutil
import subprocess
import zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(BASE, "dist")
VENDOR = os.path.join(BASE, "third_party")

APP_FILES = ["main.py", "crawler.py", "requirements.txt"]
STATIC_DIR = os.path.join(BASE, "static")

EXCLUDE = ("__pycache__", ".git", "dist", "third_party", ".DS_Store",
           "vercel.json", "Dockerfile", "Procfile", "railway.json",
           "render.yaml", ".python-version", "runtime.txt", ".dockerignore")


def log(m):
    print("[build] " + m)


def build_vendor():
    """把依赖装到 third_party/（Serverless 平台不会自动装）"""
    if os.path.exists(VENDOR):
        shutil.rmtree(VENDOR)
    os.makedirs(VENDOR, exist_ok=True)
    log("安装依赖到 third_party/ ...")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r",
         os.path.join(BASE, "requirements.txt"), "-t", VENDOR,
         "--quiet", "--upgrade"],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-2000:])
        sys.exit("依赖安装失败")
    # 清理体积
    for d in os.listdir(VENDOR):
        if d.endswith(".dist-info") or d in ("bin", "__pycache__"):
            p = os.path.join(VENDOR, d)
            shutil.rmtree(p, ignore_errors=True)
    size = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, fs in os.walk(VENDOR) for f in fs) / 1024 / 1024
    log("依赖打包完成: %.1f MB" % size)


def make_zip(target, boot_src, boot_name):
    os.makedirs(DIST, exist_ok=True)
    zp = os.path.join(DIST, target)
    if os.path.exists(zp):
        os.remove(zp)
    if not os.path.exists(os.path.join(VENDOR, "fastapi", "__init__.py")):
        build_vendor()
    n = 0
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in APP_FILES:
            p = os.path.join(BASE, f)
            if os.path.exists(p):
                z.write(p, f); n += 1
        # 静态文件
        for dp, dns, fs in os.walk(STATIC_DIR):
            dns[:] = [d for d in dns if d not in EXCLUDE]
            for f in fs:
                if f in EXCLUDE:
                    continue
                full = os.path.join(dp, f)
                z.write(full, os.path.relpath(full, BASE)); n += 1
        # 依赖
        for dp, dns, fs in os.walk(VENDOR):
            dns[:] = [d for d in dns if d != "__pycache__"]
            for f in fs:
                if f.endswith(".pyc"):
                    continue
                full = os.path.join(dp, f)
                z.write(full, os.path.relpath(full, BASE)); n += 1
        # 启动脚本（放在包根目录，强制保留 755 可执行权限）
        for src_name, arc_name in ((boot_src, boot_name), ("start.sh", "start.sh")):
            src = os.path.join(BASE, src_name)
            if not os.path.exists(src):
                continue
            info = zipfile.ZipInfo(arc_name)
            info.external_attr = 0o755 << 16
            with open(src, "rb") as fh:
                z.writestr(info, fh.read())
            n += 1
    log("%s 打包完成: %d 个文件, %.1f MB" %
        (target, n, os.path.getsize(zp) / 1024 / 1024))
    return zp


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("aliyun", "all"):
        make_zip("aliyun-fc.zip", "bootstrap", "bootstrap")
    if which in ("tencent", "all"):
        make_zip("tencent-scf.zip", "scf_bootstrap", "scf_bootstrap")
    log("输出目录: " + DIST)


if __name__ == "__main__":
    main()
