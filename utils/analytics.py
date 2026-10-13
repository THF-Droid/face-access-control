"""
数据分析与可视化模块
使用 Pandas 进行统计分析，Matplotlib 绘制图表
"""
# 系统路径操作模块，用于拼接文件路径、创建文件夹、获取文件绝对路径
import os
# 结构化数据分析核心库，处理通行记录、人员数据表，完成筛选、分组、聚合统计
import pandas as pd
# 数值计算库，辅助数学统计、数组运算，兼容Pandas数值计算
import numpy as np
# Matplotlib绘图顶层核心库，配置全局绘图参数、后端渲染引擎
import matplotlib
# Matplotlib绘图接口，用于绘制折线图、柱状图、饼图、子图画布等
import matplotlib.pyplot as plt
# 字体管理模块，遍历系统字体库、加载字体，解决中文方框乱码问题
import matplotlib.font_manager as fm
# 日期时间基础类，用于时间戳比对、日期格式化、时间范围偏移计算
from datetime import datetime, timedelta
# 从自定义数据库工具模块加载通行记录DataFrame、注册人员信息DataFrame
from utils.database import load_records, load_persons

# 切换Matplotlib渲染后端为TkAgg，支持独立弹窗展示图表、鼠标缩放、平移交互
matplotlib.use("TkAgg")

# ── 中文字体配置函数 ─────────────────────────────────────────────────────────────
def _setup_chinese_font():
    """配置中文字体，优先使用系统中文字体，自动兜底兼容"""
    # 多平台兼容中文字体优先级列表：Windows→Linux→MacOS
    candidates = [
        "Microsoft YaHei", "SimHei", "SimSun", "FangSong",
        "STSong", "Heiti TC", "PingFang SC", "Noto Sans CJK SC"
    ]
    # 遍历系统所有已安装字体，提取字体名称存入集合，快速查重匹配
    available = {f.name for f in fm.fontManager.ttflist}
    # 按优先级顺序匹配可用中文字体，匹配成功立即配置全局字体
    for font in candidates:
        if font in available:
            plt.rcParams["font.family"] = [font]
            # 关闭负号ASCII替换，解决负数坐标轴显示方框BUG
            plt.rcParams["axes.unicode_minus"] = False
            return font
    # 无匹配中文字体时，仅修复负号显示问题，使用系统默认英文字体
    plt.rcParams["axes.unicode_minus"] = False
    return "default"

# 执行字体初始化配置，记录最终生效字体名称，便于调试排查
FONT_NAME = _setup_chinese_font()

# 拼接图表存储根目录：项目根目录/data/charts，适配不同运行路径
# __file__：当前脚本文件路径；dirname两次向上取项目根目录，拼接子文件夹
CHART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "charts")
# 递归创建图表文件夹，已存在不会报错，确保保存路径一定可用
os.makedirs(CHART_DIR, exist_ok=True)

# 全局统一配色字典，全项目图表视觉风格统一，便于后期主题修改
COLORS = {
    "allow": "#4CAF50",    # 允许通行：安全绿色
    "deny": "#F44336",     # 拒绝通行：警示红色
    "unknown": "#FF9800",  # 陌生人通行：提醒橙色
    "bar": "#2196F3",      # 通用柱状图：主体蓝色
    "line": "#9C27B0",     # 排行横向柱/折线辅助色：紫色
    "bg": "#FAFAFA",       # 画布背景：浅灰白，降低视觉疲劳
}

# ── 底层统计分析函数（纯数据计算，无绘图） ──────────────────────────────────────────────────────────────

