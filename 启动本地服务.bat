@echo off
chcp 936 >nul
cd /d "%~dp0"
title 彩票统计 - 本地服务

echo ============================================
echo   彩票统计 - 本地启动
echo ============================================
echo.
echo [提示] 首次启动需要联网抓取开奖数据，
echo        页面第一次打开约需 1-3 分钟，之后会缓存到本机。
echo        想先抓数据，可先运行 "刷新数据.bat"
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有检测到 Python
  echo 请先安装 Python 3.8 以上版本: https://www.python.org/downloads/
  echo 安装时务必勾选 "Add Python to PATH"
  echo.
  pause
  exit /b 1
)

python -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo 首次运行，正在安装依赖 fastapi / uvicorn ...
  echo 使用清华镜像加速，请稍候
  echo.
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  if errorlevel 1 (
    echo.
    echo 镜像安装失败，改用官方源重试...
    pip install -r requirements.txt
  )
  echo.
)

set PORT=8000
echo --------------------------------------------
echo 服务已启动，浏览器请打开:
echo.
echo     http://localhost:8000
echo.
echo 关闭本窗口即可停止服务
echo --------------------------------------------
echo.
python main.py

echo.
echo 服务已停止
pause
