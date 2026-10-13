"""
人脸识别引擎模块
使用 OpenCV LBPH (Local Binary Patterns Histograms) 算法
支持人脸采集、训练、识别
"""
# 操作系统路径处理模块
import os
# OpenCV计算机视觉核心库，人脸检测、采集、识别、图像处理
import cv2
# 数值计算库，处理人脸图像数组、标签数组
import numpy as np
# 从数据库工具导入人脸根目录、单人头像路径获取函数
from utils.database import get_faces_dir, get_face_path
# 导入中文绘制工具，解决OpenCV原生不支持中文显示问题
from utils.chinese_text import put_text_auto

# 拼接模型保存路径：项目根目录下models文件夹face_model.yml
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "models", "face_model.yml")

# OpenCV自带正面人脸Haar级联检测器路径
CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"


def get_face_detector():
    """获取人脸检测器实例"""
    # 初始化正面人脸分类器
    detector = cv2.CascadeClassifier(CASCADE_PATH)
    # 校验检测器是否加载成功，为空则抛出运行异常
    if detector.empty():
        raise RuntimeError("无法加载 Haar 级联分类器，请检查 OpenCV 安装")
    return detector


def get_recognizer():
    """获取/加载LBPH人脸识别器，已有训练模型则直接加载"""
    # 创建LBPH人脸识别器对象
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    # 如果模型权重文件存在，读取预训练模型
    if os.path.exists(MODEL_PATH):
        recognizer.read(MODEL_PATH)
        print(f"[识别引擎] 已加载模型: {MODEL_PATH}")
    return recognizer


def detect_faces(frame: np.ndarray, detector=None):
    """
    检测图像中的人脸
    :param frame: BGR 彩色图像帧
    :param detector: 人脸检测器（可外部传入复用，减少重复初始化）
    :return: (gray_image, faces_list) faces_list 每项 (x,y,w,h) 人脸坐标宽高
    """
    # 未传入检测器则临时创建
    if detector is None:
        detector = get_face_detector()
    # 彩色帧转为灰度图，人脸检测必须基于灰度图
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # 直方图均衡化，提升暗光、低对比度人脸检测效果
    gray = cv2.equalizeHist(gray)
    # 多尺度人脸检测
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.1,          # 每次图像缩放比例
        minNeighbors=4,           # 候选框周边至少4个匹配框才判定为人脸，降噪
        minSize=(60, 60),         # 人脸最小像素尺寸，过滤极小噪点
        flags=cv2.CASCADE_SCALE_IMAGE
    )
    return gray, faces


def capture_face_samples(person_id: int, name: str, num_samples: int = 30) -> bool:
    """
    打开摄像头采集指定数量的人脸样本图像
    :param person_id: 人员 ID（文件夹命名依据）
    :param name: 人员姓名（摄像头界面显示）
    :param num_samples: 目标采集样本总数
    :return: 是否采集成功
    """
    # 获取人脸总存储根目录
    faces_dir = get_faces_dir()
    # 拼接当前人员独立样本文件夹路径
    person_dir = os.path.join(faces_dir, str(person_id))
    # 不存在则自动创建个人文件夹
    os.makedirs(person_dir, exist_ok=True)

    # 打开默认摄像头（设备0）
    cap = cv2.VideoCapture(0)
    # 摄像头打开失败直接返回
    if not cap.isOpened():
        print("[错误] 无法打开摄像头")
        return False

    # 初始化人脸检测器
    detector = get_face_detector()
    # 已采集样本计数器
    count = 0

    print(f"[采集] 开始为 {name}（ID:{person_id}）采集人脸，请面向摄像头...")
    print("  按 Space 或 S 键拍照 / 按 Q 退出")

    # 循环采集，直到达到目标样本数
    while count < num_samples:
        # 读取一帧画面
        ret, frame = cap.read()
        # 帧读取失败跳过当前循环
        if not ret:
            continue

        # 人脸检测，返回灰度图与人脸坐标
        gray, faces = detect_faces(frame, detector)
        # 拷贝原图用于绘制UI和展示，不污染原始帧
        display = frame.copy()

        # 遍历检测到的所有人脸框
        for (x, y, w, h) in faces:
            # 绘制绿色人脸矩形框
            cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
            # 裁剪人脸ROI区域
            face_roi = gray[y:y+h, x:x+w]
            # 统一缩放至训练标准尺寸200×200
            face_roi = cv2.resize(face_roi, (200, 200))

            # 在人脸框上方绘制采集提示中文
            put_text_auto(display, f"Space/S采集 ({count}/{num_samples})",
                          (x, y-25), (0, 255, 0), 18)

        # 画面顶部状态文字：当前采集进度+姓名
        status_text = f"采集中: {count}/{num_samples}  姓名: {name}"
        put_text_auto(display, status_text, (10, 30), (255, 255, 0), 22)
        # 底部操作快捷键提示
        put_text_auto(display, "Space / S = 采集    Q = 退出", (10, 60), (200, 200, 200), 16)
        # 弹出采集预览窗口
        cv2.imshow("人脸采集 - Face Capture", display)

        # 帧等待30ms，稳定捕获按键，Windows兼容性更好
        key = cv2.waitKey(30)

        # Q键、ESC键退出采集循环
        if key in (ord('q'), ord('Q'), 27):
            break
        # 空格键、小写S、大写S触发拍照，且必须检测到人脸
        elif key in (32, 115, 83) and len(faces) > 0:
            # 选取画面中面积最大的人脸作为有效采集人脸
            (x, y, w, h) = max(faces, key=lambda f: f[2]*f[3])
            # 裁剪灰度人脸
            face_roi = gray[y:y+h, x:x+w]
            face_roi = cv2.resize(face_roi, (200, 200))
            # 拼接保存路径，按序号命名图片
            img_path = os.path.join(person_dir, f"{count+1}.jpg")
            # 写入人脸图片到本地
            cv2.imwrite(img_path, face_roi)
            # 计数自增
            count += 1
            print(f"  已采集 {count}/{num_samples}")

    # 释放摄像头硬件资源
    cap.release()
    # 关闭所有OpenCV窗口
    cv2.destroyAllWindows()

    # 全程未采集任何样本，返回失败
    if count == 0:
        print("[警告] 未采集到任何样本")
        return False

    print(f"[采集完成] 共采集 {count} 张样本")
    return True


