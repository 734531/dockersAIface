from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

try:
    import faiss  # type: ignore
except Exception:  # faiss 在部分平台上可能不可用，保留 numpy 精确检索兜底
    faiss = None


MODEL_DIR = Path(os.getenv('FACE_MODEL_DIR', '/app/models'))
YUNET_MODEL = Path(os.getenv('YUNET_MODEL', str(MODEL_DIR / 'face_detection_yunet_2023mar.onnx')))
SFACE_MODEL = Path(os.getenv('SFACE_MODEL', str(MODEL_DIR / 'face_recognition_sface_2021dec.onnx')))
FACE_SCORE_THRESHOLD = float(os.getenv('FACE_SCORE_THRESHOLD', '0.55'))
FACE_TOP1_GAP = float(os.getenv('FACE_TOP1_GAP', '0.035'))
FACE_DETECT_CONFIDENCE = float(os.getenv('FACE_DETECT_CONFIDENCE', '0.85'))


@dataclass
class FaceMatch:
    ok: bool
    score: float = 0.0
    message: str = ''
    bbox: tuple[int, int, int, int] | None = None


_DETECTOR = None
_RECOGNIZER = None
_DETECTOR_SIZE: tuple[int, int] | None = None


def _load_image(path: str | Path):
    path = Path(path)
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _require_models() -> None:
    missing = [str(p) for p in (YUNET_MODEL, SFACE_MODEL) if not p.exists()]
    if missing:
        raise RuntimeError(
            '缺少深度人脸模型文件：' + '，'.join(missing) +
            '。请把 YuNet 和 SFace ONNX 模型放到 backend/models/ 后重新构建。'
        )


def _detector(width: int, height: int):
    global _DETECTOR, _DETECTOR_SIZE
    _require_models()
    size = (int(width), int(height))
    if _DETECTOR is None:
        _DETECTOR = cv2.FaceDetectorYN_create(
            str(YUNET_MODEL), '', size,
            score_threshold=FACE_DETECT_CONFIDENCE,
            nms_threshold=0.3,
            top_k=5000,
        )
        _DETECTOR_SIZE = size
    elif _DETECTOR_SIZE != size:
        _DETECTOR.setInputSize(size)
        _DETECTOR_SIZE = size
    return _DETECTOR


def _recognizer():
    global _RECOGNIZER
    _require_models()
    if _RECOGNIZER is None:
        _RECOGNIZER = cv2.FaceRecognizerSF_create(str(SFACE_MODEL), '')
    return _RECOGNIZER


def _normalize(vec: np.ndarray) -> np.ndarray:
    vec = vec.astype('float32').reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-12:
        return vec
    return vec / norm


def detect_largest_face(image: np.ndarray) -> tuple[np.ndarray | None, tuple[int, int, int, int] | None]:
    """YuNet 检测最大人脸，返回 YuNet face 行和 bbox。"""
    if image is None:
        return None, None
    h, w = image.shape[:2]
    detector = _detector(w, h)
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0:
        return None, None
    face = max(faces, key=lambda f: float(f[2] * f[3]))
    x, y, fw, fh = [int(round(v)) for v in face[:4]]
    return face.astype('float32'), (max(0, x), max(0, y), max(0, fw), max(0, fh))


def face_embedding_from_frame(image: np.ndarray) -> tuple[np.ndarray | None, tuple[int, int, int, int] | None, str]:
    """完整深度识别流水线：YuNet检测 -> 关键点对齐 -> SFace/ArcFace类512维特征。"""
    if image is None:
        return None, None, '图像为空'
    face, bbox = detect_largest_face(image)
    if face is None:
        return None, None, '未检测到人脸'
    aligned = _recognizer().alignCrop(image, face)
    feature = _recognizer().feature(aligned)
    return _normalize(feature), bbox, 'ok'


def build_embedding_from_photo(photo_path: str | Path) -> tuple[np.ndarray | None, str]:
    image = _load_image(photo_path)
    if image is None:
        return None, f'成员人脸照片读取失败：{photo_path}'
    vec, _, msg = face_embedding_from_frame(image)
    if vec is None:
        return None, f'成员人脸照片处理失败：{Path(photo_path).name}，原因：{msg}'
    return vec, 'ok'


def embedding_to_json(vec: np.ndarray) -> str:
    return json.dumps(_normalize(vec).astype('float32').round(7).tolist(), ensure_ascii=False)


def embedding_from_json(data: str) -> np.ndarray:
    return _normalize(np.array(json.loads(data), dtype='float32'))


def compare_embeddings(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(_normalize(a), _normalize(b)))