def get_summary_stats() -> dict:
    """获取全局汇总统计信息，首页仪表盘核心指标"""
    # 加载完整通行记录表、注册人员基础信息表
    records = load_records()
    persons = load_persons()

    # 判定无通行数据场景，返回全零默认值防止后续计算报错
    if len(records) == 0:
        return {
            "total_records": 0, "allow_count": 0, "deny_count": 0,
            "unknown_count": 0, "allow_rate": 0.0,
            "total_persons": len(persons), "today_records": 0
        }

    # 获取当前系统日期，格式化为年月日字符串，用于当日数据筛选
    today = datetime.now().strftime("%Y-%m-%d")
    # 匹配日期字段，筛选今日所有通行记录
    today_df = records[records["date"].dt.strftime("%Y-%m-%d") == today]

    # 布尔条件计数：统计允许通行总条数
    allow = (records["access_result"] == "允许通行").sum()
    # 布尔条件计数：统计拒绝通行总条数
    deny = (records["access_result"] == "拒绝通行").sum()
    # 布尔条件计数：统计陌生人识别通行次数
    unknown = (records["access_result"] == "陌生人").sum()
    # 全量通行记录总行数
    total = len(records)

    # 封装所有核心统计指标为字典，提供给前端仪表盘、图表调用
    return {
        "total_records": total,                     # 总通行记录数
        "allow_count": int(allow),                  # 允许通行总数
        "deny_count": int(deny),                    # 拒绝通行总数
        "unknown_count": int(unknown),              # 陌生人通行次数
        "allow_rate": round(allow / total * 100, 1) if total > 0 else 0.0,  # 通过率百分比，保留1位小数
        "total_persons": len(persons),              # 系统总注册人员数
        "today_records": len(today_df)              # 今日实时通行次数
    }

def get_hourly_stats(days: int = 7) -> pd.DataFrame:
    """统计最近 N 天各小时通行量，用于时段分布柱状图"""
    # 加载全量通行数据
    records = load_records()
    # 无数据直接返回空DataFrame，避免分组报错
    if len(records) == 0:
        return pd.DataFrame()
    # 计算时间左边界：当前时间向前偏移指定天数，划定统计时间范围
    cutoff = datetime.now() - timedelta(days=days)
    # 筛选时间范围内的近期通行数据
    recent = records[records["access_time"] >= cutoff]
    # 时间范围内无数据，返回空表
    if len(recent) == 0:
        return pd.DataFrame()
    # 按小时字段分组聚合，统计每组数量，重置索引生成标准DataFrame
    hourly = recent.groupby("hour").size().reset_index(name="count")
    # 标准化列名：小时、对应时段通行次数
    hourly.columns = ["hour", "count"]
    return hourly

def get_daily_trend(days: int = 30) -> pd.DataFrame:
    """获取最近 N 天每日通行趋势，拆分允许/拒绝/陌生人分类统计"""
    # 加载通行数据集
    records = load_records()
    # 空数据兜底返回空表
    if len(records) == 0:
        return pd.DataFrame()
    # 计算统计起始时间点
    cutoff = datetime.now() - timedelta(days=days)
    # 筛选近期数据并创建副本，防止修改原始数据集触发警告
    recent = records[records["access_time"] >= cutoff].copy()
    # 从日期字段提取年月日字符串，作为每日分组依据
    recent["date_str"] = recent["date"].dt.strftime("%Y-%m-%d")
    # 多字段分组：日期+通行结果，计数后行转列，缺失分类填充0
    daily = recent.groupby(["date_str", "access_result"]).size().unstack(fill_value=0).reset_index()
    # 统一日期列字段名，简化后续绘图调用
    daily.rename(columns={"date_str": "date"}, inplace=True)
    return daily

def get_person_stats() -> pd.DataFrame:
    """统计每位注册人员总通行次数，降序排序，用于TOP排行"""
    records = load_records()
    # 无数据返回空表
    if len(records) == 0:
        return pd.DataFrame()
    # 按人员ID、姓名、部门三维分组，统计单人总通行次数，重置索引
    stats = (records.groupby(["person_id", "name", "department"])
             .size().reset_index(name="count"))
    # 按通行次数降序排列，高频人员排在前列
    return stats.sort_values("count", ascending=False)

