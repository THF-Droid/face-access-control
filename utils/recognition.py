"""
实时人脸识别与通行管控模块
"""
# 导入OpenCV视觉库，负责摄像头读取、图像处理、人脸框绘制
import cv2
# 数值计算库，图像数组处理
import numpy as np
# 时间模块，冷却计时、运行时长统计
import time
# 日期时间格式化，界面时间戳显示
from datetime import datetime

# 数据库交互函数：人员查询、通行记录写入、加载全部人员
from utils.database import (
    get_person_by_id, add_access_record, load_persons
)
# 人脸引擎核心能力：检测器、识别器、人脸检测、单张人脸识别、模型状态检测
from utils.face_engine import (
    get_face_detector, get_recognizer, detect_faces,
    recognize_face, is_model_trained
)
# 中文绘制工具，解决OpenCV无法正常显示中文问题
from utils.chinese_text import put_text_auto

# ── 全局业务配置参数 ───────────────────────────────────────────────────────────────────
# LBPH置信度阈值：数值越低匹配要求越严格，低于阈值判定为匹配到内部人员
CONFIDENCE_THRESHOLD = 35.0
# 同一人通行记录冷却间隔，短时间重复识别只记一次日志，防刷屏
COOLDOWN_SECONDS = 5
# 限时识别模式下，人脸最少连续出现帧数才判定有效，过滤瞬时误检
MIN_DETECT_FRAMES = 2

# 界面绘制颜色，BGR格式适配OpenCV
COLOR_ALLOW = (0, 220, 0)      # 绿色：允许通行
COLOR_DENY = (0, 0, 220)       # 红色：有权限但拒绝/未知错误拒绝
COLOR_UNKNOWN = (0, 165, 255)  # 橙色：陌生人

