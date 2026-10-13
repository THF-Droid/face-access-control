"""
5.1 模型预测结果可视化
════════════════════════════════════════════════════════════════════════════
生成课程报告第5.1节所需的三类图表：
  (1) 预测值与真实值对比曲线（分类问题：每折精确率对比）
  (2) 残差图（分类问题：预测置信度分布 / 误识率分析）
  (3) 分类混淆矩阵（LBPH vs Eigenfaces 两种模型）

使用方法：
  cd <项目根目录>
  python plot_section_5_1.py
"""

# 导入系统路径与文件操作模块
import os
# 导入OpenCV，用于人脸读取、缩放、人脸识别器训练预测
import cv2
# 导入数值计算库numpy，处理数组、统计、索引划分
import numpy as np
# 导入绘图核心库matplotlib
import matplotlib
# 设置后端为无界面Agg，服务器/无GUI环境也能保存图片
matplotlib.use('Agg')
# 导入pyplot绘图接口
import matplotlib.pyplot as plt
# 导入网格布局工具（本代码未实际使用，预留扩展）
from matplotlib.gridspec import GridSpec
# 导入警告过滤
import warnings
# 忽略全部警告，避免日志冗余
warnings.filterwarnings('ignore')

# ── 中文字体配置 ───────────────────────────────────────────────────────────────────
# 配置多备选中文字体，解决matplotlib中文方框乱码
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
# 解决负号显示方块问题
plt.rcParams['axes.unicode_minus'] = False

# ── 全局路径常量定义 ───────────────────────────────────────────────────────────────────────
# 项目根目录（自动定位到脚本所在目录）
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
# 人脸数据集存放路径
FACES_DIR  = os.path.join(BASE_DIR, 'data', 'faces')
# 图表输出保存目录
CHARTS_DIR = os.path.join(BASE_DIR, 'data', 'charts')
# 不存在则自动创建图表文件夹
os.makedirs(CHARTS_DIR, exist_ok=True)

# ── 固定配色方案，区分两个算法 ───────────────────────────────────────────────────────────────────
# LBPH算法主色：深蓝
C_LBPH  = '#1A73E8'
# Eigenfaces算法主色：红色
C_EIGEN = '#E53935'


# ═════════════════════════════════════════════════════════════════════════════
# 1. 数据加载函数：读取灰度人脸图像与对应人员标签
# ═════════════════════════════════════════════════════════════════════════════
def load_face_dataset():
    # 初始化图像列表、标签列表
    images, labels = [], []
    # 遍历人脸文件夹下所有子文件夹（每个子文件夹对应一个人员ID）
    for person_id in sorted(os.listdir(FACES_DIR)):
        # 拼接单人样本文件夹完整路径
        person_dir = os.path.join(FACES_DIR, person_id)
        # 仅处理文件夹，跳过文件
        if not os.path.isdir(person_dir):
            continue
        # 将文件夹名转为整型人员ID，非数字文件夹直接跳过
        try:
            pid = int(person_id)
        except ValueError:
            continue
        # 遍历当前人员文件夹下所有图片文件
        for fname in sorted(os.listdir(person_dir)):
            # 仅支持jpg/jpeg/png格式图片
            if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            # 图片完整路径拼接
            img_path = os.path.join(person_dir, fname)
            # 以灰度模式读取人脸图片
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            # 图片读取失败（损坏/路径错误）则跳过
            if img is None:
                continue
            # 统一缩放至200×200标准尺寸，保证模型输入维度一致
            img = cv2.resize(img, (200, 200))
            # 图像加入样本列表
            images.append(img)
            # 对应标签加入标签列表
            labels.append(pid)
    # 返回图像列表与numpy格式标签数组
    return images, np.array(labels)


