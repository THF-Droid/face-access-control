"""
人脸通行管控系统 - Web 后端 (Flask)
===========================================
提供 RESTful API 接口，为前端 SPA 提供数据服务。
"""
# 系统路径操作
import os
# 系统标准输入输出
import sys
# JSON数据处理
import json
# Base64编解码，用于前端图片传输
import base64
# 字节IO流
import io
# OpenCV图像处理、人脸检测识别
import cv2
# 数值矩阵处理
import numpy as np
# 日期时间处理
from datetime import datetime
# 装饰器工具，保留函数元信息
from functools import wraps

# Flask核心组件
from flask import Flask, jsonify, request, render_template, session
# 跨域请求支持，前后端分离必备
from flask_cors import CORS

# 获取当前文件所在目录作为基准路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 将基准目录加入Python模块搜索路径，方便导入自定义工具包
sys.path.insert(0, BASE_DIR)

# 导入数据库全套操作函数
from utils.database import (
    init_database, load_persons, add_person, get_person_by_id,
    search_persons, update_person, delete_person,
    load_records, delete_record, clear_records_before,
    verify_admin, load_admins, add_admin,
    change_admin_password, delete_admin,
)
# 导入人脸引擎采集、训练、识别全套工具
from utils.face_engine import (
    capture_face_samples, train_model, is_model_trained,
    get_face_detector, get_recognizer, detect_faces, recognize_face,
)
# 中文绘制工具，解决OpenCV无法渲染中文
from utils.chinese_text import put_text_auto

# 置信度阈值，和本地识别模块保持统一，LBPH值越小匹配度越高
CONFIDENCE_THRESHOLD = 35.0

# 初始化Flask应用，指定静态资源、模板文件夹
app = Flask(__name__, static_folder="static", template_folder="templates")
# 会话加密密钥，用于登录Session安全存储
# 生产环境请通过环境变量 FLASK_SECRET_KEY 设置随机密钥
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-insecure-secret-key-change-me")
# 全局开启跨域，允许前端页面跨域调用接口
CORS(app)


# ═══════════════════════════════════════════════════════
#  工具装饰器与通用响应封装
# ═══════════════════════════════════════════════════════