def get_result_distribution() -> pd.Series:
    """统计三大通行结果全局数量分布，饼图数据源"""
    records = load_records()
    # 空数据返回空序列，适配饼图绘制逻辑
    if len(records) == 0:
        return pd.Series(dtype=int)
    # 对通行结果字段分类计数，生成分类-数值序列
    return records["access_result"].value_counts()

# ── 可视化绘图函数（单图表独立绘制） ────────────────────────────────────────────────────────────────

def plot_daily_trend(days: int = 14, save: bool = True) -> str:
    """绘制每日通行趋势折线图，区分三种通行结果"""
    # 读取指定天数的每日分类统计数据
    daily = get_daily_trend(days)

    # 创建画布，设定宽高尺寸，应用全局背景色
    fig, ax = plt.subplots(figsize=(12, 5), facecolor=COLORS["bg"])
    # 子图坐标轴背景色与画布统一
    ax.set_facecolor(COLORS["bg"])

    # 判断数据集为空，在画布中心展示占位提示文字
    if len(daily) == 0:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                fontsize=16, transform=ax.transAxes)
    else:
        # 遍历除日期外的所有通行结果分类列
        for col in daily.columns[1:]:
            # 匹配通行结果与全局配色键，无匹配则使用默认柱状蓝色
            color = COLORS.get({
                "允许通行": "allow", "拒绝通行": "deny", "陌生人": "unknown"
            }.get(col, "bar"), COLORS["bar"])
            # 绘制折线：带圆点标记、配色、线宽、标记大小，添加图例标签
            ax.plot(daily["date"], daily[col], marker="o", label=col,
                    color=color, linewidth=2, markersize=6)
        # X轴刻度与数据长度一一对应
        ax.set_xticks(range(len(daily)))
        # 赋值日期文本，旋转35度右对齐，避免日期文字重叠拥挤
        ax.set_xticklabels(daily["date"].tolist(), rotation=35, ha="right", fontsize=9)
        # 显示图例，调整字号适配画布
        ax.legend(fontsize=11)
        # 显示浅色网格线，辅助数值读取，降低透明度弱化干扰
        ax.grid(True, alpha=0.3)

    # 设置图表标题、字号、加粗、顶部内边距
    ax.set_title(f"最近 {days} 天通行趋势", fontsize=14, fontweight="bold", pad=12)
    # X轴坐标轴标签
    ax.set_xlabel("日期", fontsize=11)
    # Y轴坐标轴标签
    ax.set_ylabel("通行次数", fontsize=11)
    # 自动紧凑排版，裁剪多余留白，防止标签被截断
    plt.tight_layout()

    # 初始化文件保存路径为空字符串
    path = ""
    # 开启保存开关时，拼接完整保存路径并导出高清PNG
    if save:
        path = os.path.join(CHART_DIR, "daily_trend.png")
        # 分辨率150DPI，紧凑裁剪边框留白
        plt.savefig(path, dpi=150, bbox_inches="tight")
    # 弹出独立窗口展示绘制完成的图表
    plt.show()
    # 关闭画布释放内存，避免多次绘图内存堆积
    plt.close()
    # 返回图片本地存储路径，供前端页面加载
    return path

