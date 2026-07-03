from sqlalchemy import String, Integer, Enum, DateTime, Boolean, Time, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    real_name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(Enum('super_admin','admin'))
    direction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(Enum('enabled','disabled'), default='enabled')
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class Member(Base):
    __tablename__ = 'members'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    student_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    gender: Mapped[str] = mapped_column(Enum('男','女','其他'), default='男')
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    major: Mapped[str | None] = mapped_column(String(100), nullable=True)
    direction: Mapped[str] = mapped_column(String(100), index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    face_photo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class Attendance(Base):
    __tablename__ = 'attendance'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    member_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('members.id', ondelete='SET NULL'), nullable=True)
    name: Mapped[str] = mapped_column(String(50))
    student_no: Mapped[str] = mapped_column(String(50), index=True)
    gender: Mapped[str] = mapped_column(String(10), default='男')
    direction: Mapped[str] = mapped_column(String(100), index=True)
    check_date: Mapped[str] = mapped_column(String(20), index=True)
    check_time: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(Enum('正常','迟到','缺勤','请假'), default='正常')
    source: Mapped[str] = mapped_column(String(50), default='手动录入')
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class CameraConfig(Base):
    __tablename__ = 'camera_config'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_name: Mapped[str] = mapped_column(String(80), default='NBA-Lab Camera')
    rtsp_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    password: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    test_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FaceEncoding(Base):
    __tablename__ = 'face_encodings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    member_id: Mapped[int] = mapped_column(Integer, ForeignKey('members.id', ondelete='CASCADE'), unique=True, index=True)
    embedding: Mapped[str] = mapped_column(Text)
    photo_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class TrainingPlan(Base):
    __tablename__ = 'training_plans'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    direction: Mapped[str] = mapped_column(String(100), index=True)
    start_date: Mapped[str] = mapped_column(String(20), index=True)
    end_date: Mapped[str] = mapped_column(String(20), index=True)
    start_time: Mapped[str] = mapped_column(String(10), index=True)
    end_time: Mapped[str] = mapped_column(String(10), index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
