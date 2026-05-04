from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


OUTPUT_PATH = Path(r"C:\Users\32613\Desktop\hengping-dashboard-scored.pdf")
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"
PAGE_W, PAGE_H = letter
MARGIN = 24


MODELS = ["Claude", "Gemini", "ChatGPT"]
MODULES = {
    "模块A 周报创作": {
        "rows": [
            ("① 选题创新性", "角度新颖，有差异化", [8, 8, 9]),
            ("② 内容专业性", "洞察深刻，信息密度高", [8, 9, 9]),
            ("③ 落地可行性", "少量调整即可直接用", [9, 9, 9]),
            ("④ 语言表达力", "有感染力，节奏感强", [9, 9, 8]),
            ("⑤ 评论引导性", "能有效引发评论互动", [9, 9, 10]),
        ],
        "totals": [43, 44, 45],
    },
    "模块B 选题生成": {
        "rows": [
            ("① 标题抓眼度", "3秒内抓住目标用户", [8, 9, 8]),
            ("② 场景贴合度", "围绕职场提效主题", [8, 9, 9]),
            ("③ 可直接开拍性", "结构完整，落地感强", [8, 9, 10]),
            ("④ 平台匹配度", "平台推荐较为合理", [8, 9, 8]),
            ("⑤ 类型覆盖完整度", "三类内容覆盖达标", [7, 8, 8]),
        ],
        "totals": [39, 44, 43],
    },
    "模块C 职业观点": {
        "rows": [
            ("① 观点鲜明度", "立场清晰，不含糊", [10, 9, 9]),
            ("② 案例支撑力", "案例能托住观点", [8, 8, 9]),
            ("③ 情绪感染力", "有冲击力和记忆点", [10, 9, 8]),
            ("④ 专业说服力", "不止情绪，还有判断", [8, 8, 10]),
            ("⑤ 评论钩子强度", "结尾能激发互动", [10, 10, 10]),
        ],
        "totals": [46, 44, 46],
    },
}

RANKING = [
    ("1", "ChatGPT", 134, "最均衡，适合长期职场内容账号"),
    ("2", "Gemini", 132, "选题流量感最强，爆款策划突出"),
    ("3", "Claude", 128, "观点锋利，短口播节奏最好"),
]

NOTES = {
    "Claude": "亮点：观点最锋利，口播感强。失分：体系化偏弱，选题信息不够完整。",
    "Gemini": "亮点：最像内容策划，标题和平台感很强。失分：部分表达偏满，可信度略受影响。",
    "ChatGPT": "亮点：结构最稳，方法论最清楚。失分：情绪张力稍弱，不如Gemini炸。",
}


def register_fonts():
    pdfmetrics.registerFont(TTFont("SimHei", FONT_PATH))


def draw_round_rect(c, x, y, w, h, radius=10, fill=colors.white, stroke=colors.HexColor("#D7DDE7"), line=1):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(line)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)


def draw_text(c, text, x, y, size=10, color=colors.black, font="SimHei"):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, text)


def draw_center_text(c, text, x, y, w, size=10, color=colors.black, font="SimHei"):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(x + w / 2, y, text)


def draw_chip(c, x, y, w, h, title, fill, text_color=colors.white):
    draw_round_rect(c, x, y, w, h, radius=11, fill=fill, stroke=fill)
    draw_center_text(c, title, x, y + h / 2 - 4, w, size=10, color=text_color)


def wrap_text(c, text, width, font="SimHei", size=9):
    words = list(text)
    lines = []
    current = ""
    for ch in words:
        test = current + ch
        if pdfmetrics.stringWidth(test, font, size) <= width:
            current = test
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_wrapped(c, text, x, y, width, size=9, leading=12, color=colors.HexColor("#344054")):
    lines = wrap_text(c, text, width, size=size)
    for idx, line in enumerate(lines):
        draw_text(c, line, x, y - idx * leading, size=size, color=color)
    return len(lines)


def draw_table(c, title, module, x, top_y, w):
    header_h = 24
    row_h = 24
    total_h = 24
    title_h = 28
    col_widths = [w * 0.29, w * 0.37, w * 0.113, w * 0.113, w * 0.114]

    draw_round_rect(c, x, top_y - (title_h + header_h + row_h * 6 + total_h), w, title_h + header_h + row_h * 6 + total_h, radius=12, fill=colors.white)
    draw_text(c, title, x + 12, top_y - 18, size=12, color=colors.HexColor("#0F172A"))
    draw_text(c, "同题实测，五维评分", x + w - 120, top_y - 18, size=8, color=colors.HexColor("#667085"))

    y = top_y - title_h
    draw_round_rect(c, x + 1, y - header_h, w - 2, header_h, radius=0, fill=colors.HexColor("#F5F7FA"), stroke=colors.HexColor("#E5E7EB"))

    headers = ["评分维度", "说明", *MODELS]
    cur_x = x
    for idx, head in enumerate(headers):
        cw = col_widths[idx]
        draw_center_text(c, head, cur_x, y - 16, cw, size=8, color=colors.HexColor("#475467"))
        cur_x += cw

    current_y = y - header_h
    c.setStrokeColor(colors.HexColor("#EAECF0"))
    for label, desc, scores in module["rows"]:
        current_y -= row_h
        c.line(x, current_y, x + w, current_y)
        col_x = x
        draw_text(c, label, col_x + 8, current_y + 8, size=8, color=colors.HexColor("#101828"))
        col_x += col_widths[0]
        draw_text(c, desc, col_x + 8, current_y + 8, size=8, color=colors.HexColor("#667085"))
        col_x += col_widths[1]
        for score, cw in zip(scores, col_widths[2:]):
            draw_center_text(c, str(score), col_x, current_y + 8, cw, size=9, color=colors.HexColor("#111827"))
            col_x += cw

    current_y -= total_h
    draw_round_rect(c, x + 1, current_y, w - 2, total_h, radius=0, fill=colors.HexColor("#F8FAFC"), stroke=colors.HexColor("#E5E7EB"))
    draw_text(c, "模块总分", x + 8, current_y + 8, size=8, color=colors.HexColor("#0F172A"))
    col_x = x + col_widths[0] + col_widths[1]
    for total, cw in zip(module["totals"], col_widths[2:]):
        draw_center_text(c, str(total), col_x, current_y + 8, cw, size=10, color=colors.HexColor("#0F172A"))
        col_x += cw

    return current_y - 12