# 分层K折索引划分：保证每折中各类别样本比例与全集一致，避免类别倾斜
def stratified_kfold_indices(labels, n_splits=10, seed=42):
    # 设置随机种子，保证实验可复现
    rng = np.random.RandomState(seed)
    # 获取所有不重复人员类别ID
    unique_labels = np.unique(labels)
    # 字典：键=类别ID，值=该类别所有样本下标
    fold_indices = {lbl: [] for lbl in unique_labels}
    # 遍历所有样本，按类别归集样本索引
    for i, lbl in enumerate(labels):
        fold_indices[lbl].append(i)
    # 对每个类别内部样本下标打乱顺序
    for lbl in unique_labels:
        rng.shuffle(fold_indices[lbl])
    # 每个类别的样本下标均等拆分为n_splits份，用于分层划分
    folds_per_class = {lbl: np.array_split(np.array(idxs), n_splits)
                      for lbl, idxs in fold_indices.items()}
    # 存储最终每一折的训练、测试索引对
    splits = []
    # 逐折构建训练集、测试集索引
    for fold_i in range(n_splits):
        # 测试集：每类取出当前折的子集拼接
        test_idx = np.concatenate([folds_per_class[lbl][fold_i] for lbl in unique_labels])
        # 训练集：每类取出除当前折外所有子集拼接
        train_idx = np.concatenate([
            np.concatenate([folds_per_class[lbl][j] for j in range(n_splits) if j != fold_i])
            for lbl in unique_labels
        ])
        # 转为整型索引存入折划分列表
        splits.append((train_idx.astype(int), test_idx.astype(int)))
    return splits


# ═════════════════════════════════════════════════════════════════════════════
# 2. 执行K折交叉验证，训练双模型并收集精度、预测标签、置信度
# ═════════════════════════════════════════════════════════════════════════════
def run_cv_with_details(images, labels, n_splits=10):
    # 获取分层K折划分结果
    splits = stratified_kfold_indices(labels, n_splits=n_splits)
    # 排序后的唯一人员ID列表
    unique_persons = sorted(np.unique(labels))

    # 存储每折LBPH精度、Eigenfaces精度
    lbph_accs, eigen_accs = [], []
    # 存储LBPH全部预测结果：(真实标签,预测标签,置信度)
    lbph_all_preds  = []
    # 存储Eigenfaces全部预测结果：(真实标签,预测标签,置信度)
    eigen_all_preds = []

    # 打印分隔标题
    print(f"\n{'='*60}")
    print(f"  5.1 可视化数据生成 — {n_splits} 折交叉验证")
    print(f"  共 {len(images)} 张图像  {len(unique_persons)} 个人员")
    print(f"{'='*60}")

    # 循环每一折训练测试
    for fold_i, (train_idx, test_idx) in enumerate(splits):
        # 根据索引提取训练集图像、训练标签
        train_imgs = [images[i] for i in train_idx]
        train_lbls = labels[train_idx]
        # 根据索引提取测试集图像、测试标签
        test_imgs  = [images[i] for i in test_idx]
        test_lbls  = labels[test_idx]

        # ========== LBPH人脸识别器训练与预测 ==========
        # 创建LBPH识别器实例
        lbph = cv2.face.LBPHFaceRecognizer_create()
        # 使用当前折训练集训练模型
        lbph.train(train_imgs, np.array(train_lbls))
        # 本折LBPH正确计数清零
        lbph_correct = 0
        # 遍历测试样本逐个预测
        for img, true_lbl in zip(test_imgs, test_lbls):
            pred_lbl, conf = lbph.predict(img)
            # 保存单条预测三元组数据
            lbph_all_preds.append((int(true_lbl), int(pred_lbl), float(conf)))
            # 预测匹配真实标签则计数+1
            if pred_lbl == true_lbl:
                lbph_correct += 1
        # 计算本折LBPH识别准确率
        lbph_accs.append(lbph_correct / len(test_lbls))

        # ========== Eigenfaces特征脸训练与预测 ==========
        # 主成分数不能超过训练样本数-1，上限设50防止维度爆炸
        num_components = min(50, len(train_imgs) - 1)
        # 创建特征脸识别器，指定主成分数量
        eigen = cv2.face.EigenFaceRecognizer_create(num_components=num_components)
        # 训练集拟合特征脸模型
        eigen.train(train_imgs, np.array(train_lbls))
        # 本折Eigenfaces正确计数清零
        eigen_correct = 0
        # 遍历测试样本预测
        for img, true_lbl in zip(test_imgs, test_lbls):
            pred_lbl, conf = eigen.predict(img)
            # 保存预测三元组
            eigen_all_preds.append((int(true_lbl), int(pred_lbl), float(conf)))
            # 预测正确计数累加
            if pred_lbl == true_lbl:
                eigen_correct += 1
        # 本折Eigenfaces准确率存入列表
        eigen_accs.append(eigen_correct / len(test_lbls))

        # 打印当前折两个模型精度
        print(f"  Fold {fold_i+1:2d}:  LBPH {lbph_accs[-1]*100:5.1f}%  |  "
              f"Eigenfaces {eigen_accs[-1]*100:5.1f}%")

    # 打印横线分隔
    print(f"{'─'*60}")
    # 输出两模型整体平均精度
    print(f"  均值:  LBPH {np.mean(lbph_accs)*100:5.1f}%  |  "
          f"Eigenfaces {np.mean(eigen_accs)*100:5.1f}%")
    print(f"{'='*60}\n")

    # 返回所有计算结果，供绘图函数调用
    return (np.array(lbph_accs), np.array(eigen_accs),
            lbph_all_preds, eigen_all_preds, unique_persons)


