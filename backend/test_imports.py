# -*- coding: utf-8 -*-
"""
导入测试脚本 - 验证所有模块都可以正确导入
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("导入测试 - 基于数字孪生的洪水智能分析系统")
print("=" * 60)

try:
    print("\n[1/6] 导入配置模块...")
    from config import (
        APP_TITLE,
        APP_VERSION,
        GRID_ROWS,
        GRID_COLS,
        BASE_LAT,
        BASE_LNG,
    )
    print(f"  ✓ {APP_TITLE} v{APP_VERSION}")
    print(f"  ✓ 网格: {GRID_ROWS}x{GRID_COLS}, 基准点: ({BASE_LAT}, {BASE_LNG})")

except Exception as e:
    print(f"  ✗ 失败: {e}")
    sys.exit(1)

try:
    print("\n[2/6] 导入水动力模型...")
    from models.hydraulic import SWEModel
    model = SWEModel(rows=30, cols=40, dx=0.003, dy=0.003)
    print(f"  ✓ SWEModel 初始化成功")
    print(f"  ✓ DEM范围: {model.dem.min():.2f} - {model.dem.max():.2f} m")
    print(f"  ✓ 初始水深范围: {model.h.min():.2f} - {model.h.max():.2f} m")

except Exception as e:
    print(f"  ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[3/6] 导入LSTM预测模型...")
    from models.lstm_predict import LSTMPredictor
    import numpy as np
    predictor = LSTMPredictor(input_size=3, hidden_size=32, output_size=24)
    history = np.random.randn(24)
    rainfall = np.random.randn(24)
    predictions = predictor.predict(history, rainfall)
    result = predictor.get_prediction_with_confidence(history, rainfall)
    print(f"  ✓ LSTMPredictor 初始化成功")
    print(f"  ✓ 预测序列长度: {len(predictions)}")
    print(f"  ✓ 预测范围: {result['min_prediction']:.2f} - {result['max_prediction']:.2f} m")
    print(f"  ✓ 风险趋势: {result['risk_trend']}")

except Exception as e:
    print(f"  ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[4/6] 导入风险评估模块...")
    from models.risk_assessment import RiskAssessor, EvacuationRouter
    from config import KEY_POINTS
    assessor = RiskAssessor()
    router = EvacuationRouter(KEY_POINTS)
    print(f"  ✓ RiskAssessor 初始化成功")
    print(f"  ✓ EvacuationRouter 初始化成功")
    print(f"  ✓ 关键点数量: {len(KEY_POINTS)}")

except Exception as e:
    print(f"  ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[5/6] 导入API路由...")
    from routers import flood, sensors, predict, risk
    print(f"  ✓ flood 路由导入成功")
    print(f"  ✓ sensors 路由导入成功")
    print(f"  ✓ predict 路由导入成功")
    print(f"  ✓ risk 路由导入成功")

except Exception as e:
    print(f"  ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[6/6] 导入FastAPI主应用...")
    from main import app
    print(f"  ✓ FastAPI 应用导入成功")
    print(f"  ✓ 注册路由数: {len(app.routes)}")

except Exception as e:
    print(f"  ✗ 失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("所有模块导入测试 ✓ 通过")
print("=" * 60)

print("\n启动建议:")
print("  1. 安装依赖: pip install -r requirements.txt")
print("  2. 启动服务: python main.py")
print("  3. 访问文档: http://localhost:8000/docs")
print("  4. WebSocket: ws://localhost:8000/ws")

print("\nAPI 端点:")
print("  - 洪水模拟: /api/flood")
print("  - 传感器数据: /api/sensors")
print("  - 预测: /api/predict")
print("  - 风险评估: /api/risk")
print("=" * 60 + "\n")
