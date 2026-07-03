from pydantic import BaseModel, Field
from typing import Optional

class LoginIn(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    real_name: str
    role: str
    direction: Optional[str] = None
    status: str
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str = '123456'
    real_name: str
    role: str = Field(pattern='^(admin|super_admin)$')
    direction: Optional[str] = None
    status: str = 'enabled'

class UserUpdate(BaseModel):
    password: Optional[str] = None
    real_name: Optional[str] = None
    direction: Optional[str] = None
    status: Optional[str] = None

class MemberBase(BaseModel):
    name: str
    student_no: str
    gender: str = Field(pattern='^(男|女|其他)$')
    grade: Optional[str] = None
    major: Optional[str] = None
    direction: str
    phone: Optional[str] = None
    email: Optional[str] = None
    remark: Optional[str] = None

class MemberCreate(MemberBase):
    pass

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    student_no: Optional[str] = None
    gender: Optional[str] = Field(default=None, pattern='^(男|女|其他)$')
    grade: Optional[str] = None
    major: Optional[str] = None
    direction: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    remark: Optional[str] = None

class MemberOut(MemberBase):
    id: int
    face_photo: Optional[str] = None
    class Config:
        from_attributes = True

class AttendanceCreate(BaseModel):
    member_id: int
    status: str = Field(default='正常', pattern='^(正常|迟到|缺勤|请假)$')
    source: str = '手动录入'
    remark: Optional[str] = None

class AttendanceOut(BaseModel):
    id: int
    member_id: Optional[int] = None
    name: str
    student_no: str
    gender: str
    direction: str
    check_date: str
    check_time: str
    status: str
    source: str
    remark: Optional[str] = None
    class Config:
        from_attributes = True

class CameraIn(BaseModel):
    camera_name: str = 'NBA-Lab Camera'
    rtsp_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: bool = False
    test_mode: bool = True

class CameraOut(CameraIn):
    id: int
    class Config:
        from_attributes = True


class TrainingPlanBase(BaseModel):
    title: str
    direction: str
    start_date: str
    end_date: str
    start_time: str
    end_time: str
    description: Optional[str] = None

class TrainingPlanCreate(TrainingPlanBase):
    pass

class TrainingPlanUpdate(BaseModel):
    title: Optional[str] = None
    direction: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: Optional[str] = None

class TrainingPlanOut(TrainingPlanBase):
    id: int
    created_by: Optional[int] = None
    class Config:
        from_attributes = True
