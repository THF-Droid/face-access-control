"""
人脸通行管控系统 - 主程序入口（v2.0）
=============================================
双模式：
  · 管理员模式 — 账号密码登录，完整增删改查 + 训练 + 统计
  · 用户模式   — 直接刷脸识别，3 秒自动判定通行

技术栈：OpenCV · NumPy · Pandas · Matplotlib
"""

# 导入系统路径与标准库
import os
import sys
# 用于密码隐藏输入
import getpass

# 获取当前脚本所在绝对目录，作为项目根路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 将项目根目录加入Python环境变量，方便导入自定义工具模块
sys.path.insert(0, BASE_DIR)

# 从数据库工具模块导入所有数据库操作函数
from utils.database import (
    init_database,                  # 初始化数据库、建表
    # 人员信息CRUD操作
    load_persons, add_person, get_person_by_id,
    search_persons, update_person, delete_person,
    # 通行记录操作
    load_records, delete_record, clear_records_before,
    # 管理员账号操作
    verify_admin, load_admins, add_admin,
    change_admin_password, delete_admin,
)
# 人脸采集、模型训练、模型状态检测
from utils.face_engine import capture_face_samples, train_model, is_model_trained
# 实时人脸识别主循环函数
from utils.recognition import run_recognition_loop
# 数据分析与各类可视化绘图函数
from utils.analytics import (
    get_summary_stats, plot_daily_trend, plot_hourly_distribution,
    plot_result_pie, plot_top_persons, plot_dashboard
)

# ══════════════════════════════════════════════════════
#  通用工具函数
# ══════════════════════════════════════════════════════

def cls():
    """清屏函数，兼容Windows与Linux/macOS"""
    # Windows使用cls，类Unix系统使用clear
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    """程序暂停，按回车返回上级菜单"""
    input("\n  按 Enter 键返回...")


def header(title: str):
    """打印统一格式菜单头部标题"""
    print("\n" + "═" * 58)
    print(f"   人脸通行管控系统  ·  {title}")
    print("═" * 58)


def confirm(msg: str = "  确认操作？(y/N): ") -> bool:
    """通用二次确认弹窗，输入y返回True，其余返回False"""
    return input(msg).strip().lower() == "y"


def ask(prompt: str, default: str = "") -> str:
    """带默认值的输入函数，空输入则返回默认值"""
    val = input(f"  {prompt}").strip()
    # 输入为空返回默认值，否则返回输入内容
    return val if val else default

# ══════════════════════════════════════════════════════
#  登录入口界面与验证逻辑
# ══════════════════════════════════════════════════════

def login_screen() -> str:
    """
    显示系统初始模式选择界面
    返回: "admin" | "user" | "exit"
    """
    # 先清空控制台
    cls()
    # 打印系统欢迎边框界面
    print("""
╔══════════════════════════════════════════════════════╗
║         人脸通行管控系统  v2.0                         ║
║     OpenCV · NumPy · Pandas · Matplotlib             ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║   1.  管理员登录（账号密码）                            ║
║   2.  用户模式（刷脸通行）                              ║
║   0.  退出系统                                        ║
║                                                      ║
╚══════════════════════════════════════════════════════╝""")
    # 判断人脸识别模型是否训练完成
    model_status = "✓ 已训练" if is_model_trained() else "✗ 未训练"
    # 加载所有注册人员，统计人数
    registered_count = len(load_persons())
    print(f"  模型状态: {model_status}  |  注册人数: {registered_count}\n")
    # 获取用户菜单选择
    ch = input("  请选择 [0-2]: ").strip()
    # 根据选择返回对应标识
    if ch == "1":
        return "admin"
    elif ch == "2":
        return "user"
    elif ch == "0":
        return "exit"
    # 无效输入返回空字符串，外层循环会重新选择
    return ""


def admin_login() -> bool:
    """管理员账号密码验证，最大3次重试机会，验证成功返回True"""
    print()
    # 循环最多3次输入
    for i in range(3):
        username = ask("账号: ")
        password = input("  密码: ").strip()
        # 调用数据库函数校验账号密码
        if verify_admin(username, password):
            print(f"\n  ✓ 欢迎，{username}！")
            return True
        # 计算剩余尝试次数
        remaining = 2 - i
        if remaining > 0:
            print(f"  ✗ 账号或密码错误，还剩 {remaining} 次机会")
        else:
            print("  ✗ 验证失败，返回主界面")
    # 三次全部错误，登录失败
    return False