def train_model(persons_data: list) -> bool:
    """
    训练/更新LBPH人脸识别模型
    :param persons_data: 待训练人员列表 [(person_id, name), ...]
    :return: 是否训练成功
    """
    # 获取人脸总目录
    faces_dir = get_faces_dir()
    # 存储所有人脸训练图像
    face_samples = []
    # 对应每张人脸的人员ID标签
    face_labels = []

    # 遍历每个注册人员
    for person_id, name in persons_data:
        # 单人样本文件夹路径
        person_dir = os.path.join(faces_dir, str(person_id))
        # 文件夹不存在直接跳过该人员
        if not os.path.exists(person_dir):
            print(f"[训练] 跳过 {name}（无样本目录）")
            continue
        # 筛选文件夹内jpg图片
        imgs = [f for f in os.listdir(person_dir) if f.endswith('.jpg')]
        # 无有效样本图则跳过
        if not imgs:
            print(f"[训练] 跳过 {name}（无样本图像）")
            continue
        # 遍历该人员所有样本图片
        for img_name in imgs:
            img_path = os.path.join(person_dir, img_name)
            # 灰度模式读取人脸图像
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            # 图像读取损坏则跳过
            if img is None:
                continue
            # 统一尺寸匹配训练输入要求
            img = cv2.resize(img, (200, 200))
            # 加入训练集
            face_samples.append(img)
            face_labels.append(int(person_id))

    # 无任何训练样本，直接训练失败
    if len(face_samples) == 0:
        print("[训练] 没有可用的人脸样本，训练失败")
        return False

    # 新建LBPH识别器
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    # 投喂样本与标签开始训练
    recognizer.train(face_samples, np.array(face_labels))

    # 统计参与训练的独立人员数
    unique_labels = set(face_labels)
    # 仅单人训练警告：LBPH会把陌生人全部判定为此人，无区分能力
    if len(unique_labels) <= 1:
        print("[警告] 只有 1 个人员的样本！LBPH 模型会将陌生人误判为该人员。")
        print("[警告] 请至少注册 2 个人员并采集样本，以启用有效的人脸识别。")

    # 模型保存目录不存在则创建
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    # 持久化保存训练模型
    recognizer.save(MODEL_PATH)
    print(f"[训练完成] 模型已保存: {MODEL_PATH}，共训练 {len(face_samples)} 张图像，{len(persons_data)} 人")
    return True


def recognize_face(gray_face: np.ndarray, recognizer=None) -> tuple:
    """
    识别单张裁剪后的灰度人脸图像
    :param gray_face: 已裁剪的灰度人脸ROI
    :param recognizer: 识别器实例（可复用，避免重复加载模型）
    :return: (person_id, confidence)  LBPH置信度数值越小代表匹配度越高
    """
    # 未传入识别器则手动加载
    if recognizer is None:
        # 模型文件不存在，返回未知ID+最大置信度（判定为陌生人）
        if not os.path.exists(MODEL_PATH):
            return -1, 999.0
        recognizer = get_recognizer()

    # 人脸缩放到训练统一尺寸
    face_resized = cv2.resize(gray_face, (200, 200))
    # 执行预测，返回匹配人员ID、特征距离置信度
    person_id, confidence = recognizer.predict(face_resized)
    return person_id, confidence


def is_model_trained() -> bool:
    """检查训练模型文件是否存在，判断系统是否具备识别能力"""
    return os.path.exists(MODEL_PATH)