@echo off
rem Windows 一键启动脚本：双击本文件即可启动 Jev Studio
cd /d "%~dp0"

rem 依次尝试 python / py（Windows 上 Python 3 的命令名不统一）
where python >nul 2>nul
if %errorlevel% equ 0 (
  python server.py
  pause
  exit /b 0
)

where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 server.py
  pause
  exit /b 0
)

echo.
echo   未检测到 Python 3。
echo   请先安装 Python 3（安装时请勾选 "Add Python to PATH"）: https://www.python.org/downloads/
echo.
pause
exit /b 1