# ══════════════════════════════════════════════════════
#  访客用户模式：一键刷脸通行
# ══════════════════════════════════════════════════════

def user_mode():
    """用户模式：直接启动摄像头刷脸，3秒内完成身份判定"""
    cls()
    header("用户模式 - 刷脸通行")
    # 前置校验：必须训练模型才能识别
    if not is_model_trained():
        print("  ✗ 系统尚未完成训练，请联系管理员")
        pause()
        return
    print("  请正对摄像头，系统将在 3 秒内完成识别...\n")
    # 启动识别循环，超时3秒自动结束
    run_recognition_loop(timeout=3)
    pause()

# ══════════════════════════════════════════════════════
#  管理员子模块：人员信息管理（增删改查）
# ══════════════════════════════════════════════════════

def admin_persons_menu():
    """人员管理二级菜单循环入口"""
    while True:
        cls()
        header("人员管理")
        # 读取全部注册人员数据
        persons = load_persons()
        # 格式化打印人员表格
        _print_persons_table(persons)

        # 功能选项提示
        print("\n  [1] 新增人员   [2] 查询人员   [3] 修改人员")
        print("  [4] 删除人员   [5] 重新采集人脸  [0] 返回")
        ch = input("\n  请选择: ").strip()

        # 菜单分支跳转
        if ch == "0":
            break
        elif ch == "1":
            _person_add()
        elif ch == "2":
            _person_search()
        elif ch == "3":
            _person_update()
        elif ch == "4":
            _person_delete()
        elif ch == "5":
            _person_recapture()


def _print_persons_table(df):
    """接收人员DataFrame，格式化控制台表格输出"""
    # 无数据提示
    if len(df) == 0:
        print("  （暂无人员数据）")
        return
    # 表头格式化，固定列宽对齐
    print(f"\n  {'ID':<5} {'姓名':<10} {'部门':<12} {'职务':<10} "
          f"{'电话':<14} {'权限':<6} {'备注'}")
    print("  " + "─" * 70)
    # 逐行遍历每行人员数据并打印
    for _, r in df.iterrows():
        print(f"  {int(r['id']):<5} {str(r['name']):<10} {str(r['department']):<12} "
              f"{str(r.get('role','')):<10} {str(r.get('phone','')):<14} "
              f"{str(r['permission']):<6} {str(r.get('remark',''))}")


def _person_add():
    """新增内部人员，填写资料+可选人脸采集"""
    header("新增人员")
    # 姓名字段必填校验
    name = ask("姓名（必填）: ")
    if not name:
        print("  ✗ 姓名不能为空")
        pause()
        return
    # 其余字段带默认值
    dept  = ask("部门: ", "未分配")
    role  = ask("职务（可选）: ", "")
    phone = ask("电话（可选）: ", "")
    perm  = ask("通行权限 允许/拒绝 [默认允许]: ", "允许")
    # 权限值合法性校验，非法值强制设为允许
    if perm not in ("允许", "拒绝"):
        perm = "允许"
    remark = ask("备注（可选）: ", "")

    # 调用数据库接口插入人员，返回自增ID
    pid = add_person(name, dept, perm, role, phone, remark)
    print(f"\n  ✓ 人员已创建，ID = {pid}")

    # 询问是否立刻采集人脸样本
    if confirm("  是否立即采集人脸样本？(y/N): "):
        n = ask("采集样本数量 [默认 30]: ", "30")
        # 输入数字则转整型，否则默认30张
        num = int(n) if n.isdigit() else 30
        # 调用人脸采集函数
        ok = capture_face_samples(pid, name, num)
        print("  ✓ 采集完成，请返回后重新训练模型" if ok else "  ✗ 采集失败或已取消")
    pause()


