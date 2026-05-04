@echo off
chcp 65001 >nul
title 洪水智能分析系统 - 启动器
color 0A

echo ============================================
echo   基于数字孪生的洪水智能分析与决策系统
echo   互联网+参赛项目 · 一键启动
echo ============================================
echo.

:: 检查目录
if not exist "%~dp0backend\main.py" (
    echo [错误] 找不到后端文件，请确认脚本在项目根目录
    pause
    exit /b 1
)

if not exist "%~dp0frontend\package.json" (
    echo [错误] 找不到前端文件，请确认脚本在项目根目录
    pause
    exit /b 1
)

echo [1/3] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo       OK

echo [2/3] 检查 Node.js 环境...
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 20+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)
echo       OK

echo [3/3] 启动服务中...
echo.

:: 启动后端（新窗口）
echo >>> 启动后端服务 (http://localhost:8000) ...
start "洪水系统-后端" cmd /k "cd /d %~dp0backend && echo 正在安装Python依赖... && pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q && echo. && echo [后端已启动] API文档: http://localhost:8000/docs && echo. && python main.py"

:: 等待后端先启动
echo     等待后端启动 (5秒)...
timeout /t 5 /nobreak >nul

:: 启动前端（新窗口）
echo >>> 启动前端服务 (http://localhost:5173) ...
start "洪水系统-前端" cmd /k "cd /d %~dp0frontend && echo 正在安装前端依赖（首次约1-3分钟）... && npm install --registry https://registry.npmmirror.com && echo. && echo [前端已启动] 请打开: http://localhost:5173 && echo. && npm run dev"

echo.
echo ============================================
echo   两个窗口已打开，请稍候...
echo   后端: http://localhost:8000/docs
echo   前端: http://localhost:5173  (主界面)
echo ============================================
echo.
echo   等待服务启动完成后，浏览器访问:
echo   http://localhost:5173
echo.

:: 等待前端启动后自动打开浏览器
echo 15秒后自动打开浏览器...
timeout /t 15 /nobreak >nul

start "" "http://localhost:5173"

echo 浏览器已打开！如果页面空白请等待10秒后刷新。
pause