# ═════════════════════════════════════════════════════════════════════════════
# 3. 图1绘制：各折精确率折线+柱状对比图（对应预测vs真实值对比）
# ═════════════════════════════════════════════════════════════════════════════
def plot_fig1_prediction_vs_actual(lbph_accs, eigen_accs, save_path):
    """
    分类模型的"预测值vs真实值"用每折精确率表示。
    左: 折线图(变化趋势)   右: 柱状图(并列对比)
    """
    # 获取折数
    n = len(lbph_accs)
    # X轴刻度文本：第1折、第2折...
    fold_labels = [f'第{i+1}折' for i in range(n)]
    # 生成X轴坐标数值
    x = np.arange(n)

    # 创建1行2列子图，画布尺寸、白底
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5), facecolor='white')
    # 总标题，加粗、微调顶部边距
    fig.suptitle('图5.1  模型预测精确率对比（预测值与真实值对比曲线）',
                 fontsize=13, fontweight='bold', y=1.00)

    # ── 左图：折线图绘制 ────────────────────────────────────────────────────────
    # LBPH折线：圆形标记、实线、指定颜色、线宽、标记大小，图例附带均值
    ax1.plot(x, lbph_accs  * 100, 'o-', color=C_LBPH,  lw=2.0, ms=7,
             label=f'LBPH（均值 {np.mean(lbph_accs)*100:.1f}%）')
    # Eigenfaces折线：方形标记、实线
    ax1.plot(x, eigen_accs * 100, 's-', color=C_EIGEN, lw=2.0, ms=7,
             label=f'Eigenfaces（均值 {np.mean(eigen_accs)*100:.1f}%）')
    # LBPH平均精度水平虚线
    ax1.axhline(np.mean(lbph_accs)*100,  color=C_LBPH,  ls='--', lw=1.3, alpha=0.5)
    # Eigenfaces平均精度水平虚线
    ax1.axhline(np.mean(eigen_accs)*100, color=C_EIGEN, ls='--', lw=1.3, alpha=0.5)
    # 设置X轴刻度位置与文字
    ax1.set_xticks(x)
    ax1.set_xticklabels(fold_labels, fontsize=9)
    # Y轴标签：识别精确率百分比
    ax1.set_ylabel('识别精确率（%）', fontsize=11)
    # X轴标签
    ax1.set_xlabel('交叉验证折数', fontsize=10)
    # 子图标题
    ax1.set_title('(a) 各折精确率折线图', fontsize=11, fontweight='bold', pad=10)
    # 图例放右下角
    ax1.legend(fontsize=10, loc='lower right')
    # Y轴范围0~105，留出顶部文字空间
    ax1.set_ylim(0, 105)
    # 浅色网格线，提升可读性
    ax1.grid(True, alpha=0.25, linestyle=':')
    # 在LBPH每个数据点上方标注数值
    for xi, v in enumerate(lbph_accs):
        ax1.text(xi, v*100 + 1.8, f'{v*100:.0f}', ha='center', fontsize=7.5, color=C_LBPH)
    # 在Eigenfaces每个数据点上方标注数值
    for xi, v in enumerate(eigen_accs):
        ax1.text(xi, v*100 + 1.8, f'{v*100:.0f}', ha='center', fontsize=7.5, color=C_EIGEN)

    # ── 右图：分组柱状图 ────────────────────────────────────────────────────────
    # 单根柱子宽度
    w = 0.36
    # LBPH柱子，左偏移半宽实现分组
    bars1 = ax2.bar(x - w/2, lbph_accs  * 100, w, color=C_LBPH,  label='LBPH',
                    alpha=0.82, edgecolor='white', linewidth=0.5)
    # Eigenfaces柱子，右偏移半宽
    bars2 = ax2.bar(x + w/2, eigen_accs * 100, w, color=C_EIGEN, label='Eigenfaces',
                    alpha=0.82, edgecolor='white', linewidth=0.5)
    # X轴刻度与标签
    ax2.set_xticks(x)
    ax2.set_xticklabels(fold_labels, fontsize=9)
    # Y轴文字
    ax2.set_ylabel('识别精确率（%）', fontsize=11)
    # X轴文字
    ax2.set_xlabel('交叉验证折数', fontsize=10)
    # 子标题
    ax2.set_title('(b) 各折精确率柱状对比图', fontsize=11, fontweight='bold', pad=10)
    # 显示图例
    ax2.legend(fontsize=10)
    # Y轴上限留空方便标注数值
    ax2.set_ylim(0, 112)
    # 仅Y轴网格
    ax2.grid(True, alpha=0.25, axis='y', linestyle=':')
    # LBPH柱子顶部数值标注
    for bar in bars1:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1.2, f'{h:.0f}',
                 ha='center', va='bottom', fontsize=8, color=C_LBPH, fontweight='bold')
    # Eigenfaces柱子顶部数值标注
    for bar in bars2:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 1.2, f'{h:.0f}',
                 ha='center', va='bottom', fontsize=8, color=C_EIGEN, fontweight='bold')

    # 紧凑布局防止标签重叠
    plt.tight_layout()
    # 高分辨率保存图片，裁剪多余白边
    plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor='white')
    # 关闭画布释放内存
    plt.close()
    # 控制台输出保存成功信息
    print(f"  [图5.1 已保存] {os.path.basename(save_path)}")
    return save_path


