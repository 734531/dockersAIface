from __future__ import annotations

import os
import time
from pathlib import Path

import cv2

from .camera_service import build_rtsp_url
from .face_service import find_best_member


def read_one_frame(rtsp_url: str | None, username: str | None, password: str | None, timeout_seconds: int = 8):
    """从 RTSP 摄像头读取一帧画面。"""
    final_url = build_rtsp_url(rtsp_url, username, password)
    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        f"rtsp_transport;tcp|stimeout;{timeout_seconds * 1000000}"
    )

    cap = cv2.VideoCapture(final_url, cv2.CAP_FFMPEG)
    try:
        start = time.time()
        while time.time() - start < timeout_seconds:
            ok, frame = cap.read()
            if ok and frame is not None:
                return frame
            time.sleep(0.2)
        return None
    finally:
        cap.release()


def recognize_from_camera(
    rtsp_url: str | None,
    username: str | None,
    password: str | None,
    members,
    face_dir: str | Path,
    timeout_seconds: int = 8,
    known_faces: list[dict] | None = None,
) -> dict:
    """从摄像头抓取一帧并识别成员。"""
    frame = read_one_frame(rtsp_url, username, password, timeout_seconds=timeout_seconds)
    if frame is None:
        return {
            "ok": False,
            "message": "未能从摄像头读取画面，请先确认摄像头测试连接成功。",
        }

    return find_best_member(frame, members, face_dir, known_faces=known_faces)