class AccessController:
    """实时通行管控控制器，封装检测、识别、鉴权、绘制、日志节流全逻辑"""
    def __init__(self):
        # 初始化人脸检测器（Haar级联）
        self.detector = get_face_detector()
        # 模型已训练则加载识别器，否则置空
        self.recognizer = get_recognizer() if is_model_trained() else None
        # 冷却计时器字典：key人员ID，value上次记录时间戳
        self._cooldown: dict[int, float] = {}
        # 缓存上一帧识别结果，供调试与后续逻辑复用
        self._last_frame_result: list = []

    def reload_model(self):
        """训练新模型后手动重载识别器，无需重启程序"""
        from utils.face_engine import get_recognizer
        self.recognizer = get_recognizer()
        print("[控制器] 模型已重新加载")

    def process_frame(self, frame: np.ndarray) -> tuple:
        """
        处理单帧图像：检测+识别+权限判定+画面绘制
        :param frame: 摄像头原始BGR图像帧
        :return: (annotated_frame, results_list)
                 annotated_frame：绘制完框、文字的渲染画面
                 results_list：单帧内所有人脸识别详情字典数组
        """
        # 灰度转换+人脸检测，获取灰度图与所有人脸坐标框
        gray, faces = detect_faces(frame, self.detector)
        results = []

        # 遍历当前帧每一个检测到的人脸
        for (x, y, w, h) in faces:
            # 裁剪人脸感兴趣区域
            face_roi = gray[y:y+h, x:x+w]
            # 人脸识别+权限校验，获取身份、权限、置信度、显示颜色
            info = self._identify_and_authorize(face_roi)
            results.append(info)
            # 在原图绘制人脸框、中文标签、置信度
            self._draw_annotation(frame, x, y, w, h, info)
            # 符合冷却规则则写入通行记录
            self._try_log(info)

        # 缓存本帧结果
        self._last_frame_result = results
        return frame, results

    def _identify_and_authorize(self, face_gray: np.ndarray) -> dict:
        """
        内部私有方法：人脸特征匹配 + 数据库权限校验
        :param face_gray: 裁剪后的灰度人脸ROI
        :return: 结构化身份与权限字典
        """
        # 识别器为空，直接返回无模型状态
        if self.recognizer is None:
            return {
                "person_id": -1, "name": "无模型", "department": "-",
                "result": "无模型", "confidence": 999.0,
                "permission": "拒绝通行", "color": COLOR_DENY
            }

        # LBPH预测，返回匹配ID与特征距离置信度（越小越相似）
        person_id, confidence = recognize_face(face_gray, self.recognizer)

        # 置信度超过阈值，判定为陌生人
        if confidence > CONFIDENCE_THRESHOLD:
            return {
                "person_id": -1, "name": "陌生人", "department": "-",
                "result": "陌生人", "confidence": confidence,
                "permission": "拒绝通行", "color": COLOR_UNKNOWN
            }

        # 根据ID查询数据库人员详情
        person = get_person_by_id(person_id)
        # ID存在但数据库无匹配人员，判定未知人员
        if not person:
            return {
                "person_id": person_id, "name": "未知", "department": "-",
                "result": "陌生人", "confidence": confidence,
                "permission": "拒绝通行", "color": COLOR_UNKNOWN
            }

        # 读取数据库通行权限，分配结果文字与显示颜色
        if person.get("permission") == "允许":
            result = "允许通行"
            color = COLOR_ALLOW
        else:
            result = "拒绝通行"
            color = COLOR_DENY

        # 打包完整人员识别信息返回
        return {
            "person_id": person_id,
            "name": person.get("name", ""),
            "department": person.get("department", ""),
            "result": result,
            "confidence": confidence,
            "permission": person.get("permission", ""),
            "color": color
        }

    def _draw_annotation(self, frame, x, y, w, h, info):
        """在画面绘制人脸矩形框、姓名权限文字、置信度文本，兼容中文"""
        color = info["color"]
        # 绘制人脸包围矩形框
        cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

        # 拼接姓名+通行结果标签
        label = f"{info['name']}  {info['result']}"
        # 人脸框上方绘制中文标签
        put_text_auto(frame, label, (x+3, y-28), color, 20)

        # 非陌生人时，在框下方绘制相似度百分比（转换置信度为友好百分比）
        if info["confidence"] < 900:
            conf_text = f"Conf: {100 - info['confidence']:.1f}%"
            put_text_auto(frame, conf_text, (x, y+h+8), color, 16)

    def _try_log(self, info: dict):
        """通行记录节流写入：冷却时间内同一人员重复识别不重复落库"""
        pid = info["person_id"]
        now = time.time()
        # 处于冷却时间则直接退出，不记录
        if pid in self._cooldown and now - self._cooldown[pid] < COOLDOWN_SECONDS:
            return
        # 更新该人员最新记录时间戳
        self._cooldown[pid] = now
        # 写入数据库通行记录表
        add_access_record(
            person_id=pid,
            name=info["name"],
            department=info["department"],
            result=info["result"],
            confidence=info["confidence"]
        )

