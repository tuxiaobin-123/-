@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "LOGDIR=%ROOT%runtime-logs"
set "PACKAGE=%ROOT%..\flood-twin-system-claude-source.zip"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

:menu
cls
echo ============================================
echo   大坝洪水数字孪生系统 - 一键工具
echo ============================================
echo.
echo   1. 启动系统（后端 + 前端）
echo   2. 打开主大屏
echo   3. 打开案例数据全屏页
echo   4. 打包源码给 Claude
echo   5. 停止本项目服务
echo   0. 退出
echo.
set /p CHOICE=请选择操作：

if "%CHOICE%"=="1" goto start_system
if "%CHOICE%"=="2" goto open_main
if "%CHOICE%"=="3" goto open_case
if "%CHOICE%"=="4" goto package_claude
if "%CHOICE%"=="5" goto stop_services
if "%CHOICE%"=="0" exit /b 0
goto menu

:start_system
cls
echo [检查] Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 Python。请先安装 Python 3.10+。
  pause
  goto menu
)

echo [检查] Node.js...
node --version >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 Node.js。请先安装 Node.js 18+。
  pause
  goto menu
)

echo [启动] 后端 http://localhost:8000
start "flood-backend" cmd /k "cd /d "%BACKEND%" && pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q && python main.py"

echo [等待] 后端启动中...
timeout /t 5 /nobreak >nul

echo [启动] 前端 http://localhost:5173
start "flood-frontend" cmd /k "cd /d "%FRONTEND%" && if not exist node_modules npm install --registry https://registry.npmmirror.com && npm run dev -- --host 127.0.0.1"

echo.
echo 系统正在启动。若页面暂时打不开，请等待 10-20 秒后刷新。
echo 主大屏:   http://localhost:5173
echo 案例页:   http://localhost:5173/case-data
echo 后端文档: http://localhost:8000/docs
timeout /t 8 /nobreak >nul
start "" "http://localhost:5173"
pause
goto menu

:open_main
start "" "http://localhost:5173"
goto menu

:open_case
start "" "http://localhost:5173/case-data"
goto menu

:package_claude
cls
echo [打包] 正在生成 Claude 源码包...
where git >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$root=(Resolve-Path '%ROOT%').Path; $out=(Resolve-Path '%ROOT%\..').Path + '\flood-twin-system-claude-source.zip'; if(Test-Path $out){Remove-Item $out -Force}; Compress-Archive -Path (Join-Path $root '*') -DestinationPath $out -Force"
) else (
  cd /d "%ROOT%"
  git archive --format=zip --output="%PACKAGE%" HEAD
)
echo.
echo 已生成:
echo %PACKAGE%
pause
goto menu

:stop_services
cls
echo [停止] 正在关闭占用 5173 和 8000 端口的进程...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports=5173,8000; Get-NetTCPConnection -LocalPort $ports -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
echo 完成。
pause
goto menu
