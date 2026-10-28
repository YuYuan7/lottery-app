@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ============================================================
echo   创建云端登记表（让一个授权码只能在一台设备激活）
echo ============================================================
echo.
echo   说明：默认方案「设备绑定码」完全离线、不需要本步骤。
echo   本脚本是可选增强：启用后，普通授权码也能自动做到一码一机，
echo   但首次激活需要联网访问第三方存储服务（国内可能不稳定）。
echo.
echo   服务商： 1 = jsonblob.com   2 = getpantry.cloud
set /p P=请选择（1 或 2，直接回车用 1）: 
if "%P%"=="2" (set PROV=pantry) else (set PROV=jsonblob)

python make_license.py --init-registry --provider %PROV%
if errorlevel 1 goto fail

echo.
echo 正在重新生成单文件页面 ...
python build_single.py --no-refresh
if errorlevel 1 goto fail

echo.
echo ============================================================
echo   完成！登记表地址已写入 license.json 并重新生成页面。
echo   把 dist\单文件版\彩票统计.html 重新上传到 GitHub 即可。
echo.
echo   停用：python make_license.py --reg-off
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
echo 创建失败。常见原因：网络访问不了该服务。
echo 可以换个服务商再试；或者直接用「设备绑定码」（离线，不需要登记表）。
echo.
pause
exit /b 1
