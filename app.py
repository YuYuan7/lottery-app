# -*- coding: utf-8 -*-
"""
Vercel Python 入口（框架预设）
官方要求：入口文件必须在顶层定义 app / application / handler 变量
见 https://vercel.com/docs/functions/runtimes/python#python-entrypoints
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app as _fastapi_app   # noqa: E402

# 顶层显式赋值，确保 Vercel 能静态识别到 app
app = _fastapi_app

__all__ = ["app"]