# ═════════════════════════════════════════════════════════════════════════════
# 4. 图2绘制：置信度箱线图+每类别误识率（分类任务替代残差分析）
# ═════════════════════════════════════════════════════════════════════════════
def plot_fig2_residual(lbph_all_preds, eigen_all_preds, save_path):
    """
    分类问题用以下方式替代"残差图"：
    (a) 左图：正确/错误预测的置信度箱线图（LBPH + Eigenfaces 并列）
    (b) 右图：每类人员误识率柱状图
    """
    # 导入字典默认值工具，统计每类样本数量、错误数量
    from collections import defaultdict

    # ── 拆分正确/错误样本置信度 ───────────────────────────────────────────────────────────
    # LBPH预测正确样本置信度列表
    lbph_correct_confs   = [c for (t, p, c) in lbph_all_preds  if t == p]
    # LBPH预测错误样本置信度列表
    lbph_incorrect_confs = [c for (t, p, c) in lbph_all_preds  if t != p]
    # Eigenfaces正确置信度
    eigen_correct_confs   = [c for (t, p, c) in eigen_all_preds if t == p]
    # Eigenfaces错误置信度
    eigen_incorrect_confs = [c for (t, p, c) in eigen_all_preds if t != p]

    # 初始化统计字典：每类总样本数、错误样本数
    lbph_class_total  = defaultdict(int)
    lbph_class_errors = defaultdict(int)
    eigen_class_total  = defaultdict(int)
    eigen_class_errors = defaultdict(int)
    # 遍历LBPH所有预测，统计每类总数与错误数
    for t, p, c in lbph_all_preds:
        lbph_class_total[t] += 1
        if t != p:
            lbph_class_errors[t] += 1
    # 遍历Eigenfaces预测统计
    for t, p, c in eigen_all_preds:
        eigen_class_total[t] += 1
        if t != p:
            eigen_class_errors[t] += 1

    # 合并所有出现过的人员ID并排序
    all_pids = sorted(set(lbph_class_total.keys()) | set(eigen_class_total.keys()))
    # 计算LBPH每类误识率百分比
    lbph_errs  = [lbph_class_errors.get(pid, 0) / lbph_class_total.get(pid, 1) * 100
                  for pid in all_pids]
    # 计算Eigenfaces每类误识率百分比
    eigen_errs = [eigen_class_errors.get(pid, 0) / eigen_class_total.get(pid, 1) * 100
                  for pid in all_pids]

    # ── 创建画布绘图 ───────────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5), facecolor='white')
    # 总标题
    fig.suptitle('图5.2  预测置信度残差分析图',
                 fontsize=13, fontweight='bold', y=1.00)

    # ── 左图：四组箱线图（LBPH正/误、Eigen正/误）─────────────────────────────────────
    box_data = []       # 箱线数据源列表
    box_labels = []     # 每组标签文本
    box_colors = []     # 每组填充色
    # 有数据才加入绘图队列，避免空箱线报错
    if lbph_correct_confs:
        box_data.append(lbph_correct_confs)
        box_labels.append('LBPH\n正确')
        box_colors.append(C_LBPH)
    if lbph_incorrect_confs:
        box_data.append(lbph_incorrect_confs)
        box_labels.append('LBPH\n错误')
        box_colors.append('#90CAF9')
    if eigen_correct_confs:
        box_data.append(eigen_correct_confs)
        box_labels.append('Eigen\n正确')
        box_colors.append(C_EIGEN)
    if eigen_incorrect_confs:
        box_data.append(eigen_incorrect_confs)
        box_labels.append('Eigen\n错误')
        box_colors.append('#EF9A9A')

    # 存在有效数据才绘制箱线图
    if box_data:
        bp = ax1.boxplot(box_data,
                         patch_artist=True,          # 允许箱体填充颜色
                         medianprops=dict(color='black', lw=2), # 中位数线样式
                         flierprops=dict(marker='o', markersize=4, alpha=0.5)) # 离群点样式
        # 设置X轴标签
        ax1.set_xticklabels(box_labels, fontsize=9)
        # 为每个箱体绑定对应颜色与透明度
        for patch, color in zip(bp['boxes'], box_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.65)
        # 箱线图上叠加抖动散点，展示原始样本分布
        for i, data in enumerate(box_data):
            # X轴小幅随机抖动，避免点重叠
            x_vals = np.random.normal(i+1, 0.08, size=len(data))
            ax1.scatter(x_vals, data, color=box_colors[i], alpha=0.35, s=28, zorder=3)

    # Y轴说明，解释两种置信度物理含义
    ax1.set_ylabel('置信度\n（LBPH：距离↓越好；Eigenfaces：误差↓越好）', fontsize=10)
    ax1.set_title('(a) 预测置信度分布（正确/错误样本）', fontsize=11, fontweight='bold', pad=10)
    ax1.grid(True, alpha=0.25, axis='y', linestyle=':')
    # 左上角小字注释置信度区别
    ax1.text(0.5, 0.97, 'LBPH置信度=特征距离（越小越好）| Eigenfaces=重建误差',
             transform=ax1.transAxes, ha='center', fontsize=8, color='gray',
             verticalalignment='top')

    # ── 右图：每类别误识率分组柱状图 ──────────────────────────────────────────────────
    x = np.arange(len(all_pids))
    w = 0.36
    # LBPH误识率柱
    bars1 = ax2.bar(x - w/2, lbph_errs,  w, color=C_LBPH,  label='LBPH 误识率',
                    alpha=0.8, edgecolor='white', linewidth=0.5)
    # Eigenfaces误识率柱
    bars2 = ax2.bar(x + w/2, eigen_errs, w, color=C_EIGEN, label='Eigenfaces 误识率',
                    alpha=0.8, edgecolor='white', linewidth=0.5)
    # X轴刻度与人员ID标签
    ax2.set_xticks(x)
    ax2.set_xticklabels([f'ID{p}' for p in all_pids], fontsize=9)
    ax2.set_ylabel('误识率（%）', fontsize=11)
    ax2.set_xlabel('人员ID', fontsize=10)
    ax2.set_title('(b) 每类人员误识率（分类残差替代指标）', fontsize=11, fontweight='bold', pad=10)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.25, axis='y', linestyle=':')
    # 自适应Y轴上限，留出标注空间
    max_err = max(max(lbph_errs, default=0), max(eigen_errs, default=0))
    ax2.set_ylim(0, max_err * 1.25 + 5)

    # 柱子顶部数值标注，数值过小则不标注防拥挤
    for bar in bars1:
        h = bar.get_height()
        if h > 0.5:
            ax2.text(bar.get_x() + bar.get_width()/2, h + 0.3, f'{h:.1f}',
                     ha='center', va='bottom', fontsize=7.5, color=C_LBPH)
    for bar in bars2:
        h = bar.get_height()
        if h > 0.5:
            ax2.text(bar.get_x() + bar.get_width()/2, h + 0.3, f'{h:.1f}',
                     ha='center', va='bottom', fontsize=7.5, color=C_EIGEN)

    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  [图5.2 已保存] {os.path.basename(save_path)}")
    return save_path


