# Face models

把下面两个 ONNX 模型文件放到本目录：

- `face_detection_yunet_2023mar.onnx`
- `face_recognition_sface_2021dec.onnx`

后端启动后会执行：RTSP -> YuNet 人脸检测 -> 关键点对齐 -> SFace 512维特征 -> Faiss 余弦相似度检索 -> 自动签到。

模型文件较大，不建议提交 GitHub；本目录只提交 README。
