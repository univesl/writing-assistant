from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import asc

from ..database import get_db
from ..models import Session as SessionModel, Content as ContentModel
from ..utils import ok, err, dt_str

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/get/{session_id}")
def get_contents(session_id: int, db: OrmSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        return err(404, "会话不存在")

    rows = (
        db.query(ContentModel)
        .filter(ContentModel.session_id == session_id)
        .order_by(asc(ContentModel.created_at))
        .all()
    )
    data = [
        {
            "content_id": r.content_id,
            "content": r.content,
            "content_type": r.content_type,
            "created_at": dt_str(r.created_at),
        }
        for r in rows
    ]
    return ok(data)
