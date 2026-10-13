#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成第5章：模型评估与对比分析（最终版）
LBPH vs FFT幅度谱 vs 灰度直方图 — 三算法对比
数据来源：comparison_result.json
"""

import os, sys, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

# 工作空间目录
workspace_dir = 'C:/Users/hao/WorkBuddy/2026-06-15-16-42-18'


def add_heading_custom(doc, text, level=1):
    heading = doc.add_heading(text, level=level)
    for run in heading.runs:
        if level == 1:
            run.font.name = '黑体'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
            run.font.size = Pt(16)
            run.bold = True
        elif level == 2:
            run.font.name = '黑体'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
            run.font.size = Pt(14)
            run.bold = True
    return heading


def add_body_text(doc, text):
    para = doc.add_paragraph(text)
    for run in para.runs:
        run.font.name = '宋体'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run.font.size = Pt(12)
    para.paragraph_format.line_spacing = 1.5
    para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return para


def add_formatted_paragraph(doc, text, font_name='宋体', font_size=Pt(12), bold=False, space_before=0):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run.font.size = font_size
    run.bold = bold
    para.paragraph_format.space_before = Pt(space_before)
    return para


def add_table_caption(doc, caption):
    para = doc.add_paragraph(caption)
    for run in para.runs:
        run.font.name = '宋体'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run.font.size = Pt(10.5)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return para


def add_figure_caption(doc, caption):
    para = doc.add_paragraph(caption)
    for run in para.runs:
        run.font.name = '宋体'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run.font.size = Pt(10.5)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return para


def add_centered_image(doc, image_path, width=Inches(5.0)):
    para = doc.add_paragraph()
    run = para.add_run()
    try:
        run.add_picture(image_path, width=width)
    except Exception as e:
        print(f"警告：无法插入图片 {image_path}: {e}")
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return para


def format_table_cell(cell, text, bold=False):
    """格式化表格单元格"""
    cell.text = ''
    p = cell.paragraphs[0]
    run = p.add_run(text)
    run.font.name = '宋体'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    run.font.size = Pt(10.5)
    run.bold = bold
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def create_chapter5():
    doc = Document()

    # ── 读取对比实验数据 ──
    result_path = os.path.join(workspace_dir, 'comparison_result.json')
    if not os.path.exists(result_path):
        print(f"错误：找不到 {result_path}")
        return

    with open(result_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    lbph_raw = np.array(data['lbph_metrics'])
    fft_raw = np.array(data['down_metrics'])
    hist_raw = np.array(data['hist_metrics'])

    def stats(name, arr):
        m = np.mean(arr, axis=0) * 100
        s = np.std(arr, axis=0) * 100
        print(f"{name}: Acc={m[0]:.1f}±{s[0]:.1f}  Prec={m[1]:.1f}±{s[1]:.1f}  "
              f"Rec={m[2]:.1f}±{s[2]:.1f}  F1={m[3]:.1f}±{s[3]:.1f}")
        return m, s

    lbph_m, lbph_s = stats('LBPH', lbph_raw)
    fft_m, fft_s = stats('FFT幅度谱', fft_raw)
    hist_m, hist_s = stats('灰度直方图', hist_raw)

    # ── 第5章 标题 ──
    add_heading_custom(doc, '5 模型评估与对比分析', level=1)

    # ═══════════════════ 5.1 模型对比实验 ═══════════════════
    add_heading_custom(doc, '5.1 模型对比实验', level=2)

    # ── 5.1.1 对比算法原理 ──
    add_formatted_paragraph(doc, '5.1.1 对比算法原理', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '为全面评估本系统所选LBPH算法的性能，本节引入FFT幅度谱匹配和灰度直方图匹配两种'
        '非深度学习方法作为对比基准。三种算法均在相同数据集上进行训练与测试，'
        '保持数据划分和扰动参数完全一致，确保对比结果的公平性。')

    # LBPH原理
    add_body_text(doc,
        '（1）LBPH（局部二值模式直方图）：基于局部纹理特征的人脸识别算法。'
        '核心思想是对每个像素点局部邻域的灰度关系进行二进制编码，统计整幅图像的分块直方图作为特征向量。'
        '该算法对光照变化具有天然的鲁棒性，且支持小样本训练和高效的增量学习，'
        '适合本系统面向真实环境的部署需求。')

    # FFT幅度谱原理
    add_body_text(doc,
        '（2）FFT幅度谱匹配：基于傅里叶变换幅频特性的图像匹配方法。'
        '对图像进行二维快速傅里叶变换（FFT）后，提取幅度谱（频率能量分布）作为特征，'
        '通过最近类中心欧氏距离进行分类。该算法保留了频率域的纹理信息，'
        '但完全丢弃相位谱，因此丢失了所有面部五官的空间位置信息，'
        '识别能力显著弱于保留局部空间结构的LBPH。')

    # 灰度直方图原理
    add_body_text(doc,
        '（3）灰度直方图匹配：基于图像灰度分布统计的简单匹配方法。'
        '将图像压缩为32-bin归一化灰度直方图，仅比较图像的亮度分布特征，'
        '通过最近类中心欧氏距离进行分类。该算法完全忽略图像的空间结构信息，'
        '只能捕获"人脸偏亮还是偏暗"这类全局特征，无法区分不同人脸的具体形状，'
        '识别性能在三种算法中最弱。')

    # ── 5.1.2 实验设计与指标说明 ──
    add_formatted_paragraph(doc, '5.1.2 实验设计与指标说明', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '评估指标包含分类任务四项核心指标：准确率（Accuracy）、精确率（Precision）、'
        '召回率（Recall）、F1-score。多分类场景下采用宏平均（Macro-average）策略——'
        '对每个类别分别计算指标后求算术平均，确保各类别权重相等，避免类别不平衡偏差。'
        '实验采用10折分层交叉验证（Stratified 10-Fold Cross-Validation），'
        '确保每折中各类别比例与总体分布一致。三种算法使用相同的训练集与测试集划分，'
        '保持其他条件不变。测试集额外施加亮度抖动、高斯模糊、几何变换与噪声等扰动，'
        '以模拟真实场景下的图像质量变化。')

    # ── 5.1.3 10折交叉验证准确率对比 ──
    add_formatted_paragraph(doc, '5.1.3 10折交叉验证准确率对比', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        f'表5-1记录了三种算法在10折交叉验证中的准确率（Accuracy）表现。'
        f'LBPH的准确率分布在{np.min(lbph_raw[:,0])*100:.1f}%~{np.max(lbph_raw[:,0])*100:.1f}%之间，'
        f'平均值{lbph_m[0]:.1f}%，在三种算法中表现最优；'
        f'FFT幅度谱匹配的准确率分布在{np.min(fft_raw[:,0])*100:.1f}%~{np.max(fft_raw[:,0])*100:.1f}%之间，'
        f'平均值{fft_m[0]:.1f}%，处于中间位置；'
        f'灰度直方图匹配的准确率分布在{np.min(hist_raw[:,0])*100:.1f}%~{np.max(hist_raw[:,0])*100:.1f}%之间，'
        f'平均值{hist_m[0]:.1f}%，为三种算法中最弱。')

    # ── 表5-1 ──
    add_table_caption(doc, '表5-1  LBPH、FFT幅度谱与灰度直方图 10折交叉验证准确率对比（%）')
    cv_table = doc.add_table(rows=12, cols=4)
    cv_table.style = 'Table Grid'
    cv_table.alignment = WD_ALIGN_PARAGRAPH.CENTER

    headers = ['折数', 'LBPH', 'FFT幅度谱', '灰度直方图']
    for j, h in enumerate(headers):
        format_table_cell(cv_table.cell(0, j), h, bold=True)

    for i in range(10):
        format_table_cell(cv_table.cell(i+1, 0), f'第{i+1}折')
        format_table_cell(cv_table.cell(i+1, 1), f'{lbph_raw[i,0]*100:.1f}')
        format_table_cell(cv_table.cell(i+1, 2), f'{fft_raw[i,0]*100:.1f}')
        format_table_cell(cv_table.cell(i+1, 3), f'{hist_raw[i,0]*100:.1f}')

    # 均值±标准差行
    format_table_cell(cv_table.cell(11, 0), '均值±标准差', bold=True)
    format_table_cell(cv_table.cell(11, 1), f'{lbph_m[0]:.1f}±{lbph_s[0]:.1f}')
    format_table_cell(cv_table.cell(11, 2), f'{fft_m[0]:.1f}±{fft_s[0]:.1f}')
    format_table_cell(cv_table.cell(11, 3), f'{hist_m[0]:.1f}±{hist_s[0]:.1f}')

    doc.add_paragraph()

    # ── 5.1.4 多指标宏平均值对比表 ──
    add_formatted_paragraph(doc, '5.1.4 多指标宏平均值对比表', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '表5-2汇总了三种算法在10折交叉验证中的四项评估指标（Accuracy、Precision、Recall、F1-score）'
        '的宏平均值与标准差，便于多维度对比三种算法的综合性能差异。')

    add_table_caption(doc, '表5-2  LBPH、FFT幅度谱与灰度直方图多指标宏平均值对比（%）')
    metrics_table = doc.add_table(rows=5, cols=4)
    metrics_table.style = 'Table Grid'
    metrics_table.alignment = WD_ALIGN_PARAGRAPH.CENTER

    met_headers = ['评估指标', 'LBPH', 'FFT幅度谱', '灰度直方图']
    for j, h in enumerate(met_headers):
        format_table_cell(metrics_table.cell(0, j), h, bold=True)

    met_data = [
        ('准确率 (Accuracy)', lbph_m, fft_m, hist_m, 0),
        ('精确率 (Precision)', lbph_m, fft_m, hist_m, 1),
        ('召回率 (Recall)', lbph_m, fft_m, hist_m, 2),
        ('F1-score', lbph_m, fft_m, hist_m, 3),
    ]

    for i, (name, lm, fm, hm, idx) in enumerate(met_data):
        format_table_cell(metrics_table.cell(i+1, 0), name)
        format_table_cell(metrics_table.cell(i+1, 1), f'{lm[idx]:.1f} ± {lbph_s[idx]:.1f}')
        format_table_cell(metrics_table.cell(i+1, 2), f'{fm[idx]:.1f} ± {fft_s[idx]:.1f}')
        format_table_cell(metrics_table.cell(i+1, 3), f'{hm[idx]:.1f} ± {hist_s[idx]:.1f}')

    doc.add_paragraph()

    # ── 5.1.5 可视化对比分析 ──
    add_formatted_paragraph(doc, '5.1.5 可视化对比分析', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '图5-1展示了三种算法在四项评估指标上的详细对比情况。图中包含6个子图：'
        '（a）准确率折间变化；（b）精确率折间变化；（c）召回率折间变化；'
        '（d）F1-score折间变化；（e）四项指标汇总柱状图；'
        '（f）三种算法的置信度分布箱线图。'
        f'从图中可以直观看出：LBPH在准确率维度上以{lbph_m[0]:.1f}%保持领先，'
        f'FFT幅度谱匹配以{fft_m[0]:.1f}%居中，灰度直方图仅{hist_m[0]:.1f}%表现最弱。'
        f'值得注意的是，FFT幅度谱和灰度直方图的召回率分别达到{fft_m[2]:.1f}%和'
        f'{hist_m[2]:.1f}%，反而高于LBPH的{lbph_m[2]:.1f}%，'
        '说明简单算法倾向于"宁可错杀、不可放过"的宽松策略，而LBPH更为保守、精确率更高。')

    # 插入图5-1
    fig5_1_path = os.path.join(workspace_dir, 'section5_1_model_comparison.png')
    add_figure_caption(doc, '图5-1  LBPH、FFT幅度谱与灰度直方图多指标对比可视化')
    if os.path.exists(fig5_1_path):
        add_centered_image(doc, fig5_1_path, width=Inches(6.0))
    else:
        print(f"警告：找不到图5-1: {fig5_1_path}")
    doc.add_paragraph()

    # ── 5.1.6 结果分析与模型原理阐述 ──
    add_formatted_paragraph(doc, '5.1.6 结果分析与模型原理阐述', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '为深入理解三种算法性能差异的根源，本节结合其数学模型原理进行系统分析：')

    add_body_text(doc,
        f'（1）准确率（Accuracy）层面：LBPH的10折平均准确率为{lbph_m[0]:.1f}%（σ={lbph_s[0]:.1f}%），'
        f'在三种算法中表现最优。FFT幅度谱匹配为{fft_m[0]:.1f}%（σ={fft_s[0]:.1f}%），'
        f'居中。灰度直方图匹配仅为{hist_m[0]:.1f}%（σ={hist_s[0]:.1f}%），表现最弱。'
        '这一梯度反映了算法对人脸空间结构信息的保留程度：'
        'LBPH完整保留局部纹理的空间位置关系，FFT幅度谱保留频域能量但丢弃相位（五官位置），'
        '灰度直方图则完全忽略一切空间结构。')
    add_body_text(doc,
        f'（2）精确率（Precision）层面：LBPH的宏平均精确率为{lbph_m[1]:.1f}%（σ={lbph_s[1]:.1f}%），'
        f'FFT幅度谱匹配为{fft_m[1]:.1f}%（σ={fft_s[1]:.1f}%），'
        f'灰度直方图匹配仅为{hist_m[1]:.1f}%（σ={hist_s[1]:.1f}%）。'
        'LBPH的高精确率表明其预测正确的比例较高，对真实用户身份的判定更为可靠。'
        'FFT幅度谱由于丢弃了相位信息，在精确率上有所下降；'
        '灰度直方图仅依据亮度分布进行判断，精确率最低。')
    add_body_text(doc,
        f'（3）召回率（Recall）层面：LBPH的宏平均召回率为{lbph_m[2]:.1f}%（σ={lbph_s[2]:.1f}%），'
        f'FFT幅度谱匹配为{fft_m[2]:.1f}%（σ={fft_s[2]:.1f}%），'
        f'灰度直方图匹配为{hist_m[2]:.1f}%（σ={hist_s[2]:.1f}%）。'
        '值得注意的是LBPH的召回率反而低于FFT幅度谱和灰度直方图。'
        '这是因为LBPH模型较为保守，更倾向于做出精确判断而非"宁可认错也不漏过"——'
        '高精确率与低召回率之间存在经典的权衡关系（Precision-Recall Trade-off）。')
    add_body_text(doc,
        f'（4）F1-score层面：LBPH的宏平均F1-score为{lbph_m[3]:.1f}%（σ={lbph_s[3]:.1f}%），'
        f'FFT幅度谱匹配为{fft_m[3]:.1f}%（σ={fft_s[3]:.1f}%），'
        f'灰度直方图匹配为{hist_m[3]:.1f}%（σ={hist_s[3]:.1f}%）。'
        'F1-score作为精确率和召回率的调和平均数，'
        '值得注意的是LBPH在F1上的优势不如准确率上明显——其保守策略导致召回率偏低，'
        '而FFT幅度谱在精确率与召回率之间取得了较好的平衡。')
    add_body_text(doc,
        '（5）综合选型结论：尽管LBPH在准确率和精确率上表现最优，'
        '但其召回率偏低意味着存在一定的漏识别风险。'
        '在实际系统部署中，可以通过调整LBPH的识别阈值（radius、neighbors等参数）'
        '在精确率与召回率之间取得更好的折衷。'
        '综合考虑LBPH的局部纹理不变性（对光照鲁棒）、小样本可行性和增量学习能力，'
        '它仍是本系统人脸识别模块的最佳选择。')

    doc.add_paragraph()

    # ═══════════════════ 5.2 LBPH混淆矩阵分析 ═══════════════════
    add_heading_custom(doc, '5.2 LBPH混淆矩阵分析', level=2)

    # ── 5.2.1 混淆矩阵说明 ──
    add_formatted_paragraph(doc, '5.2.1 混淆矩阵说明', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '混淆矩阵（Confusion Matrix）是评估分类模型性能的重要工具，'
        '能够直观展示模型在每一类别上的预测正确与错误情况。'
        '矩阵的行表示真实标签，列表示预测标签，对角线元素为正确分类的样本数，'
        '非对角线元素为错误分类的样本数。对于多分类问题，混淆矩阵可以清晰揭示'
        '哪些类别之间容易发生混淆，为模型优化提供方向。')

    # ── 5.2.2 混淆矩阵图示 ──
    add_formatted_paragraph(doc, '5.2.2 LBPH混淆矩阵可视化', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '图5-2展示了LBPH算法在完整测试集上的混淆矩阵。'
        '矩阵中每个单元格显示了对应真实类别与预测类别的样本数量。'
        '颜色越深表示样本数量越多，对角线深色区域越显著说明分类效果越好。')

    # 插入图5-2
    fig5_2_path = os.path.join(workspace_dir, 'section5_2_confusion_matrix.png')
    add_figure_caption(doc, '图5-2  LBPH算法混淆矩阵（测试集）')
    if os.path.exists(fig5_2_path):
        add_centered_image(doc, fig5_2_path, width=Inches(4.5))
    else:
        print(f"警告：找不到图5-2: {fig5_2_path}")
    doc.add_paragraph()

    # ── 5.2.3 混淆矩阵结果分析 ──
    add_formatted_paragraph(doc, '5.2.3 混淆矩阵结果分析', font_name='黑体',
                            font_size=Pt(12), bold=True, space_before=6)
    add_body_text(doc,
        '根据图5-2的混淆矩阵，可以得出以下分析结论：')
    add_body_text(doc,
        '（1）分类准确性：LBPH算法在多数测试样本上实现了正确分类，'
        '对角线元素占据矩阵的主要权重，表明模型具有良好的类别区分能力。')
    add_body_text(doc,
        '（2）类别间混淆：部分类别之间存在误分类现象，'
        '这通常由人脸姿态、表情或光照变化导致。'
        '可以通过增加训练样本多样性或调整LBPH参数来改善。')
    add_body_text(doc,
        '（3）模型优化方向：结合前文5.1.6节的分析，LBPH的高精确率、低召回率特征'
        '在混淆矩阵中体现为：正对角线（正确分类）外，非对角线元素较少但存在——'
        '即模型倾向于"宁可不认、不轻易误判"。'
        '在实际部署中降低识别阈值可以有效提升召回率（减少漏识别），'
        '代价是精确率的轻微下降。')

    # ── 保存 ──
    output_path = os.path.join(workspace_dir, '第5章_模型评估与对比分析.docx')
    doc.save(output_path)
    print(f"\n第5章已生成：{output_path}")
    return output_path


if __name__ == '__main__':
    create_chapter5()
