from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import desc

from ..database import get_db
from ..models import Session as SessionModel
from ..schemas import SessionCreateIn, SessionRenameIn
from ..utils import ok, err, dt_str
from ..services.document_processor import delete_session_files

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/create")
def create_session(payload: SessionCreateIn, db: OrmSession = Depends(get_db)):
    # 打印前端传入的完整数据
    print("[DEBUG] 前端传入的会话创建数据:", payload.dict())
    name = (payload.session_name or "").strip() if payload.session_name else ""
    tmp_name = name if name else "新会话"
    s = SessionModel(session_name=tmp_name)
    db.add(s)
    db.commit()
    db.refresh(s)

    if not name:
        s.session_name = f"会话{ s.session_id }"
        db.commit()
        db.refresh(s)

    return ok(
        {
            "session_id": s.session_id,
            "session_name": s.session_name,
            "created_at": dt_str(s.created_at),
        }
    )


@router.get("/list")
def list_sessions(db: OrmSession = Depends(get_db)):
    rows = db.query(SessionModel).order_by(desc(SessionModel.created_at)).all()
    data = [
        {
            "session_id": r.session_id,
            "session_name": r.session_name,
            "created_at": dt_str(r.created_at),
        }
        for r in rows
    ]
    return ok(data)


from ..models import Content

@router.delete("/delete/{session_id}")
def delete_session(session_id: int, db: OrmSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        return err(404, "会话不存在")
    
    # 删除所有关联的内容
    db.query(Content).filter(Content.session_id == session_id).delete()
    
    # 删除会话的所有文件（物理文件和数据库记录）
    # 数据库记录会通过 cascade 自动删除
    delete_session_files(session_id)
    
    db.delete(s)
    db.commit()
    return ok(None, "会话删除成功")


@router.put("/rename/{session_id}")
def rename_session(session_id: int, payload: SessionRenameIn, db: OrmSession = Depends(get_db)):
    # 打印前端传入的完整数据
    print(f"[DEBUG] 前端传入的会话重命名数据: session_id={session_id}, {payload.dict()}")
    s = db.get(SessionModel, session_id)
    if not s:
        return err(404, "会话不存在")
    s.session_name = payload.session_name.strip()
    db.commit()
    return ok(None, "重命名成功")