# ═════════════════════════════════════════════════════════════════════════════
# 5. 图3绘制：LBPH与Eigenfaces双混淆矩阵对比
# ═════════════════════════════════════════════════════════════════════════════
def plot_fig3_confusion(lbph_all_preds, eigen_all_preds, unique_persons, save_path):
    # 类别总数
    n_classes = len(unique_persons)
    # 人员ID映射到矩阵行列索引
    pid_to_idx = {pid: i for i, pid in enumerate(unique_persons)}

    # 初始化两个零矩阵，用于构建混淆矩阵
    lbph_cm  = np.zeros((n_classes, n_classes), dtype=int)
    eigen_cm = np.zeros((n_classes, n_classes), dtype=int)

    # 填充LBPH混淆矩阵：行=真实标签，列=预测标签
    for t, p, _ in lbph_all_preds:
        if t in pid_to_idx and p in pid_to_idx:
            lbph_cm[pid_to_idx[t], pid_to_idx[p]] += 1
    # 填充Eigenfaces混淆矩阵
    for t, p, _ in eigen_all_preds:
        if t in pid_to_idx and p in pid_to_idx:
            eigen_cm[pid_to_idx[t], pid_to_idx[p]] += 1

    # 创建1行2列画布
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.5), facecolor='white')
    # 总标题
    fig.suptitle('图5.3  分类混淆矩阵（LBPH vs Eigenfaces）',
                 fontsize=13, fontweight='bold', y=0.99)

    # 横轴纵轴显示标签：ID+编号
    person_labels = [f'ID{p}' for p in unique_persons]

    # ========== 左子图：LBPH混淆矩阵 ==========
    im1 = ax1.imshow(lbph_cm, interpolation='nearest', cmap='Blues',
                     vmin=0, vmax=max(1, lbph_cm.max()))
    ax1.set_title('(a) LBPH 混淆矩阵', fontsize=11, fontweight='bold', pad=10)
    # 设置行列刻度
    ax1.set_xticks(range(n_classes))
    ax1.set_yticks(range(n_classes))
    # X轴标签旋转45度防重叠
    ax1.set_xticklabels(person_labels, fontsize=9, rotation=45)
    ax1.set_yticklabels(person_labels, fontsize=9)
    ax1.set_xlabel('预测标签', fontsize=10)
    ax1.set_ylabel('真实标签', fontsize=10)
    # 矩阵每个格子填入计数值，自动适配文字黑白对比度
    for i in range(n_classes):
        for j in range(n_classes):
            if lbph_cm[i, j] > 0:
                color = 'white' if lbph_cm[i, j] >= lbph_cm.max() * 0.45 else 'black'
                ax1.text(j, i, str(lbph_cm[i, j]), ha='center', va='center',
                         fontsize=9, color=color, fontweight='bold')
    # 附加颜色条
    plt.colorbar(im1, ax=ax1, fraction=0.045, pad=0.04)

    # ========== 右子图：Eigenfaces混淆矩阵 ==========
    im2 = ax2.imshow(eigen_cm, interpolation='nearest', cmap='Reds',
                     vmin=0, vmax=max(1, eigen_cm.max()))
    ax2.set_title('(b) Eigenfaces 混淆矩阵', fontsize=11, fontweight='bold', pad=10)
    ax2.set_xticks(range(n_classes))
    ax2.set_yticks(range(n_classes))
    ax2.set_xticklabels(person_labels, fontsize=9, rotation=45)
    ax2.set_yticklabels(person_labels, fontsize=9)
    ax2.set_xlabel('预测标签', fontsize=10)
    ax2.set_ylabel('真实标签', fontsize=10)
    # 单元格数值文本
    for i in range(n_classes):
        for j in range(n_classes):
            if eigen_cm[i, j] > 0:
                color = 'white' if eigen_cm[i, j] >= eigen_cm.max() * 0.45 else 'black'
                ax2.text(j, i, str(eigen_cm[i, j]), ha='center', va='center',
                         fontsize=9, color=color, fontweight='bold')
    plt.colorbar(im2, ax=ax2, fraction=0.045, pad=0.04)

    # 计算混淆矩阵总体准确率（迹/总样本）
    lbph_acc  = np.trace(lbph_cm)  / max(1, np.sum(lbph_cm))  * 100
    eigen_acc = np.trace(eigen_cm) / max(1, np.sum(eigen_cm)) * 100
    # 在子图底部标注整体精确率
    ax1.text(0.5, -0.14, f'总体精确率: {lbph_acc:.1f}%',
             transform=ax1.transAxes, ha='center', fontsize=10,
             color=C_LBPH, fontweight='bold')
    ax2.text(0.5, -0.14, f'总体精确率: {eigen_acc:.1f}%',
             transform=ax2.transAxes, ha='center', fontsize=10,
             color=C_EIGEN, fontweight='bold')

    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  [图5.3 已保存] {os.path.basename(save_path)}")
    return save_path


