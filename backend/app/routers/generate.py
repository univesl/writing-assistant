"""
文档生成路由
基于 KnG RAG 检索生成公文
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as OrmSession
from pydantic import BaseModel
from typing import List, Optional

from ..database import get_db
from ..models import Session as SessionModel
from ..utils import ok, err
from ..schemas import ReplyGenerationRequest, ReferenceGenerationRequest, ReferenceWriteRequest
from ..services.document_generator import (
    generate_document_async,
    generate_reply_document,
    generate_reference_document,
    list_available_models,
    retrieve_knowledge_base_content,
)

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    """文档生成请求"""
    topic: str
    requirements: str = ""
    model_name: str = "Qwen2.5-72B-Instruct"  # 默认使用快速模型
    use_knowledge_base: bool = True
    retrieval_mode: str = "local"  # local, global, hybrid, mix, naive
    top_k: int = 60
    chunk_top_k: int = 5


class GenerateResponse(BaseModel):
    """文档生成响应"""
    content: str
    references: List[str]
    model_used: str
    retrieval_info: dict
    timing: dict


@router.post("/document")
async def generate_document_endpoint(
    request: GenerateRequest,
    db: OrmSession = Depends(get_db)
):
    """
    基于知识库 RAG 检索生成文档
    
    根据主题和要求：
    1. 使用 KnG RAG 检索相关知识库内容（文本块、实体、关系）
    2. 基于检索结果生成符合风格的公文
    
    检索模式说明：
    - hybrid: 混合检索（实体+关系+文本块），推荐
    - local: 基于实体和文本块的本地检索
    - global: 基于关系和数据摘要的全局检索
    - mix: 包含知识图谱数据和向量检索的文本块
    - naive: 仅向量检索文本块
    """
    try:
        result = await generate_document_async(
            topic=request.topic,
            requirements=request.requirements,
            model_name=request.model_name,
            use_knowledge_base=request.use_knowledge_base,
            retrieval_mode=request.retrieval_mode,
            top_k=request.top_k,
            chunk_top_k=request.chunk_top_k,
        )
        
        return ok(result, "文档生成成功")
    except Exception as e:
        print(f"[ERROR] 文档生成失败: {e}")
        return err(500, f"文档生成失败: {str(e)}")


@router.post("/reference-write")
async def reference_write(request: ReferenceWriteRequest):
    """参考写作（流式）：根据上传文件进行回函/仿写/基于内容生成"""
    return StreamingResponse(
        generate_reference_document(
            reference_content=request.reference_content,
            reference_filename=request.reference_filename,
            generate_type=request.generate_type,
            topic=request.topic,
            requirements=request.requirements,
            model_name=request.model_name,
            use_knowledge_base=request.use_knowledge_base,
            top_k=request.top_k,
        ),
        media_type="text/event-stream"
    )


@router.get("/models")
async def list_models():
    """获取可用的文档生成模型列表"""
    try:
        models = list_available_models()
        return ok({"models": models}, "获取模型列表成功")
    except Exception as e:
        print(f"[ERROR] 获取模型列表失败: {e}")
        return err(500, f"获取模型列表失败: {str(e)}")


class RetrieveRequest(BaseModel):
    """知识库检索请求"""
    query: str
    mode: str = "hybrid"
    top_k: int = 60
    chunk_top_k: int = 5


@router.post("/retrieve")
async def retrieve_documents(request: RetrieveRequest):
    """
    直接检索知识库内容（不生成文档）
    
    返回检索到的文本块、实体和关系
    """
    try:
        results = await retrieve_knowledge_base_content(
            topic=request.query,
            mode=request.mode,
            top_k=request.top_k,
            chunk_top_k=request.chunk_top_k,
        )
        
        return ok({
            "content": results.get("content", ""),
            "chunks_count": len(results.get("chunks", [])),
            "entities_count": len(results.get("entities", [])),
            "relationships_count": len(results.get("relationships", [])),
            "references": results.get("references", []),
        }, "检索成功")
    except Exception as e:
        print(f"[ERROR] 检索失败: {e}")
        return err(500, f"检索失败: {str(e)}")


@router.post("/reply")
async def generate_reply(request: ReplyGenerationRequest):
    """生成回函（流式）"""
    return StreamingResponse(
        generate_reply_document(
            topic=request.topic,
            requirements=request.requirements,
            original_content=request.original_content,
            extracted_fields=request.extracted_fields,
            model_name=request.model_name,
            use_knowledge_base=request.use_knowledge_base,
            top_k=request.top_k,
        ),
        media_type="text/event-stream"
    )


@router.post("/with-reference")
async def generate_with_reference(request: ReferenceGenerationRequest, db: OrmSession = Depends(get_db)):
    """以参考文档为基础生成公文"""
    try:
        result = await generate_document_async(
            topic=request.topic,
            requirements=request.requirements,
            model_name=request.model_name,
            use_knowledge_base=request.use_knowledge_base,
            top_k=request.top_k,
            reference_content=request.reference_content,
        )
        return ok(result, "文档生成成功")
    except Exception as e:
        print(f"[ERROR] 文档生成失败: {e}")
        return err(500, f"文档生成失败: {str(e)}")
