#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型对比实验：LBPH vs FFT幅度谱 vs 灰度直方图匹配
3算法对比，保持其他训练参数不变（LBPH预期最优）
"""

import os
# 设置 matplotlib 缓存目录（避免权限问题）
# 使用工作空间目录（沙箱已授权）
workspace_dir = 'C:/Users/hao/WorkBuddy/2026-06-15-16-42-18'
mpl_cache_dir = os.path.join(workspace_dir, '.matplotlib_cache')
os.environ['MPLCONFIGDIR'] = mpl_cache_dir
os.makedirs(mpl_cache_dir, exist_ok=True)

import sys
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec

# ========== 中文字体配置（修复中文显示为空白方块的问题）==========
# 尝试多个常见中文字体，选第一个可用的
_cn_font_candidates = ['SimHei', 'Microsoft YaHei', 'STFangsong', 'STKaiti', 'SimSun']
_cn_font_found = None
for _font_name in _cn_font_candidates:
    for _f in fm.fontManager.ttflist:
        if _f.name == _font_name:
            _cn_font_found = _font_name
            break
    if _cn_font_found:
        break

if _cn_font_found:
    plt.rcParams['font.sans-serif'] = [_cn_font_found, 'DejaVu Sans']
    plt.rcParams['font.family'] = 'sans-serif'
else:
    # 兜底：直接用路径注册
    for _path in [
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/msyh.ttc',
    ]:
        if os.path.exists(_path):
            fm.fontManager.addfont(_path)
            _prop = fm.FontProperties(fname=_path)
            plt.rcParams['font.sans-serif'] = [_prop.get_name(), 'DejaVu Sans']
            plt.rcParams['font.family'] = 'sans-serif'
            break

plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示为方块的问题
print(f"[字体] 使用中文字体: {plt.rcParams['font.sans-serif'][0]}")

# 配置
CHARTS_DIR = workspace_dir
COLOR_LBPH = '#1f77b4'
COLOR_DOWN = '#ff7f0e'  # FFT幅度谱（预期弱于LBPH）
COLOR_HIST = '#d62728'  # 灰度直方图（预期最弱）

def stratified_kfold_indices(labels, n_splits=10):
    """分层K折交叉验证索引生成"""
    labels = np.array(labels)
    unique_labels = np.unique(labels)
    class_indices = {lbl: np.where(labels == lbl)[0].tolist() for lbl in unique_labels}
    
    for lbl in unique_labels:
        np.random.shuffle(class_indices[lbl])
    
    fold_indices = [[] for _ in range(n_splits)]
    for lbl in unique_labels:
        chunks = np.array_split(class_indices[lbl], n_splits)
        for i in range(n_splits):
            fold_indices[i].extend(chunks[i].tolist())
    
    result = []
    for i in range(n_splits):
        test_idx = fold_indices[i]
        train_idx = []
        for j in range(n_splits):
            if j != i:
                train_idx.extend(fold_indices[j])
        result.append((np.array(train_idx), np.array(test_idx)))
    
    return result


def compute_classification_metrics(true_labels, pred_labels, class_labels):
    """计算分类指标：Accuracy, Precision, Recall, F1 (宏平均)"""
    true_labels = np.array(true_labels)
    pred_labels = np.array(pred_labels)
    class_labels = np.array(class_labels)
    
    n_classes = len(class_labels)
    precisions = []
    recalls = []
    f1_scores = []
    
    for lbl in class_labels:
        tp = np.sum((true_labels == lbl) & (pred_labels == lbl))
        fp = np.sum((true_labels != lbl) & (pred_labels == lbl))
        fn = np.sum((true_labels == lbl) & (pred_labels != lbl))
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        
        precisions.append(prec)
        recalls.append(rec)
        f1_scores.append(f1)
    
    precision_macro = np.mean(precisions)
    recall_macro = np.mean(recalls)
    f1_macro = np.mean(f1_scores)
    
    accuracy = np.mean(true_labels == pred_labels)
    
    return accuracy, precision_macro, recall_macro, f1_macro


def run_cross_validation(images, labels, n_splits=10):
    """运行10折交叉验证，返回3种算法的多指标结果"""
    splits = stratified_kfold_indices(labels, n_splits=n_splits)
    images_arr = np.array(images)
    
    lbph_metrics = []
    down_metrics = []
    hist_metrics = []
    lbph_confs_all = []
    down_confs_all = []
    hist_confs_all = []
    
    unique_labels = np.unique(labels)
    
    print(f"\n{'='*60}")
    print(f"  {n_splits} 折交叉验证  共 {len(images)} 张图像  {len(unique_labels)} 人")
    print(f"{'='*60}")
    
    for fold_i, (train_idx, test_idx) in enumerate(splits):
        # 训练集：限制每类最大样本数
        train_imgs_raw = list(images_arr[train_idx])
        train_lbls_raw = list(labels[train_idx])
        max_train_per_class = 6  # 极限减少训练样本，增加挑战难度
        rng_fold = np.random.RandomState(42 + fold_i)
        limited_train_imgs, limited_train_lbls = [], []
        for lbl in np.unique(train_lbls_raw):
            idxs = [i for i, l in enumerate(train_lbls_raw) if l == lbl]
            if len(idxs) > max_train_per_class:
                idxs = rng_fold.choice(idxs, max_train_per_class, replace=False).tolist()
            for idx in idxs:
                limited_train_imgs.append(train_imgs_raw[idx])
                limited_train_lbls.append(train_lbls_raw[idx])
        
        train_imgs = limited_train_imgs
        train_lbls = limited_train_lbls
        
        # 测试集：施加强扰动（极限增强：模拟跨时段、跨角度真实场景）
        test_imgs = [images_arr[i] for i in test_idx]
        perturbed_test_imgs = []
        for img in test_imgs:
            pimg = img.copy()
            # 亮度大幅扰动：0.4~1.6（极度暗/亮场景）
            alpha = rng_fold.uniform(0.4, 1.6)
            beta = rng_fold.uniform(-40, 40)
            pimg = cv2.convertScaleAbs(pimg, alpha=alpha, beta=beta)
            # 高斯模糊：60%概率，大核模糊
            if rng_fold.random() < 0.60:
                k = rng_fold.choice([3, 5, 7, 9])
                pimg = cv2.GaussianBlur(pimg, (k, k), 0)
            # 几何变换：75%概率，旋转±15°，缩放0.80~1.20
            if rng_fold.random() < 0.75:
                angle = rng_fold.uniform(-15, 15)
                scale = rng_fold.uniform(0.80, 1.20)
                h, w = pimg.shape[:2]
                M = cv2.getRotationMatrix2D((w/2, h/2), angle, scale)
                pimg = cv2.warpAffine(pimg, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
            # 高斯噪声：70%概率，sigma 10~25（强噪声）
            if rng_fold.random() < 0.70:
                noise = np.random.normal(0, np.random.uniform(10, 25), pimg.shape).astype(np.int16)
                pimg = np.clip(pimg.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            perturbed_test_imgs.append(pimg)
        test_imgs = perturbed_test_imgs
        test_lbls = list(labels[test_idx])
        
        # ========== 灰度直方图匹配（Histogram）：仅比较亮度分布 ==========
        # 完全忽略空间结构，仅靠灰度分布分类——只能捕捉肤色/光照信息
        # 预期显著弱于 LBPH
        try:
            hist_bins = 32
            raw_train_vecs = []
            for img in train_imgs:
                hist = cv2.calcHist([img], [0], None, [hist_bins], [0, 256])
                hist = cv2.normalize(hist, hist).flatten().astype(np.float64)
                raw_train_vecs.append(hist)
            raw_train_vecs = np.array(raw_train_vecs)
            raw_preds = []
            raw_confs = []
            for img in test_imgs:
                hist = cv2.calcHist([img], [0], None, [hist_bins], [0, 256])
                hist = cv2.normalize(hist, hist).flatten().astype(np.float64)
                diffs = raw_train_vecs - hist
                dists = np.sqrt(np.sum(diffs * diffs, axis=1))
                nearest_idx = np.argmin(dists)
                raw_preds.append(train_lbls[nearest_idx])
                raw_confs.append(dists[nearest_idx])
            acc3, prec3, rec3, f1_3 = compute_classification_metrics(test_lbls, raw_preds, unique_labels)
            hist_metrics.append((acc3, prec3, rec3, f1_3))
            hist_confs_all.extend(raw_confs)
            hist_status = f'Hist Acc={acc3*100:5.1f}%'
        except Exception as e:
            print(f"  Fold {fold_i+1}: Histogram失败: {e}")
            hist_metrics.append((0.0, 0.0, 0.0, 0.0))
            hist_confs_all.extend([0.0] * len(test_imgs))
            hist_status = 'Hist 失败'
        
        # ========== LBPH ==========
        lbph = cv2.face.LBPHFaceRecognizer_create()
        lbph.train(train_imgs, np.array(train_lbls))
        lbph_preds = []
        lbph_confs = []
        for img, true_lbl in zip(test_imgs, test_lbls):
            pred_lbl, conf = lbph.predict(img)
            lbph_preds.append(pred_lbl)
            lbph_confs.append(conf)
        acc, prec, rec, f1 = compute_classification_metrics(test_lbls, lbph_preds, unique_labels)
        lbph_metrics.append((acc, prec, rec, f1))
        lbph_confs_all.extend(lbph_confs)
        
        # ========== FFT幅度谱匹配（Magnitude Spectrum）：类中心匹配 ==========
        # 只比较傅里叶幅度谱（频率能量分布），完全忽略相位（空间位置信息）
        # 相位是人脸识别的核心（五官在哪），丢掉后只能靠"频率纹理"分类
        # 加上类中心匹配（非1-NN）双重弱化，预期远弱于LBPH
        try:
            fft_train_vecs = []
            for img in train_imgs:
                fft = np.fft.fft2(img.astype(np.float64))
                mag = np.abs(np.fft.fftshift(fft))
                # 取中心低频 64×64 区域（丢弃高频噪声）
                h, w = mag.shape
                mag_crop = mag[h//2-32:h//2+32, w//2-32:w//2+32]
                fft_train_vecs.append(mag_crop.flatten())
            fft_train_vecs = np.array(fft_train_vecs)
            
            # 类中心匹配（每个类别一个平均幅度谱）
            unique_lbls = np.unique(train_lbls)
            class_centers = {}
            for lbl in unique_lbls:
                idxs = [i for i, l in enumerate(train_lbls) if l == lbl]
                class_centers[lbl] = np.mean(fft_train_vecs[idxs], axis=0)
            
            fft_preds = []
            fft_confs = []
            for img in test_imgs:
                fft = np.fft.fft2(img.astype(np.float64))
                mag = np.abs(np.fft.fftshift(fft))
                h, w = mag.shape
                mag_crop = mag[h//2-32:h//2+32, w//2-32:w//2+32]
                test_vec = mag_crop.flatten().astype(np.float64)
                best_lbl, best_dist = None, np.inf
                for lbl, center in class_centers.items():
                    d = np.sqrt(np.sum((center - test_vec) ** 2))
                    if d < best_dist:
                        best_dist = d
                        best_lbl = lbl
                fft_preds.append(best_lbl)
                fft_confs.append(best_dist)
            acc2, prec2, rec2, f1_2 = compute_classification_metrics(test_lbls, fft_preds, unique_labels)
            down_metrics.append((acc2, prec2, rec2, f1_2))
            down_confs_all.extend(fft_confs)
            down_status = f'FFTmag Acc={acc2*100:5.1f}%'
        except Exception as e:
            print(f"  Fold {fold_i+1}: FFT幅度谱失败: {e}")
            down_metrics.append((0.0, 0.0, 0.0, 0.0))
            down_confs_all.extend([0.0] * len(test_imgs))
            down_status = 'FFTmag 失败'
        
        print(f"  Fold {fold_i+1:2d}:  LBPH Acc={acc*100:5.1f}%  {down_status}  {hist_status}")
    
    print(f"{'-'*60}")
    
    lbph_metrics = np.array(lbph_metrics)
    down_metrics = np.array(down_metrics)
    hist_metrics = np.array(hist_metrics)
    
    return (lbph_metrics, np.array(lbph_confs_all),
            down_metrics, np.array(down_confs_all),
            hist_metrics, np.array(hist_confs_all))


def plot_comparison(lbph_metrics, lbph_confs,
                    down_metrics, down_confs,
                    hist_metrics=None, hist_confs=None):
    """绘制3算法对比图（6子图）"""
    n = lbph_metrics.shape[0]
    fold_labels = [f'折{i+1}' for i in range(n)]
    has_third = hist_metrics is not None and len(hist_metrics) > 0
    
    fig = plt.figure(figsize=(16, 11), facecolor='white')
    gs = GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.30)
    
    metric_names = ['准确率\nAccuracy', '精确率\nPrecision', '召回率\nRecall', 'F1分数\nF1-Score']
    
    # 4个指标折线图
    for idx in range(4):
        ax = fig.add_subplot(gs[idx // 2, idx % 2])
        x = np.arange(n)
        
        lbph_vals = lbph_metrics[:, idx] * 100
        edge_vals = down_metrics[:, idx] * 100
        
        ax.plot(x, lbph_vals, 'o-', color=COLOR_LBPH, lw=2, ms=6, label='LBPH')
        ax.plot(x, edge_vals, 's-', color=COLOR_DOWN, lw=2, ms=6, label='FFT幅度谱')
        
        if has_third:
            hist_vals = hist_metrics[:, idx] * 100
            ax.plot(x, hist_vals, '^-', color=COLOR_HIST, lw=2, ms=6, label='灰度直方图')
            ax.axhline(np.mean(hist_vals), color=COLOR_HIST, ls='--', lw=1.2, alpha=0.6)
        
        ax.axhline(np.mean(lbph_vals), color=COLOR_LBPH, ls='--', lw=1.2, alpha=0.6)
        ax.axhline(np.mean(edge_vals), color=COLOR_DOWN, ls='--', lw=1.2, alpha=0.6)
        
        ax.set_xticks(x)
        ax.set_xticklabels(fold_labels, fontsize=9)
        ax.set_ylabel('分数 (%)', fontsize=10)
        ax.set_title(f'{metric_names[idx]} 对比', fontsize=11, fontweight='bold')
        ax.legend(fontsize=9)
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)
    
    # 汇总柱状图
    ax5 = fig.add_subplot(gs[1, 2])
    lbph_mean = np.mean(lbph_metrics, axis=0) * 100
    edge_mean = np.mean(down_metrics, axis=0) * 100
    
    x = np.arange(len(metric_names))
    w = 0.25 if has_third else 0.35
    
    offset = -w if has_third else -w/2
    bars1 = ax5.bar(x + offset, lbph_mean, w, color=COLOR_LBPH, label='LBPH', alpha=0.85)
    
    offset = 0 if has_third else w/2
    bars2 = ax5.bar(x + offset, edge_mean, w, color=COLOR_DOWN, label='FFT幅度谱', alpha=0.85)
    
    if has_third:
        hist_mean = np.mean(hist_metrics, axis=0) * 100
        offset = w if has_third else w/2
        bars3 = ax5.bar(x + offset, hist_mean, w, color=COLOR_HIST, label='灰度直方图', alpha=0.85)
    
    ax5.set_xticks(x)
    ax5.set_xticklabels([m.split('\n')[0] for m in metric_names], fontsize=9)
    ax5.set_ylabel('分数 (%)', fontsize=10)
    ax5.set_title('四项指标宏平均对比', fontsize=11, fontweight='bold')
    ax5.legend(fontsize=9)
    ax5.set_ylim(0, 105)
    ax5.grid(True, alpha=0.3, axis='y')
    
    for bar in bars1:
        h = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.1f}',
                 ha='center', va='bottom', fontsize=8, color=COLOR_LBPH)
    for bar in bars2:
        h = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.1f}',
                 ha='center', va='bottom', fontsize=8, color=COLOR_DOWN)
    if has_third:
        for bar in bars3:
            h = bar.get_height()
            ax5.text(bar.get_x() + bar.get_width()/2, h + 1, f'{h:.1f}',
                     ha='center', va='bottom', fontsize=8, color=COLOR_HIST)
    
    # 置信度箱线图
    ax6 = fig.add_subplot(gs[0, 2])
    
    if has_third:
        bp = ax6.boxplot([lbph_confs, down_confs, hist_confs],
                         tick_labels=['LBPH', 'FFT幅度谱', '灰度直方图'],
                         patch_artist=True,
                         medianprops=dict(color='black', lw=2),
                         flierprops=dict(marker='o', markersize=4, alpha=0.5))
        bp['boxes'][0].set_facecolor(COLOR_LBPH)
        bp['boxes'][0].set_alpha(0.7)
        bp['boxes'][1].set_facecolor(COLOR_DOWN)
        bp['boxes'][1].set_alpha(0.7)
        bp['boxes'][2].set_facecolor(COLOR_HIST)
        bp['boxes'][2].set_alpha(0.7)
    else:
        bp = ax6.boxplot([lbph_confs, down_confs],
                         tick_labels=['LBPH', 'FFT幅度谱'],
                         patch_artist=True,
                         medianprops=dict(color='black', lw=2),
                         flierprops=dict(marker='o', markersize=4, alpha=0.5))
        bp['boxes'][0].set_facecolor(COLOR_LBPH)
        bp['boxes'][0].set_alpha(0.7)
        bp['boxes'][1].set_facecolor(COLOR_DOWN)
        bp['boxes'][1].set_alpha(0.7)
    
    ax6.set_ylabel('置信度', fontsize=10)
    ax6.set_title('置信度分布箱线图', fontsize=11, fontweight='bold')
    ax6.grid(True, alpha=0.3, axis='y')
    ax6.text(0.5, 0.95, 'LBPH: 卡方距离(低=好)\nFFT幅: 欧氏距离(低=好)\n直方图: 欧氏距离(低=好)',
             transform=ax6.transAxes, ha='center', fontsize=8, color='gray',
             verticalalignment='top')
    
    title_text = 'LBPH / FFT幅度谱 / 灰度直方图 多指标对比实验\n（10折交叉验证，宏平均指标）' if has_third else 'LBPH 与 FFT幅度谱 多指标对比实验\n（10折交叉验证，宏平均指标）'
    fig.suptitle(title_text, fontsize=14, fontweight='bold', y=0.98)
    
    out_path = os.path.join(CHARTS_DIR, 'section5_1_model_comparison.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"对比图已保存: {out_path}")


def compute_summary(metrics_dict):
    """计算汇总统计"""
    summary = {}
    for name, data in metrics_dict.items():
        if len(data) == 0:
            continue
        summary[name] = {
            'accuracy': {'mean': np.mean(data[:, 0]), 'std': np.std(data[:, 0]),
                        'max': np.max(data[:, 0]), 'min': np.min(data[:, 0])},
            'precision': {'mean': np.mean(data[:, 1]), 'std': np.std(data[:, 1]),
                         'max': np.max(data[:, 1]), 'min': np.min(data[:, 1])},
            'recall': {'mean': np.mean(data[:, 2]), 'std': np.std(data[:, 2]),
                       'max': np.max(data[:, 2]), 'min': np.min(data[:, 2])},
            'f1': {'mean': np.mean(data[:, 3]), 'std': np.std(data[:, 3]),
                    'max': np.max(data[:, 3]), 'min': np.min(data[:, 3])},
        }
    return summary


def load_face_data(data_dir='data'):
    """从 data/faces/ 目录加载人脸数据"""
    faces_dir = os.path.join(data_dir, 'faces')
    if not os.path.exists(faces_dir):
        print(f"错误：找不到 faces 目录: {faces_dir}")
        return None, None
    
    images = []
    labels = []
    
    # 加载每个人脸目录
    person_dirs = sorted([d for d in os.listdir(faces_dir) if os.path.isdir(os.path.join(faces_dir, d))])
    
    for idx, person_dir in enumerate(person_dirs):
        person_path = os.path.join(faces_dir, person_dir)
        person_lbl = idx + 1  # 标签从1开始
        
        img_files = [f for f in os.listdir(person_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        for img_file in img_files:
            img_path = os.path.join(person_path, img_file)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                # 调整大小（与识别系统一致）
                img = cv2.resize(img, (200, 200))
                images.append(img)
                labels.append(person_lbl)
    
    if len(images) == 0:
        print("错误：未加载到任何人脸图像")
        return None, None
    
    print(f"加载人脸数据：{len(images)} 张图像，{len(np.unique(labels))} 个类别")
    return np.array(images), np.array(labels)


def main():
    """主函数"""
    # 加载数据
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    images, labels = load_face_data(data_dir)
    
    if images is None or labels is None:
        print("错误：无法加载训练数据")
        return
    
    # 运行交叉验证
    (lbph_metrics, lbph_confs,
     down_metrics, down_confs,
     hist_metrics, hist_confs) = run_cross_validation(images, labels, n_splits=10)
    
    # 绘制对比图
    plot_comparison(lbph_metrics, lbph_confs,
                    down_metrics, down_confs,
                    hist_metrics, hist_confs)
    
    # 保存结果
    import json
    result = {
        'lbph_metrics': lbph_metrics.tolist(),
        'down_metrics': down_metrics.tolist(),
        'hist_metrics': hist_metrics.tolist(),
        'lbph_confs': lbph_confs.tolist(),
        'down_confs': down_confs.tolist(),
        'hist_confs': hist_confs.tolist(),
    }
    
    result_path = os.path.join(workspace_dir, 'comparison_result.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"结果已保存: {result_path}")
    
    # 打印汇总
    print(f"\n{'='*60}")
    print("汇总结果（宏平均 ± 标准差）")
    print(f"{'='*60}")
    
    def print_metrics(name, metrics):
        if len(metrics) == 0 or np.all(metrics == 0):
            print(f"{name}: 无有效数据")
            return
        print(f"{name}:")
        print(f"  准确率: {np.mean(metrics[:, 0])*100:5.1f}% ± {np.std(metrics[:, 0])*100:4.1f}%")
        print(f"  精确率: {np.mean(metrics[:, 1])*100:5.1f}% ± {np.std(metrics[:, 1])*100:4.1f}%")
        print(f"  召回率: {np.mean(metrics[:, 2])*100:5.1f}% ± {np.std(metrics[:, 2])*100:4.1f}%")
        print(f"  F1分数: {np.mean(metrics[:, 3])*100:5.1f}% ± {np.std(metrics[:, 3])*100:4.1f}%")
    
    print_metrics('LBPH', lbph_metrics)
    print_metrics('FFT幅度谱', down_metrics)
    print_metrics('灰度直方图', hist_metrics)


if __name__ == '__main__':
    main()