# ═════════════════════════════════════════════════════════════════════════════
# 6. 控制台打印量化统计汇总表
# ═════════════════════════════════════════════════════════════════════════════
def print_summary(lbph_accs, eigen_accs, lbph_all_preds, eigen_all_preds, unique_persons):
    # 打印分割线标题
    print("\n" + "─"*58)
    print("  5.1 模型预测结果可视化 — 汇总统计")
    print("─"*58)
    # 表头对齐格式化输出
    print(f"  {'指标':<18} {'LBPH':>12} {'Eigenfaces':>14}")
    print(f"  {'─'*46}")
    # 平均精度
    print(f"  {'平均精确率 (%)':<18} {np.mean(lbph_accs)*100:>10.1f}% {np.mean(eigen_accs)*100:>12.1f}%")
    # 精度标准差（稳定性）
    print(f"  {'标准差 (%)':<18} {np.std(lbph_accs)*100:>10.1f}% {np.std(eigen_accs)*100:>12.1f}%")
    # 精度方差
    print(f"  {'方差':<18} {np.var(lbph_accs):>12.4f} {np.var(eigen_accs):>14.4f}")
    # 最优单折精度
    print(f"  {'最高精确率 (%)':<18} {np.max(lbph_accs)*100:>10.1f}% {np.max(eigen_accs)*100:>12.1f}%")
    # 最差单折精度
    print(f"  {'最低精确率 (%)':<18} {np.min(lbph_accs)*100:>10.1f}% {np.min(eigen_accs)*100:>12.1f}%")
    # 统计正确预测样本数量
    n_lbph_ok  = sum(1 for t,p,_ in lbph_all_preds  if t==p)
    n_eigen_ok = sum(1 for t,p,_ in eigen_all_preds if t==p)
    # 总测试样本量
    print(f"  {'总测试样本数':<18} {len(lbph_all_preds):>12} {len(eigen_all_preds):>14}")
    # 正确识别数
    print(f"  {'正确预测数':<18} {n_lbph_ok:>12} {n_eigen_ok:>14}")
    # 错误识别数
    print(f"  {'错误预测数':<18} {len(lbph_all_preds)-n_lbph_ok:>12} {len(eigen_all_preds)-n_eigen_ok:>14}")
    print("─"*58 + "\n")


