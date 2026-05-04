#!/bin/bash
# 启动脚本

echo "========================================"
echo "基于数字孪生的洪水智能分析与决策系统"
echo "========================================"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

echo "Python版本:"
python3 --version

# 检查依赖
echo ""
echo "安装依赖..."
pip install -r requirements.txt

# 运行导入测试
echo ""
echo "运行导入测试..."
python3 test_imports.py

if [ $? -ne 0 ]; then
    echo "导入测试失败"
    exit 1
fi

# 启动服务
echo ""
echo "启动 FastAPI 服务..."
echo "访问地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo ""

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