def run_recognition_loop(timeout: float = None):
    """
    启动实时识别主循环
    :param timeout: 限时自动判定时长(秒)，到期自动综合判定；None为手动Q键退出持续实时监控
    """
    # 开启默认摄像头
    cap = cv2.VideoCapture(0)
    # 摄像头打开失败直接终止
    if not cap.isOpened():
        print("[错误] 无法打开摄像头")
        return

    # 设置摄像头分辨率1280×720高清，提升识别稳定性
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # 实例化通行管控核心控制器
    controller = AccessController()
    fps_time = time.time()
    fps = 0
    frame_count = 0
    start_time = time.time()

    # 限时模式缓存：记录每个身份最佳置信度、累计出现帧数，用于最终综合判定
    best_per_person: dict = {}

    # 启动提示文案区分限时/常驻模式
    if timeout:
        print(f"\n[识别] 摄像头已开启，检测时长 {timeout:.0f} 秒，请看向镜头...")
    else:
        print("[识别] 启动实时识别... 按 Q 退出")

    while True:
        # 读取一帧视频流
        ret, frame = cap.read()
        if not ret:
            continue

        frame_count += 1
        # 隔帧处理，降低CPU负载，偶数帧执行识别渲染，奇数帧直接原图展示
        if frame_count % 2 == 0:
            annotated, results = controller.process_frame(frame)
            # 遍历本帧识别结果，更新各身份统计数据
            for r in results:
                pid = r["person_id"]
                # 陌生人身份处理
                if pid == -1:
                    # 首次出现陌生人则初始化记录，已有记录则帧数+1，更新最优置信度
                    if -1 not in best_per_person or r["confidence"] < best_per_person[-1]["best_confidence"]:
                        best_per_person[-1] = {
                            "name": r["name"], "department": r["department"],
                            "result": r["result"], "best_confidence": r["confidence"],
                            "color": r["color"], "permission": r["permission"],
                            "frame_count": 1
                        }
                    else:
                        best_per_person[-1]["frame_count"] = best_per_person[-1].get("frame_count", 1) + 1
                # 内部注册人员处理
                else:
                    prev = best_per_person.get(pid)
                    # 首次检测到该人员，初始化统计信息
                    if prev is None:
                        best_per_person[pid] = {
                            "name": r["name"], "department": r["department"],
                            "result": r["result"], "best_confidence": r["confidence"],
                            "color": r["color"], "permission": r["permission"],
                            "frame_count": 1
                        }
                    # 已存在记录：帧数累加，若当前置信度更优则更新最佳置信度
                    else:
                        best_per_person[pid]["frame_count"] = prev.get("frame_count", 1) + 1
                        if r["confidence"] < prev["best_confidence"]:
                            best_per_person[pid]["best_confidence"] = r["confidence"]
        else:
            # 奇数帧不处理，直接原图赋值
            annotated = frame

        # 每秒计算一次FPS帧率
        elapsed = time.time() - fps_time
        if elapsed >= 1.0:
            fps = frame_count / elapsed
            fps_time = time.time()
            frame_count = 0

        # 计算剩余倒计时时长（限时模式）
        remaining = ""
        if timeout:
            remain = max(0, timeout - (time.time() - start_time))
            remaining = f"剩余 {remain:.0f}s"

        # 绘制顶部半透明黑色状态栏背景
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.rectangle(annotated, (0, 0), (annotated.shape[1], 42), (30, 30, 30), -1)
        # 状态栏系统信息文字
        put_text_auto(annotated, f"人脸通行管控系统  {now_str}  FPS:{fps:.1f}  {remaining}",
                      (10, 5), (255, 255, 255), 22)

        # 模型未训练警告提示
        if not is_model_trained():
            put_text_auto(annotated, "! 模型未训练，请先注册人员并训练",
                          (10, 70), (0, 165, 255), 20)

        # 弹出实时监控窗口
        cv2.imshow("人脸通行管控系统 - Press Q to Quit", annotated)

        # 限时模式倒计时结束跳出循环
        if timeout and (time.time() - start_time) >= timeout:
            break
        # Q键、ESC键退出循环
        if cv2.waitKey(30) in (ord('q'), ord('Q'), 27):
            break

    # 释放摄像头硬件资源
    cap.release()
    # 销毁所有OpenCV窗口
    cv2.destroyAllWindows()

    # 限时模式：执行综合判定输出最终单次通行结果
    if timeout:
        _make_single_verdict(best_per_person, time.time() - start_time)
    # 常驻实时模式：输出检测汇总报表
    else:
        _print_detection_report(best_per_person, time.time() - start_time)

