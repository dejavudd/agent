from __future__ import annotations

import json
from pathlib import Path
from textwrap import wrap

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle


OUT_DIR = Path(__file__).resolve().parent
QA_LOG = OUT_DIR / "figure_render_check.jsonl"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]

COLORS = {
    "ink": "#1F2A37",
    "muted": "#667085",
    "rule": "#D6DEE8",
    "panel": "#F7FAFD",
    "white": "#FFFFFF",
    "blue": "#1B66B1",
    "blue_soft": "#EAF3FC",
    "cyan": "#16899A",
    "cyan_soft": "#E7F6F8",
    "violet": "#6E59C8",
    "violet_soft": "#F1EDFF",
    "green": "#2E8F4E",
    "green_soft": "#EAF7EE",
    "amber": "#C77700",
    "amber_soft": "#FFF5E5",
    "red": "#C84848",
    "red_soft": "#FDECEC",
    "slate": "#475467",
    "slate_soft": "#F1F5F9",
}


def _font() -> font_manager.FontProperties:
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return font_manager.FontProperties(fname=str(path))
    return font_manager.FontProperties(family="sans-serif")


FONT = _font()

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.unicode_minus": False,
        "figure.dpi": 160,
        "savefig.dpi": 340,
    }
)


def canvas(width=13.2, height=7.4):
    fig, ax = plt.subplots(figsize=(width, height), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax._suppress_label_check = True
    return fig, ax


def draw_text(
    ax,
    x,
    y,
    text,
    *,
    size=9.0,
    color=None,
    weight="normal",
    ha="center",
    va="center",
    max_chars=None,
    linespacing=1.18,
):
    content = str(text)
    if max_chars:
        lines: list[str] = []
        for part in content.split("\n"):
            lines.extend(wrap(part, max_chars, break_long_words=False) or [""])
        content = "\n".join(lines)
    return ax.text(
        x,
        y,
        content,
        fontproperties=FONT,
        fontsize=size,
        color=color or COLORS["ink"],
        fontweight=weight,
        ha=ha,
        va=va,
        linespacing=linespacing,
    )


def title(ax, main, sub):
    draw_text(ax, 0.035, 0.960, main, size=15.0, weight="bold", ha="left", va="top")
    draw_text(ax, 0.035, 0.918, sub, size=8.5, color=COLORS["muted"], ha="left", va="top", max_chars=95)
    ax.plot([0.035, 0.965], [0.888, 0.888], color=COLORS["rule"], lw=1.0)


def round_box(
    ax,
    x,
    y,
    w,
    h,
    head,
    body=None,
    *,
    fc=None,
    ec=None,
    accent=None,
    radius=0.018,
    lw=1.0,
    head_size=8.7,
    body_size=7.1,
    align="center",
    body_lines=2,
):
    fc = fc or COLORS["white"]
    ec = ec or COLORS["rule"]
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.010,rounding_size={radius}",
        lw=lw,
        ec=ec,
        fc=fc,
        zorder=2,
    )
    ax.add_patch(patch)
    if accent:
        ax.add_patch(Rectangle((x, y), 0.0048, h, lw=0, fc=accent, zorder=3))
    ha = "center" if align == "center" else "left"
    tx = x + w / 2 if align == "center" else x + 0.016
    if body:
        draw_text(ax, tx, y + h * 0.70, head, size=head_size, weight="bold", ha=ha, max_chars=max(5, int(w * 86)))
        draw_text(
            ax,
            tx,
            y + h * 0.28,
            body,
            size=body_size,
            color=COLORS["muted"],
            ha=ha,
            max_chars=max(10, int(w * 112 / max(body_lines, 1))),
        )
    else:
        draw_text(ax, tx, y + h * 0.50, head, size=head_size, weight="bold", ha=ha, max_chars=max(5, int(w * 64)))
    return patch


def lane(ax, x, y, w, h, label, color):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.008,rounding_size=0.018",
            lw=0.9,
            ec="#DDE5EE",
            fc=COLORS["panel"],
            zorder=0,
        )
    )
    ax.add_patch(Rectangle((x + 0.024, y + h - 0.048), 0.006, 0.030, lw=0, fc=color, zorder=1))
    draw_text(ax, x + 0.040, y + h - 0.033, label, size=7.5, color=color, weight="bold", ha="left")