def build_pdf():
    register_fonts()
    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=letter)
    c.setTitle("三模型横评 · 现场评分仪表盘")

    c.setFillColor(colors.HexColor("#F5F7FB"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    draw_text(c, "三模型横评 · 现场评分仪表盘", MARGIN, PAGE_H - 32, size=18, color=colors.HexColor("#0F172A"))
    draw_text(c, "4月28日 12:30  |  Claude · Gemini · ChatGPT  |  五维度量化评分 · 满分150分", MARGIN, PAGE_H - 50, size=8, color=colors.HexColor("#667085"))

    chip_y = PAGE_H - 84
    draw_chip(c, MARGIN, chip_y, 92, 24, "模型A Claude", colors.HexColor("#8B5CF6"))
    draw_chip(c, MARGIN + 102, chip_y, 98, 24, "模型B Gemini", colors.HexColor("#22C55E"))
    draw_chip(c, MARGIN + 210, chip_y, 110, 24, "模型C ChatGPT", colors.HexColor("#0EA5E9"))

    # Ranking panel
    rank_x = PAGE_W - 194
    rank_y = PAGE_H - 285
    rank_w = 170
    rank_h = 177
    draw_round_rect(c, rank_x, rank_y, rank_w, rank_h, radius=14, fill=colors.white)
    draw_text(c, "综合排名", rank_x + 12, rank_y + rank_h - 18, size=12, color=colors.HexColor("#0F172A"))
    draw_text(c, "按三模块总分汇总", rank_x + 12, rank_y + rank_h - 34, size=8, color=colors.HexColor("#667085"))
    row_y = rank_y + rank_h - 58
    medal_colors = [colors.HexColor("#F59E0B"), colors.HexColor("#94A3B8"), colors.HexColor("#F97316")]
    for idx, (rank, model, score, tag) in enumerate(RANKING):
        draw_round_rect(c, rank_x + 10, row_y - 40 * idx, rank_w - 20, 32, radius=10, fill=colors.HexColor("#F8FAFC"), stroke=colors.HexColor("#E5E7EB"))
        c.setFillColor(medal_colors[idx])
        c.circle(rank_x + 24, row_y - 40 * idx + 16, 10, fill=1, stroke=0)
        draw_center_text(c, rank, rank_x + 14, row_y - 40 * idx + 12, 20, size=9, color=colors.white)
        draw_text(c, model, rank_x + 40, row_y - 40 * idx + 18, size=10, color=colors.HexColor("#111827"))
        draw_text(c, f"{score}分", rank_x + 105, row_y - 40 * idx + 18, size=10, color=colors.HexColor("#111827"))
        draw_text(c, tag[:14], rank_x + 40, row_y - 40 * idx + 7, size=7, color=colors.HexColor("#667085"))

    # Tables
    table_w = PAGE_W - 2 * MARGIN - 186
    top_y = PAGE_H - 118
    after_a = draw_table(c, "模块A · 周报类内容创作", MODULES["模块A 周报创作"], MARGIN, top_y, table_w)
    after_b = draw_table(c, "模块B · 选题生成", MODULES["模块B 选题生成"], MARGIN, after_a, table_w)
    after_c = draw_table(c, "模块C · 职业观点", MODULES["模块C 职业观点"], MARGIN, after_b, table_w)

    # Notes area
    notes_y = max(32, after_c - 120)
    draw_round_rect(c, MARGIN, notes_y, PAGE_W - 2 * MARGIN, 100, radius=14, fill=colors.white)
    draw_text(c, "模型笔记", MARGIN + 12, notes_y + 82, size=12, color=colors.HexColor("#0F172A"))
    draw_text(c, "亮点 / 失分点 / 适用建议", MARGIN + 74, notes_y + 82, size=8, color=colors.HexColor("#667085"))

    note_w = (PAGE_W - 2 * MARGIN - 24) / 3
    for idx, model in enumerate(MODELS):
        box_x = MARGIN + 8 + idx * (note_w + 4)
        draw_round_rect(c, box_x, notes_y + 12, note_w, 58, radius=10, fill=colors.HexColor("#F8FAFC"), stroke=colors.HexColor("#E5E7EB"))
        draw_text(c, model, box_x + 8, notes_y + 54, size=10, color=colors.HexColor("#111827"))
        draw_wrapped(c, NOTES[model], box_x + 8, notes_y + 39, note_w - 16, size=7, leading=10)

    c.save()


if __name__ == "__main__":
    build_pdf()
    print(f"Created: {OUTPUT_PATH}")
