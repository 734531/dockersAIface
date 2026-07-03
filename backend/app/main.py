import os, shutil, csv, io, threading, time
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, text
from .database import Base, engine, get_db
from .models import User, Member, CameraConfig, Attendance, FaceEncoding, TrainingPlan
from .schemas import *
from .auth import verify_password, hash_password, is_legacy_hash, create_token, current_user, require_super
from .camera_service import test_camera, save_snapshot, DEFAULT_RTSP_URL, DEFAULT_CAMERA_USERNAME, DEFAULT_CAMERA_PASSWORD
from .recognition_service import recognize_from_camera
from .attendance_service import create_camera_attendance, already_signed_today
from .face_service import build_embedding_from_photo, embedding_to_json, embedding_from_json

Base.metadata.create_all(bind=engine)

def migrate_database():
    """兼容旧数据库卷：旧版本表没有 gender/attendance 时，启动自动补字段。"""
    statements = [
        "ALTER TABLE members CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
        "ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
        "ALTER TABLE camera_config CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
        "ALTER TABLE members ADD COLUMN gender ENUM('男','女','其他') NOT NULL DEFAULT '男' AFTER student_no",
        "ALTER TABLE members ADD COLUMN grade VARCHAR(20) NULL AFTER gender",
        "ALTER TABLE members ADD COLUMN major VARCHAR(100) NULL AFTER grade",
        "ALTER TABLE members ADD COLUMN direction VARCHAR(100) NOT NULL DEFAULT '未设置方向' AFTER major",
        "CREATE TABLE IF NOT EXISTS face_encodings (id INT AUTO_INCREMENT PRIMARY KEY, member_id INT NOT NULL UNIQUE, embedding LONGTEXT NOT NULL, photo_name VARCHAR(255) NULL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, INDEX(member_id), CONSTRAINT fk_face_member FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE)",
        "CREATE TABLE IF NOT EXISTS training_plans (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(120) NOT NULL, direction VARCHAR(100) NOT NULL, start_date VARCHAR(20) NOT NULL, end_date VARCHAR(20) NOT NULL, start_time VARCHAR(10) NOT NULL, end_time VARCHAR(10) NOT NULL, description VARCHAR(500) NULL, created_by INT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, INDEX(direction), INDEX(start_date), INDEX(end_date), CONSTRAINT fk_training_user FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL)",
    ]
    with engine.begin() as conn:
        conn.execute(text('SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci'))
        for sql in statements:
            try:
                conn.execute(text(sql))
            except Exception:
                pass
        # 修复旧测试数据乱码/旧数据为空的情况。已有真实数据不会被删除。
        try:
            conn.execute(text("UPDATE users SET real_name='超级管理员' WHERE username='superadmin'"))
            conn.execute(text("UPDATE users SET real_name='AI方向管理员', direction='人工智能方向' WHERE username='aiadmin'"))
            conn.execute(text("UPDATE users SET real_name='视觉方向管理员', direction='计算机视觉方向' WHERE username='cvadmin'"))
            conn.execute(text("UPDATE members SET name='张三', gender='男', direction='人工智能方向', major='计算机科学与技术' WHERE student_no='20240001'"))
            conn.execute(text("UPDATE members SET name='李四', gender='女', direction='计算机视觉方向', major='软件工程' WHERE student_no='20240002'"))
        except Exception:
            pass

migrate_database()
FACE_DIR = Path(os.getenv('FACE_DIR', '/app/faces'))
FACE_DIR.mkdir(parents=True, exist_ok=True)
FACE_EMBEDDING_VERSION = 'yunet_sface_faiss_v1'

app = FastAPI(title='NBA-Lab Face System')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