def arrow(ax, start, end, *, color=None, lw=1.1, dashed=False, rad=0.0, alpha=1.0, ms=11):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=ms,
        linewidth=lw,
        color=color or COLORS["slate"],
        linestyle=(0, (4, 3)) if dashed else "solid",
        connectionstyle=f"arc3,rad={rad}",
        shrinkA=5,
        shrinkB=5,
        alpha=alpha,
        zorder=1,
    )
    ax.add_patch(patch)
    return patch


def poly_arrow(ax, points, *, color=None, lw=1.0, dashed=False, alpha=1.0, ms=10):
    color = color or COLORS["slate"]
    if len(points) > 2:
        xs = [p[0] for p in points[:-1]]
        ys = [p[1] for p in points[:-1]]
        ax.plot(
            xs,
            ys,
            color=color,
            lw=lw,
            ls=(0, (4, 3)) if dashed else "solid",
            alpha=alpha,
            zorder=1,
        )
    arrow(ax, points[-2], points[-1], color=color, lw=lw, dashed=dashed, alpha=alpha, ms=ms)


def diamond(ax, cx, cy, w, h, head, body=None, color=None):
    color = color or COLORS["blue"]
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, fc="white", ec=color, lw=1.25, zorder=2))
    draw_text(ax, cx, cy + (0.014 if body else 0), head, size=8.0, weight="bold", max_chars=8)
    if body:
        draw_text(ax, cx, cy - 0.032, body, size=6.8, color=COLORS["muted"], max_chars=9)


def stage(ax, n, x, y, color):
    circ = plt.Circle((x, y), 0.012, fc=color, ec=color, zorder=4)
    ax.add_patch(circ)
    draw_text(ax, x, y, str(n), size=5.8, weight="bold", color="white")


def save(fig, stem):
    png = OUT_DIR / f"{stem}.png"
    svg = OUT_DIR / f"{stem}.svg"
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    fig.savefig(png, dpi=340, bbox_inches="tight", facecolor="white")
    render_check(fig, png, svg)
    plt.close(fig)


def render_check(fig, png_path: Path, svg_path: Path):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    fig_bbox = fig.bbox
    issues = []
    bboxes = []
    for ax in fig.get_axes():
        for artist in ax.texts:
            content = artist.get_text().strip()
            if not content:
                continue
            fs = artist.get_fontsize()
            if fs < 6.6:
                issues.append({"kind": "font_too_small", "text": content[:40], "fontsize": fs})
            bbox = artist.get_window_extent(renderer=renderer)
            if not fig_bbox.contains(bbox.x0, bbox.y0) or not fig_bbox.contains(bbox.x1, bbox.y1):
                issues.append({"kind": "text_out_of_canvas", "text": content[:40]})
            bboxes.append((content[:40], bbox))
    for i in range(len(bboxes)):
        for j in range(i + 1, len(bboxes)):
            a_text, a = bboxes[i]
            b_text, b = bboxes[j]
            overlap_x = min(a.x1, b.x1) - max(a.x0, b.x0)
            overlap_y = min(a.y1, b.y1) - max(a.y0, b.y0)
            if overlap_x > 4 and overlap_y > 4:
                if len(a_text) <= 2 or len(b_text) <= 2:
                    continue
                if a_text == b_text:
                    continue
                issues.append({"kind": "text_overlap", "text_a": a_text, "text_b": b_text})
                break
    for path in (png_path, svg_path):
        if not path.exists() or path.stat().st_size == 0:
            issues.append({"kind": "file_missing_or_empty", "path": str(path)})
    with QA_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"figure": png_path.name, "passed": not issues, "issues": issues}, ensure_ascii=False) + "\n")


