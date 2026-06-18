import json
import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as OrmSession

from ..database import get_db
from ..models import Session as SessionModel, Content as ContentModel
from ..schemas import WriteQuickIn, WriteSaveIn
from ..utils import ok, err
from ..services.llm import stream_text_from_llm
from ..services.prompt_builder import build_prompt
from ..services.kng_rag_service import get_kng_rag_service

router = APIRouter(prefix="/write", tags=["write"])


def sse_pack(content: str, finish: bool) -> str:
    return f"data: {json.dumps({'content': content, 'finish': finish}, ensure_ascii=False)}\n\n"


@router.post("/quick")
async def write_quick(payload: WriteQuickIn, db: OrmSession = Depends(get_db)):
    session = db.get(SessionModel, payload.session_id)
    if not session:
        session = SessionModel(session_name="新会话")
        db.add(session)
        db.commit()
        db.refresh(session)
        payload.session_id = session.session_id

    # 仅当用户勾选了"启用知识库检索"且未提供 rag_content 时，才做 RAG 检索
    rag_content = payload.rag_content
    rag_references = payload.rag_references
    if payload.use_rag and not rag_content:
        try:
            service = get_kng_rag_service()
            if service.is_ready():
                topic = payload.user_requirements or (
                    "通知公文" if payload.style == "notice" else
                    "规章制度" if payload.style == "regulation" else
                    "讲话稿" if payload.style == "speech" else
                    "文章"
                )
                result = service.retrieve_for_document_generation(
                    topic=topic,
                    requirements=payload.user_requirements or "",
                    mode="local",
                )
                if result.get("content"):
                    rag_content = result["content"]
                    rag_references = result.get("references", [])
                    print(f"[write] RAG 检索完成，内容长度: {len(rag_content)}")
        except Exception as e:
            print(f"[write] RAG 检索失败（跳过）: {e}")

    messages = build_prompt(
        mode=payload.mode,
        style=payload.style,
        data={
            "user_requirements": payload.user_requirements,
            "reference_content": payload.reference_content,
            "reference_filename": payload.reference_filename,
            "rag_content": rag_content,
            "rag_references": rag_references,
            "quotes": payload.quotes,
            "article_content": payload.article_content,
            "extracted_fields": payload.extracted_fields,
            "style": payload.style,
        },
    )

    llm_model = payload.llm_model or "xhang"
    print(f"[write] mode={payload.mode}, model={llm_model}, prompt_len={len(messages[0]['content'])}/{len(messages[1]['content'])}")

    async def gen():
        full_text = ""
        async for chunk in stream_text_from_llm(messages, llm_model=llm_model):
            full_text += chunk
            yield sse_pack(chunk, False)

        print(f"[write] LLM 生成完成，总长度: {len(full_text)}")
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
    session = db.get(SessionModel, payload.session_id)
    if not session:
        session = SessionModel(session_name="新会话")
        db.add(session)
        db.commit()
        db.refresh(session)
        payload.session_id = session.session_id

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