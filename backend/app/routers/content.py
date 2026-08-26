from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy import asc
import os
import subprocess
import tempfile
import re
import uuid
import zipfile
from pathlib import Path
from datetime import datetime

from ..database import get_db
from ..models import DocumentRevision, Session as SessionModel, Content as ContentModel, Template
from ..utils import ok, err, dt_str
from ..schemas import SaveArticleIn
from ..services.mineru_service import mineru_service

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/get/{session_id}")
def get_contents(session_id: int, db: OrmSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        return err(404, "会话不存在")

    rows = (
        db.query(ContentModel)
        .filter(ContentModel.session_id == session_id, ContentModel.content_category == "chat")
        .order_by(asc(ContentModel.created_at))
        .all()
    )
    data = [
        {
            "content_id": r.content_id,
            "content": r.content,
            "content_type": r.content_type,
            "content_category": r.content_category,
            "role": r.role,
            "created_at": dt_str(r.created_at),
        }
        for r in rows
    ]
    return ok(data)


@router.get("/article/{session_id}")
def get_article(session_id: int, db: OrmSession = Depends(get_db)):
    s = db.get(SessionModel, session_id)
    if not s:
        return err(404, "会话不存在")
    
    return ok({
        "article_content": s.article_content or "",
        "article_version": s.article_version,
    })


@router.post("/article/save")
def save_article(data: SaveArticleIn, db: OrmSession = Depends(get_db)):
    try:
        s = db.get(SessionModel, data.session_id)
        if not s:
            return err(404, "会话不存在")
        
        if data.base_version is not None and data.base_version != s.article_version:
            return err(409, "正文已被更新，请刷新后重试")
        s.article_content = data.article_content
        s.article_version += 1
        db.add(DocumentRevision(
            revision_id=str(uuid.uuid4()),
            session_id=s.session_id,
            version=s.article_version,
            article_content=data.article_content,
            created_by="user",
        ))
        db.commit()
        
        return ok({"article_version": s.article_version}, "文章保存成功")
    
    except Exception as e:
        print(f"[DEBUG] 保存文章失败: {str(e)}")
        return err(500, f"保存失败: {str(e)}")


@router.delete("/clear/{session_id}")
def clear_session_content(session_id: int, db: OrmSession = Depends(get_db)):
    """
    清空会话的所有内容
    """
    try:
        # 检查会话是否存在
        s = db.get(SessionModel, session_id)
        if not s:
            return err(404, "会话不存在")
        
        # 删除该会话的所有内容
        deleted_count = db.query(ContentModel).filter(ContentModel.session_id == session_id).delete()
        db.commit()
        
        print(f"[DEBUG] 清空会话 {session_id} 的内容，删除了 {deleted_count} 条记录")
        
        return ok(None, f"已清空 {deleted_count} 条内容")
    
    except Exception as e:
        print(f"[DEBUG] 清空内容失败: {str(e)}")
        return err(500, f"清空失败: {str(e)}")


@router.post("/upload")
async def upload_reference_document(file: UploadFile = File(...)):
    """
    上传参考文档，支持 .pdf、.docx、.md、.txt 文件
    所有格式最终都会转换为 Markdown 内容用于 AI 处理
    """
    try:
        file_extension = Path(file.filename).suffix.lower()
        allowed_extensions = ['.pdf', '.docx', '.md', '.txt']

        if file_extension not in allowed_extensions:
            return err(400, f"不支持的文件类型，请上传 {', '.join(allowed_extensions)} 文件")

        content_bytes = await file.read()
        markdown_content = None

        if file_extension == '.pdf':
            markdown_content = await _process_pdf(content_bytes, file.filename)
        elif file_extension == '.docx':
            markdown_content = await _process_docx(content_bytes, file.filename)
        elif file_extension == '.md':
            markdown_content = content_bytes.decode('utf-8')
        elif file_extension == '.txt':
            markdown_content = _txt_to_markdown(content_bytes.decode('utf-8'))

        if markdown_content is None:
            return err(500, "文件处理失败")

        return ok({
            "filename": file.filename,
            "content": markdown_content,
            "type": "markdown",
            "original_type": file_extension[1:]
        }, f"文档上传成功（{file_extension[1:]} -> Markdown）")

    except Exception as e:
        print(f"[DEBUG] 文件上传过程中出错: {str(e)}")
        return err(500, f"文件上传失败: {str(e)}")


async def _process_pdf(content_bytes: bytes, filename: str) -> str:
    """处理PDF文件：保存临时文件并调用MinerU API解析"""
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        temp_file.write(content_bytes)
        temp_path = temp_file.name

    try:
        result = mineru_service.parse_pdf_to_markdown(temp_path)
        return result or ""
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


async def _process_docx(content_bytes: bytes, filename: str) -> str:
    """处理DOCX文件：使用pandoc转换为Markdown"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
        temp_file.write(content_bytes)
        docx_temp_path = temp_file.name

    md_temp_path = docx_temp_path.replace('.docx', '.md')

    try:
        result = subprocess.run(
            ['pandoc', '-f', 'docx', '-t', 'markdown', '-o', md_temp_path, docx_temp_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and os.path.exists(md_temp_path):
            with open(md_temp_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            print(f"[DEBUG] Pandoc转换docx失败: {result.stderr}")
            return ""
    finally:
        for p in [docx_temp_path, md_temp_path]:
            if os.path.exists(p):
                os.unlink(p)


def _txt_to_markdown(text: str) -> str:
    """将纯文本转换为简单Markdown格式"""
    lines = text.split('\n')
    md_lines = []
    for line in lines:
        if line.strip():
            md_lines.append(line)
        else:
            md_lines.append('')
    return '\n'.join(md_lines)


def _registered_template_path(template: Template | None) -> Path | None:
    if template is None:
        return None
    format_dir = (Path(__file__).resolve().parents[3] / "format").resolve()
    filename = Path(template.filename).name
    if filename != template.filename:
        return None
    candidate = (format_dir / filename).resolve()
    if format_dir not in candidate.parents or not candidate.is_file():
        return None
    if candidate.suffix.lower() != ".docx" or not zipfile.is_zipfile(candidate):
        return None
    return candidate


@router.get("/export/{session_id}")
def export_document(
    session_id: int,
    background_tasks: BackgroundTasks,
    export_type: str = "md",
    template_id: int | None = None,
    reference_doc: str | None = None,
    db: OrmSession = Depends(get_db),
):
    """
    导出会话内容为文档
    export_type: "md" 或 "docx"
    template_id: 已登记的 DOCX 模板 ID。reference_doc 仅为旧前端兼容参数，仍需匹配数据库记录。
    """
    temp_md_path = None
    temp_docx_path = None
    temp_file_path = None
    try:
        # 验证导出类型
        if export_type not in ['md', 'docx']:
            return err(400, "不支持的导出类型，请选择 md 或 docx")
        
        # 获取会话信息
        s = db.get(SessionModel, session_id)
        if not s:
            return err(404, "会话不存在")
        
        # 获取文章主体内容
        if not s.article_content:
            return err(404, "该会话没有可导出的内容")
        
        # 清理内容：去除"标题："、"正文："等前缀
        cleaned_content = re.sub(r'^(标题：|正文：|Title:|Content:)\s*', '', s.article_content, flags=re.MULTILINE)
        
        # 去除开头和结尾的空白
        cleaned_content = cleaned_content.strip()
        
        # 创建临时文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if export_type == "md":
            # 导出为markdown文件
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                suffix='.md',
                encoding='utf-8'
            )
            temp_file.write(cleaned_content)
            temp_file.close()
            temp_file_path = temp_file.name
            
            filename = f"{s.session_name}_{timestamp}.md"
            
            background_tasks.add_task(os.unlink, temp_file_path)
            
            return FileResponse(
                path=temp_file_path,
                media_type='text/markdown',
                filename=filename
            )
        
        elif export_type == "docx":
            # 导出为docx文件
            # 先创建临时markdown文件
            temp_md_file = tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                suffix='.md',
                encoding='utf-8'
            )
            temp_md_file.write(cleaned_content)
            temp_md_file.close()
            temp_md_path = temp_md_file.name
            
            # 使用pandoc转换为docx
            temp_docx_path = temp_md_path.replace('.md', '.docx')
            
            # 构建pandoc命令
            pandoc_cmd = ['pandoc', '-f', 'markdown', '-t', 'docx', '-o', temp_docx_path, temp_md_path]
            
            # 只允许使用数据库中登记且位于 format 目录内的有效 DOCX 模板。
            selected_template = None
            if template_id is not None:
                selected_template = db.get(Template, template_id)
                if selected_template is None:
                    os.unlink(temp_md_path)
                    return err(404, "导出模板不存在")
            elif reference_doc:
                selected_template = db.query(Template).filter(Template.filename == reference_doc).first()
                if selected_template is None:
                    os.unlink(temp_md_path)
                    return err(400, "导出模板未登记")
            else:
                selected_template = db.query(Template).filter(Template.is_default == True).first()

            if selected_template is not None:
                reference_path = _registered_template_path(selected_template)
                if reference_path is None:
                    os.unlink(temp_md_path)
                    return err(400, "导出模板不是有效的 DOCX 文件")
                pandoc_cmd = [
                    'pandoc', '--reference-doc', str(reference_path), '-f', 'markdown',
                    '-t', 'docx', '-o', temp_docx_path, temp_md_path,
                ]
            try:
                result = subprocess.run(
                    pandoc_cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=30,
                )
            finally:
                if os.path.exists(temp_md_path):
                    os.unlink(temp_md_path)
            
            if result.returncode != 0:
                print(f"[DEBUG] Pandoc转换失败: {result.stderr}")
                if os.path.exists(temp_docx_path):
                    os.unlink(temp_docx_path)
                return err(500, "文档转换失败，请检查模板或稍后重试")
            if not os.path.exists(temp_docx_path) or not zipfile.is_zipfile(temp_docx_path):
                if os.path.exists(temp_docx_path):
                    os.unlink(temp_docx_path)
                return err(500, "Pandoc 未生成有效的 DOCX 文件")
            
            filename = f"{s.session_name}_{timestamp}.docx"
            
            background_tasks.add_task(os.unlink, temp_docx_path)
            
            return FileResponse(
                path=temp_docx_path,
                media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                filename=filename
            )
    
    except Exception as e:
        print(f"[DEBUG] 导出文档过程中出错: {str(e)}")
        for temporary_path in (temp_md_path, temp_docx_path, temp_file_path):
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
        return err(500, "导出文档失败，请稍后重试")
