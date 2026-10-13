-- ============================================================
-- 人脸通行管控系统 — MySQL 数据库初始化脚本
-- ============================================================
-- 使用方法：
--   1. 打开 Navicat，连接到你的 MySQL 服务器
--   2. 新建查询，粘贴此文件全部内容
--   3. 点击"运行"执行
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS face_access_control
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE face_access_control;

-- -----------------------------------------------------------
-- 人员信息表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS persons (
    id            INT           AUTO_INCREMENT PRIMARY KEY  COMMENT '人员ID',
    name          VARCHAR(50)   NOT NULL                     COMMENT '姓名',
    department    VARCHAR(100)  DEFAULT '未分配'             COMMENT '部门',
    role          VARCHAR(50)   DEFAULT ''                   COMMENT '角色/职位',
    phone         VARCHAR(20)   DEFAULT ''                   COMMENT '联系电话',
    permission    VARCHAR(10)   DEFAULT '允许'               COMMENT '通行权限：允许/拒绝',
    register_time DATETIME      DEFAULT CURRENT_TIMESTAMP    COMMENT '注册时间',
    remark        VARCHAR(200)  DEFAULT ''                   COMMENT '备注'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='注册人员信息表';

-- -----------------------------------------------------------
-- 通行记录表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_records (
    record_id     INT           AUTO_INCREMENT PRIMARY KEY  COMMENT '记录ID',
    person_id     INT           NOT NULL                     COMMENT '人员ID（-1=陌生人）',
    name          VARCHAR(50)   NOT NULL                     COMMENT '识别姓名',
    department    VARCHAR(100)  DEFAULT '-'                  COMMENT '部门',
    access_time   DATETIME      DEFAULT CURRENT_TIMESTAMP    COMMENT '通行时间',
    access_result VARCHAR(20)   NOT NULL                     COMMENT '通行结果：允许通行/拒绝通行/陌生人',
    confidence    DECIMAL(8,2)  DEFAULT 0                    COMMENT '置信度（LBPH距离，越低越匹配）',
    date          DATE          NOT NULL                     COMMENT '通行日期',
    hour          TINYINT       NOT NULL                     COMMENT '通行时段（0-23）',
    INDEX idx_person  (person_id),
    INDEX idx_date    (date),
    INDEX idx_hour    (hour),
    INDEX idx_result  (access_result)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='通行记录表';

-- -----------------------------------------------------------
-- 管理员账户表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS admins (
    username      VARCHAR(50)   PRIMARY KEY                  COMMENT '登录账号',
    password_hash VARCHAR(64)   NOT NULL                     COMMENT 'SHA-256 密码哈希',
    create_time   DATETIME      DEFAULT CURRENT_TIMESTAMP    COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='管理员账户表';

-- -----------------------------------------------------------
-- 默认管理员账户（admin / admin123）
-- -----------------------------------------------------------
INSERT IGNORE INTO admins (username, password_hash)
VALUES ('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9');

-- ============================================================
-- 完成！数据库 face_access_control 已就绪
-- 在 Navicat 中刷新即可看到 3 张表
-- ============================================================