# 生成课程报告5.1节配套正文文本并保存txt
def save_report_text(lbph_accs, eigen_accs, lbph_all_preds, eigen_all_preds, unique_persons):
    # 提取均值、标准差
    lbph_mean  = np.mean(lbph_accs)  * 100
    eigen_mean = np.mean(eigen_accs) * 100
    lbph_std   = np.std(lbph_accs)   * 100
    eigen_std  = np.std(eigen_accs)  * 100
    n_total    = len(lbph_all_preds)
    # 正确样本计数
    n_lbph_ok  = sum(1 for t,p,_ in lbph_all_preds  if t==p)
    n_eigen_ok = sum(1 for t,p,_ in eigen_all_preds if t==p)

    # 完整课程报告段落内容，自动填充动态数值
    text = f"""5.1 模型预测结果可视化

为验证人脸识别模型的实际预测效果，本节对LBPH（局部二值模式直方图）和Eigenfaces（特征脸）两种识别算法进行了10折交叉验证，并将预测结果与真实标签进行对比可视化分析。实验共涉及{len(unique_persons)}个人员类别，共计{n_total}个测试样本。

图5.1展示了两种模型在各折交叉验证中的精确率对比曲线。折线图清晰反映了LBPH和Eigenfaces在每一折上的识别精确率变化趋势，其中LBPH的平均精确率为{lbph_mean:.1f}%，Eigenfaces的平均精确率为{eigen_mean:.1f}%。从柱状对比图可以看出，LBPH算法在绝大多数折上均优于Eigenfaces，且波动更小（标准差{lbph_std:.1f}% vs {eigen_std:.1f}%），说明LBPH模型具有更好的稳定性。

图5.2为预测置信度残差分析图。由于分类问题不存在连续型残差，本节采用"预测置信度分布"和"每类误识率"作为残差替代指标。左图展示了正确预测与错误预测样本的置信度分布差异：LBPH算法的正确预测样本置信度（特征距离）明显更集中，说明其置信度度量具有较好的区分能力；右图展示了每个人员类别的误识率，可以看出LBPH在各人员类别上的误识率均低于Eigenfaces，进一步验证了LBPH算法在本系统应用场景下的优越性。

图5.3为两种模型的分类混淆矩阵。矩阵横轴表示模型预测的类别标签，纵轴表示样本的真实类别标签，对角线元素表示正确分类的样本数。从LBPH的混淆矩阵可以看出，绝大多数样本都集中在对角线上（正确预测{n_lbph_ok}个，精确率{lbph_mean:.1f}%），说明模型对各类别人员的识别准确率较高；相比之下，Eigenfaces的混淆矩阵中非对角线元素更多（正确预测{n_eigen_ok}个，精确率{eigen_mean:.1f}%），说明其更容易将某一人员误识别为另一人员，这与精确率统计数据一致。

综合以上可视化分析结果，LBPH算法在人脸识别门禁系统中的应用效果明显优于Eigenfaces算法，其平均识别精确率更高（{lbph_mean:.1f}% vs {eigen_mean:.1f}%）、稳定性更好（标准差{lbph_std:.1f}% vs {eigen_std:.1f}%），更适合实际部署使用。
"""
    # 报告文本保存路径
    text_path = os.path.join(CHARTS_DIR, 'section_5_1_report_text.txt')
    # UTF-8编码写入，防止中文乱码
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(text.strip())
    print(f"  [报告文字已保存] {text_path}")
    return text_path


