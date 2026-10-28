@echo off
chcp 936 >nul
cd /d "%~dp0"
title 彩票统计 - 刷新数据

echo ============================================
echo   重新抓取最新开奖数据并生成单文件版
echo ============================================
echo.
echo 四种玩法全部重抓，约需 1-3 分钟，请稍候...
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 没有检测到 Python
  pause
  exit /b 1
)

python build_single.py --refresh
if errorlevel 1 (
  echo.
  echo [失败] 抓取出错，请检查网络后重试
  pause
  exit /b 1
)

echo.
echo --------------------------------------------
echo 完成！生成的文件在:
echo     dist\单文件版\彩票统计.html
echo.
echo 双击该文件即可查看，也可直接发给别人
echo --------------------------------------------
echo.
pause
