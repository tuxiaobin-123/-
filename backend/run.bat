@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo 基于数字孪生的洪水智能分析与决策系统
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python
    pause
    exit /b 1
)

echo Python版本:
python --version

REM 安装依赖
echo.
echo 安装依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo 依赖安装失败
    pause
    exit /b 1
)

REM 运行导入测试
echo.
echo 运行导入测试...
python test_imports.py
if errorlevel 1 (
    echo 导入测试失败
    pause
    exit /b 1
)

REM 启动服务
echo.
echo 启动 FastAPI 服务...
echo 访问地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