def rebuild_face_encoding(db: Session, member: Member) -> tuple[bool, str]:
    """上传/更新照片后立即生成特征缓存，后续识别不再遍历读取所有图片。"""
    if not member.face_photo:
        return False, '成员没有人脸照片'
    photo_path = FACE_DIR / member.face_photo
    vec, msg = build_embedding_from_photo(photo_path)
    if vec is None:
        old = db.scalar(select(FaceEncoding).where(FaceEncoding.member_id == member.id))
        if old:
            db.delete(old)
            db.commit()
        return False, msg
    row = db.scalar(select(FaceEncoding).where(FaceEncoding.member_id == member.id))
    if not row:
        row = FaceEncoding(member_id=member.id)
        db.add(row)
    row.embedding = embedding_to_json(vec)
    row.photo_name = f'{member.face_photo}|{FACE_EMBEDDING_VERSION}'
    db.commit()
    return True, '人脸特征已更新'


def get_known_faces(db: Session, members: list[Member]) -> list[dict]:
    """读取数据库中已缓存的人脸特征；旧照片缺缓存时自动补建一次。"""
    by_id = {m.id: m for m in members}
    if not by_id:
        return []
    rows = db.scalars(select(FaceEncoding).where(FaceEncoding.member_id.in_(by_id.keys()))).all()
    row_by_member = {r.member_id: r for r in rows}

    for member in members:
        if not member.face_photo:
            continue
        row = row_by_member.get(member.id)
        expected_key = f'{member.face_photo}|{FACE_EMBEDDING_VERSION}'
        if row and row.photo_name == expected_key:
            continue
        ok, _ = rebuild_face_encoding(db, member)
        if ok:
            new_row = db.scalar(select(FaceEncoding).where(FaceEncoding.member_id == member.id))
            if new_row:
                row_by_member[member.id] = new_row

    known = []
    for member in members:
        row = row_by_member.get(member.id)
        if not row:
            continue
        try:
            known.append({'member': member, 'embedding': embedding_from_json(row.embedding)})
        except Exception:
            continue
    return known


def _to_dt(date_text: str, time_text: str) -> datetime:
    try:
        return datetime.strptime(f'{date_text} {time_text}', '%Y-%m-%d %H:%M')
    except ValueError:
        return datetime.strptime(f'{date_text} {time_text}', '%Y-%m-%d %H:%M:%S')


def validate_training_payload(data):
    start = _to_dt(data.start_date, data.start_time)
    end = _to_dt(data.end_date, data.end_time)
    if end <= start:
        raise HTTPException(status_code=400, detail='结束时间必须晚于开始时间')
    if not data.title.strip() or not data.direction.strip():
        raise HTTPException(status_code=400, detail='日程名称和方向不能为空')
    return start, end


def find_training_conflict(db: Session, data, exclude_id: int | None = None):
    start, end = validate_training_payload(data)
    rows = db.scalars(select(TrainingPlan)).all()
    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        # 同方向可以连续安排；不同方向抢同一实验室时间段时禁止。
        if row.direction == data.direction:
            continue
        row_start = _to_dt(row.start_date, row.start_time)
        row_end = _to_dt(row.end_date, row.end_time)
        if start < row_end and end > row_start:
            return row
    return None

# =========================
# 自动人脸识别签到后台任务
# =========================
AUTO_FACE_RUNNING = False
AUTO_FACE_THREAD = None
AUTO_FACE_INTERVAL_SECONDS = 3