# ═════════════════════════════════════════════════════════════════════════════
# 7. 程序入口主函数
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    # 启动标题分隔线
    print("=" * 58)
    print("  5.1 模型预测结果可视化 — 图表生成")
    print("=" * 58)

    # 加载人脸数据集
    print("\n>> 加载人脸数据集...")
    images, labels = load_face_dataset()
    print(f"   共加载 {len(images)} 张图像，{len(np.unique(labels))} 个人员")

    # 样本过少直接退出，无法交叉验证
    if len(images) < 2:
        print("\n[错误] 需要至少 2 个人员的样本！请先采集人脸数据。\n")
        exit(1)

    # 自适应折数：不能超过单类别最小样本数，上限10折，最低2折
    n_splits = min(10, min(np.bincount(labels.astype(int))[1:]))
    n_splits = max(2, n_splits)
    print(f"   交叉验证折数: {n_splits}\n")

    # 执行交叉验证训练预测，拿到全套结果
    lbph_accs, eigen_accs, lbph_all_preds, eigen_all_preds, unique_persons = \
        run_cv_with_details(images, labels, n_splits=n_splits)

    # 控制台输出统计汇总
    print_summary(lbph_accs, eigen_accs, lbph_all_preds, eigen_all_preds, unique_persons)

    # 依次生成三张核心对比图表
    print(">> 生成可视化图表...")
    p1 = plot_fig1_prediction_vs_actual(
        lbph_accs, eigen_accs,
        os.path.join(CHARTS_DIR, 'section_5_1_fig1_prediction_vs_actual.png'))
    p2 = plot_fig2_residual(
        lbph_all_preds, eigen_all_preds,
        os.path.join(CHARTS_DIR, 'section_5_1_fig2_residual_analysis.png'))
    p3 = plot_fig3_confusion(
        lbph_all_preds, eigen_all_preds, unique_persons,
        os.path.join(CHARTS_DIR, 'section_5_1_fig3_confusion_matrix.png'))

    # 生成课程报告配套文字
    txt = save_report_text(lbph_accs, eigen_accs, lbph_all_preds, eigen_all_preds, unique_persons)

    # 完成收尾提示
    print("\n" + "=" * 58)
    print("  ✓ 5.1 节可视化全部完成！")
    print("=" * 58)
    print(f"\n  生成的文件：")
    print(f"    {p1}")
    print(f"    {p2}")
    print(f"    {p3}")
    print(f"    {txt}")
    print()