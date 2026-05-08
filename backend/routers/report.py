# -*- coding: utf-8 -*-
"""
洪水态势报告 PDF 生成接口

GET /api/report/pdf  → 返回 application/pdf 二进制流
GET /api/report/preview → 返回 JSON 预览数据（供前端调试）

报告内容：
  封面：项目名 + 时间 + 案例信息
  第一节：当前态势摘要（风险等级 / 水位 / 影响范围）
  第二节：4个监测站实时数据表
  第三节：24小时水位预测折线图（ASCII近似）
  第四节：风险评估与避险建议
  尾页：技术说明（数字孪生 + LSTM + PINN方向）
"""

import io
from datetime import datetime
from typing import Dict, Any

import numpy as np
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from config import DAM_CONFIG, SENSOR_STATIONS, WARNING_LEVELS
from routers import flood
from routers.sensors import generate_sensor_reading

router = APIRouter(prefix="/api/report", tags=["report"])

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
FONT_PATH_HEI = r"C:\Windows\Fonts\simhei.ttf"
FONT_PATH_SUN = r"C:\Windows\Fonts\simsun.ttc"

ACCENT  = colors.HexColor("#0077cc")
DARK    = colors.HexColor("#0a1628")
LIGHT   = colors.HexColor("#e8f4ff")
TEXT    = colors.HexColor("#1a2a3a")
MUTED   = colors.HexColor("#5a7a9a")
WARN    = colors.HexColor("#ff6600")
DANGER  = colors.HexColor("#cc0000")
OK      = colors.HexColor("#00884a")


def _register_fonts():
    try:
        pdfmetrics.registerFont(TTFont("SimHei", FONT_PATH_HEI))
        return "SimHei"
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("SimSun", FONT_PATH_SUN))
        return "SimSun"
    except Exception:
        pass
    return "Helvetica"


def _risk_color(level: str) -> colors.Color:
    return {
        "low":      OK,
        "medium":   colors.HexColor("#ffaa00"),
        "high":     WARN,
        "critical": DANGER,
    }.get(level, MUTED)


def _risk_label(level: str) -> str:
    return {"low": "低", "medium": "中", "high": "高", "critical": "极高"}.get(level, "未知")


# ── 绘制辅助函数 ─────────────────────────────────────────────────

def _hline(c, x, y, w, color=MUTED, lw=0.5):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x, y, x + w, y)


def _box(c, x, y, w, h, fill=LIGHT, stroke=ACCENT, radius=3*mm, lw=0.8):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(lw)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def _text(c, txt, x, y, font, size=10, color=TEXT):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, txt)


def _ctext(c, txt, cx, y, font, size=10, color=TEXT):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(cx, y, txt)


def _rtext(c, txt, rx, y, font, size=10, color=TEXT):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawRightString(rx, y, txt)


