import json
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as OrmSession

from ..database import get_db
from ..models import Session as SessionModel, Content as ContentModel
from ..schemas import WriteQuickIn, WriteSaveIn
from ..utils import ok, err
from ..services.llm import stream_text_from_llm
from ..services.prompt_builder import build_prompt

router = APIRouter(prefix="/write", tags=["write"])


def sse_pack(content: str, finish: bool) -> str:
    return f"data: {json.dumps({'content': content, 'finish': finish}, ensure_ascii=False)}\n\n"


@router.post("/quick")
async def write_quick(payload: WriteQuickIn, db: OrmSession = Depends(get_db)):
    print("[DEBUG] 前端传入的快速写作数据:", payload.dict())
    
    session = db.get(SessionModel, payload.session_id)
    if not session:
        print(f"[DEBUG] 会话ID {payload.session_id} 不存在，创建新会话")
        session = SessionModel(session_name="新会话")
        db.add(session)
        db.commit()
        db.refresh(session)
        payload.session_id = session.session_id
    else:
        print(f"[DEBUG] 会话ID {payload.session_id} 存在")

    # 使用 PromptBuilder 统一构建 prompt
    messages = build_prompt(
        mode=payload.mode,
        style=payload.style,
        data={
            "user_requirements": payload.user_requirements,
            "reference_content": payload.reference_content,
            "reference_filename": payload.reference_filename,
            "rag_content": payload.rag_content,
            "rag_references": payload.rag_references,
            "quotes": payload.quotes,
            "article_content": payload.article_content,
            "extracted_fields": payload.extracted_fields,
            "style": payload.style,
        },
    )
    
    llm_model = payload.llm_model or "xhang"
    print(f"[DEBUG] 使用的LLM模型: {llm_model}")
    print(f"[DEBUG] 构建的 system prompt 长度: {len(messages[0]['content'])}")
    print(f"[DEBUG] 构建的 user prompt 长度: {len(messages[1]['content'])}")

    async def gen():
        full_text = ""
        chunk_count = 0
        async for chunk in stream_text_from_llm(messages, llm_model=llm_model):
            chunk_count += 1
            print(f"[DEBUG] yield chunk #{chunk_count}: {chunk[:50] if len(chunk) > 50 else chunk}...")
            full_text += chunk
            yield sse_pack(chunk, False)
            await asyncio.sleep(0.01)
        
        print(f"[DEBUG] LLM完整回复：{full_text}")
        print(f"[DEBUG] 总共 yield 了 {chunk_count} 个 chunk")
        yield sse_pack("", True)

    headers = {
        "Cache-Control": "no-cache",
        "Content-Type": "text/event-stream",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
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
        content_category=payload.content_category or "chat",
        role=payload.role or "user",
        original_content=payload.original_content,
    )
    db.add(c)

    db.commit()
    db.refresh(c)

    return ok({"content_id": c.content_id}, "保存成功")