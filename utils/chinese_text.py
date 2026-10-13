"""
中文文本绘制工具
OpenCV 的 putText 不支持 CJK 字符，用 PIL 渲染中文后叠加到图像上
"""
import cv2
import numpy as np

# 尝试导入 PIL/Pillow
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def get_chinese_font(size=20):
    """获取系统中文字体"""
    if not _PIL_AVAILABLE:
        return None
    # Windows 中文字体优先级列表
    candidates = [
        "msyh.ttc",       # 微软雅黑
        "simhei.ttf",     # 黑体
        "simsun.ttc",     # 宋体
    ]
    import os
    windows_font_dir = r"C:\Windows\Fonts"
    for name in candidates:
        path = os.path.join(windows_font_dir, name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # 回退到默认字体
    return ImageFont.load_default()


def put_chinese_text(img, text, position, color=(0, 255, 0),
                     font_size=20, thickness=None):
    """
    在 OpenCV 图像上绘制中文文本（通过 PIL）
    :param img: BGR numpy 数组（会被原地修改）
    :param text: 中文文本字符串
    :param position: (x, y) 左上角坐标
    :param color: BGR 颜色元组，如 (0, 255, 0) 绿色
    :param font_size: 字号大小
    """
    if not _PIL_AVAILABLE or not text.strip():
        # PIL 不可用或空文本时回退到英文占位
        fallback = text.encode("ascii", errors="replace").decode("ascii")
        cv2.putText(img, fallback, position,
                    cv2.FONT_HERSHEY_SIMPLEX, max(0.5, font_size / 30.0),
                    color, thickness or 2)
        return

    x, y = int(position[0]), int(position[1])
    font = get_chinese_font(font_size)

    # 转换 BGR → RGB 给 PIL 使用
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    # PIL 颜色是 RGB
    rgb_color = (int(color[2]), int(color[1]), int(color[0]))
    draw.text((x, y), text, font=font, fill=rgb_color)

    # RGB → BGR 写回原图
    result = np.array(img_pil)
    img[:, :, :] = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)


def put_text_auto(img, text, position, color=(255, 255, 255),
                  font_size=20, thickness=None):
    """
    自动选择绘制方式：包含中文用 PIL，纯 ASCII 用原生 OpenCV（更快）
    """
    has_cjk = any('\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f'
                   for ch in text)
    if has_cjk and _PIL_AVAILABLE:
        put_chinese_text(img, text, position, color, font_size, thickness)
    else:
        cv2.putText(img, text, position,
                    cv2.FONT_HERSHEY_SIMPLEX, max(0.5, font_size / 30.0),
                    color, thickness or 2)
