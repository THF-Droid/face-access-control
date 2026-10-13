"""
数据库模块 - 人员信息、识别记录、管理员账户管理（MySQL 版）
=========================================================================
使用 pymysql + SQLAlchemy 操作 MySQL，用 pd.read_sql() 保持与 CSV 版相同的
DataFrame 返回格式，app.py / analytics.py / main.py 无需修改。
"""
# 系统路径操作模块
import os
# 哈希加密模块，用于管理员密码加密存储
import hashlib
# MySQL原生连接驱动
import pymysql
# 数据分析库，查询结果统一封装为DataFrame，兼容旧版CSV逻辑
import pandas as pd
# 日期时间处理，用于通行记录时间戳
from datetime import datetime
# SQLAlchemy引擎，适配pandas读取MySQL
from sqlalchemy import create_engine

# 导入MySQL连接配置
try:
    # 优先从外部配置文件加载数据库参数
    from config import DB_CONFIG
except ImportError:
    # 配置文件缺失时使用默认本地配置（密码请通过环境变量 DB_PASSWORD 或 config.py 提供）
    DB_CONFIG = {
        "host": "localhost", "port": 3306, "user": "root",
        "password": "", "database": "face_access_control",
        "charset": "utf8mb4", "autocommit": True
    }

# ── 路径常量定义 ──────────────────────────────────────────────────────────────────
# 获取当前文件上级的上级目录，定位项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 项目data总目录
DATA_DIR = os.path.join(BASE_DIR, "data")
# 人脸样本存储根目录
FACES_DIR = os.path.join(DATA_DIR, "faces")
# 通行记录文件附属目录（兼容文件兜底）
RECORDS_DIR = os.path.join(DATA_DIR, "records")
# 不存在则自动创建文件夹，避免保存人脸时报错
os.makedirs(FACES_DIR, exist_ok=True)
os.makedirs(RECORDS_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  内部工具私有函数
# ═══════════════════════════════════════════════════════════════════════════════

def _hash_password(password: str) -> str:
    """SHA-256 哈希密码加密，明文密码不可逆加密存储"""
    # 字符串转utf8字节流，进行sha256哈希，返回十六进制密文字符串
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_engine():
    """获取 SQLAlchemy 引擎（专供 pd.read_sql 查询使用）"""
    db = DB_CONFIG
    # 拼接MySQL连接URL，符合SQLAlchemy格式规范
    url = (f"mysql+pymysql://{db['user']}:{db['password']}"
           f"@{db['host']}:{db['port']}/{db['database']}"
           f"?charset={db.get('charset', 'utf8mb4')}")
    # 创建连接引擎，配置连接池参数：常驻连接3，最大溢出5，1小时回收空闲连接
    return create_engine(url, pool_size=3, max_overflow=5, pool_recycle=3600)


def _get_conn():
    """获取原生 pymysql 连接（专供增删改执行语句）"""
    # 直接用配置字典创建原生数据库连接
    return pymysql.connect(**DB_CONFIG)


def _query_df(sql: str, params=None):
    """执行查询SQL并返回 pandas DataFrame，统一查询返回格式"""
    engine = _get_engine()
    try:
        # pandas读取SQL查询结果，自动转为DataFrame，参数防SQL注入
        return pd.read_sql(sql, engine, params=params)
    finally:
        # 无论是否报错，释放引擎连接，避免连接泄漏
        engine.dispose()


def _execute(sql: str, params=None) -> int:
    """执行非查询DML语句（UPDATE/DELETE/CREATE），返回受影响行数"""
    conn = _get_conn()
    try:
        # 上下文管理器创建游标，自动关闭游标
        with conn.cursor() as cur:
            # 执行带参数SQL，预编译防注入
            n = cur.execute(sql, params)
            # 手动提交事务
            conn.commit()
            # 返回本次操作影响的数据行数
            return n
    finally:
        # 关闭数据库连接
        conn.close()


def _execute_insert(sql: str, params=None) -> int:
    """执行 INSERT 插入语句，执行成功后返回自增主键ID"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            # 获取插入后自动生成的自增ID
            return cur.lastrowid
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
#  数据库初始化函数：建库、建表、初始化默认管理员
# ═══════════════════════════════════════════════════════════════════════════════

def init_database():
    """初始化数据库表（自动建库 + 建表 + 默认管理员）"""
    # 从配置读取目标数据库名
    db_name = DB_CONFIG.get("database", "face_access_control")

    # 1) 先不带指定数据库连接，创建数据库本身（库不存在时创建）
    try:
        # 临时连接，不选定数据库，仅用于创建库
        conn_no_db = pymysql.connect(
            host=DB_CONFIG.get("host", "localhost"),
            port=DB_CONFIG.get("port", 3306),
            user=DB_CONFIG.get("user", "root"),
            password=DB_CONFIG.get("password", ""),
            charset=DB_CONFIG.get("charset", "utf8mb4"),
            autocommit=True,
        )
        cur = conn_no_db.cursor()
        # 不存在则创建数据库，指定utf8mb4完整字符集，支持emoji
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        # 关闭临时库连接
        conn_no_db.close()
    except pymysql.Error as e:
        # 捕获MySQL连接/权限错误并打印
        print(f"[DB] 创建数据库失败: {e}")
        return

    # 2) 进入目标数据库，创建三张业务数据表+默认管理员账号
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # 人员信息表：存储注册员工基础信息
        cur.execute("""
            CREATE TABLE IF NOT EXISTS persons (
                id            INT           AUTO_INCREMENT PRIMARY KEY,
                name          VARCHAR(50)   NOT NULL,
                department    VARCHAR(100)  DEFAULT '未分配',
                role          VARCHAR(50)   DEFAULT '',
                phone         VARCHAR(20)   DEFAULT '',
                permission    VARCHAR(10)   DEFAULT '允许',
                register_time DATETIME      DEFAULT CURRENT_TIMESTAMP,
                remark        VARCHAR(200)  DEFAULT ''
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        # 通行记录表：每一次刷脸识别都会写入一条记录
        cur.execute("""
            CREATE TABLE IF NOT EXISTS access_records (
                record_id     INT           AUTO_INCREMENT PRIMARY KEY,
                person_id     INT           NOT NULL,
                name          VARCHAR(50)   NOT NULL,
                department    VARCHAR(100)  DEFAULT '-',
                access_time   DATETIME      DEFAULT CURRENT_TIMESTAMP,
                access_result VARCHAR(20)   NOT NULL,
                confidence    DECIMAL(8,2)  DEFAULT 0,
                date          DATE          NOT NULL,
                hour          TINYINT       NOT NULL,
                INDEX idx_person  (person_id),
                INDEX idx_date    (date),
                INDEX idx_hour    (hour),
                INDEX idx_result  (access_result)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        # 管理员账号表：后台登录账号密码哈希存储
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                username      VARCHAR(50)   PRIMARY KEY,
                password_hash VARCHAR(64)   NOT NULL,
                create_time   DATETIME      DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 插入默认管理员账号，IGNORE保证重复创建不会报错
        cur.execute(
            "INSERT IGNORE INTO admins (username, password_hash) VALUES (%s, %s)",
            ("admin", _hash_password("admin123"))
        )
        # 提交表结构与初始数据
        conn.commit()
        print("[DB] MySQL 数据库表已初始化  默认账号: admin  密码: admin123")
        cur.close()
        conn.close()
    except pymysql.Error as e:
        print(f"[DB] 数据库连接失败: {e}")
        print("[DB] 请确认 MySQL 已启动，且 config.py 中的连接参数正确")


# ═══════════════════════════════════════════════════════════════════════════════
#  管理员账户CRUD管理
# ═══════════════════════════════════════════════════════════════════════════════

def verify_admin(username: str, password: str) -> bool:
    """验证管理员账号密码，校验成功返回True"""
    try:
        # 根据用户名查询加密后的密码
        df = _query_df(
            "SELECT password_hash FROM admins WHERE username=%s", (username,)
        )
        # 无此用户直接返回False
        if len(df) == 0:
            return False
        # 比对输入密码哈希与库中存储哈希值
        return df.iloc[0]["password_hash"] == _hash_password(password)
    except pymysql.Error:
        # 数据库异常直接认证失败
        return False


def load_admins() -> pd.DataFrame:
    """加载全部管理员列表，返回DataFrame"""
    try:
        # 查询管理员账号、哈希密码、创建时间，按创建时间排序
        return _query_df("SELECT username, password_hash, create_time FROM admins ORDER BY create_time")
    except pymysql.Error:
        # 异常返回空框架，保证上层调用不崩溃
        return pd.DataFrame(columns=["username", "password_hash", "create_time"])


def add_admin(username: str, password: str) -> bool:
    """新增管理员，用户名唯一冲突则返回False"""
    try:
        # 插入新管理员账号与加密密码
        _execute("INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                 (username, _hash_password(password)))
        print(f"[DB] 新增管理员: {username}")
        return True
    except pymysql.IntegrityError:
        # 唯一性约束冲突（账号已存在）捕获
        return False


def change_admin_password(username: str, new_password: str) -> bool:
    """修改指定管理员密码，修改成功返回True"""
    # 执行更新语句，传入新密码哈希与目标用户名
    n = _execute(
        "UPDATE admins SET password_hash=%s WHERE username=%s",
        (_hash_password(new_password), username)
    )
    if n:
        print(f"[DB] 管理员 {username} 密码已修改")
    # 受影响行数大于0代表修改成功
    return n > 0


def delete_admin(username: str) -> bool:
    """删除管理员，禁止删除最后一个管理员账号"""
    df = load_admins()
    # 管理员只剩一人时拒绝删除，保证系统可登录
    if len(df) <= 1:
        return False
    # 执行删除
    n = _execute("DELETE FROM admins WHERE username=%s", (username,))
    if n:
        print(f"[DB] 已删除管理员: {username}")
    return n > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  人员信息管理 增删改查
# ═══════════════════════════════════════════════════════════════════════════════

def load_persons() -> pd.DataFrame:
    """加载所有注册人员完整信息，按ID升序"""
    try:
        return _query_df("""
            SELECT id, name, department, role, phone, permission,
                   register_time, remark
            FROM persons ORDER BY id
        """)
    except pymysql.Error:
        # 异常返回空表，保持字段结构兼容上层代码
        return pd.DataFrame(columns=[
            "id", "name", "department", "role", "phone",
            "permission", "register_time", "remark"
        ])


def add_person(name: str, department: str, permission: str = "允许",
               role: str = "", phone: str = "", remark: str = "") -> int:
    """添加新注册人员，自动生成ID并返回自增主键"""
    new_id = _execute_insert(
        "INSERT INTO persons (name, department, role, phone, permission, remark) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (name, department, role, phone, permission, remark)
    )
    print(f"[DB] 新增人员: ID={new_id}, 姓名={name}, 部门={department}")
    return new_id


def get_person_by_id(person_id: int) -> dict:
    """根据人员ID查询单人详情，返回字典格式，无数据返回空字典"""
    try:
        df = _query_df("SELECT * FROM persons WHERE id=%s", (person_id,))
        if len(df) == 0:
            return {}
        # 转为单行字典
        row = df.iloc[0].to_dict()
        # Timestamp转为字符串，适配控制台打印兼容性
        if isinstance(row.get("register_time"), pd.Timestamp):
            row["register_time"] = row["register_time"].strftime("%Y-%m-%d %H:%M:%S")
        return row
    except pymysql.Error:
        return {}


def search_persons(keyword: str) -> pd.DataFrame:
    """模糊搜索：姓名、部门双字段模糊匹配，空关键词返回全部人员"""
    kw = keyword.strip()
    if not kw:
        return load_persons()
    try:
        # 左右百分号包裹实现模糊查询
        df = _query_df(
            "SELECT * FROM persons WHERE name LIKE %s OR department LIKE %s ORDER BY id",
            (f"%{kw}%", f"%{kw}%")
        )
        return df
    except pymysql.Error:
        return load_persons()


def update_person(person_id: int, **fields) -> bool:
    """
    动态更新人员信息，仅更新传入的合法字段
    允许更新字段: name, department, role, phone, permission, remark
    """
    # 过滤仅允许的字段，防止注入非法字段
    allowed = {"name", "department", "role", "phone", "permission", "remark"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    # 无有效更新字段直接返回
    if not updates:
        return False
    # 拼接动态SET语句
    set_clause = ", ".join(f"{k}=%s" for k in updates)
    # 参数：更新值列表 + 条件ID
    values = list(updates.values()) + [person_id]
    n = _execute(f"UPDATE persons SET {set_clause} WHERE id=%s", values)
    if n:
        print(f"[DB] 更新人员 {person_id}: {updates}")
    return n > 0


def update_permission(person_id: int, permission: str):
    """单独更新人员通行权限，兼容旧版接口封装"""
    update_person(person_id, permission=permission)


def delete_person(person_id: int):
    """删除数据库人员记录，同时本地删除该人员全部人脸样本文件夹"""
    # 数据库删除人员行
    _execute("DELETE FROM persons WHERE id=%s", (person_id,))
    # 导入文件删除工具
    import shutil
    # 该人员人脸样本文件夹路径
    person_dir = os.path.join(FACES_DIR, str(person_id))
    # 存在文件夹则递归删除
    if os.path.exists(person_dir):
        shutil.rmtree(person_dir)
    # 兜底单张人脸图片删除
    face_path = os.path.join(FACES_DIR, f"{person_id}.jpg")
    if os.path.exists(face_path):
        os.remove(face_path)
    print(f"[DB] 已删除人员 {person_id}")


# ═══════════════════════════════════════════════════════════════════════════════
#  通行记录读写管理
# ═══════════════════════════════════════════════════════════════════════════════

def add_access_record(person_id: int, name: str, department: str,
                      result: str, confidence: float):
    """新增一条刷脸通行识别记录，自动填充时间、日期、时段用于统计"""
    now = datetime.now()
    _execute_insert(
        "INSERT INTO access_records "
        "(person_id, name, department, access_time, access_result, confidence, date, hour) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (person_id, name, department, now,
         result, round(confidence, 4),
         now.strftime("%Y-%m-%d"), now.hour)
    )


def delete_record(record_id: int) -> bool:
    """删除单条通行记录，按记录主键ID删除"""
    n = _execute("DELETE FROM access_records WHERE record_id=%s", (record_id,))
    if n:
        print(f"[DB] 已删除记录 {record_id}")
    return n > 0


def clear_records_before(date_str: str) -> int:
    """清理指定日期之前所有历史记录，返回删除总条数"""
    # 先统计符合删除条件的记录总数
    df = _query_df("SELECT COUNT(*) AS cnt FROM access_records WHERE date < %s", (date_str,))
    count = df.iloc[0]["cnt"] if len(df) > 0 else 0
    # 有数据才执行删除
    if count > 0:
        _execute("DELETE FROM access_records WHERE date < %s", (date_str,))
    return count


def load_records() -> pd.DataFrame:
    """加载全部通行记录，时间字段转为datetime，兼容统计分析代码dt属性调用"""
    try:
        df = _query_df("""
            SELECT record_id, person_id, name, department,
                   access_time, access_result, confidence, date, hour
            FROM access_records ORDER BY record_id
        """)
        if len(df) > 0:
            # 时间字段强制转为datetime类型，支持按月、日、小时统计
            df["access_time"] = pd.to_datetime(df["access_time"])
            df["date"] = pd.to_datetime(df["date"])
        return df
    except pymysql.Error:
        # 异常返回空结构，保证上层稳定
        return pd.DataFrame(columns=[
            "record_id", "person_id", "name", "department",
            "access_time", "access_result", "confidence", "date", "hour"
        ])


# ═══════════════════════════════════════════════════════════════════════════════
#  人脸路径工具（纯文件路径拼接，无数据库交互）
# ═══════════════════════════════════════════════════════════════════════════════

def get_face_path(person_id: int) -> str:
    """获取单人单张人脸缩略图完整路径"""
    return os.path.join(FACES_DIR, f"{person_id}.jpg")


def get_faces_dir() -> str:
    """获取人脸样本根目录路径"""
    return FACES_DIR