def _wrap(text: str, max_width: float, font: str, size: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if pdfmetrics.stringWidth(test, font, size) <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


# ── 各页绘制 ─────────────────────────────────────────────────────

def _draw_cover(c, font: str, data: Dict[str, Any]):
    """封面页"""
    # 深色背景
    c.setFillColor(DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # 顶部彩带
    c.setFillColor(ACCENT)
    c.rect(0, PAGE_H - 10*mm, PAGE_W, 10*mm, fill=1, stroke=0)

    # 标题区
    _ctext(c, "桑干河（怀仁段）", PAGE_W/2, PAGE_H - 52*mm, font, 22, colors.white)
    _ctext(c, "洪水智能分析与决策系统", PAGE_W/2, PAGE_H - 64*mm, font, 18, colors.HexColor("#7fc8ff"))
    _ctext(c, "态 势 报 告", PAGE_W/2, PAGE_H - 80*mm, font, 32, colors.white)

    # 分割线
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1)
    c.line(MARGIN * 2, PAGE_H - 88*mm, PAGE_W - MARGIN * 2, PAGE_H - 88*mm)

    # 信息栏
    now_str = data["generated_at"]
    risk = data.get("risk_level", "low")
    risk_lbl = _risk_label(risk)

    info_items = [
        ("报告时间", now_str),
        ("研究区域", "桑干河怀仁段（永定河流域）"),
        ("当前风险等级", risk_lbl),
        ("监测站数量", f"{len(SENSOR_STATIONS)} 个"),
        ("预测时效", "24 小时"),
    ]

    y = PAGE_H - 100*mm
    for label, val in info_items:
        _text(c, f"▸  {label}：", MARGIN*2, y, font, 11, MUTED)
        _text(c, val, MARGIN*2 + 38*mm, y, font, 11, colors.white)
        y -= 8*mm

    # 底部技术标签
    tags = ["数字孪生", "LSTM 预测", "SWE 水动力", "动态避险路径", "和风天气"]
    tag_x = MARGIN * 2
    tag_y = 32*mm
    for tag in tags:
        tw = pdfmetrics.stringWidth(tag, font, 10) + 8*mm
        _box(c, tag_x, tag_y, tw, 7*mm, fill=colors.HexColor("#0d2a45"),
             stroke=ACCENT, radius=3*mm, lw=0.6)
        _ctext(c, tag, tag_x + tw/2, tag_y + 2*mm, font, 10, colors.HexColor("#7fc8ff"))
        tag_x += tw + 3*mm

    _ctext(c, "基于数字孪生技术的洪水智能分析与决策系统  ·  互联网+大学生创新创业大赛",
           PAGE_W/2, 14*mm, font, 8, MUTED)


def _draw_section_header(c, font, title: str, y: float) -> float:
    c.setFillColor(ACCENT)
    c.rect(MARGIN, y - 1*mm, 3*mm, 7*mm, fill=1, stroke=0)
    _text(c, title, MARGIN + 5*mm, y, font, 13, ACCENT)
    _hline(c, MARGIN + 5*mm, y - 2*mm, PAGE_W - 2*MARGIN - 5*mm, ACCENT, 0.5)
    return y - 10*mm


def _draw_status_cards(c, font, data: Dict[str, Any], y: float) -> float:
    """态势摘要 4张卡片"""
    risk = data.get("risk_level", "low")
    metrics = [
        ("整体风险", _risk_label(risk), _risk_color(risk)),
        ("影响面积", f"{data.get('flooded_area', 0):.1f} km²", ACCENT),
        ("受影响人口", f"{data.get('affected_population', 0):,} 人", TEXT),
        ("模拟进度", f"{data.get('sim_progress', 0):.0f}%", ACCENT),
    ]
    card_w = (PAGE_W - 2*MARGIN - 3*3*mm) / 4
    x = MARGIN
    for label, val, vc in metrics:
        _box(c, x, y - 18*mm, card_w, 18*mm, fill=LIGHT, stroke=ACCENT, radius=3*mm)
        _ctext(c, label, x + card_w/2, y - 6*mm, font, 9, MUTED)
        c.setFont(font, 14)
        c.setFillColor(vc)
        c.drawCentredString(x + card_w/2, y - 13*mm, val)
        x += card_w + 3*mm
    return y - 24*mm


def _draw_sensor_table(c, font, sensors: list, y: float) -> float:
    """监测站数据表"""
    cols = ["站点名称", "水位 (m)", "降雨 (mm/h)", "流量 (m³/s)", "电量", "状态"]
    col_ws = [52*mm, 22*mm, 24*mm, 24*mm, 16*mm, 16*mm]
    row_h = 7*mm
    header_h = 8*mm

    # 表头
    _box(c, MARGIN, y - header_h, PAGE_W - 2*MARGIN, header_h,
         fill=ACCENT, stroke=ACCENT, radius=2*mm)
    cx = MARGIN
    for col, cw in zip(cols, col_ws):
        _ctext(c, col, cx + cw/2, y - 5.5*mm, font, 9, colors.white)
        cx += cw

    # 数据行
    row_y = y - header_h
    for i, s in enumerate(sensors):
        row_y -= row_h
        fill = colors.HexColor("#f0f7ff") if i % 2 == 0 else colors.white
        c.setFillColor(fill)
        c.rect(MARGIN, row_y, PAGE_W - 2*MARGIN, row_h, fill=1, stroke=0)
        _hline(c, MARGIN, row_y, PAGE_W - 2*MARGIN, colors.HexColor("#d0dce8"))

        vals = [
            s.get("name", ""),
            f"{s.get('water_level', 0):.2f}",
            f"{s.get('rainfall', 0):.1f}",
            f"{s.get('flow_rate', 0):.3f}",
            f"{s.get('battery', 0):.0f}%",
            "正常" if s.get('battery', 100) > 20 else "低电",
        ]
        cx = MARGIN
        for val, cw in zip(vals, col_ws):
            _ctext(c, val, cx + cw/2, row_y + 2*mm, font, 9, TEXT)
            cx += cw

    # 底部边框
    _hline(c, MARGIN, row_y, PAGE_W - 2*MARGIN, ACCENT, 0.8)
    return row_y - 6*mm


def _draw_prediction_chart(c, font, predictions: list, y: float, title: str) -> float:
    """简化折线图（ReportLab 矢量绘制）"""
    chart_h = 40*mm
    chart_w = PAGE_W - 2*MARGIN
    x0, y0 = MARGIN, y - chart_h

    # 背景
    _box(c, x0, y0, chart_w, chart_h, fill=colors.HexColor("#f5faff"),
         stroke=ACCENT, radius=2*mm)

    if not predictions:
        _ctext(c, "暂无预测数据", x0 + chart_w/2, y0 + chart_h/2, font, 10, MUTED)
        return y0 - 6*mm

    vals = [p.get("predicted_level", 0) for p in predictions[:24]]
    uppers = [p.get("confidence_upper", v) for p, v in zip(predictions[:24], vals)]
    lowers = [p.get("confidence_lower", v) for p, v in zip(predictions[:24], vals)]
    n = len(vals)

    vmin = min(lowers) - 0.5
    vmax = max(uppers) + 0.5
    vrange = vmax - vmin or 1

    pad_x, pad_y = 12*mm, 5*mm

    def to_px(i, v):
        px = x0 + pad_x + i * (chart_w - 2*pad_x) / max(n-1, 1)
        py = y0 + pad_y + (v - vmin) / vrange * (chart_h - 2*pad_y)
        return px, py

    # 置信区间填充
    c.setFillColor(colors.HexColor("#cce8ff"))
    c.setStrokeColor(colors.HexColor("#cce8ff"))
    path = c.beginPath()
    px, py = to_px(0, uppers[0])
    path.moveTo(px, py)
    for i in range(1, n):
        px, py = to_px(i, uppers[i])
        path.lineTo(px, py)
    for i in range(n-1, -1, -1):
        px, py = to_px(i, lowers[i])
        path.lineTo(px, py)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    # 预测主线
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.5)
    path = c.beginPath()
    px, py = to_px(0, vals[0])
    path.moveTo(px, py)
    for i in range(1, n):
        px, py = to_px(i, vals[i])
        path.lineTo(px, py)
    c.drawPath(path, fill=0, stroke=1)

    # Y轴刻度
    for tick in [vmin, (vmin+vmax)/2, vmax]:
        _, ty = to_px(0, tick)
        _text(c, f"{tick:.1f}m", x0 + 1*mm, ty - 1.5*mm, font, 7, MUTED)

    # X轴刻度（0h / 12h / 24h）
    for hi in [0, 11, 23]:
        px, _ = to_px(hi, vmin)
        _ctext(c, f"+{hi+1}h", px, y0 + 1*mm, font, 7, MUTED)

    # 图例
    _text(c, "▬ 预测水位", x0 + chart_w - 38*mm, y0 + chart_h - 4*mm, font, 8, ACCENT)
    _text(c, "▪ 置信区间", x0 + chart_w - 38*mm, y0 + chart_h - 9*mm, font, 8, MUTED)

    return y0 - 6*mm


