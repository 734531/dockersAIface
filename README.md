# NBA-Lab 人脸识别考勤系统

本版本后端已升级为研究生级深度人脸识别流程：

```text
摄像头 RTSP
  ↓
YuNet 人脸检测
  ↓
Face Alignment 关键点矫正
  ↓
SFace / ArcFace 类 512维 Embedding
  ↓
Faiss 向量库
  ↓
余弦相似度检索
  ↓
自动签到
```

## 安全改造

- 用户密码不再明文保存，使用 `PBKDF2-SHA256 + salt` 哈希。
- 旧数据库里 `plain:123456` 格式账号登录成功后会自动升级成哈希。
- 摄像头密码、MySQL 密码、JWT 密钥统一放在 `.env`。
- `.env` 已加入 `.gitignore`，上传 GitHub 时只提交 `.env.example`。

## 第一次运行

```powershell
cd E:\docker\claendar\final
copy .env.example .env
```

然后打开 `.env`，把里面的 MySQL、JWT、摄像头密码改成自己的。

再运行：

```powershell
docker compose up -d --build
```

访问：

```text
前端：http://localhost:8080
后端：http://localhost:8000/docs
```

默认初始化账号仍然是：

```text
superadmin / 123456
aiadmin / 123456
cvadmin / 123456
```

注意：数据库里保存的是哈希，不是明文。首次登录后建议立即在系统里修改密码。

## 模型文件

请把下面两个 ONNX 模型放到：

```text
backend/models/
```

文件名必须是：

```text
face_detection_yunet_2023mar.onnx
face_recognition_sface_2021dec.onnx
```

模型文件不要上传 GitHub，`.gitignore` 已忽略 `backend/models/*.onnx`。

## GitHub 上传建议

可以上传：

```text
backend/
frontend/
mysql/
docker-compose.yml
.env.example
.gitignore
README.md
```

不要上传：

```text
.env
backend/faces/
backend/models/*.onnx
frontend/node_modules/
frontend/dist/
mysql_data/
__pycache__/
```
