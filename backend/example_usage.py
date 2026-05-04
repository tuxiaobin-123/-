# -*- coding: utf-8 -*-
"""
API 使用示例
演示如何调用所有主要 API 端点
"""

import httpx
import asyncio
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def print_response(title: str, response):
    """打印格式化的响应"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(response.text)


async def main():
    """主函数"""

    async with httpx.AsyncClient() as client:

        # ==================== 系统信息 ====================
        print(f"\n【1】获取系统信息")
        resp = await client.get(f"{BASE_URL}/")
        await print_response("系统根路由", resp)

        resp = await client.get(f"{BASE_URL}/health")
        await print_response("健康检查", resp)

        resp = await client.get(f"{BASE_URL}/api/system/info")
        await print_response("系统详细信息", resp)

        # ==================== 洪水模拟 ====================
        print(f"\n【2】洪水模拟 API")

        # 启动模拟
        resp = await client.post(
            f"{BASE_URL}/api/flood/simulate",
            json={
                "rainfall_mm_h": 50.0,
                "duration_hours": 12.0,
                "upstream_m3s": 100.0,
            }
        )
        await print_response("启动模拟", resp)

        # 获取模拟状态
        resp = await client.get(f"{BASE_URL}/api/flood/status")
        await print_response("模拟状态", resp)

        # 执行一步
        resp = await client.post(f"{BASE_URL}/api/flood/simulate/step")
        await print_response("执行时间步", resp)

        # 获取格点数据
        resp = await client.get(f"{BASE_URL}/api/flood/grid")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  洪水格点数据 (部分)")
        print(f"{'='*60}")
        print(f"时间步: {data['time_step']}")
        print(f"总格点数: {data['total_points']}")
        print(f"统计信息: {json.dumps(data['statistics'], indent=2, ensure_ascii=False)}")
        print(f"前3个格点:")
        for i, point in enumerate(data['points'][:3]):
            print(f"  {i+1}. 水深={point['depth']:.3f}m, 淹没={point['flooded']}")

        # 历史数据
        resp = await client.get(f"{BASE_URL}/api/flood/history/upstream")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  洪水历史数据")
        print(f"{'='*60}")
        print(f"站点: {data['station_id']}")
        print(f"查询时长: {data['hours']}小时")
        print(f"数据条数: {len(data['entries'])}")
        if data['entries']:
            print(f"最新数据: {json.dumps(data['entries'][-1], indent=2, ensure_ascii=False)}")

        # ==================== 传感器数据 ====================
        print(f"\n【3】传感器数据 API")

        # 实时数据
        resp = await client.get(f"{BASE_URL}/api/sensors/realtime")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  实时传感器数据")
        print(f"{'='*60}")
        print(f"更新时间: {data['timestamp']}")
        print(f"站点数: {len(data['stations'])}")
        for station in data['stations']:
            print(f"  {station['name']:20} 水位={station['water_level']:.2f}m "
                  f"降雨={station['rainfall']:.1f}mm/h 电池={station['battery']:.1f}%")

        # 站点列表
        resp = await client.get(f"{BASE_URL}/api/sensors/stations")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  传感器站点列表")
        print(f"{'='*60}")
        print(f"总站点数: {data['total_stations']}")
        for station in data['stations']:
            print(f"  {station['station_id']:15} {station['name']:20} "
                  f"({station['lat']:.4f}, {station['lng']:.4f})")

        # 单站点实时数据
        resp = await client.get(f"{BASE_URL}/api/sensors/realtime/urban_a")
        await print_response("城区A站实时数据", resp)

        # 站点历史数据
        resp = await client.get(f"{BASE_URL}/api/sensors/history/urban_a?hours=24")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  站点历史数据")
        print(f"{'='*60}")
        print(f"站点: {data['station_name']} ({data['station_id']})")
        print(f"查询时长: {data['hours']}小时")
        print(f"数据条数: {len(data['readings'])}")
        if data['readings']:
            first = data['readings'][0]
            last = data['readings'][-1]
            print(f"首条数据: 水位={first['water_level']:.2f}m, 降雨={first['rainfall']:.1f}mm/h")
            print(f"末条数据: 水位={last['water_level']:.2f}m, 降雨={last['rainfall']:.1f}mm/h")

        # 统计信息
        resp = await client.get(f"{BASE_URL}/api/sensors/stats/urban_a?hours=48")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  站点统计信息")
        print(f"{'='*60}")
        print(f"站点: {data['station_name']}")
        print(f"统计时长: {data['statistics']['hours']}小时")
        stats = data['statistics']
        print(f"  水位: 最小={stats['water_level']['min']:.2f}m, "
              f"最大={stats['water_level']['max']:.2f}m, "
              f"平均={stats['water_level']['mean']:.2f}m")
        print(f"  降雨: 累计={stats['rainfall']['total']:.1f}mm, "
              f"小时最大={stats['rainfall']['max_hourly']:.1f}mm/h")

        # ==================== 预测 ====================
        print(f"\n【4】预测 API")

        # 水位预测
        resp = await client.get(f"{BASE_URL}/api/predict/flood?station_id=urban_a&hours=24")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  24小时水位预测")
        print(f"{'='*60}")
        print(f"站点: {data['station_id']}")
        print(f"预测类型: {data['prediction_type']}")
        print(f"预测小时数: {data['forecast_hours']}")
        print(f"统计信息: {json.dumps(data['statistics'], indent=2, ensure_ascii=False)}")
        print(f"前3个预测点:")
        for i, point in enumerate(data['points'][:3]):
            print(f"  {i+1}. {point['timestamp']}: "
                  f"预测={point['predicted_level']:.2f}m, "
                  f"上界={point['confidence_upper']:.2f}m, "
                  f"下界={point['confidence_lower']:.2f}m")

        # 风险趋势
        resp = await client.get(f"{BASE_URL}/api/predict/risk-trend?hours=12")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  风险趋势预测")
        print(f"{'='*60}")
        print(f"预测时长: {data['forecast_hours']}小时")
        print(f"总体趋势: {data['overall_trend']}")
        print(f"预测点数: {len(data['trend_points'])}")
        print(f"前3个趋势点:")
        for i, point in enumerate(data['trend_points'][:3]):
            print(f"  {i+1}. {point['timestamp']}: "
                  f"风险={point['risk_level']}, "
                  f"分数={point['risk_score']:.1f}")

        # 情景预测
        resp = await client.post(
            f"{BASE_URL}/api/predict/scenario",
            json={
                "scenario_type": "heavy_rain",
                "duration_hours": 6.0,
                "intensity": 1.0,
            }
        )
        data = resp.json()
        print(f"\n{'='*60}")
        print("  情景预测 (暴雨)")
        print(f"{'='*60}")
        print(f"情景类型: {data['scenario_type']}")
        print(f"持续时长: {data['duration_hours']}小时")
        print(f"最大水位: {data['maximum_water_level']:.2f}m")
        print(f"是否预警: {data['warning_issued']}")
        print(f"建议: {data['recommendation']}")

        # 集合预测
        resp = await client.get(f"{BASE_URL}/api/predict/ensemble?hours=24")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  集合预测")
        print(f"{'='*60}")
        print(f"预测类型: {data['prediction_type']}")
        print(f"预测小时数: {data['forecast_hours']}")
        print(f"预测点数: {len(data['points'])}")
        if data['points']:
            first = data['points'][0]
            print(f"首个预测点: {json.dumps(first, indent=2, ensure_ascii=False)}")

        # ==================== 风险评估 ====================
        print(f"\n【5】风险评估与避险 API")

        # 风险评估
        resp = await client.get(f"{BASE_URL}/api/risk/assessment")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  风险评估")
        print(f"{'='*60}")
        print(f"全局风险等级: {data['global_risk_level']}")
        print(f"风险分数: {data['risk_score']:.1f}")
        print(f"风险区域数: {len(data['zones'])}")
        for zone in data['zones']:
            print(f"  - {zone['id']:20} 风险={zone['risk_level']:10} "
                  f"面积={zone['area_km2']:.2f}km² 人口={zone['population']}")
        print(f"统计信息:")
        for key, value in data['statistics'].items():
            print(f"  - {key}: {value}")
        if data['affected_key_points']:
            print(f"受影响关键点: {len(data['affected_key_points'])}")
            for point in data['affected_key_points']:
                print(f"  - {point['name']:20} 风险={point['risk_level']:10} 水深={point['water_depth']:.2f}m")

        # 避险路径
        resp = await client.get(f"{BASE_URL}/api/risk/evacuation/routes")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  避险路径")
        print(f"{'='*60}")
        print(f"推荐路线: {data['recommended_route_id']}")
        print(f"总路径数: {data['total_routes']}")
        for route in data['routes']:
            print(f"  路线{route['route_id']}: {route['origin']} → {route['destination']}")
            print(f"    距离={route['distance_km']:.2f}km, "
                  f"风险={route['risk_score']:.1f}, "
                  f"耗时≈{route['estimated_minutes']:.0f}分钟, "
                  f"状态={route['status']}")

        # 人口统计
        resp = await client.get(f"{BASE_URL}/api/risk/affected-population")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  受影响人口统计")
        print(f"{'='*60}")
        pop = data['affected_population']
        print(f"总受影响人口: {pop['total_affected']}")
        print(f"  - 极危险区: {pop['critical_zone']}人")
        print(f"  - 高危险区: {pop['high_risk_zone']}人")
        print(f"  - 中危险区: {pop['medium_risk_zone']}人")
        print(f"  - 低危险区: {pop['low_risk_zone']}人")
        print(f"建议: {data['recommendation']}")

        # 早期预警
        resp = await client.get(f"{BASE_URL}/api/risk/early-warning")
        data = resp.json()
        print(f"\n{'='*60}")
        print("  早期预警")
        print(f"{'='*60}")
        print(f"是否需要预警: {data['should_warn']}")
        print(f"预警等级: {data['warning_level']}")
        print(f"受影响人口: {data['affected_population']}")
        print(f"极危险面积: {data['critical_area_km2']:.2f}km²")
        print(f"受影响关键点: {data['affected_key_points']}")
        print(f"预警信息: {data['message']}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  洪水智能分析系统 - API 使用示例")
    print("="*60)
    print("\n确保 FastAPI 服务正在运行: python main.py")
    print("然后运行此脚本来测试所有 API 端点\n")

    try:
        asyncio.run(main())
        print("\n" + "="*60)
        print("所有API测试完成 ✓")
        print("="*60 + "\n")
    except httpx.ConnectError:
        print("\n错误: 无法连接到服务器")
        print("请确保 FastAPI 服务在 http://localhost:8000 运行")
        print("\n启动服务:")
        print("  python main.py")
    except KeyboardInterrupt:
        print("\n\n已中止")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
