from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Attendance, Member


def create_camera_attendance(
    db: Session,
    member: Member,
    status: str = "正常",
    source: str = "人脸识别自动签到",
    remark: str | None = None,
) -> Attendance:
    """创建一条签到记录。"""
    now = datetime.now()
    a = Attendance(
        member_id=member.id,
        name=member.name,
        student_no=member.student_no,
        gender=member.gender,
        direction=member.direction,
        check_date=now.strftime("%Y-%m-%d"),
        check_time=now.strftime("%H:%M:%S"),
        status=status,
        source=source,
        remark=remark,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def already_signed_today(db: Session, member: Member) -> Attendance | None:
    """避免同一个成员同一天被摄像头反复刷出多条自动签到。"""
    today = datetime.now().strftime("%Y-%m-%d")
    return db.scalar(
        select(Attendance)
        .where(
            Attendance.member_id == member.id,
            Attendance.check_date == today,
            Attendance.source == "人脸识别自动签到",
        )
        .order_by(Attendance.id.desc())
    )
