# -*- coding: utf-8 -*-
"""
彩票查询 · 后端服务
本地运行:  uvicorn main:app --reload --port 8000
浏览器打开: http://localhost:8000
"""
import os, sys, time
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crawler

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")

app = FastAPI(title="彩票查询", docs_url=None, redoc_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024)
# 允许前端页面单独部署（如本地 file:// 打开、或静态托管在别处）时跨域调用接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

META_KEYS = ("name", "redMax", "blueMax", "redCount", "blueCount",
             "redLabel", "blueLabel")


def strip(obj):
    return {k: v for k, v in obj.items() if k in META_KEYS or k == "rows"}


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/ping")
def ping():
    return {"ok": True, "ts": int(time.time())}


@app.get("/api/history")
def history(lot: str = Query("ssq", pattern="^(ssq|dlt)$"),
            force: int = 0):
    """返回某彩种全部历史开奖数据（前端据此做统计与走势）"""
    try:
        data, src = crawler.get_data_safe(lot, force=bool(force))
    except Exception as e:                       # noqa
        raise HTTPException(502, "数据抓取失败：%s" % e)
    body = strip(data)
    body["source"] = src
    body["stale"] = bool(data.get("_stale"))
    body["updatedAt"] = int(data.get("_t", time.time()))
    body["count"] = len(body["rows"])
    return JSONResponse(body, headers={"Cache-Control": "public, max-age=600"})


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    # 端口：Serverless（阿里云 FC / 腾讯云 SCF）固定 9000；
    #       本地运行可用 PORT=8000 python main.py 覆盖
    port = int(os.environ.get("PORT") or os.environ.get("FC_SERVER_PORT") or 9000)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        # Serverless 平台用 Keep-Alive 复用连接，必须放宽 keep-alive 超时
        timeout_keep_alive=int(os.environ.get("KEEP_ALIVE", "900")),
        # 注意：不可设 limit_max_requests=0，uvicorn 会理解为「0 个请求后终止」
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
