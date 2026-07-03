from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse, quote

import cv2


# =========================
# 默认摄像头配置
# =========================
DEFAULT_CAMERA_IP = os.getenv("HIK_IP", "192.168.1.111")
DEFAULT_CAMERA_PORT = os.getenv("HIK_PORT", "554")
DEFAULT_CAMERA_USERNAME = os.getenv("HIK_USER", "admin")
DEFAULT_CAMERA_PASSWORD = os.getenv("HIK_PWD", "")

# 101 = 主码流，102 = 子码流
DEFAULT_CAMERA_CHANNEL = "101"

DEFAULT_RTSP_URL = (
    f"rtsp://{DEFAULT_CAMERA_USERNAME}:{DEFAULT_CAMERA_PASSWORD}"
    f"@{DEFAULT_CAMERA_IP}:{DEFAULT_CAMERA_PORT}"
    f"/Streaming/Channels/{DEFAULT_CAMERA_CHANNEL}?transportmode=unicast"
)


def build_rtsp_url(
    rtsp_url: str | None = None,
    username: str | None = None,
    password: str | None = None
) -> str:
    """返回可用的 RTSP 地址。

    默认海康威视格式：
    rtsp://用户名:密码@摄像头IP:554/Streaming/Channels/101?transportmode=unicast

    101 = 主码流
    102 = 子码流
    """

    raw = (rtsp_url or "").strip()

    # 如果外部没有传 RTSP 地址，就使用默认摄像头地址
    if not raw:
        raw = DEFAULT_RTSP_URL

    # 如果没有传用户名密码，也使用默认用户名密码
    username = username or DEFAULT_CAMERA_USERNAME
    password = password or DEFAULT_CAMERA_PASSWORD

    parsed = urlparse(raw)

    if parsed.scheme.lower() != "rtsp":
        raise ValueError("RTSP 地址必须以 rtsp:// 开头")

    # 如果 RTSP 地址里面已经带了用户名密码，直接使用
    if parsed.username:
        return raw

    host = parsed.hostname or ""
    if not host:
        raise ValueError("RTSP 地址缺少摄像头 IP")

    port = f":{parsed.port}" if parsed.port else ""

    user = quote(username or "", safe="")
    pwd = quote(password or "", safe="")

    auth = f"{user}:{pwd}@" if pwd else f"{user}@"
    netloc = f"{auth}{host}{port}"

    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path or "",
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def test_camera(
    rtsp_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    timeout_seconds: int = 8
) -> dict:
    """测试 RTSP 摄像头连接，并读取一帧画面。"""

    final_url = build_rtsp_url(rtsp_url, username, password)

    safe_url = final_url.replace(DEFAULT_CAMERA_PASSWORD, "******") if DEFAULT_CAMERA_PASSWORD else final_url

    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        f"rtsp_transport;tcp|stimeout;{timeout_seconds * 1000000}"
    )

    cap = cv2.VideoCapture(final_url, cv2.CAP_FFMPEG)

    try:
        start = time.time()
        opened = cap.isOpened()
        frame_ok = False
        width = 0
        height = 0
        fps = 0.0
        frame = None

        while time.time() - start < timeout_seconds:
            if not opened:
                opened = cap.isOpened()

            ok, frame = cap.read()

            if ok and frame is not None:
                frame_ok = True
                height, width = frame.shape[:2]
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                break

            time.sleep(0.2)

        if not opened:
            return {
                "ok": False,
                "message": "OpenCV 未能打开摄像头，请检查摄像头 IP、554端口、RTSP地址、用户名密码和电脑是否在同一局域网。",
                "rtsp_url": safe_url,
            }

        if not frame_ok:
            return {
                "ok": False,
                "message": "摄像头已打开，但没有读取到画面帧，请检查主码流/子码流路径，例如 /Streaming/Channels/101 或 /102。",
                "rtsp_url": safe_url,
            }

        return {
            "ok": True,
            "message": "摄像头连接成功，已读取到视频帧。",
            "rtsp_url": safe_url,
            "width": width,
            "height": height,
            "fps": round(fps, 2),
        }

    finally:
        cap.release()


def save_snapshot(
    rtsp_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    target_dir: str | Path = "/app/faces",
    timeout_seconds: int = 8
) -> dict:
    """抓取一帧摄像头画面并保存成 jpg。"""

    final_url = build_rtsp_url(rtsp_url, username, password)

    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        f"rtsp_transport;tcp|stimeout;{timeout_seconds * 1000000}"
    )

    cap = cv2.VideoCapture(final_url, cv2.CAP_FFMPEG)

    try:
        start = time.time()
        frame = None

        while time.time() - start < timeout_seconds:
            ok, img = cap.read()

            if ok and img is not None:
                frame = img
                break

            time.sleep(0.2)

        if frame is None:
            return {
                "ok": False,
                "message": "未能抓取画面，请先确认“测试连接”成功。",
            }

        out_dir = Path(target_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"camera_snapshot_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        path = out_dir / filename

        cv2.imwrite(str(path), frame)

        return {
            "ok": True,
            "message": "抓拍成功",
            "filename": filename,
            "path": str(path),
        }

    finally:
        cap.release()