def _person_search():
    """按关键词模糊查询人员，支持姓名、部门检索"""
    header("查询人员")
    kw = ask("关键词（姓名/部门，留空显示全部）: ", "")
    # 调用检索函数
    result = search_persons(kw)
    _print_persons_table(result)
    # 查到数据后可输入ID查看单条详情
    if len(result) > 0:
        pid_str = ask("\n  输入 ID 查看详情（留空跳过）: ", "")
        if pid_str.isdigit():
            p = get_person_by_id(int(pid_str))
            if p:
                print()
                # 键值对逐条打印详情
                for k, v in p.items():
                    print(f"    {k}: {v}")
    pause()


def _person_update():
    """根据人员ID修改已有信息，回车保留原值"""
    header("修改人员信息")
    persons = load_persons()
    _print_persons_table(persons)
    pid_str = ask("\n  请输入要修改的人员 ID: ")
    # ID格式校验
    if not pid_str.isdigit():
        pause()
        return
    pid = int(pid_str)
    p = get_person_by_id(pid)
    # 校验ID是否存在
    if not p:
        print("  ✗ 找不到该 ID")
        pause()
        return

    # 展示当前基础信息
    print(f"\n  当前信息：{p['name']} | {p['department']} | {p['permission']}")
    print("  （直接回车保留原值）\n")

    # 构建更新字段字典，仅存储修改项
    fields = {}
    v = ask(f"  姓名 [{p['name']}]: ", "")
    if v: fields["name"] = v
    v = ask(f"  部门 [{p['department']}]: ", "")
    if v: fields["department"] = v
    v = ask(f"  职务 [{p.get('role','')}]: ", "")
    if v: fields["role"] = v
    v = ask(f"  电话 [{p.get('phone','')}]: ", "")
    if v: fields["phone"] = v
    v = ask(f"  权限 允许/拒绝 [{p['permission']}]: ", "")
    if v in ("允许", "拒绝"): fields["permission"] = v
    v = ask(f"  备注 [{p.get('remark','')}]: ", "")
    if v: fields["remark"] = v

    # 无任何修改直接退出
    if not fields:
        print("  未做任何修改")
        pause()
        return

    # 执行数据库更新
    if update_person(pid, **fields):
        print("  ✓ 信息已更新")
    else:
        print("  ✗ 更新失败")
    pause()


def _person_delete():
    """删除指定人员，连带人脸样本，高危二次确认"""
    header("删除人员")
    persons = load_persons()
    _print_persons_table(persons)
    pid_str = ask("\n  请输入要删除的人员 ID: ")
    if not pid_str.isdigit():
        pause()
        return
    pid = int(pid_str)
    p = get_person_by_id(pid)
    if not p:
        print("  ✗ 找不到该 ID")
        pause()
        return

    # 风险提示
    print(f"\n  即将删除：{p['name']}（{p['department']}）及其全部人脸样本")
    if confirm("  ⚠ 此操作不可恢复，确认删除？(y/N): "):
        delete_person(pid)
        print("  ✓ 已删除，请重新训练模型使更改生效")
    else:
        print("  已取消")
    pause()


def _person_recapture():
    """为已有人员重新采集人脸图像，覆盖旧样本"""
    header("重新采集人脸")
    persons = load_persons()
    _print_persons_table(persons)
    pid_str = ask("\n  请输入人员 ID: ")
    if not pid_str.isdigit():
        pause()
        return
    pid = int(pid_str)
    p = get_person_by_id(pid)
    if not p:
        print("  ✗ 找不到该 ID")
        pause()
        return
    # 自定义采集数量
    n = ask("  采集样本数量 [默认 30]: ", "30")
    num = int(n) if n.isdigit() else 30
    ok = capture_face_samples(pid, p["name"], num)
    print("  ✓ 采集完成，请重新训练模型" if ok else "  ✗ 采集失败")
    pause()

# ══════════════════════════════════════════════════════
#  管理员子模块：通行记录查询与清理
# ══════════════════════════════════════════════════════