def plot_hourly_distribution(days: int = 7, save: bool = True) -> str:
    """绘制各小时时段通行量柱状图"""
    # 获取近N小时段通行统计数据
    hourly = get_hourly_stats(days)

    # 创建画布，配置尺寸与背景色
    fig, ax = plt.subplots(figsize=(12, 5), facecolor=COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    # 空数据占位提示
    if len(hourly) == 0:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                fontsize=16, transform=ax.transAxes)
    else:
        # 绘制柱状图：主配色、透明度、白色描边区分柱子、柱宽度
        bars = ax.bar(hourly["hour"], hourly["count"],
                      color=COLORS["bar"], alpha=0.85, edgecolor="white", width=0.7)
        # 遍历每根柱子，在柱顶标注对应通行数值
        for bar, val in zip(bars, hourly["count"]):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    str(int(val)), ha="center", va="bottom", fontsize=9)
        # X轴强制0-24小时全刻度展示，保证时段完整性
        ax.set_xticks(range(24))
        # 刻度文本格式化，旋转45度防止拥挤
        ax.set_xticklabels([f"{h}时" for h in range(24)], rotation=45, fontsize=8)
        # 仅纵向网格线，辅助对比数值高低
        ax.grid(True, axis="y", alpha=0.3)

    # 图表标题配置
    ax.set_title(f"最近 {days} 天各时段通行量分布", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("时段（小时）", fontsize=11)
    ax.set_ylabel("通行次数", fontsize=11)
    plt.tight_layout()

    path = ""
    # 保存图片至指定目录
    if save:
        path = os.path.join(CHART_DIR, "hourly_dist.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
    # 弹窗展示图表
    plt.show()
    plt.close()
    return path

def plot_result_pie(save: bool = True) -> str:
    """绘制通行结果占比饼图（允许/拒绝/陌生人）"""
    # 获取三大通行结果分类计数
    dist = get_result_distribution()

    # 创建正方形画布，适配饼图圆形比例，背景配色统一
    fig, ax = plt.subplots(figsize=(7, 7), facecolor=COLORS["bg"])

    # 空数据占位
    if len(dist) == 0:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                fontsize=16, transform=ax.transAxes)
    else:
        # 建立分类与配色映射关系
        color_map = {"允许通行": COLORS["allow"], "拒绝通行": COLORS["deny"],
                     "陌生人": COLORS["unknown"]}
        # 按分类顺序匹配配色，未知分类用灰色兜底
        colors = [color_map.get(k, "#9E9E9E") for k in dist.index]
        # 绘制饼图：标签、百分比格式、配色、起始旋转角度、白色分割边框
        wedges, texts, autotexts = ax.pie(
            dist.values, labels=dist.index, autopct="%1.1f%%",
            colors=colors, startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 2}
        )
        # 放大百分比文字并加粗，提升可读性
        for at in autotexts:
            at.set_fontsize(12)
            at.set_fontweight("bold")

    # 饼图标题
    ax.set_title("通行结果分布", fontsize=14, fontweight="bold", pad=12)
    plt.tight_layout()

    path = ""
    if save:
        path = os.path.join(CHART_DIR, "result_pie.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.show()
    plt.close()
    return path

def plot_top_persons(top_n: int = 10, save: bool = True) -> str:
    """绘制高频通行人员TOP N横向柱状排行图"""
    # 获取人员通行统计，截取前N名高频人员
    stats = get_person_stats().head(top_n)

    # 创建画布，配置尺寸与背景色
    fig, ax = plt.subplots(figsize=(10, 6), facecolor=COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    # 空数据提示
    if len(stats) == 0:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                fontsize=16, transform=ax.transAxes)
    else:
        # Y轴标签拼接姓名+所属部门，区分同名人员
        labels = stats["name"] + "\n(" + stats["department"] + ")"
        # 绘制横向柱状图，配置配色、透明度、白色边框
        bars = ax.barh(labels, stats["count"], color=COLORS["bar"],
                       alpha=0.85, edgecolor="white")
        # 在横向柱右侧标注通行次数
        for bar, val in zip(bars, stats["count"]):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height()/2,
                    str(int(val)), va="center", fontsize=10)
        # 反转Y轴，让排行第一名显示在最顶部
        ax.invert_yaxis()
        # 横向网格线，便于读取次数数值
        ax.grid(True, axis="x", alpha=0.3)

    # 排行图表标题
    ax.set_title(f"通行次数 Top {top_n} 人员", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("通行次数", fontsize=11)
    plt.tight_layout()

    path = ""
    if save:
        path = os.path.join(CHART_DIR, "top_persons.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.show()
    plt.close()
    return path

def plot_dashboard(save: bool = True) -> str:
    """综合数据看板：2行2列整合四大核心图表，一体化大屏"""
    # 一次性预加载所有子图需要的全部数据源，减少重复数据库查询
    stats = get_summary_stats()
    hourly = get_hourly_stats(7)
    daily = get_daily_trend(14)
    dist = get_result_distribution()
    persons_top = get_person_stats().head(8)

    # 创建超大总画布，适配四合一看板尺寸，背景色统一
    fig = plt.figure(figsize=(16, 10), facecolor=COLORS["bg"])
    # 设置总看板大标题，拼接核心全局指标，顶部展示整体概况
    fig.suptitle(
        f"人脸通行管控系统 · 数据看板\n"
        f"总记录: {stats['total_records']}  注册人员: {stats['total_persons']}  "
        f"今日: {stats['today_records']}  允许率: {stats['allow_rate']}%",
        fontsize=14, fontweight="bold", y=0.98
    )

    # 划分2行2列网格布局，设置子图垂直、水平间距，避免重叠
    gs = fig.add_gridspec(2, 2, hspace=0.4, wspace=0.35)
    # 按网格顺序实例化四个子图坐标轴对象
    axes = [fig.add_subplot(gs[i, j]) for i in range(2) for j in range(2)]
    # 循环统一所有子图背景色，视觉一体化
    for ax in axes:
        ax.set_facecolor(COLORS["bg"])

    # ① 左上子图：每日通行趋势折线图
    ax = axes[0]
    if len(daily) > 0:
        # 遍历各类通行结果绘制独立折线
        for col in daily.columns[1:]:
            color = COLORS.get({
                "允许通行": "allow", "拒绝通行": "deny", "陌生人": "unknown"
            }.get(col, "bar"), COLORS["bar"])
            ax.plot(range(len(daily)), daily[col], marker="o", label=col,
                    color=color, linewidth=2, markersize=5)
        # 稀疏X轴刻度，间隔取样避免日期拥挤
        ax.set_xticks(range(0, len(daily), max(1, len(daily)//6)))
        ax.set_xticklabels(
            [daily["date"].iloc[i] for i in range(0, len(daily), max(1, len(daily)//6))],
            rotation=30, ha="right", fontsize=8
        )
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("每日通行趋势", fontsize=12, fontweight="bold")

    # ② 右上子图：时段通行分布柱状图
    ax = axes[1]
    if len(hourly) > 0:
        ax.bar(hourly["hour"], hourly["count"], color=COLORS["bar"],
               alpha=0.85, edgecolor="white")
        # 每3小时展示一个刻度，精简视觉元素
        ax.set_xticks(range(0, 24, 3))
        ax.set_xticklabels([f"{h}时" for h in range(0, 24, 3)])
        ax.grid(True, axis="y", alpha=0.3)
    else:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("各时段通行量（近7天）", fontsize=12, fontweight="bold")

    # ③ 左下子图：通行结果占比饼图
    ax = axes[2]
    if len(dist) > 0:
        color_map = {"允许通行": COLORS["allow"], "拒绝通行": COLORS["deny"],
                     "陌生人": COLORS["unknown"]}
        colors = [color_map.get(k, "#9E9E9E") for k in dist.index]
        ax.pie(dist.values, labels=dist.index, autopct="%1.1f%%",
               colors=colors, startangle=90,
               wedgeprops={"edgecolor": "white", "linewidth": 2})
    else:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("通行结果分布", fontsize=12, fontweight="bold")

    # ④ 右下子图：高频人员横向排行
    ax = axes[3]
    if len(persons_top) > 0:
        labels = persons_top["name"].tolist()
        bars = ax.barh(labels, persons_top["count"], color=COLORS["line"],
                       alpha=0.85, edgecolor="white")
        # 柱右侧标注通行次数
        for bar, val in zip(bars, persons_top["count"]):
            ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                    str(int(val)), va="center", fontsize=9)
        ax.invert_yaxis()
        ax.grid(True, axis="x", alpha=0.3)
    else:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("人员通行排行", fontsize=12, fontweight="bold")

    path = ""
    # 保存整合大屏高清图片
    if save:
        path = os.path.join(CHART_DIR, "dashboard.png")
        plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.show()
    plt.close()
    return path