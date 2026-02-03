import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as OrmSession

from ..database import get_db
from ..models import Session as SessionModel, Content as ContentModel
from ..schemas import WriteQuickIn, WriteSaveIn
from ..utils import ok, err
from ..services.llm import stream_text_from_llm

router = APIRouter(prefix="/write", tags=["write"])


def sse_pack(content: str, finish: bool) -> str:
    return f"data: {json.dumps({'content': content, 'finish': finish}, ensure_ascii=False)}\n\n"


@router.post("/quick")
async def write_quick(payload: WriteQuickIn, db: OrmSession = Depends(get_db)):
    # 打印前端传入的完整数据
    print("[DEBUG] 前端传入的快速写作数据:", payload.dict())
    
    # 检查会话是否存在，如果不存在则创建新会话
    session = db.get(SessionModel, payload.session_id)
    if not session:
        print(f"[DEBUG] 会话ID {payload.session_id} 不存在，创建新会话")
        # 创建新会话
        session = SessionModel(session_name="新会话")
        db.add(session)
        db.commit()
        db.refresh(session)
        # 更新payload中的session_id
        payload.session_id = session.session_id
    else:
        print(f"[DEBUG] 会话ID {payload.session_id} 存在")

    # 构建系统提示词
    if payload.model_type == "creative":
        system_prompt = "你是一个创意文案专家，请根据用户提供的提示生成富有创意和吸引力的文案。"
    else:
        system_prompt = "你是一个专业文案撰写人，请根据用户提供的提示生成结构完整、表达清晰的通用文案。"

    async def gen():
        # 使用LLM流式生成内容
        full_text = ""
        async for chunk in stream_text_from_llm(payload.prompt, system_prompt=system_prompt):
            full_text += chunk
            # 打印大模型的回复内容（流式）
            print(f"[DEBUG] LLM回复内容：{chunk}")
            yield sse_pack(chunk, False)
        # 打印完整的大模型回复
        print(f"[DEBUG] LLM完整回复：{full_text}")
        # 发送结束信号，不包含重复内容
        yield sse_pack("", True)

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
    }
    return StreamingResponse(gen(), headers=headers, media_type="text/event-stream")


@router.post("/save")
def write_save(payload: WriteSaveIn, db: OrmSession = Depends(get_db)):
    # 打印前端传入的完整数据
    print("[DEBUG] 前端传入的内容保存数据:", payload.dict())
    
    # 检查会话是否存在，如果不存在则创建新会话
    session = db.get(SessionModel, payload.session_id)
    if not session:
        print(f"[DEBUG] 会话ID {payload.session_id} 不存在，创建新会话")
        # 创建新会话
        session = SessionModel(session_name="新会话")
        db.add(session)
        db.commit()
        db.refresh(session)
        # 更新payload中的session_id
        payload.session_id = session.session_id
    else:
        print(f"[DEBUG] 会话ID {payload.session_id} 存在")

    c = ContentModel(
        session_id=payload.session_id,
        content=payload.content,
        content_type=payload.content_type,
        original_content=payload.original_content,
    )
    db.add(c)

    db.commit()
    db.refresh(c)

    return ok({"content_id": c.content_id}, "保存成功")
