#!/usr/bin/env python3
"""
文件上传与解析路由
职责：处理会话级文件的上传、解析、字段提取
"""

import json
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session as OrmSession
from pathlib import Path

from ..database import get_db
from ..models import Session as SessionModel, SessionFile
from ..schemas import FileUploadResponse, FileListResponse
from ..utils import ok, err, dt_str
from ..services.document_processor import (
    save_uploaded_file,
    parse_document,
    extract_fields_from_content,
    get_file_type,
    is_supported_file,
)

from ..services.field_extractor import AVAILABLE_MODELS

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/session/{session_id}")
async def upload_session_file(
    session_id: int,
    file: UploadFile = File(...),
    auto_parse: bool = Form(True),
    auto_extract: bool = Form(True),
    model_name: str = Form("qwen2.5-72b"),
    db: OrmSession = Depends(get_db)
):
    """
    上传文件到指定会话
    
    Args:
        session_id: 会话ID
        file: 上传的文件
        auto_parse: 是否自动解析文档
        auto_extract: 是否自动提取字段
        model_name: 用于字段提取的模型名称
    """
    # 检查会话是否存在
    session = db.get(SessionModel, session_id)
    if not session:
        return err(404, "会话不存在")
    
    # 检查文件类型
    if not is_supported_file(file.filename):
        return err(400, "不支持的文件类型，请上传 PDF、DOCX、MD 或 TXT 文件")
    
    try:
        # 读取文件内容
        content = await file.read()
        if len(content) == 0:
            return err(400, "文件内容为空")
        
        # 保存文件到会话目录
        file_path = save_uploaded_file(session_id, file.filename, content)
        relative_path = str(Path(file_path).relative_to(Path("/home/liubin/writing-assistant/session_files")))
        
        # 创建数据库记录
        session_file = SessionFile(
            session_id=session_id,
            original_filename=file.filename,
            storage_path=relative_path,
            file_type=get_file_type(file.filename),
            status="pending"
        )
        db.add(session_file)
        db.commit()
        db.refresh(session_file)
        
        result = {
            "file_id": session_file.file_id,
            "session_id": session_id,
            "original_filename": file.filename,
            "file_type": session_file.file_type,
            "status": session_file.status,
        }
        
        # 自动解析文档
        if auto_parse:
            session_file.status = "parsing"
            db.commit()
            
            parsed_content = parse_document(file_path)
            
            if parsed_content is not None:
                session_file.parsed_content = parsed_content
                session_file.status = "extracting" if auto_extract else "completed"
                result["parsed"] = True
                result["content_length"] = len(parsed_content)
                result["parsed_content"] = parsed_content
                
                # 自动提取字段
                if auto_extract:
                    extracted_fields = extract_fields_from_content(parsed_content, model_name)
                    session_file.extracted_fields = json.dumps(extracted_fields, ensure_ascii=False)
                    session_file.status = "completed"
                    result["extracted"] = True
                    result["fields"] = extracted_fields
            else:
                session_file.status = "failed"
                session_file.error_message = "文档解析失败"
                result["parsed"] = False
                result["error"] = "文档解析失败"
        
        db.commit()
        
        return ok(result, "文件上传成功")
        
    except Exception as e:
        print(f"[ERROR] 文件上传失败: {e}")
        import traceback
        traceback.print_exc()
        return err(500, f"文件上传失败: {str(e)}")


@router.get("/session/{session_id}/files")
def list_session_files(session_id: int, db: OrmSession = Depends(get_db)):
    """获取会话的所有文件列表"""
    session = db.get(SessionModel, session_id)
    if not session:
        return err(404, "会话不存在")
    
    files = db.query(SessionFile).filter(SessionFile.session_id == session_id).all()
    
    data = []
    for f in files:
        item = {
            "file_id": f.file_id,
            "original_filename": f.original_filename,
            "file_type": f.file_type,
            "status": f.status,
            "created_at": dt_str(f.created_at),
            "updated_at": dt_str(f.updated_at),
        }
        
        # 如果提取完成，包含字段结果
        if f.status == "completed" and f.extracted_fields:
            try:
                item["fields"] = json.loads(f.extracted_fields)
            except:
                item["fields"] = {}
        
        data.append(item)
    
    return ok(data)