def _draw_tech_footer(c, font, y: float) -> float:
    """技术说明页脚"""
    _box(c, MARGIN, y - 28*mm, PAGE_W - 2*MARGIN, 28*mm,
         fill=colors.HexColor("#f0f7ff"), stroke=ACCENT, radius=3*mm)
    _text(c, "核心技术架构", MARGIN + 4*mm, y - 5*mm, font, 11, ACCENT)

    techs = [
        ("数字孪生", "SWE浅水方程 + 有限体积法，实现物理-数字双向映射，2秒实时推进"),
        ("LSTM预测", "NumPy轻量实现，桑干河历史数据训练，24小时水位预测 + 置信区间"),
        ("溃坝推演", "堰流公式 + Muskingum演算 + Manning反算，级联风险链量化"),
        ("PINN方向", "物理信息神经网络：SWE方程嵌入损失函数，极端工况泛化能力更强"),
    ]
    tx, ty = MARGIN + 4*mm, y - 12*mm
    for name, desc in techs:
        _text(c, f"• {name}：", tx, ty, font, 9, TEXT)
        lines = _wrap(desc, PAGE_W - 2*MARGIN - 28*mm, font, 8)
        for li, line in enumerate(lines[:1]):
            _text(c, line, tx + 22*mm, ty - li*4*mm, font, 8, MUTED)
        ty -= 5*mm

    return y - 32*mm