def fig_system_architecture():
    fig, ax = canvas()
    title(
        ax,
        "系统总体架构",
        "面向本地学习工作台的分层架构：入口层触发任务，编排层调度智能体，核心能力层统一处理模型、文档和状态。",
    )
    rows = [
        ("入口层", COLORS["blue"], ["Web 学习工作台", "CLI 命令行"]),
        ("接口编排层", COLORS["cyan"], ["FastAPI 路由", "静态资源", "SSE 进度", "线程隔离"]),
        ("智能体业务层", COLORS["violet"], ["资料解析", "知识图解", "拓展材料", "智能测评", "诊断反馈", "画像路径"]),
        ("核心能力层", COLORS["green"], ["配置解析", "LLMRouter", "课程库", "PDF/OCR", "规则校验", "安全检查", "行为日志", "RAG 客户端"]),
        ("数据与服务层", COLORS["amber"], ["课程文件库", "LightRAG", "Tesseract", "云模型 API", "Ollama/vLLM"]),
    ]
    y_top, row_h, gap = 0.780, 0.090, 0.038
    for i, (name, color, items) in enumerate(rows):
        y = y_top - i * (row_h + gap)
        ax.add_patch(
            FancyBboxPatch(
                (0.050, y),
                0.128,
                row_h,
                boxstyle="round,pad=0.010,rounding_size=0.016",
                lw=0,
                ec=color,
                fc=color,
                zorder=2,
            )
        )
        draw_text(ax, 0.114, y + row_h / 2, name, size=8.8, weight="bold", color="white")
        ax.add_patch(
            FancyBboxPatch(
                (0.206, y),
                0.740,
                row_h,
                boxstyle="round,pad=0.010,rounding_size=0.016",
                lw=0.9,
                ec=COLORS["rule"],
                fc=COLORS["panel"],
                zorder=0,
            )
        )
        n = len(items)
        item_gap = 0.011
        item_w = (0.710 - item_gap * (n - 1)) / n
        for j, item in enumerate(items):
            x = 0.221 + j * (item_w + item_gap)
            round_box(
                ax,
                x,
                y + 0.022,
                item_w,
                row_h - 0.044,
                item,
                fc="white",
                ec="#DCE6F0",
                head_size=7.2,
                radius=0.010,
            )
        if i < len(rows) - 1:
            arrow(ax, (0.576, y - 0.002), (0.576, y - gap + 0.010), color=COLORS["slate"], lw=0.9)
    ax.add_patch(FancyBboxPatch((0.110, 0.105), 0.780, 0.064, boxstyle="round,pad=0.010,rounding_size=0.016", lw=0.9, ec=COLORS["rule"], fc=COLORS["slate_soft"]))
    ax.add_patch(FancyBboxPatch((0.110, 0.159), 0.780, 0.010, boxstyle="round,pad=0,rounding_size=0.016", lw=0, fc=COLORS["slate"]))
    draw_text(ax, 0.130, 0.137, "设计约束", size=8.0, weight="bold", ha="left")
    draw_text(ax, 0.250, 0.137, "Web 与 CLI 共用业务逻辑；模型调用集中到 LLMRouter；LightRAG 不可用时自动回退到本地检索。", size=7.0, color=COLORS["muted"], ha="left")
    save(fig, "fig_system_architecture")


