"""
数据库连接配置模板
========================
使用方法：
  1. 复制本文件并重命名为 config.py
  2. 填入你的 MySQL 连接参数（或设置对应的环境变量）

  Windows:  copy config.example.py config.py
  Linux/Mac: cp config.example.py config.py

注意：config.py 已在 .gitignore 中，不会被提交到仓库。
也可通过环境变量配置（优先级高于下方默认值）：
  DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
"""

import os

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": int(os.environ.get("DB_PORT", "3306")),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "请填写你的数据库密码"),
    "database": os.environ.get("DB_NAME", "face_access_control"),
    "charset": "utf8mb4",
    "autocommit": True,
    "connect_timeout": 5,
}