def auto_face_loop():
    """后台循环：定时抓拍摄像头画面，识别成功后自动签到。

    注意：
    1. 同一个成员当天已签到则不会重复写入。
    2. 这个任务会跟随 backend 容器运行；容器重启后需要再次调用启动接口。
    """
    global AUTO_FACE_RUNNING

    while AUTO_FACE_RUNNING:
        db = next(get_db())

        try:
            c = db.get(CameraConfig, 1)

            if not c or not c.enabled:
                print("[AUTO_FACE] 摄像头未配置或未启用", flush=True)
                time.sleep(AUTO_FACE_INTERVAL_SECONDS)
                continue

            members = db.scalars(select(Member)).all()

            if not members:
                print("[AUTO_FACE] 暂无成员，跳过本次识别", flush=True)
                time.sleep(AUTO_FACE_INTERVAL_SECONDS)
                continue

            known_faces = get_known_faces(db, members)
            result = recognize_from_camera(
                c.rtsp_url,
                c.username,
                c.password,
                members,
                FACE_DIR,
                known_faces=known_faces
            )

            if not result.get("ok"):
                print("[AUTO_FACE]", result.get("message", "未识别到成员"), flush=True)
                time.sleep(AUTO_FACE_INTERVAL_SECONDS)
                continue

            member = db.get(Member, result["member_id"])

            if not member:
                print("[AUTO_FACE] 识别到成员，但数据库成员不存在", flush=True)
                time.sleep(AUTO_FACE_INTERVAL_SECONDS)
                continue

            old = already_signed_today(db, member)

            if old:
                print(f"[AUTO_FACE] {member.name} 今天已签到，不重复写入", flush=True)
                time.sleep(AUTO_FACE_INTERVAL_SECONDS)
                continue

            create_camera_attendance(
                db,
                member,
                status="正常",
                source="人脸识别自动签到",
                remark=f"自动巡检签到，相似度：{result.get('best_score')}"
            )

            print(f"[AUTO_FACE] 识别成功，已为 {member.name} 自动签到，相似度：{result.get('best_score')}", flush=True)

        except Exception as e:
            print("[AUTO_FACE_ERROR]", repr(e), flush=True)

        finally:
            db.close()

        time.sleep(AUTO_FACE_INTERVAL_SECONDS)


@app.get('/api/health')
def health():
    return {'ok': True, 'lab': 'NBA-Lab'}

@app.post('/api/auth/login')
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    if is_legacy_hash(user.password_hash):
        user.password_hash = hash_password(data.password)
        db.commit()
    if user.status != 'enabled':
        raise HTTPException(status_code=403, detail='账号已禁用')
    return {'access_token': create_token(user), 'token_type': 'bearer', 'user': UserOut.model_validate(user)}

@app.get('/api/auth/me', response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.get('/api/stats')
def stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Member)
    aq = select(Attendance)
    if user.role == 'admin':
        q = q.where(Member.direction == user.direction)
        aq = aq.where(Attendance.direction == user.direction)
    members = db.scalars(q).all()
    attendance_count = len(db.scalars(aq).all())
    admins = db.scalars(select(User).where(User.role == 'admin')).all() if user.role == 'super_admin' else []
    return {'members': len(members), 'admins': len(admins), 'directions': sorted(list({m.direction for m in members})), 'attendance': attendance_count}

@app.get('/api/users', response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_super)):
    # 管理员设置页只显示普通管理员，超级管理员账号不允许在页面里被误改/误删。
    return db.scalars(select(User).where(User.role == 'admin').order_by(User.id.desc())).all()