def fig_learning_workflow():
    fig, ax = canvas()
    title(
        ax,
        "核心学习闭环流程",
        "流程按资源生成、测评诊断、个性化反馈三条泳道展开；诊断与画像结果反向驱动下一轮学习任务。",
    )
    lane(ax, 0.055, 0.662, 0.890, 0.165, "资源生成链", COLORS["blue"])
    lane(ax, 0.055, 0.430, 0.890, 0.165, "测评诊断链", COLORS["violet"])
    lane(ax, 0.055, 0.198, 0.890, 0.165, "个性化反馈链", COLORS["amber"])
    node_w = 0.138
    node_h = 0.080
    top_y = 0.704
    mid_y = 0.472
    bot_y = 0.240
    steps = [
        ("导入资料", "PDF 上传", 0.205, top_y, COLORS["blue"]),
        ("解析资料", "文本抽取 + OCR", 0.395, top_y, COLORS["cyan"]),
        ("分层讲义", "三层 Markdown", 0.585, top_y, COLORS["violet"]),
        ("图解拓展", "Diagrams / Extension", 0.775, top_y, COLORS["green"]),
        ("生成题库", "Quiz.json", 0.775, mid_y, COLORS["green"]),
        ("学生作答", "Answers / Essay", 0.585, mid_y, COLORS["violet"]),
        ("诊断反馈", "Feedback.md", 0.395, mid_y, COLORS["red"]),
        ("诊断沉淀", "Diagnostic.md", 0.205, mid_y, COLORS["slate"]),
        ("画像更新", "Profile.json", 0.205, bot_y, COLORS["cyan"]),
        ("路径规划", "LearningPath.md", 0.460, bot_y, COLORS["violet"]),
        ("下一步推荐", "行为日志 + 推荐", 0.715, bot_y, COLORS["amber"]),
    ]
    centers = {}
    for head, body, x, y, color in steps:
        round_box(ax, x, y, node_w, node_h, head, body, fc="white", ec=color, accent=color, head_size=8.0, body_size=6.9)
        centers[head] = (x + node_w / 2, y + node_h / 2)
    for a, b in [("导入资料", "解析资料"), ("解析资料", "分层讲义"), ("分层讲义", "图解拓展")]:
        arrow(ax, centers[a], centers[b], color=COLORS["blue"], lw=1.0, ms=10)
    arrow(ax, (centers["图解拓展"][0], top_y), (centers["生成题库"][0], mid_y + node_h), color=COLORS["green"], lw=1.0, ms=10)
    for a, b in [("生成题库", "学生作答"), ("学生作答", "诊断反馈"), ("诊断反馈", "诊断沉淀")]:
        arrow(ax, centers[a], centers[b], color=COLORS["violet"], lw=1.0, ms=10)
    arrow(ax, (centers["诊断沉淀"][0], mid_y), (centers["画像更新"][0], bot_y + node_h), color=COLORS["slate"], lw=1.0, ms=10)
    arrow(ax, centers["画像更新"], centers["路径规划"], color=COLORS["cyan"], lw=1.0, ms=10)
    arrow(ax, centers["路径规划"], centers["下一步推荐"], color=COLORS["amber"], lw=1.0, ms=10)
    ax.plot(
        [0.853, 0.960, 0.960, centers["导入资料"][0]],
        [0.280, 0.280, 0.850, 0.850],
        color=COLORS["amber"],
        lw=0.9,
        ls=(0, (4, 3)),
        alpha=0.72,
        zorder=1,
    )
    arrow(
        ax,
        (centers["导入资料"][0], 0.850),
        (centers["导入资料"][0], top_y + node_h),
        color=COLORS["amber"],
        dashed=True,
        alpha=0.78,
        lw=0.9,
        ms=9,
    )
    draw_text(ax, 0.800, 0.862, "闭环驱动下一轮学习", size=7.1, color=COLORS["amber"], ha="center")
    save(fig, "fig_learning_workflow")


