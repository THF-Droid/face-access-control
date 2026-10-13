# 人脸识别通行管控系统

基于 Python + OpenCV (LBPH) + Flask 的人脸识别通行管控系统：集人脸采集、模型训练、实时识别、权限管控、通行记录与统计可视化于一体，并提供 Web 管理后台与 MySQL 数据持久化。

## 功能特性

- **人脸注册采集**：摄像头实时采集人脸样本（默认 30 张/人，可调）
- **模型训练**：基于 LBPH 算法训练人脸识别模型
- **实时识别管控**：绿框 = 允许通行 / 红框 = 拒绝通行 / 橙框 = 陌生人
- **通行记录**：自动记录每次识别事件（时间、结果、置信度），5 秒冷却防重复
- **数据统计**：每日趋势、时段分布、结果占比、人员排行、综合看板
- **Web 管理后台**：Flask + 前端页面，人员管理、记录查询、数据看板、单张图片识别
- **MySQL 持久化**：pymysql + SQLAlchemy，查询结果统一封装为 DataFrame

## 技术栈

| 库 | 用途 |
|---|---|
| **OpenCV** (`opencv-contrib-python`) | 人脸检测（Haar 级联）、LBPH 人脸识别、摄像头采集 |
| **NumPy** | 图像数组运算、标签数组处理 |
| **Pandas** | 数据存储、通行记录时序分析、统计聚合 |
| **Matplotlib** | 折线图、柱状图、饼图、综合数据看板 |
| **Flask** + **flask-cors** | Web 管理后台与 REST API |
| **PyMySQL** + **SQLAlchemy** | MySQL 连接与查询 |

---

## 目录结构

```
├── main.py                  # 主程序入口（命令行菜单 UI）
├── app.py                   # Flask Web 服务与 REST API（端口 5000）
├── compare_models.py        # LBPH / EigenFaces 模型对比实验
├── DB_Init.sql              # MySQL 数据库初始化脚本
├── config.example.py        # 数据库配置模板（复制为 config.py 使用）
├── requirements.txt         # 依赖列表
├── utils/
│   ├── database.py          # 数据层：人员 / 记录 / 管理员（MySQL）
│   ├── face_engine.py       # 人脸采集 & 训练 & 识别（OpenCV）
│   ├── recognition.py       # 实时识别与通行管控循环
│   ├── analytics.py         # 统计分析 & 可视化（Matplotlib）
│   └── chinese_text.py      # OpenCV 中文绘制工具
├── templates/               # Flask 页面模板（后台 / 登录 / 用户端）
├── static/                  # 前端静态资源（CSS / JS）
├── data/                    # 运行数据（人脸图像、CSV、图表，已 gitignore）
├── models/                  # LBPH 训练模型（训练后生成，已 gitignore）
└── generate_*.py            # 课程报告图表 / 文档生成脚本（可选）
```

---

## 安装依赖

```bash
pip install -r requirements.txt
```

> `opencv-contrib-python` 包含 `LBPHFaceRecognizer`，请勿安装普通版 `opencv-python`。

---

## 数据库配置

系统通过 `config.py` 读取 MySQL 连接参数（缺失时回退到内置默认配置）：

```bash
# Windows
copy config.example.py config.py
# Linux / macOS
cp config.example.py config.py
```

编辑 `config.py` 填入你的数据库密码，然后执行 `DB_Init.sql` 初始化数据库
（默认管理员账号 `admin` / 密码 `admin123`，**首次使用请立即修改**）。

> `config.py` 含数据库密码，已在 `.gitignore` 中排除，不会提交到仓库。
> 也可通过环境变量配置：`DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`。

---

## 快速开始

### 方式一：命令行程序

```bash
python main.py
```

1. **选 1 → 注册新人员**：输入姓名、部门、权限，按**空格键**采集人脸
2. **选 2 → 训练模型**：所有已注册人员样本一起训练（新增人员后需重新训练）
3. **选 3 → 启动实时识别**：摄像头实时识别并判定通行权限，按 **Q** 退出
4. **选 4 → 人员管理**：修改权限、删除人员
5. **选 5 → 查看通行记录**：最近 20 条时序记录
6. **选 6 → 数据统计与可视化**：趋势图 / 时段图 / 饼图 / 综合看板

### 方式二：Web 管理后台

```bash
python app.py
```

访问 `http://127.0.0.1:5000/admin` 进入管理后台（需登录），
`http://127.0.0.1:5000/user` 为用户端查询页面。

---

## 参数调整

编辑 `utils/recognition.py` 顶部：

```python
CONFIDENCE_THRESHOLD = 35.0   # 越小越严格（推荐 35~80）
COOLDOWN_SECONDS = 5           # 同一人重复记录冷却时间
```

---

## 安全说明

- 人脸图像与训练模型属于**生物特征敏感数据**，已通过 `.gitignore` 排除，请勿提交
- `config.py` 含数据库密码，不会上传；仓库仅提供 `config.example.py` 模板
- 生产部署请修改默认管理员密码，并通过环境变量 `FLASK_SECRET_KEY` 设置随机会话密钥

---

## 常见问题

| 问题 | 解决方法 |
|---|---|
| 摄像头无法打开 | 检查摄像头权限，或修改 `VideoCapture(0)` 的索引 |
| 中文乱码 | 确认系统已安装微软雅黑 / 黑体等中文字体 |
| 识别率低 | 增加采集样本数（60+），光线均匀，正面采集 |
| `LBPHFaceRecognizer` 找不到 | 安装 `opencv-contrib-python` 而非 `opencv-python` |
| 数据库连接失败 | 检查 `config.py` 中的账号密码，确认已执行 `DB_Init.sql` |

---

## License

本项目基于 [MIT License](LICENSE) 开源。