def _make_single_verdict(best_per_person: dict, elapsed: float):
    """
    限时采集后综合判定唯一通行结果
    核心规则：注册人员需满足最小出现帧数阈值，选取置信度最优者；无合格人员则拒绝
    """
    print("\n" + "=" * 56)
    print("  >>> 人脸通行判定结果 <<<")
    print("=" * 56)

    # 全程未检测到人脸，直接拒绝通行并记录
    if not best_per_person:
        print("  未检测到任何人脸 → 拒绝通行")
        print("=" * 56)
        add_access_record(-1, "无人", "-", "拒绝通行", 999.0)
        return

    # 筛选：已知注册人员 且 出现帧数达到最低有效帧数要求
    known = {
        k: v for k, v in best_per_person.items()
        if k != -1 and v.get("frame_count", 1) >= MIN_DETECT_FRAMES
    }
    # 所有检测到的内部注册人员（无论帧数是否达标）
    known_all = {k: v for k, v in best_per_person.items() if k != -1}
    # 陌生人检测数据
    stranger = best_per_person.get(-1)

    # 基础检测统计信息打印
    print(f"  检测耗时: {elapsed:.1f} 秒")
    print(f"  检测到身份数: {len(best_per_person)}")
    for pid, info in best_per_person.items():
        name = info.get("name", "陌生人") if pid != -1 else "陌生人"
        fc = info.get("frame_count", 1)
        conf = info.get("best_confidence", 999)
        print(f"    - {name}  出现{fc}帧  最佳置信度:{conf:.1f}")
    print()

    # 存在符合帧数要求的可信内部人员
    if known:
        # 选取置信度数值最小（匹配度最高）的人员作为最终判定对象
        best_pid = min(known, key=lambda k: known[k]["best_confidence"])
        best = known[best_pid]
        judge = "✓ 允许通行" if best["result"] == "允许通行" else "✗ 拒绝通行"
        # 输出详细判定依据
        print(f"  识别身份: {best['name']}（{best['department']}）")
        print(f"  匹配置信度: {100 - best['best_confidence']:.1f}%")
        print(f"  出现帧数: {best.get('frame_count', 1)}")
        print(f"  数据库权限: {best['permission']}")
        print(f"  ───────────────────────")
        print(f"  最终判定: {judge}")

        # 写入最终判定通行记录
        add_access_record(
            person_id=best_pid,
            name=best["name"],
            department=best["department"],
            result=best["result"],
            confidence=best["best_confidence"]
        )
    else:
        # 有内部人员但帧数不足，提示可信度不足
        if known_all:
            print(f"  以下已知人员检测帧数不足（需>= {MIN_DETECT_FRAMES}帧），视为不可信：")
            for pid, info in known_all.items():
                print(f"    - {info['name']} 仅出现{info.get('frame_count', 1)}帧")
            print()
        # 无有效可信身份，统一拒绝通行
        print(f"  所有检测均不可信或陌生")
        print(f"  ───────────────────────")
        print(f"  最终判定: ✗ 拒绝通行（未通过身份验证）")
        conf = stranger["best_confidence"] if stranger else 999.0
        add_access_record(-1, "陌生人", "-", "拒绝通行", conf)

    print("=" * 56)

def _print_detection_report(detected: dict, elapsed: float):
    """常驻实时模式退出后，打印简洁识别汇总报告"""
    print("\n" + "=" * 60)
    print(f"  检测完成 · 用时 {elapsed:.1f} 秒")
    print("=" * 60)

    # 全程无人脸检测
    if not detected:
        print("  未检测到任何人脸")
        print("=" * 60)
        return

    # 按置信度升序排序，匹配度由高到低展示
    sorted_results = sorted(detected.items(),
                            key=lambda x: x[1].get("best_confidence", 999))

    # 表格表头
    print(f"  {'姓名':<12} {'通行结果':<10} {'最佳置信度':<12}")
    print("  " + "-" * 40)
    # 遍历打印每个识别到的人员信息
    for pid, info in sorted_results:
        conf = info.get("best_confidence", 999)
        print(f"  {info['name']:<12} {info['result']:<10} {100-conf:.1f}%")

    print("=" * 60)
    print(f"  共识别 {len(detected)} 个唯一身份")
    print("=" * 60)