def fig_agent_collaboration():
    fig, ax = canvas()
    title(
        ax,
        "多智能体协作机制",
        "智能体不直接共享长上下文，而是经由统一模型路由调用推理能力，并通过课程文件库交换稳定产物。",
    )
    round_box(
        ax,
        0.365,
        0.758,
        0.270,
        0.088,
        "LLMRouter",
        "统一模型、密钥、错误处理",
        fc=COLORS["cyan_soft"],
        ec=COLORS["cyan"],
        accent=COLORS["cyan"],
        head_size=10.0,
        body_size=7.3,
    )

    ax.plot([0.105, 0.895], [0.682, 0.682], color=COLORS["cyan"], lw=1.15, ls=(0, (4, 3)), zorder=1)
    arrow(ax, (0.500, 0.758), (0.500, 0.690), color=COLORS["cyan"], dashed=True, lw=0.95, ms=9)
    draw_text(ax, 0.500, 0.705, "推理调用总线", size=7.6, color=COLORS["cyan"], weight="bold")

    for y, label, color in [
        (0.505, "资源与题库生成", COLORS["blue"]),
        (0.320, "反馈与个性化规划", COLORS["violet"]),
    ]:
        ax.add_patch(
            FancyBboxPatch(
                (0.065, y),
                0.870,
                0.138,
                boxstyle="round,pad=0.006,rounding_size=0.016",
                lw=0.8,
                ec=COLORS["rule"],
                fc=COLORS["panel"],
                zorder=0,
            )
        )
        ax.add_patch(Rectangle((0.083, y + 0.105), 0.006, 0.024, lw=0, fc=color, zorder=1))
        draw_text(ax, 0.098, y + 0.117, label, size=7.3, color=color, weight="bold", ha="left")

    agents = [
        ("Ingestion", "PDF→讲义", 0.235, 0.536, COLORS["blue"]),
        ("WebExplorer", "讲义→图解", 0.405, 0.536, COLORS["blue"]),
        ("Extension", "拓展材料", 0.575, 0.536, COLORS["green"]),
        ("Quiz", "结构化题库", 0.745, 0.536, COLORS["green"]),
        ("Grader", "测评诊断", 0.260, 0.351, COLORS["red"]),
        ("Profile", "学习画像", 0.470, 0.351, COLORS["violet"]),
        ("PathPlanner", "学习路径", 0.680, 0.351, COLORS["amber"]),
    ]
    centers = []
    for head, body, x, y, color in agents:
        w = 0.146 if y > 0.4 else 0.156
        round_box(ax, x, y, w, 0.080, head, body, fc="white", ec=color, accent=color, head_size=7.9, body_size=6.8)
        centers.append((x + w / 2, y + 0.040, y))

    for cx, cy, y in centers:
        ax.plot([cx, cx], [cy + 0.040, 0.682], color=COLORS["cyan"], lw=0.85, ls=(0, (4, 3)), alpha=0.75, zorder=1)

    ax.plot([0.105, 0.895], [0.278, 0.278], color=COLORS["slate"], lw=1.0, alpha=0.82, zorder=1)
    draw_text(ax, 0.500, 0.298, "文件产物交换总线", size=7.4, color=COLORS["slate"], weight="bold")
    for cx, cy, y in centers:
        ax.plot([cx, cx], [cy - 0.040, 0.278], color=COLORS["slate"], lw=0.82, alpha=0.75, zorder=1)

    round_box(
        ax,
        0.305,
        0.118,
        0.390,
        0.095,
        "课程文件库",
        "讲义、题库、答案、反馈、画像、诊断、日志",
        fc=COLORS["slate_soft"],
        ec=COLORS["slate"],
        accent=COLORS["slate"],
        head_size=9.5,
        body_size=7.0,
    )
    arrow(ax, (0.500, 0.278), (0.500, 0.213), color=COLORS["slate"], lw=0.95, ms=9)

    round_box(ax, 0.080, 0.125, 0.158, 0.083, "RAG Tutor", "LightRAG / 本地检索", fc=COLORS["amber_soft"], ec=COLORS["amber"], accent=COLORS["amber"], head_size=7.7, body_size=6.6)
    round_box(ax, 0.762, 0.125, 0.158, 0.083, "规则校验", "格式、中文、图表、安全", fc=COLORS["red_soft"], ec=COLORS["red"], accent=COLORS["red"], head_size=7.7, body_size=6.6)
    arrow(ax, (0.305, 0.166), (0.238, 0.166), color=COLORS["amber"], lw=0.85, ms=8)
    arrow(ax, (0.695, 0.166), (0.762, 0.166), color=COLORS["red"], lw=0.85, ms=8)
    save(fig, "fig_agent_collaboration")