def admin_records_menu():
    """通行记录管理二级菜单循环"""
    while True:
        cls()
        header("通行记录管理")
        records = load_records()

        # 空记录判断
        if len(records) == 0:
            print("  （暂无记录）")
        else:
            print(f"  共 {len(records)} 条，显示最近 20 条：\n")
            # 表头格式化
            print(f"  {'记录ID':<8} {'时间':<21} {'姓名':<10} {'部门':<12} {'结果':<10} {'置信度'}")
            print("  " + "─" * 72)
            # 取最后20条并倒序，最新记录置顶
            for _, r in records.tail(20).iloc[::-1].iterrows():
                t = str(r["access_time"])[:19]
                print(f"  {int(r['record_id']):<8} {t:<21} {str(r['name']):<10} "
                      f"{str(r['department']):<12} {str(r['access_result']):<10} "
                      f"{float(r['confidence']):.2f}")

        # 功能选择
        print("\n  [1] 删除指定记录  [2] 按日期清理历史  [0] 返回")
        ch = input("\n  请选择: ").strip()

        if ch == "0":
            break
        elif ch == "1":
            rid = ask("  请输入记录 ID: ")
            if rid.isdigit():
                ok = delete_record(int(rid))
                print("  ✓ 已删除" if ok else "  ✗ 记录不存在")
            pause()
        elif ch == "2":
            date_str = ask("  清除此日期之前的记录（格式 YYYY-MM-DD）: ")
            if date_str:
                n = clear_records_before(date_str)
                print(f"  ✓ 已清除 {n} 条记录")
            pause()

# ══════════════════════════════════════════════════════
#  管理员子模块：后台管理员账号管理
# ══════════════════════════════════════════════════════

def admin_accounts_menu():
    """管理员账号新增、改密、删除管理菜单"""
    while True:
        cls()
        header("管理员账户管理")
        admins = load_admins()
        # 账号列表表头
        print(f"\n  {'账号':<16} {'创建时间'}")
        print("  " + "─" * 40)
        for _, r in admins.iterrows():
            print(f"  {r['username']:<16} {r['create_time']}")

        print("\n  [1] 新增管理员  [2] 修改密码  [3] 删除管理员  [0] 返回")
        ch = input("\n  请选择: ").strip()

        if ch == "0":
            break
        elif ch == "1":
            username = ask("  新账号: ")
            if not username:
                pause(); continue
            # 隐藏密码输入
            password = getpass.getpass("  新密码: ")
            confirm_pw = getpass.getpass("  确认密码: ")
            # 两次密码一致性校验
            if password != confirm_pw:
                print("  ✗ 两次密码不一致")
            elif add_admin(username, password):
                print("  ✓ 管理员已添加")
            else:
                print("  ✗ 账号已存在")
            pause()
        elif ch == "2":
            username = ask("  要修改密码的账号: ")
            new_pw = getpass.getpass("  新密码: ")
            confirm_pw = getpass.getpass("  确认密码: ")
            if new_pw != confirm_pw:
                print("  ✗ 两次密码不一致")
            elif change_admin_password(username, new_pw):
                print("  ✓ 密码已修改")
            else:
                print("  ✗ 账号不存在")
            pause()
        elif ch == "3":
            username = ask("  要删除的账号: ")
            if confirm(f"  确认删除管理员 {username}？(y/N): "):
                ok = delete_admin(username)
                # 底层限制至少保留一个管理员，删除失败会提示
                print("  ✓ 已删除" if ok else "  ✗ 删除失败（至少保留一个管理员）")
            pause()

# ══════════════════════════════════════════════════════
#  管理员顶层主菜单
# ══════════════════════════════════════════════════════

