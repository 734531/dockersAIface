SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS nba_lab DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nba_lab;

CREATE TABLE IF NOT EXISTS users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  real_name VARCHAR(50) NOT NULL,
  role ENUM('super_admin','admin') NOT NULL,
  direction VARCHAR(100) NULL,
  status ENUM('enabled','disabled') NOT NULL DEFAULT 'enabled',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS members (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL,
  student_no VARCHAR(50) NOT NULL UNIQUE,
  gender ENUM('男','女','其他') NOT NULL DEFAULT '男',
  grade VARCHAR(20) NULL,
  major VARCHAR(100) NULL,
  direction VARCHAR(100) NOT NULL,
  phone VARCHAR(30) NULL,
  email VARCHAR(120) NULL,
  face_photo VARCHAR(255) NULL,
  remark VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS attendance (
  id INT PRIMARY KEY AUTO_INCREMENT,
  member_id INT NULL,
  name VARCHAR(50) NOT NULL,
  student_no VARCHAR(50) NOT NULL,
  gender VARCHAR(10) NOT NULL,
  direction VARCHAR(100) NOT NULL,
  check_date VARCHAR(20) NOT NULL,
  check_time VARCHAR(20) NOT NULL,
  status ENUM('正常','迟到','缺勤','请假') NOT NULL DEFAULT '正常',
  source VARCHAR(50) NOT NULL DEFAULT '手动录入',
  remark VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_attendance_direction(direction),
  INDEX idx_attendance_student_no(student_no)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS camera_config (
  id INT PRIMARY KEY AUTO_INCREMENT,
  camera_name VARCHAR(80) NOT NULL DEFAULT 'NBA-Lab Camera',
  rtsp_url VARCHAR(255) NULL,
  username VARCHAR(80) NULL,
  password VARCHAR(120) NULL,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  test_mode BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO users(username,password_hash,real_name,role,direction,status)
VALUES
('superadmin', 'pbkdf2_sha256$260000$zL8Va0UtrxAbvl80R7-rwA$x4TaeLYRpHQ3GuQ3KxIIDnDzfdMqLNpnOIfJLS0I7po', '超级管理员', 'super_admin', NULL, 'enabled'),
('aiadmin', 'pbkdf2_sha256$260000$zL8Va0UtrxAbvl80R7-rwA$x4TaeLYRpHQ3GuQ3KxIIDnDzfdMqLNpnOIfJLS0I7po', 'AI方向管理员', 'admin', '人工智能方向', 'enabled'),
('cvadmin', 'pbkdf2_sha256$260000$zL8Va0UtrxAbvl80R7-rwA$x4TaeLYRpHQ3GuQ3KxIIDnDzfdMqLNpnOIfJLS0I7po', '视觉方向管理员', 'admin', '计算机视觉方向', 'enabled')
ON DUPLICATE KEY UPDATE real_name=VALUES(real_name), direction=VALUES(direction), status=VALUES(status);

INSERT INTO members(name,student_no,gender,grade,major,direction,phone,email,remark)
VALUES
('张三','20240001','男','2024级','计算机科学与技术','人工智能方向','13800000001','zhangsan@nlab.local','测试成员'),
('李四','20240002','女','2024级','软件工程','计算机视觉方向','13800000002','lisi@nlab.local','测试成员')
ON DUPLICATE KEY UPDATE name=VALUES(name), gender=VALUES(gender), direction=VALUES(direction);

INSERT INTO attendance(member_id,name,student_no,gender,direction,check_date,check_time,status,source,remark)
VALUES
(1,'张三','20240001','男','人工智能方向','2026-05-17','09:00:00','正常','测试数据','系统初始化样例'),
(2,'李四','20240002','女','计算机视觉方向','2026-05-17','09:05:00','迟到','测试数据','系统初始化样例');

INSERT INTO camera_config(id,camera_name,rtsp_url,username,password,enabled,test_mode)
VALUES(1,'NBA-Lab Hikvision Camera','rtsp://192.168.1.111:554/Streaming/Channels/101','admin','',TRUE,FALSE)
ON DUPLICATE KEY UPDATE
  camera_name=VALUES(camera_name),
  rtsp_url=VALUES(rtsp_url),
  username=VALUES(username),
  password=VALUES(password),
  enabled=VALUES(enabled),
  test_mode=VALUES(test_mode);