def fig_module_structure():
    fig, ax = canvas()
    title(ax, "功能模块划分", "模块按业务职责与公共支撑能力分组，共享 REST API、文件化状态和统一模型路由。")
    modules = [
        ("课程管理", "课程、章节、PDF、状态汇总", COLORS["blue"], 0.085, 0.640),
        ("资源生成", "解析、OCR、讲义、图解拓展", COLORS["cyan"], 0.305, 0.640),
        ("测评反馈", "题库、作答、评分、诊断", COLORS["violet"], 0.525, 0.640),
        ("个性化", "画像、路径、推荐", COLORS["amber"], 0.745, 0.640),
        ("知识问答", "LightRAG、本地检索、来源展示", COLORS["green"], 0.195, 0.430),
        ("基础设施", "配置、路由、校验、安全、日志", COLORS["slate"], 0.415, 0.430),
        ("前端交互", "工作台、Markdown、Mermaid", COLORS["red"], 0.635, 0.430),
    ]
    centers = []
    for head, body, color, x, y in modules:
        round_box(ax, x, y, 0.170, 0.108, head, body, fc="white", ec=color, accent=color, head_size=8.4, body_size=6.9)
        centers.append((x + 0.085, y + 0.0525))
    round_box(
        ax,
        0.300,
        0.205,
        0.400,
        0.105,
        "共享支撑面",
        "REST API 统一入口 + 文件化课程状态 + LLMRouter 模型路由",
        fc=COLORS["slate_soft"],
        ec=COLORS["slate"],
        accent=COLORS["slate"],
        head_size=9.2,
        body_size=7.2,
    )
    for c in centers:
        arrow(ax, c, (0.500, 0.310), color=COLORS["slate"], lw=0.78, alpha=0.72, ms=9)
    draw_text(ax, 0.500, 0.150, "模块边界与源码目录保持一致；复杂能力通过公共支撑面复用，避免重复实现。", size=7.8, color=COLORS["muted"])
    save(fig, "fig_module_structure")


def fig_filesystem_data_model():
    fig, ax = canvas()
    title(ax, "文件化数据结构", "课程级状态与章节级产物共同构成系统数据模型，便于调试、交付和设计溯源。")
    ax.add_patch(FancyBboxPatch((0.060, 0.145), 0.420, 0.675, boxstyle="round,pad=0.014,rounding_size=0.018", lw=0.95, ec=COLORS["rule"], fc=COLORS["panel"]))
    draw_text(ax, 0.088, 0.785, "目录骨架", size=9.0, weight="bold", ha="left")
    tree = [
        ("curriculum/", 0, True),
        ("<course-slug>/", 1, True),
        ("subject.json", 2, False),
        ("Profile.json / Profile.md", 2, False),
        ("Diagnostic.md", 2, False),
        ("LearningPath.md", 2, False),
        ("BehaviorLog.jsonl", 2, False),
        ("Week_NN/", 2, True),
        ("meta.json", 3, False),
        ("input/*.pdf", 3, False),
        ("assets/*.png", 3, False),
        ("generated_assets/*", 3, False),
        ("Beginner / Intermediate / Advanced.md", 3, False),
        ("Diagrams.md / Extension.md", 3, False),
        ("Quiz.json / Quiz.md", 3, False),
        ("Answers.md / Essay.md / Feedback.md", 3, False),
    ]
    y = 0.742
    for label, indent, folder in tree:
        draw_text(ax, 0.090 + indent * 0.028, y, label, size=7.35, ha="left", color=COLORS["blue"] if folder else COLORS["ink"], weight="bold" if folder else "normal")
        y -= 0.034
    groups = [
        ("课程级状态", "subject、profile、diagnostic、path、behavior", 0.570, 0.670, COLORS["cyan"]),
        ("章节输入与解析", "input PDF、页面图、OCR 文本", 0.570, 0.520, COLORS["blue"]),
        ("学习资源产物", "讲义、图解、拓展材料、生成资源", 0.570, 0.370, COLORS["green"]),
        ("测评与反馈", "Quiz、Answers、Essay、Feedback", 0.570, 0.220, COLORS["violet"]),
    ]
    for head, body, x, y, color in groups:
        round_box(ax, x, y, 0.345, 0.090, head, body, fc="white", ec=color, accent=color, head_size=8.2, body_size=6.9, align="left")
    for start_y, end_y, color in [(0.620, 0.713, COLORS["cyan"]), (0.470, 0.563, COLORS["blue"]), (0.350, 0.413, COLORS["green"]), (0.270, 0.263, COLORS["violet"])]:
        arrow(ax, (0.480, start_y), (0.570, end_y), color=color, lw=0.85, ms=9)
    round_box(ax, 0.570, 0.115, 0.345, 0.055, "可选增强：LightRAG 外部索引不替代课程原始文件。", fc=COLORS["amber_soft"], ec=COLORS["amber"], head_size=7.4)
    save(fig, "fig_filesystem_data_model")


