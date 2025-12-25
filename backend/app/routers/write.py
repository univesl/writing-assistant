import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as OrmSession

from ..database import get_db
from ..models import Session as SessionModel, Content as ContentModel
from ..schemas import WriteQuickIn, WriteStepIn, WritePolishIn, WriteSaveIn
from ..utils import ok, err
from ..services.llm import build_quick_output, build_step_output, polish_text, stream_text_from_llm, stream_text

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


@router.post("/step")
async def write_step(payload: WriteStepIn, db: OrmSession = Depends(get_db)):
    # 打印前端传入的完整数据
    print("[DEBUG] 前端传入的分步写作数据:", payload.dict())
    
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

    # 构建提示词
    sp = "；".join([s for s in payload.selling_points if s.strip()]) or "（暂无卖点）"
    prompt = (
        f"请为产品 '{payload.product_name}' 生成一份文案，要求如下：\n"
        f"- 产品卖点：{sp}\n"
        f"- 写作风格：{payload.style}\n"
        f"- 内容长度：{payload.length}\n"
        f"请确保文案结构清晰、重点突出。"
    )
    
    system_prompt = "你是一个专业的产品文案策划师，请根据用户提供的产品信息生成结构化的产品文案。"

    async def gen():
        # 使用LLM流式生成内容
        full_text = ""
        async for chunk in stream_text_from_llm(prompt, system_prompt=system_prompt):
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


@router.post("/polish")
async def write_polish(payload: WritePolishIn, db: OrmSession = Depends(get_db)):
    # 打印前端传入的完整数据
    print("[DEBUG] 前端传入的校对润色数据:", payload.dict())
    
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

    # 根据不同的润色类型构建不同的提示词
    if payload.polish_type == "check":
        prompt = f"请检查以下文本的语法和拼写错误，并进行修正：\n\n{payload.content}"
        system_prompt = "你是一个专业的文本校对员，请检查用户提供的文本并修正语法和拼写错误。"
    elif payload.polish_type == "optimize":
        prompt = f"请优化以下文本的表达，使其更加流畅自然：\n\n{payload.content}"
        system_prompt = "你是一个专业的文本优化师，请优化用户提供的文本表达，使其更加流畅自然。"
    else:  # expand
        prompt = f"请扩写以下文本，增加更多细节和背景信息：\n\n{payload.content}"
        system_prompt = "你是一个专业的文本扩写师，请扩写用户提供的文本，增加更多细节和背景信息。"

    async def gen():
        # 使用LLM流式生成内容
        full_text = ""
        async for chunk in stream_text_from_llm(prompt, system_prompt=system_prompt):
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