# ── 主入口 ───────────────────────────────────────────────────────

def _collect_data(request: Request) -> Dict[str, Any]:
    """从当前运行状态收集报告所需数据"""
    model = getattr(request.app.state, "swe_model", None)
    flood_state = getattr(request.app.state, "flood_router_state", None)

    # 传感器读数
    sensors = []
    for sid in SENSOR_STATIONS:
        try:
            reading = generate_sensor_reading(sid, request)
            sensors.append({
                "name": reading.name,
                "water_level": reading.water_level,
                "rainfall": reading.rainfall,
                "flow_rate": reading.flow_rate,
                "battery": reading.battery,
            })
        except Exception:
            pass

    # 模拟状态
    sim_progress = 0.0
    if flood_state:
        total = getattr(flood_state, "total_steps", 0)
        current = getattr(flood_state, "current_step", 0)
        sim_progress = (current / total * 100) if total > 0 else 0.0

    # 洪水格点统计
    flooded_area = 0.0
    affected_pop = 0
    risk_level = "low"
    if model is not None:
        flooded_cells = int(np.sum(model.h > 0.05))
        flooded_area = round(flooded_cells * 0.25, 1)  # 每格约0.25 km²
        if model.h.max() > WARNING_LEVELS["critical"]:
            risk_level = "critical"
        elif model.h.max() > WARNING_LEVELS["dangerous"]:
            risk_level = "high"
        elif model.h.max() > WARNING_LEVELS["alert"]:
            risk_level = "medium"
        affected_pop = int(flooded_cells * 280)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sensors": sensors,
        "risk_level": risk_level,
        "flooded_area": flooded_area,
        "affected_population": affected_pop,
        "sim_progress": sim_progress,
        "predictions": [],  # 由调用方填入
    }