def admin_required(f):
    """管理员登录鉴权装饰器，保护后台接口必须登录后访问"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 会话中无登录标记，返回未登录401
        if not session.get("admin_logged_in"):
            return jsonify({"error": "未登录"}), 401
        # 已登录放行执行原接口
        return f(*args, **kwargs)
    return decorated


def api_response(success: bool, data=None, message: str = ""):
    """统一API返回格式，规范前后端交互结构"""
    return jsonify({"success": success, "data": data, "message": message})


# ═══════════════════════════════════════════════════════
#  页面路由：渲染HTML模板页面
# ═══════════════════════════════════════════════════════

@app.route("/")
def index():
    """根路由：跳转管理员登录页"""
    return render_template("login.html")


@app.route("/admin")
def admin_page():
    """管理员后台仪表盘页面，未登录则强制跳转登录页"""
    if not session.get("admin_logged_in"):
        return render_template("login.html")
    return render_template("dashboard.html")


@app.route("/user")
def user_page():
    """普通用户刷脸通行页面，无需登录"""
    return render_template("user.html")


# ═══════════════════════════════════════════════════════
#  身份认证API：登录、登出、登录状态校验
# ═══════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def api_login():
    """管理员账号密码登录接口"""
    # 解析前端POST JSON数据
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    # 调用数据库校验账号密码
    if verify_admin(username, password):
        # 登录成功写入Session会话
        session["admin_logged_in"] = True
        session["admin_username"] = username
        return api_response(True, {"username": username}, "登录成功")
    # 认证失败返回错误
    return api_response(False, message="账号或密码错误"), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    """退出登录，清空当前会话"""
    session.clear()
    return api_response(True, message="已退出")


@app.route("/api/check-auth")
def api_check_auth():
    """前端轮询校验管理员登录状态"""
    if session.get("admin_logged_in"):
        return api_response(True, {"username": session.get("admin_username")})
    return api_response(False, message="未登录"), 401


# ═══════════════════════════════════════════════════════
#  人员管理CRUD API（管理员权限）
# ═══════════════════════════════════════════════════════

@app.route("/api/persons", methods=["GET"])
@admin_required
def api_persons_list():
    """获取人员列表，支持关键词模糊搜索"""
    keyword = request.args.get("keyword", "").strip()
    # 有关键词则搜索，无关键词加载全部人员
    if keyword:
        df = search_persons(keyword)
    else:
        df = load_persons()
    persons = []
    # 遍历DataFrame封装为前端友好字典
    for _, r in df.iterrows():
        person_id = int(r["id"])
        face_folder = os.path.join(BASE_DIR, "data", "faces", str(person_id))
        # 判断该人员是否上传人脸样本
        has_face = os.path.exists(face_folder) and len(os.listdir(face_folder)) > 0
        persons.append({
            "id": person_id,
            "name": str(r["name"]),
            "department": str(r["department"]),
            "role": str(r.get("role", "")),
            "phone": str(r.get("phone", "")),
            "permission": str(r["permission"]),
            "register_time": str(r.get("register_time", "")),
            "remark": str(r.get("remark", "")),
            "has_face": has_face
        })
    return api_response(True, persons)


@app.route("/api/persons/<int:pid>", methods=["GET"])
@admin_required
def api_person_get(pid):
    """根据人员ID查询单人详情"""
    p = get_person_by_id(pid)
    if not p:
        return api_response(False, message="人员不存在"), 404
    p["id"] = int(p["id"])
    return api_response(True, p)


@app.route("/api/persons", methods=["POST"])
@admin_required
def api_person_add():
    """新增注册人员基础信息"""
    data = request.get_json()
    name = data.get("name", "").strip()
    # 姓名字段非空校验
    if not name:
        return api_response(False, message="姓名不能为空"), 400
    dept = data.get("department", "未分配").strip()
    role = data.get("role", "").strip()
    phone = data.get("phone", "").strip()
    perm = data.get("permission", "允许").strip()
    # 权限值合法性过滤
    if perm not in ("允许", "拒绝"):
        perm = "允许"
    remark = data.get("remark", "").strip()
    # 写入数据库获取自增ID
    pid = add_person(name, dept, perm, role, phone, remark)
    return api_response(True, {"id": pid}, f"人员 {name} 已创建")


@app.route("/api/persons/<int:pid>", methods=["PUT"])
@admin_required
def api_person_update(pid):
    """更新已有人员信息，仅允许指定字段"""
    data = request.get_json()
    # 限定可更新白名单字段，防止恶意修改
    allowed = {"name", "department", "role", "phone", "permission", "remark"}
    fields = {k: v for k, v in data.items() if k in allowed and v}
    if not fields:
        return api_response(False, message="无有效更新字段"), 400
    ok = update_person(pid, **fields)
    if ok:
        return api_response(True, message="更新成功")
    return api_response(False, message="人员不存在"), 404


@app.route("/api/persons/<int:pid>", methods=["DELETE"])
@admin_required
def api_person_delete(pid):
    """删除人员数据库记录+本地人脸文件夹"""
    p = get_person_by_id(pid)
    if not p:
        return api_response(False, message="人员不存在"), 404
    delete_person(pid)
    return api_response(True, message=f"已删除 {p['name']}")


# ═══════════════════════════════════════════════════════
#  Web端人脸采集接口（Base64图片上传）
# ═══════════════════════════════════════════════════════

@app.route("/api/face/capture", methods=["POST"])
@admin_required
def api_face_capture():
    """
    接收前端Base64编码图片，检测人脸并保存单张样本
    前端摄像头拍照逐张上传
    """
    data = request.get_json()
    pid = data.get("person_id")
    image_b64 = data.get("image", "")

    # 参数完整性校验
    if not pid or not image_b64:
        return api_response(False, message="缺少参数"), 400

    # 剔除Base64头部标识前缀
    if "," in image_b64:
        image_b64 = image_b64.split(",")[1]
    try:
        # Base64解码转OpenCV图像
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return api_response(False, message="图片解析失败"), 400

    # 初始化人脸检测器，灰度均衡化提升检测稳定性
    detector = get_face_detector()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_eq = cv2.equalizeHist(gray)
    # 多尺度人脸检测参数与本地采集保持一致
    faces = detector.detectMultiScale(
        gray_eq, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60),
        flags=cv2.CASCADE_SCALE_IMAGE
    )

    # 未检测到人脸直接返回
    if len(faces) == 0:
        return api_response(False, message="未检测到人脸，请正对摄像头并确保光线充足")

    # 选取画面面积最大人脸作为有效采集对象
    (x, y, w, h) = max(faces, key=lambda r: r[2] * r[3])
    face_roi = gray_eq[y:y+h, x:x+w]
    face_roi = cv2.resize(face_roi, (200, 200))

    # 构建人员人脸存储目录
    person_dir = os.path.join(BASE_DIR, "data", "faces", str(pid))
    os.makedirs(person_dir, exist_ok=True)
    # 统计已有样本数量，序号顺延
    existing = [f for f in os.listdir(person_dir) if f.endswith(".jpg")]
    sample_num = len(existing) + 1
    save_path = os.path.join(person_dir, f"{sample_num:04d}.jpg")
    cv2.imwrite(save_path, face_roi)

    return api_response(True, {
        "sample_num": sample_num,
        "total": sample_num
    }, f"已采集第 {sample_num} 张样本")


# ═══════════════════════════════════════════════════════
#  模型状态查询、训练、单帧识别、限时综合识别
# ═══════════════════════════════════════════════════════

@app.route("/api/model/status", methods=["GET"])
def api_model_status():
    """查询模型是否训练完成、注册总人数，游客与管理员均可访问"""
    trained = is_model_trained()
    persons = load_persons()
    return api_response(True, {
        "trained": trained,
        "person_count": len(persons)
    })


@app.route("/api/model/train", methods=["POST"])
@admin_required
def api_train():
    """触发LBPH模型训练，整合所有人员人脸样本"""
    persons = load_persons()
    if len(persons) == 0:
        return api_response(False, message="没有已注册人员")
    # 组装训练所需ID+姓名数据集
    persons_data = [(int(r["id"]), r["name"]) for _, r in persons.iterrows()]
    ok = train_model(persons_data)
    if ok:
        return api_response(True, message="模型训练完成")
    return api_response(False, message="训练失败，请确认已采集人脸样本"), 500


@app.route("/api/recognize/single", methods=["POST"])
@admin_required
def api_recognize_single():
    """单张图片即时识别接口，后台管理端人脸核验使用"""
    data = request.get_json()
    image_b64 = data.get("image", "")
    if not image_b64:
        return api_response(False, message="缺少图片数据"), 400

    # 前置校验模型状态
    if not is_model_trained():
        return api_response(False, message="模型未训练"), 400

    # Base64解码图像
    if "," in image_b64:
        image_b64 = image_b64.split(",")[1]
    try:
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception:
        return api_response(False, message="图片解析失败"), 400

    detector = get_face_detector()
    recognizer = get_recognizer()
    # 灰度均衡化预处理
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_eq = cv2.equalizeHist(gray)
    faces = detector.detectMultiScale(
        gray_eq, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60),
        flags=cv2.CASCADE_SCALE_IMAGE
    )

    results = []
    # 遍历检测到的所有人脸逐一识别鉴权
    for (x, y, w, h) in faces:
        face_roi = gray_eq[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (200, 200))
        person_id, confidence = recognize_face(face_roi, recognizer)

        # 置信度超标判定陌生人
        if confidence > CONFIDENCE_THRESHOLD:
            person_id = -1
            name = "陌生人"
            department = "-"
            permission = "拒绝"
            result = "陌生人"
        else:
            person = get_person_by_id(person_id) if person_id != -1 else {}
            permission = person.get("permission", "拒绝")
            department = person.get("department", "-")
            name = person.get("name", "陌生人")
            result = "允许通行" if permission == "允许" else "拒绝通行"

        results.append({
            "person_id": person_id,
            "name": name,
            "department": department,
            "confidence": round(confidence, 2),
            "permission": permission,
            "result": result,
            "face_rect": {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
        })

    return api_response(True, {
        "faces_detected": len(faces),
        "results": results
    })


@app.route("/api/recognize/quick", methods=["POST"])
def api_recognize_quick():
    """
    用户端3秒多帧综合识别，多帧投票+帧数校验防误判
    前端连续上传多帧画面，后端统计出现频次+最优置信度判定最终通行
    """
    data = request.get_json()
    images = data.get("images", [])
    if not images:
        return api_response(False, message="缺少图片数据"), 400

    if not is_model_trained():
        return api_response(False, message="系统未完成训练")

    detector = get_face_detector()
    recognizer = get_recognizer()

    # 字典存储各身份最佳置信度、累计出现帧数
    best_per_person = {}

    # 循环解析每一帧图像并识别
    for img_b64 in images:
        if "," in img_b64:
            img_b64 = img_b64.split(",")[1]
        try:
            img_bytes = base64.b64decode(img_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_eq = cv2.equalizeHist(gray)
        faces = detector.detectMultiScale(
            gray_eq, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )

        for (x, y, w, h) in faces:
            face_roi = gray_eq[y:y+h, x:x+w]
            face_roi = cv2.resize(face_roi, (200, 200))
            pid, conf = recognize_face(face_roi, recognizer)

            # 置信度不达标统一标记为陌生人ID
            if conf > CONFIDENCE_THRESHOLD:
                pid = -1
            key = pid

            # 首次检测到该身份初始化信息
            prev = best_per_person.get(key)
            if prev is None:
                person = get_person_by_id(pid) if pid != -1 else {}
                perm = person.get("permission", "拒绝")
                pname = person.get("name", "陌生人")
                best_per_person[key] = {
                    "person_id": pid,
                    "name": pname,
                    "department": person.get("department", "-"),
                    "confidence": round(conf, 2),
                    "permission": perm,
                    "result": "允许通行" if perm == "允许" else "拒绝通行",
                    "frame_count": 1
                }
            else:
                # 帧数累加，更新最优（最小）置信度
                prev["frame_count"] = prev.get("frame_count", 1) + 1
                if conf < prev["confidence"]:
                    prev["confidence"] = round(conf, 2)

    # 全程未检测人脸
    if not best_per_person:
        return api_response(False, message="未检测到人脸")

    # 筛选有效可信人员：非陌生人且至少出现2帧
    known = {
        k: v for k, v in best_per_person.items()
        if k != -1 and v.get("frame_count", 1) >= 2
    }

    if known:
        # 选取置信度最低（匹配度最高）作为最终判定对象
        best_pid = min(known, key=lambda k: known[k]["confidence"])
        verdict = known[best_pid]
    else:
        # 存在注册人员但帧数不足，判定识别不可信
        known_weak = {k: v for k, v in best_per_person.items() if k != -1}
        if known_weak:
            names = ", ".join(v["name"] for v in known_weak.values())
            return api_response(False, message=f"身份识别不可信（{names} 出现帧数不足），拒绝通行")
        # 纯陌生人判定拒绝
        verdict = {"person_id": -1, "name": "陌生人", "result": "拒绝通行",
                   "confidence": best_per_person.get(-1, {}).get("confidence", 999.0)}

    # 写入本次最终判定通行记录
    from utils.database import add_access_record
    add_access_record(
        person_id=verdict["person_id"],
        name=verdict["name"],
        department=verdict.get("department", "-"),
        result=verdict["result"],
        confidence=verdict.get("confidence", 999.0)
    )

    return api_response(True, {
        "verdict": verdict,
        "all_detected": list(best_per_person.values())
    })


# ═══════════════════════════════════════════════════════
#  通行记录管理API：分页查询、单人记录、删除、批量清空
# ═══════════════════════════════════════════════════════

@app.route("/api/records", methods=["GET"])
@admin_required
def api_records_list():
    """分页加载全部通行记录，倒序展示最新数据"""
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    records = load_records()

    if len(records) == 0:
        return api_response(True, {"records": [], "total": 0})

    total = len(records)
    # 按记录ID倒序，新记录在前
    df_sorted = records.sort_values("record_id", ascending=False)
    # 分页切片
    df_page = df_sorted.iloc[(page-1)*per_page : page*per_page]

    recs = []
    for _, r in df_page.iterrows():
        recs.append({
            "record_id": int(r["record_id"]),
            "person_id": int(r["person_id"]),
            "name": str(r["name"]),
            "department": str(r["department"]),
            "access_time": str(r["access_time"])[:19],
            "access_result": str(r["access_result"]),
            "confidence": float(r["confidence"]),
            "date": str(r["date"])[:10],
            "hour": int(r["hour"])
        })
    return api_response(True, {"records": recs, "total": total})


@app.route("/api/records/user/<int:pid>", methods=["GET"])
def api_records_by_person(pid):
    """普通用户查询本人历史刷脸记录，无需管理员权限"""
    limit = int(request.args.get("limit", 20))
    records = load_records()
    if len(records) == 0:
        return api_response(True, {"records": [], "total": 0})

    # 筛选指定人员ID记录并倒序
    df = records[records["person_id"] == pid].sort_values("record_id", ascending=False)
    total = len(df)
    df = df.head(limit)

    recs = []
    for _, r in df.iterrows():
        recs.append({
            "record_id": int(r["record_id"]),
            "access_time": str(r["access_time"])[:19],
            "access_result": str(r["access_result"]),
            "confidence": round(float(r["confidence"]), 1),
            "date": str(r["date"])[:10],
            "hour": int(r["hour"])
        })
    return api_response(True, {"records": recs, "total": total})


@app.route("/api/records/<int:rid>", methods=["DELETE"])
@admin_required
def api_record_delete(rid):
    """删除单条通行记录"""
    ok = delete_record(rid)
    if ok:
        return api_response(True, message="已删除")
    return api_response(False, message="记录不存在"), 404


@app.route("/api/records/clear", methods=["POST"])
@admin_required
def api_records_clear():
    """按日期批量清理指定日期前的历史记录"""
    data = request.get_json()
    date_str = data.get("before_date", "")
    if not date_str:
        return api_response(False, message="缺少日期参数"), 400
    n = clear_records_before(date_str)
    return api_response(True, {"deleted": n}, f"已清除 {n} 条记录")


# ═══════════════════════════════════════════════════════
#  数据统计与可视化图表API
# ═══════════════════════════════════════════════════════

@app.route("/api/stats", methods=["GET"])
@admin_required
def api_stats():
    """首页核心综合统计指标"""
    records = load_records()
    persons = load_persons()
    today = datetime.now().strftime("%Y-%m-%d")

    total_records = len(records)
    if total_records > 0:
        # 今日记录统计
        today_df = records[records["date"].astype(str).str.startswith(today)] if "date" in records.columns else records
        today_records = len(today_df) if "date" in records.columns else 0
        allow_count = len(records[records["access_result"] == "允许通行"])
        deny_count = len(records[records["access_result"] == "拒绝通行"])
        unknown_count = len(records[records["access_result"] == "陌生人"])
        allow_rate = round(allow_count / total_records * 100, 1) if total_records > 0 else 0
    else:
        today_records = 0
        allow_count = deny_count = unknown_count = 0
        allow_rate = 0

    return api_response(True, {
        "total_persons": len(persons),
        "total_records": total_records,
        "today_records": today_records,
        "allow_count": allow_count,
        "deny_count": deny_count,
        "unknown_count": unknown_count,
        "allow_rate": allow_rate,
        "model_trained": is_model_trained()
    })


@app.route("/api/analytics/daily", methods=["GET"])
@admin_required
def api_analytics_daily():
    """每日通行量趋势折线图数据"""
    records = load_records()
    if len(records) == 0:
        return api_response(True, {"dates": [], "counts": []})
    # 提取日期字符串，按日期分组计数
    records["date_str"] = records["access_time"].astype(str).str[:10]
    daily = records.groupby("date_str").size().reset_index(name="count")
    daily = daily.sort_values("date_str")
    return api_response(True, {
        "dates": daily["date_str"].tolist(),
        "counts": daily["count"].tolist()
    })


@app.route("/api/analytics/hourly", methods=["GET"])
@admin_required
def api_analytics_hourly():
    """24小时时段通行分布柱状图数据"""
    records = load_records()
    if len(records) == 0:
        return api_response(True, {"hours": [], "counts": [], "allows": [], "denies": []})
    # 按小时分组，统计总数、允许数、拒绝数
    hourly = records.groupby("hour").agg(
        total=("hour", "count"),
        allows=("access_result", lambda x: (x == "允许通行").sum()),
        denies=("access_result", lambda x: (x == "拒绝通行").sum())
    ).reset_index()
    hourly = hourly.sort_values("hour")
    return api_response(True, {
        "hours": [f"{h:02d}:00" for h in hourly["hour"].tolist()],
        "counts": hourly["total"].tolist(),
        "allows": hourly["allows"].tolist(),
        "denies": hourly["denies"].tolist()
    })


@app.route("/api/analytics/result-pie", methods=["GET"])
@admin_required
def api_analytics_pie():
    """通行结果分类饼图数据（允许/拒绝/陌生人）"""
    records = load_records()
    if len(records) == 0:
        return api_response(True, {"labels": [], "values": []})
    pie = records["access_result"].value_counts()
    return api_response(True, {
        "labels": pie.index.tolist(),
        "values": pie.values.tolist()
    })


@app.route("/api/analytics/top-persons", methods=["GET"])
@admin_required
def api_analytics_top():
    """高频通行人员TOP10排行"""
    records = load_records()
    if len(records) == 0:
        return api_response(True, {"names": [], "counts": []})
    # 过滤陌生人，统计注册人员通行频次，取前10
    top = records[records["person_id"] != -1].groupby("name").size().sort_values(ascending=False).head(10)
    return api_response(True, {
        "names": top.index.tolist(),
        "counts": top.values.tolist()
    })


# ═══════════════════════════════════════════════════════
#  管理员账号管理API
# ═══════════════════════════════════════════════════════

@app.route("/api/admins", methods=["GET"])
@admin_required
def api_admins_list():
    """获取全部管理员账号列表"""
    df = load_admins()
    admins = []
    for _, r in df.iterrows():
        admins.append({
            "username": r["username"],
            "create_time": str(r["create_time"])
        })
    return api_response(True, admins)


@app.route("/api/admins", methods=["POST"])
@admin_required
def api_admin_add():
    """新增后台管理员账号"""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return api_response(False, message="账号和密码不能为空"), 400
    if add_admin(username, password):
        return api_response(True, message=f"管理员 {username} 已添加")
    return api_response(False, message="账号已存在"), 400


@app.route("/api/admins/password", methods=["PUT"])
@admin_required
def api_admin_password():
    """修改管理员登录密码"""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return api_response(False, message="参数不完整"), 400
    if change_admin_password(username, password):
        return api_response(True, message="密码已修改")
    return api_response(False, message="账号不存在"), 404


@app.route("/api/admins/<username>", methods=["DELETE"])
@admin_required
def api_admin_delete(username):
    """删除管理员，底层限制最少保留一个管理员"""
    if delete_admin(username):
        return api_response(True, message=f"已删除 {username}")
    return api_response(False, message="删除失败（至少保留一个管理员）"), 400


# ═══════════════════════════════════════════════════════
#  服务程序入口启动
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # 程序启动自动初始化数据库表结构
    init_database()
    # 启动提示信息
    print("\n" + "=" * 56)
    print("  人脸通行管控系统 Web 版")
    print(f"  访问地址: http://localhost:5000")
    print("  管理员: admin / admin123")
    print("=" * 56 + "\n")
    # 启动Flask服务，开放外网访问，端口5000，调试模式开启
    app.run(host="0.0.0.0", port=5000, debug=True)