def fig_rag_flow():
    fig, ax = canvas()
    title(ax, "RAG 问答与回退流程", "优先使用 LightRAG 增强检索；服务未配置或调用失败时，自动退回本地分块检索。")
    round_box(ax, 0.070, 0.530, 0.135, 0.082, "用户问题", "question + mode", fc="white", ec=COLORS["blue"], accent=COLORS["blue"], head_size=8.1, body_size=6.7)
    diamond(ax, 0.300, 0.571, 0.145, 0.114, "LightRAG\n可用？", color=COLORS["cyan"])
    round_box(ax, 0.455, 0.650, 0.160, 0.080, "增强检索", "调用 /query", fc=COLORS["cyan_soft"], ec=COLORS["cyan"], accent=COLORS["cyan"], head_size=7.9, body_size=6.8)
    round_box(ax, 0.455, 0.412, 0.160, 0.084, "本地回退", "分块检索 + 可选综合", fc=COLORS["amber_soft"], ec=COLORS["amber"], accent=COLORS["amber"], head_size=7.9, body_size=6.7)
    round_box(ax, 0.665, 0.530, 0.135, 0.082, "结果组装", "answer + sources", fc=COLORS["blue_soft"], ec=COLORS["blue"], accent=COLORS["blue"], head_size=7.8, body_size=6.7)
    round_box(ax, 0.830, 0.530, 0.135, 0.082, "安全检查", "敏感内容与数字声明", fc=COLORS["red_soft"], ec=COLORS["red"], accent=COLORS["red"], head_size=7.7, body_size=6.6)
    round_box(ax, 0.665, 0.392, 0.135, 0.078, "行为记录", "rag_ask + 画像信号", fc=COLORS["slate_soft"], ec=COLORS["slate"], accent=COLORS["slate"], head_size=7.6, body_size=6.6)
    round_box(ax, 0.665, 0.205, 0.300, 0.092, "返回结果", "answer、sources、fallback_reason、安全提示", fc="white", ec=COLORS["blue"], accent=COLORS["blue"], head_size=8.3, body_size=6.6)

    arrow(ax, (0.205, 0.571), (0.228, 0.571), color=COLORS["blue"], lw=1.0, ms=10)
    poly_arrow(ax, [(0.365, 0.605), (0.410, 0.605), (0.410, 0.690), (0.455, 0.690)], color=COLORS["cyan"], lw=1.0, ms=10)
    poly_arrow(ax, [(0.365, 0.537), (0.410, 0.537), (0.410, 0.454), (0.455, 0.454)], color=COLORS["amber"], lw=1.0, ms=10)
    draw_text(ax, 0.401, 0.632, "可用", size=7.4, color=COLORS["cyan"], weight="bold")
    draw_text(ax, 0.401, 0.511, "不可用 / 失败", size=7.4, color=COLORS["amber"], weight="bold")
    poly_arrow(ax, [(0.615, 0.690), (0.640, 0.690), (0.640, 0.571), (0.665, 0.571)], color=COLORS["cyan"], lw=1.0, ms=10)
    poly_arrow(ax, [(0.615, 0.454), (0.640, 0.454), (0.640, 0.571), (0.665, 0.571)], color=COLORS["amber"], lw=1.0, ms=10)
    arrow(ax, (0.800, 0.571), (0.830, 0.571), color=COLORS["blue"], lw=1.0, ms=10)
    arrow(ax, (0.732, 0.530), (0.732, 0.470), color=COLORS["slate"], lw=0.85, ms=8)
    poly_arrow(ax, [(0.897, 0.530), (0.897, 0.360), (0.815, 0.360), (0.815, 0.297)], color=COLORS["blue"], lw=1.0, ms=10)
    poly_arrow(ax, [(0.732, 0.392), (0.732, 0.350), (0.815, 0.350), (0.815, 0.297)], color=COLORS["slate"], lw=0.85, ms=8)
    save(fig, "fig_rag_flow")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    QA_LOG.write_text("", encoding="utf-8")
    fig_system_architecture()
    fig_learning_workflow()
    fig_agent_collaboration()
    fig_module_structure()
    fig_filesystem_data_model()
    fig_rag_flow()
    print(f"Generated publication-style SVG/PNG figures in {OUT_DIR}")


if __name__ == "__main__":
    main()