def generate_pdf(data: Dict[str, Any]) -> bytes:
    font = _register_fonts()
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle("桑干河洪水态势报告")

    # ── 封面 ──
    _draw_cover(c, font, data)
    c.showPage()

    # ── 第1页：态势摘要 + 传感器表 ──
    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    y = PAGE_H - MARGIN
    _hline(c, MARGIN, y, PAGE_W - 2*MARGIN, ACCENT, 1.5)
    _text(c, "桑干河洪水态势报告", MARGIN, y - 8*mm, font, 14, DARK)
    _rtext(c, data["generated_at"], PAGE_W - MARGIN, y - 8*mm, font, 9, MUTED)
    y -= 16*mm

    y = _draw_section_header(c, font, "一、当前态势摘要", y)
    y = _draw_status_cards(c, font, data, y)
    y -= 4*mm

    y = _draw_section_header(c, font, "二、实时监测站数据", y)
    if data["sensors"]:
        y = _draw_sensor_table(c, font, data["sensors"], y)
    else:
        _text(c, "（传感器数据暂不可用，后端未启动）", MARGIN, y - 6*mm, font, 9, MUTED)
        y -= 12*mm

    y -= 4*mm
    y = _draw_section_header(c, font, "三、24小时水位预测", y)
    y = _draw_prediction_chart(c, font, data.get("predictions", []), y, "桑干河怀仁主站")

    y -= 8*mm
    y = _draw_section_header(c, font, "四、核心技术架构", y)
    _draw_tech_footer(c, font, y)

    # 页码
    _ctext(c, "— 1 —", PAGE_W/2, 10*mm, font, 9, MUTED)
    c.showPage()

    # ── 第2页：风险建议 ──
    c.setFillColor(colors.white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    y = PAGE_H - MARGIN
    _hline(c, MARGIN, y, PAGE_W - 2*MARGIN, ACCENT, 1.5)
    _text(c, "风险评估与应急建议", MARGIN, y - 8*mm, font, 14, DARK)
    y -= 16*mm

    risk = data.get("risk_level", "low")
    risk_color = _risk_color(risk)

    y = _draw_section_header(c, font, "五、风险等级评估", y)
    _box(c, MARGIN, y - 20*mm, PAGE_W - 2*MARGIN, 20*mm,
         fill=colors.HexColor("#f5faff"), stroke=risk_color, radius=3*mm, lw=1.5)
    _text(c, f"当前综合风险等级：", MARGIN + 5*mm, y - 8*mm, font, 11, TEXT)
    c.setFont(font, 16)
    c.setFillColor(risk_color)
    c.drawString(MARGIN + 50*mm, y - 9*mm, f"【{_risk_label(risk)}】")
    y -= 26*mm

    y = _draw_section_header(c, font, "六、应急处置建议", y)
    suggestions = {
        "low":      ["维持常规巡检频次（每2小时一次）",
                     "确保桑干河大桥及S322省道保持畅通",
                     "检查上游应县—怀仁段监测站通信状态"],
        "medium":   ["提升巡检频次至每小时一次",
                     "通知怀仁市区低洼地带居民关注汛情",
                     "预置防洪物资于马鞍山高地避险点",
                     "联系山阴县做好下游预警接收准备"],
        "high":     ["立即启动III级防汛应急响应",
                     "组织桑干河两岸500m范围内居民有序转移",
                     "封闭桑干河大桥，实施S322交通管制",
                     "怀仁人民医院、第一中学启动应急预案",
                     "向朔州市防指报告当前险情态势"],
        "critical": ["立即启动I级防汛应急响应，上报省防指",
                     "全面疏散桑干河怀仁段两岸受影响居民（约8.5万人）",
                     "请求省级增援，调配应急救援力量",
                     "封闭所有跨桑干河通道，禁止车辆通行",
                     "向下游山阴县发出最高级别洪水预警"],
    }
    items = suggestions.get(risk, suggestions["low"])
    sy = y
    for i, item in enumerate(items):
        _text(c, f"  {i+1}. {item}", MARGIN + 2*mm, sy - (i+1)*7*mm, font, 10, TEXT)

    y = sy - (len(items)+2)*7*mm

    # 免责声明
    _hline(c, MARGIN, y, PAGE_W - 2*MARGIN, MUTED)
    disclaimer = ("本报告由基于数字孪生的洪水智能分析与决策系统自动生成，"
                  "预测结果仅供参考，实际防汛决策请结合现场观测和水文专家研判。"
                  "系统核心算法：SWE浅水方程 + LSTM水位预测 + 动态Dijkstra避险路径。")
    disc_lines = _wrap(disclaimer, PAGE_W - 2*MARGIN, font, 8)
    for li, line in enumerate(disc_lines):
        _text(c, line, MARGIN, y - (li+1)*5*mm, font, 8, MUTED)

    _ctext(c, "— 2 —", PAGE_W/2, 10*mm, font, 9, MUTED)
    c.save()
    return buf.getvalue()


@router.get("/pdf", summary="导出当前态势报告 PDF")
async def export_pdf_report(request: Request):
    data = _collect_data(request)
    pdf_bytes = generate_pdf(data)
    filename = f"sanggan_flood_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/preview", summary="报告数据预览（JSON）")
async def preview_report_data(request: Request):
    return _collect_data(request)