@app.post('/api/users', response_model=UserOut)
def create_user(data: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_super)):
    username = (data.username or '').strip()
    real_name = (data.real_name or '').strip()
    direction = (data.direction or '').strip()
    password = (data.password or '').strip()
    if not username or not real_name or not direction or not password:
        raise HTTPException(status_code=400, detail='账号、密码、姓名、负责方向不能为空')
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=400, detail='用户名已存在')
    user = User(
        username=username,
        password_hash=hash_password(password),
        real_name=real_name,
        role='admin',
        direction=direction,
        status=data.status or 'enabled'
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.put('/api/users/{user_id}', response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_super)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    if user.role == 'super_admin':
        raise HTTPException(status_code=400, detail='超级管理员账号不在此处修改')
    update = data.model_dump(exclude_unset=True)
    if 'password' in update and update['password']:
        new_password = update['password'].strip()
        user.password_hash = hash_password(new_password)
    if 'real_name' in update and update['real_name'] is not None:
        user.real_name = update['real_name'].strip()
    if 'direction' in update and update['direction'] is not None:
        user.direction = update['direction'].strip()
    if 'status' in update and update['status'] is not None:
        user.status = update['status']
    if not user.real_name or not user.direction:
        raise HTTPException(status_code=400, detail='姓名、负责方向不能为空')
    db.commit()
    db.refresh(user)
    return user

@app.delete('/api/users/{user_id}')
def delete_user(user_id: int, db: Session = Depends(get_db), me: User = Depends(require_super)):
    if user_id == me.id: raise HTTPException(status_code=400, detail='不能删除当前登录账号')
    user = db.get(User, user_id)
    if not user: raise HTTPException(status_code=404, detail='用户不存在')
    if user.role == 'super_admin': raise HTTPException(status_code=400, detail='不能删除超级管理员')
    db.delete(user); db.commit()
    return {'ok': True}

@app.get('/api/members', response_model=list[MemberOut])
def list_members(keyword: str = '', db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Member)
    if user.role == 'admin':
        q = q.where(Member.direction == user.direction)
    if keyword:
        like = f'%{keyword}%'
        q = q.where(or_(Member.name.like(like), Member.student_no.like(like), Member.major.like(like), Member.direction.like(like), Member.gender.like(like)))
    return db.scalars(q.order_by(Member.id.desc())).all()

@app.post('/api/members', response_model=MemberOut)
def create_member(data: MemberCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == 'admin' and data.direction != user.direction:
        raise HTTPException(status_code=403, detail='管理员只能添加自己方向的成员')
    if db.scalar(select(Member).where(Member.student_no == data.student_no)):
        raise HTTPException(status_code=400, detail='学号已存在')
    m = Member(**data.model_dump())
    db.add(m); db.commit(); db.refresh(m)
    return m

@app.put('/api/members/{member_id}', response_model=MemberOut)
def update_member(member_id: int, data: MemberUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.get(Member, member_id)
    if not m: raise HTTPException(status_code=404, detail='成员不存在')
    if user.role == 'admin' and m.direction != user.direction:
        raise HTTPException(status_code=403, detail='不能修改其他方向成员')
    update = data.model_dump(exclude_unset=True)
    if user.role == 'admin' and update.get('direction', m.direction) != user.direction:
        raise HTTPException(status_code=403, detail='不能把成员改到其他方向')
    for k,v in update.items(): setattr(m, k, v)
    db.commit(); db.refresh(m)
    return m

@app.delete('/api/members/{member_id}')
def delete_member(member_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.get(Member, member_id)
    if not m: raise HTTPException(status_code=404, detail='成员不存在')
    if user.role == 'admin' and m.direction != user.direction:
        raise HTTPException(status_code=403, detail='不能删除其他方向成员')
    db.delete(m); db.commit()
    return {'ok': True}

@app.post('/api/members/{member_id}/face', response_model=MemberOut)
def upload_face(member_id: int, photo: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.get(Member, member_id)
    if not m: raise HTTPException(status_code=404, detail='成员不存在')
    if user.role == 'admin' and m.direction != user.direction:
        raise HTTPException(status_code=403, detail='不能操作其他方向成员')
    suffix = Path(photo.filename).suffix or '.jpg'
    safe_no = ''.join(ch for ch in m.student_no if ch.isalnum() or ch in ('_', '-'))
    filename = f'member_{member_id}_{safe_no}{suffix}'
    target = FACE_DIR / filename
    with target.open('wb') as f: shutil.copyfileobj(photo.file, f)
    m.face_photo = filename
    db.commit(); db.refresh(m)
    ok, msg = rebuild_face_encoding(db, m)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    db.refresh(m)
    return m

@app.get('/api/attendance', response_model=list[AttendanceOut])
def list_attendance(keyword: str = '', db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = select(Attendance)
    if user.role == 'admin':
        q = q.where(Attendance.direction == user.direction)
    if keyword:
        like = f'%{keyword}%'
        q = q.where(or_(Attendance.name.like(like), Attendance.student_no.like(like), Attendance.direction.like(like), Attendance.status.like(like)))
    return db.scalars(q.order_by(Attendance.id.desc())).all()

@app.post('/api/attendance', response_model=AttendanceOut)
def create_attendance(data: AttendanceCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    m = db.get(Member, data.member_id)
    if not m: raise HTTPException(status_code=404, detail='成员不存在')
    if user.role == 'admin' and m.direction != user.direction:
        raise HTTPException(status_code=403, detail='只能给自己方向成员记录签到')
    now = datetime.now()
    a = Attendance(member_id=m.id, name=m.name, student_no=m.student_no, gender=m.gender, direction=m.direction,
                   check_date=now.strftime('%Y-%m-%d'), check_time=now.strftime('%H:%M:%S'),
                   status=data.status, source=data.source, remark=data.remark)
    db.add(a); db.commit(); db.refresh(a)
    return a



@app.delete('/api/attendance/{attendance_id}')
def delete_attendance(attendance_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """删除单条签到记录。超级管理员可删全部；普通管理员只能删除自己方向的记录。"""
    a = db.get(Attendance, attendance_id)
    if not a:
        raise HTTPException(status_code=404, detail='签到记录不存在')
    if user.role == 'admin' and a.direction != user.direction:
        raise HTTPException(status_code=403, detail='只能删除自己方向的签到记录')
    db.delete(a)
    db.commit()
    return {'ok': True, 'message': '签到记录已删除', 'deleted': 1}


@app.post('/api/attendance/batch-delete')
def batch_delete_attendance(ids: list[int] = Body(..., embed=True), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """批量删除签到记录。请求体格式：{"ids":[1,2,3]}。"""
    clean_ids = sorted({int(i) for i in ids if int(i) > 0})
    if not clean_ids:
        raise HTTPException(status_code=400, detail='请选择要删除的签到记录')

    rows = db.scalars(select(Attendance).where(Attendance.id.in_(clean_ids))).all()
    if not rows:
        raise HTTPException(status_code=404, detail='没有找到要删除的签到记录')

    denied = [a.id for a in rows if user.role == 'admin' and a.direction != user.direction]
    if denied:
        raise HTTPException(status_code=403, detail='包含无权删除的其他方向签到记录')

    deleted = len(rows)
    for a in rows:
        db.delete(a)
    db.commit()

    return {'ok': True, 'message': f'已删除 {deleted} 条签到记录', 'deleted': deleted}

@app.get('/api/attendance/export')
def export_attendance(keyword: str = '', db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = list_attendance(keyword=keyword, db=db, user=user)
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['姓名','学号','性别','方向','日期','时间','状态','来源','备注'])
    for a in rows:
        writer.writerow([a.name, a.student_no, a.gender, a.direction, a.check_date, a.check_time, a.status, a.source, a.remark or ''])
    output.seek(0)
    filename = f"nba_lab_attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {'Content-Disposition': f'attachment; filename={filename}'}
    return StreamingResponse(iter([output.getvalue()]), media_type='text/csv; charset=utf-8', headers=headers)

@app.get('/api/camera', response_model=CameraOut)
def get_camera(db: Session = Depends(get_db)):
    c = db.get(CameraConfig, 1)
    if not c:
        c = CameraConfig(
            id=1,
            camera_name='NBA-Lab Hikvision Camera',
            rtsp_url=DEFAULT_RTSP_URL,
            username=DEFAULT_CAMERA_USERNAME,
            password=DEFAULT_CAMERA_PASSWORD,
            enabled=True,
            test_mode=False
        )
        db.add(c)
        db.commit()
        db.refresh(c)
    return c


@app.put('/api/camera', response_model=CameraOut)
def save_camera(data: CameraIn, db: Session = Depends(get_db)):
    c = db.get(CameraConfig, 1) or CameraConfig(id=1)

    for k, v in data.model_dump().items():
        setattr(c, k, v)

    # 强制填充摄像头真实信息
    c.camera_name = 'NBA-Lab Hikvision Camera'
    c.rtsp_url = data.rtsp_url or DEFAULT_RTSP_URL
    c.username = data.username or DEFAULT_CAMERA_USERNAME
    c.password = data.password or DEFAULT_CAMERA_PASSWORD
    c.enabled = True
    c.test_mode = False

    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@app.post('/api/camera/test-connect')
def camera_test_connect(db: Session = Depends(get_db)):
    c = db.get(CameraConfig, 1)

    if not c:
        c = CameraConfig(
            id=1,
            camera_name='NBA-Lab Hikvision Camera',
            rtsp_url=DEFAULT_RTSP_URL,
            username=DEFAULT_CAMERA_USERNAME,
            password=DEFAULT_CAMERA_PASSWORD,
            enabled=True,
            test_mode=False
        )
        db.add(c)
        db.commit()
        db.refresh(c)

    try:
        return test_camera(c.rtsp_url, c.username, c.password)
    except Exception as e:
        return {
            'ok': False,
            'message': str(e)
        }


@app.post('/api/camera/snapshot')
def camera_snapshot(db: Session = Depends(get_db)):
    c = db.get(CameraConfig, 1)

    if not c:
        c = CameraConfig(
            id=1,
            camera_name='NBA-Lab Hikvision Camera',
            rtsp_url=DEFAULT_RTSP_URL,
            username=DEFAULT_CAMERA_USERNAME,
            password=DEFAULT_CAMERA_PASSWORD,
            enabled=True,
            test_mode=False
        )
        db.add(c)
        db.commit()
        db.refresh(c)

    try:
        return save_snapshot(c.rtsp_url, c.username, c.password, FACE_DIR / '_snapshots')
    except Exception as e:
        return {
            'ok': False,
            'message': str(e)
        }


@app.post('/api/face/test')
def face_test(db: Session = Depends(get_db)):
    c = db.get(CameraConfig, 1)

    if not c:
        c = CameraConfig(
            id=1,
            camera_name='NBA-Lab Hikvision Camera',
            rtsp_url=DEFAULT_RTSP_URL,
            username=DEFAULT_CAMERA_USERNAME,
            password=DEFAULT_CAMERA_PASSWORD,
            enabled=True,
            test_mode=False
        )
        db.add(c)
        db.commit()
        db.refresh(c)

    try:
        result = test_camera(c.rtsp_url, c.username, c.password)
        return {
            'ok': result.get('ok', False),
            'message': result.get('message', '摄像头检测完成'),
            'camera': result
        }
    except Exception as e:
        return {
            'ok': False,
            'message': str(e)
        }

@app.post('/api/face/recognize-and-sign')
def face_recognize_and_sign(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """摄像头抓拍一帧 -> 人脸识别 -> 自动写入签到记录。"""
    c = db.get(CameraConfig, 1)
    if not c:
        c = CameraConfig(
            id=1,
            camera_name='NBA-Lab Hikvision Camera',
            rtsp_url=DEFAULT_RTSP_URL,
            username=DEFAULT_CAMERA_USERNAME,
            password=DEFAULT_CAMERA_PASSWORD,
            enabled=True,
            test_mode=False
        )
        db.add(c)
        db.commit()
        db.refresh(c)

    if not c.enabled:
        raise HTTPException(status_code=400, detail='摄像头未启用，请先在摄像头配置中启用摄像头')

    members_query = select(Member)
    if user.role == 'admin':
        members_query = members_query.where(Member.direction == user.direction)

    members = db.scalars(members_query).all()
    known_faces = get_known_faces(db, members)
    result = recognize_from_camera(c.rtsp_url, c.username, c.password, members, FACE_DIR, known_faces=known_faces)

    if not result.get('ok'):
        return result

    member = db.get(Member, result['member_id'])
    if not member:
        return {'ok': False, 'message': '识别到成员，但数据库成员不存在'}

    old = already_signed_today(db, member)
    if old:
        result.update({
            'ok': True,
            'message': f'{member.name} 今天已经自动签到过，不重复写入。',
            'attendance': AttendanceOut.model_validate(old).model_dump(),
            'duplicated': True,
        })
        return result

    attendance = create_camera_attendance(
        db,
        member,
        status='正常',
        source='人脸识别自动签到',
        remark=f"相似度：{result.get('best_score')}"
    )

    result.update({
        'ok': True,
        'message': f'识别成功，已为 {member.name} 自动签到。',
        'attendance': AttendanceOut.model_validate(attendance).model_dump(),
        'duplicated': False,
    })
    return result


@app.post('/api/face/auto/start')
def start_auto_face():
    """启动后台自动识别。

    启动后，不需要再手动点击“识别并自动签到”。
    人站到摄像头前，后台会每隔几秒自动识别一次。
    """
    global AUTO_FACE_RUNNING, AUTO_FACE_THREAD

    if AUTO_FACE_RUNNING:
        return {
            'ok': True,
            'running': True,
            'message': '自动识别已经在运行'
        }

    AUTO_FACE_RUNNING = True
    AUTO_FACE_THREAD = threading.Thread(target=auto_face_loop, daemon=True)
    AUTO_FACE_THREAD.start()
    print('[AUTO_FACE] 自动识别线程已启动', flush=True)

    return {
        'ok': True,
        'running': True,
        'message': '自动识别已启动，站到摄像头前会自动签到'
    }


@app.post('/api/face/auto/stop')
def stop_auto_face():
    """停止后台自动识别。"""
    global AUTO_FACE_RUNNING

    AUTO_FACE_RUNNING = False

    return {
        'ok': True,
        'running': False,
        'message': '自动识别已停止'
    }


@app.get('/api/face/auto/status')
def auto_face_status():
    """查看后台自动识别状态。"""
    return {
        'ok': True,
        'running': AUTO_FACE_RUNNING,
        'interval_seconds': AUTO_FACE_INTERVAL_SECONDS
    }


@app.get('/api/training-plans', response_model=list[TrainingPlanOut])
def list_training_plans(start: str = '', end: str = '', db: Session = Depends(get_db), user: User = Depends(current_user)):
    # 日程是实验室公共资源：超级管理员和各方向管理员都可以查看全部方向日程。
    # 但创建、修改、删除仍然在下面接口里限制：方向管理员只能操作自己方向的日程。
    q = select(TrainingPlan)
    if start and end:
        q = q.where(TrainingPlan.start_date <= end, TrainingPlan.end_date >= start)
    return db.scalars(q.order_by(TrainingPlan.start_date.asc(), TrainingPlan.start_time.asc())).all()


@app.post('/api/training-plans', response_model=TrainingPlanOut)
def create_training_plan(data: TrainingPlanCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == 'admin' and data.direction != user.direction:
        raise HTTPException(status_code=403, detail='方向管理员只能创建自己方向的培训/比赛日程')
    conflict = find_training_conflict(db, data)
    if conflict:
        raise HTTPException(status_code=400, detail=f'该时间段已被【{conflict.direction}】占用：{conflict.title} {conflict.start_date} {conflict.start_time}-{conflict.end_date} {conflict.end_time}，请换个时间')
    row = TrainingPlan(**data.model_dump(), created_by=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put('/api/training-plans/{plan_id}', response_model=TrainingPlanOut)
def update_training_plan(plan_id: int, data: TrainingPlanUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.get(TrainingPlan, plan_id)
    if not row:
        raise HTTPException(status_code=404, detail='日程不存在')
    if user.role == 'admin' and row.direction != user.direction:
        raise HTTPException(status_code=403, detail='只能修改自己方向的日程')
    update = data.model_dump(exclude_unset=True)
    for k, v in update.items():
        setattr(row, k, v)
    if user.role == 'admin':
        row.direction = user.direction
    conflict = find_training_conflict(db, row, exclude_id=row.id)
    if conflict:
        raise HTTPException(status_code=400, detail=f'该时间段已被【{conflict.direction}】占用：{conflict.title} {conflict.start_date} {conflict.start_time}-{conflict.end_date} {conflict.end_time}，请换个时间')
    db.commit()
    db.refresh(row)
    return row


@app.delete('/api/training-plans/{plan_id}')
def delete_training_plan(plan_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.get(TrainingPlan, plan_id)
    if not row:
        raise HTTPException(status_code=404, detail='日程不存在')
    if user.role == 'admin' and row.direction != user.direction:
        raise HTTPException(status_code=403, detail='只能删除自己方向的日程')
    db.delete(row)
    db.commit()
    return {'ok': True}

@app.on_event("startup")
def startup_auto_face():
    global AUTO_FACE_RUNNING, AUTO_FACE_THREAD

    if AUTO_FACE_RUNNING:
        return

    AUTO_FACE_RUNNING = True
    AUTO_FACE_THREAD = threading.Thread(target=auto_face_loop, daemon=True)
    AUTO_FACE_THREAD.start()

    print("[AUTO_FACE] 后端启动时已自动开启人脸识别线程")