def admin_main_menu():
    """管理员登录后的核心功能总菜单"""
    while True:
        cls()
        header("管理员后台")
        # 获取全局统计摘要数据
        stats = get_summary_stats()
        model_status = "✓ 已训练" if is_model_trained() else "✗ 未训练"
        # 顶部状态栏核心指标展示
        print(f"  模型: {model_status}  |  注册人员: {stats['total_persons']}  "
              f"|  总记录: {stats['total_records']}  |  今日: {stats['today_records']}")
        print(f"  允许通行: {stats['allow_count']}  拒绝: {stats['deny_count']}  "
              f"陌生人: {stats['unknown_count']}  允许率: {stats['allow_rate']}%")
        # 分区功能菜单文字界面
        print("""
  ┌── 人员管理 ───────────────────────────────────────────┐
  │  1. 人员增删改查（注册 / 修改 / 删除 / 查询）             │
  │  2. 训练识别模型                                       │
  ├── 运行管理 ───────────────────────────────────────────┤
  │  3. 启动实时识别（3 秒自动判定）                          │
  │  4. 通行记录管理（查看 / 删除 / 清理）                    │
  ├── 统计分析 ───────────────────────────────────────────┤
  │  5. 数据统计与可视化                                    │
  ├── 系统管理 ───────────────────────────────────────────┤
  │  6. 管理员账户管理（增删改密码）                          │
  │  0. 退出登录                                          │
  └──────────────────────────────────────────────────────┘""")

        ch = input("\n  请选择 [0-6]: ").strip()

        # 菜单路由分发
        if ch == "0":
            break
        elif ch == "1":
            admin_persons_menu()
        elif ch == "2":
            _admin_train()
        elif ch == "3":
            _admin_recognition()
        elif ch == "4":
            admin_records_menu()
        elif ch == "5":
            _admin_analytics()
        elif ch == "6":
            admin_accounts_menu()


def _admin_train():
    """管理员手动启动人脸模型训练"""
    cls()
    header("训练识别模型")
    persons = load_persons()
    # 无注册人员无法训练
    if len(persons) == 0:
        print("  没有已注册人员，请先添加人员")
        pause()
        return
    print(f"  当前注册 {len(persons)} 人，开始训练...")
    # 封装训练所需ID和姓名数据
    persons_data = [(int(r["id"]), r["name"]) for _, r in persons.iterrows()]
    ok = train_model(persons_data)
    print("  ✓ 模型训练完成！" if ok else "  ✗ 训练失败，请确认已采集人脸样本")
    pause()


def _admin_recognition():
    """管理员后台启动实时人脸识别"""
    cls()
    header("实时识别与通行管控")
    # 校验模型训练状态
    if not is_model_trained():
        print("  ✗ 尚未训练模型，请先完成训练")
        pause()
        return
    print("  摄像头即将启动，3 秒后自动判定（按 Q 可提前退出）...")
    run_recognition_loop(timeout=3)
    pause()


def _admin_analytics():
    """数据分析可视化子菜单，切换各类图表"""
    while True:
        cls()
        header("数据统计与可视化")
        stats = get_summary_stats()
        # 基础统计数据展示
        print(f"  总记录: {stats['total_records']}  |  注册人员: {stats['total_persons']}")
        print(f"  允许: {stats['allow_count']}  拒绝: {stats['deny_count']}  "
              f"陌生人: {stats['unknown_count']}  |  允许率: {stats['allow_rate']}%")
        print(f"  今日记录: {stats['today_records']}\n")
        # 图表类型选择
        print("  [1] 每日趋势折线图  [2] 各时段柱状图")
        print("  [3] 结果分布饼图   [4] 人员排行榜")
        print("  [5] 综合数据看板   [0] 返回")
        ch = input("\n  请选择: ").strip()
        # 调用对应绘图函数
        if ch == "0": break
        elif ch == "1": plot_daily_trend()
        elif ch == "2": plot_hourly_distribution()
        elif ch == "3": plot_result_pie()
        elif ch == "4": plot_top_persons()
        elif ch == "5": plot_dashboard()

# ══════════════════════════════════════════════════════
#  程序全局入口
# ══════════════════════════════════════════════════════

def main():
    """程序主入口，初始化数据库+循环模式选择"""
    # 程序启动第一件事：初始化数据库表结构，不存在则创建
    init_database()

    # 主循环，持续提供模式选择
    while True:
        mode = login_screen()

        # 退出系统
        if mode == "exit":
            print("\n  再见！\n")
            sys.exit(0)
        # 访客刷脸模式
        elif mode == "user":
            user_mode()
        # 管理员登录校验，成功进入后台
        elif mode == "admin":
            if admin_login():
                admin_main_menu()
            # 登录失败自动回到选择界面，无需额外处理

        # 无效输入自动循环回登录选择页


# 脚本直接运行时启动主函数
if __name__ == "__main__":
    main()