@router.get("/file/{file_id}")
def get_file_detail(file_id: int, db: OrmSession = Depends(get_db)):
    """获取文件详情（包括解析内容和提取字段）"""
    file = db.get(SessionFile, file_id)
    if not file:
        return err(404, "文件不存在")
    
    result = {
        "file_id": file.file_id,
        "session_id": file.session_id,
        "original_filename": file.original_filename,
        "file_type": file.file_type,
        "status": file.status,
        "error_message": file.error_message,
        "created_at": dt_str(file.created_at),
        "updated_at": dt_str(file.updated_at),
    }
    
    if file.parsed_content:
        result["parsed_content"] = file.parsed_content
    
    if file.extracted_fields:
        try:
            result["fields"] = json.loads(file.extracted_fields)
        except:
            result["fields"] = {}
    
    return ok(result)


@router.post("/file/{file_id}/extract")
def extract_file_fields(
    file_id: int,
    model_name: str = Form("qwen2.5-72b"),
    db: OrmSession = Depends(get_db)
):
    """重新提取文件字段（用于手动触发或更换模型）"""
    file = db.get(SessionFile, file_id)
    if not file:
        return err(404, "文件不存在")
    
    if not file.parsed_content:
        return err(400, "文件尚未解析，请先解析文档")
    
    try:
        file.status = "extracting"
        db.commit()
        
        extracted_fields = extract_fields_from_content(file.parsed_content, model_name)
        file.extracted_fields = json.dumps(extracted_fields, ensure_ascii=False)
        file.status = "completed"
        db.commit()
        
        return ok({
            "file_id": file_id,
            "fields": extracted_fields
        }, "字段提取成功")
        
    except Exception as e:
        file.status = "failed"
        file.error_message = f"字段提取失败: {str(e)}"
        db.commit()
        return err(500, f"字段提取失败: {str(e)}")


@router.put("/file/{file_id}/fields")
def update_file_fields(
    file_id: int,
    request: dict,
    db: OrmSession = Depends(get_db)
):
    """
    更新文件的提取字段（用户手动编辑后保存）
    
    Args:
        file_id: 文件ID
        request: {"fields": {字段名: 字段值, ...}}
    """
    file = db.get(SessionFile, file_id)
    if not file:
        return err(404, "文件不存在")
    
    try:
        fields = request.get("fields", {})
        
        # 验证字段格式
        if not isinstance(fields, dict):
            return err(400, "字段格式错误，必须是对象")
        
        # 保存字段到数据库
        file.extracted_fields = json.dumps(fields, ensure_ascii=False)
        db.commit()
        db.refresh(file)
        
        return ok({
            "file_id": file_id,
            "fields": fields,
            "updated_at": dt_str(file.updated_at)
        }, "字段更新成功")
        
    except Exception as e:
        db.rollback()
        return err(500, f"字段更新失败: {str(e)}")


@router.delete("/file/{file_id}")
def delete_file(file_id: int, db: OrmSession = Depends(get_db)):
    """删除文件"""
    file = db.get(SessionFile, file_id)
    if not file:
        return err(404, "文件不存在")
    
    try:
        # 删除物理文件
        from ..services.document_processor import SESSION_FILES_ROOT
        file_path = SESSION_FILES_ROOT / file.storage_path
        if file_path.exists():
            file_path.unlink()
        
        # 删除数据库记录
        db.delete(file)
        db.commit()
        
        return ok(None, "文件删除成功")
        
    except Exception as e:
        return err(500, f"删除失败: {str(e)}")


# 模型显示名称映射（统一使用 Qwen2.5-72B）
MODEL_DISPLAY_NAMES = {
    "qwen2.5-72b": "Qwen2.5-72B (统一模型)",
}


@router.get("/models")
def list_available_models():
    """列出所有可用的字段提取模型"""
    models = []
    for name, config in AVAILABLE_MODELS.items():
        models.append({
            "name": name,
            "display_name": MODEL_DISPLAY_NAMES.get(name, name),
            "model": config["model"],
            "base_url": config["base_url"]
        })
    return ok(models)