class FaceVectorIndex:
    """Faiss 向量索引。向量已 L2 归一化，IndexFlatIP 等价于余弦相似度检索。"""

    def __init__(self, known_faces: Iterable[dict]):
        self.members = []
        vectors = []
        for item in known_faces or []:
            member = item.get('member')
            emb = item.get('embedding')
            if member is None or emb is None:
                continue
            self.members.append(member)
            vectors.append(_normalize(np.asarray(emb, dtype='float32')))
        # 防止旧版本缓存向量维度混入导致索引异常，只保留当前批次的主维度。
        if vectors:
            dims = [v.shape[0] for v in vectors]
            main_dim = max(set(dims), key=dims.count)
            kept = [(m, v) for m, v in zip(self.members, vectors) if v.shape[0] == main_dim]
            self.members = [m for m, _ in kept]
            vectors = [v for _, v in kept]
        self.matrix = np.vstack(vectors).astype('float32') if vectors else np.empty((0, 0), dtype='float32')
        self.index = None
        if self.matrix.size and faiss is not None:
            self.index = faiss.IndexFlatIP(self.matrix.shape[1])
            self.index.add(self.matrix)

    @property
    def size(self) -> int:
        return len(self.members)

    def search(self, query: np.ndarray, top_k: int = 2) -> list[tuple[object, float]]:
        if self.size == 0:
            return []
        q = _normalize(query).reshape(1, -1).astype('float32')
        if self.matrix.shape[1] != q.shape[1]:
            return []
        k = min(top_k, self.size)
        if self.index is not None:
            scores, ids = self.index.search(q, k)
            return [(self.members[int(i)], float(s)) for i, s in zip(ids[0], scores[0]) if int(i) >= 0]
        scores = self.matrix @ q.reshape(-1)
        order = np.argsort(-scores)[:k]
        return [(self.members[int(i)], float(scores[int(i)])) for i in order]


def find_best_member(frame, members, face_dir: str | Path, known_faces: list[dict] | None = None) -> dict:
    live_vec, bbox, msg = face_embedding_from_frame(frame)
    if live_vec is None:
        return {'ok': False, 'message': msg, 'best_score': 0}

    if not known_faces:
        # 只作为兜底：正常情况下上传照片时已生成 embedding，识别时不再逐图遍历。
        known_faces = []
        face_dir = Path(face_dir)
        for member in members:
            if not getattr(member, 'face_photo', None):
                continue
            photo_path = face_dir / member.face_photo
            if not photo_path.exists():
                continue
            ref_vec, _ = build_embedding_from_photo(photo_path)
            if ref_vec is not None:
                known_faces.append({'member': member, 'embedding': ref_vec})

    vector_index = FaceVectorIndex(known_faces)
    if vector_index.size == 0:
        return {'ok': False, 'message': '没有可用于识别的人脸向量，请先上传清晰正脸照片。', 'best_score': 0}

    hits = vector_index.search(live_vec, top_k=2)
    if not hits:
        return {'ok': False, 'message': 'Faiss向量检索无结果。', 'best_score': 0}

    best_member, best_score = hits[0]
    second_score = hits[1][1] if len(hits) > 1 else -1.0
    if best_score < FACE_SCORE_THRESHOLD:
        return {
            'ok': False,
            'message': f'未匹配到成员，最高余弦相似度 {best_score:.3f}，低于阈值 {FACE_SCORE_THRESHOLD:.3f}。',
            'best_score': round(best_score, 3),
            'checked': vector_index.size,
            'mode': 'yunet_sface_faiss',
            'bbox': bbox,
        }
    if second_score >= 0 and (best_score - second_score) < FACE_TOP1_GAP:
        return {
            'ok': False,
            'message': f'疑似相似人员，第一名 {best_score:.3f} 与第二名 {second_score:.3f} 差距过小。',
            'best_score': round(best_score, 3),
            'second_score': round(second_score, 3),
            'checked': vector_index.size,
            'mode': 'yunet_sface_faiss',
            'bbox': bbox,
        }

    m = best_member
    return {
        'ok': True,
        'message': f'识别成功：{m.name}',
        'member_id': m.id,
        'name': m.name,
        'student_no': m.student_no,
        'direction': m.direction,
        'best_score': round(best_score, 3),
        'second_score': round(second_score, 3) if second_score >= 0 else None,
        'checked': vector_index.size,
        'mode': 'yunet_sface_faiss',
        'bbox': bbox,
    }


def compare_face_with_photo(frame, photo_path: str | Path) -> FaceMatch:
    live_vec, bbox, msg = face_embedding_from_frame(frame)
    if live_vec is None:
        return FaceMatch(False, 0.0, msg, bbox)
    ref_vec, msg = build_embedding_from_photo(photo_path)
    if ref_vec is None:
        return FaceMatch(False, 0.0, msg, bbox)
    score = compare_embeddings(live_vec, ref_vec)
    return FaceMatch(score >= FACE_SCORE_THRESHOLD, score, 'ok', bbox)
