"""
模板管理路由
支持上传 .docx 模板文件、列表查询、删除
"""

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session as OrmSession

from ..database import get_db
from ..models import Template
from ..schemas import TemplateOut
from ..utils import ok, err

router = APIRouter(prefix="/templates", tags=["templates"])

# 模板文件存储目录（与 content.py 中 export 使用的 format_dir 一致）
TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'format'))


@router.get("/list")
def list_templates(db: OrmSession = Depends(get_db)):
    """获取模板列表"""
    rows = db.query(Template).order_by(Template.is_default.desc(), Template.created_at.desc()).all()
    data = [
        {
            "template_id": t.template_id,
            "name": t.name,
            "filename": t.filename,
            "description": t.description or "",
            "is_default": bool(t.is_default),
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
        }
        for t in rows
    ]
    return ok(data, "获取模板列表成功")


@router.post("/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str = Form(""),
    db: OrmSession = Depends(get_db),
):
    """上传模板文件（.docx）"""
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.docx'):
        return err(400, "仅支持 .docx 格式的模板文件")

    # 生成存储文件名（时间戳 + 原始文件名）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_original = Path(file.filename).name
    storage_filename = f"{timestamp}_{safe_original}"
    file_path = os.path.join(TEMPLATES_DIR, storage_filename)

    # 保存文件
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    content = await file.read()
    if not content:
        return err(400, "模板文件为空")
    if len(content) > 20 * 1024 * 1024:
        return err(400, "模板文件不能超过 20 MB")
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as probe:
        probe.write(content)
        probe_path = probe.name
    try:
        if not zipfile.is_zipfile(probe_path):
            return err(400, "模板不是有效的 DOCX 文件")
        with zipfile.ZipFile(probe_path) as archive:
            required_parts = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
            if not required_parts.issubset(set(archive.namelist())):
                return err(400, "模板缺少必要的 Word 文档结构")
    finally:
        os.unlink(probe_path)
    with open(file_path, 'wb') as f:
        f.write(content)

    # 使用文件名（不含扩展名）作为模板名称
    template_name = name.strip() or os.path.splitext(safe_original)[0]

    # 创建数据库记录
    t = Template(
        name=template_name,
        filename=storage_filename,
        description=description.strip() or "",
    )
    db.add(t)
    db.commit()
    db.refresh(t)

    return ok({
        "template_id": t.template_id,
        "name": t.name,
        "filename": t.filename,
    }, "模板上传成功")


@router.delete("/delete/{template_id}")
def delete_template(template_id: int, db: OrmSession = Depends(get_db)):
    """删除模板"""
    t = db.get(Template, template_id)
    if not t:
        return err(404, "模板不存在")

    was_default = t.is_default

    # 删除文件
    templates_root = Path(TEMPLATES_DIR).resolve()
    file_path = (templates_root / Path(t.filename).name).resolve()
    if templates_root in file_path.parents and Path(t.filename).name == t.filename and file_path.exists():
        os.remove(file_path)

    # 删除数据库记录
    db.delete(t)
    db.commit()

    # 如果删除的是默认模板，自动将第一个可用模板设为默认
    if was_default:
        first = db.query(Template).first()
        if first:
            first.is_default = True
            db.commit()
            print(f"[templates] 默认模板已删除，自动切换到: {first.filename}")

    return ok(None, "模板删除成功")


@router.post("/{template_id}/set-default")
def set_default_template(template_id: int, db: OrmSession = Depends(get_db)):
    """设置默认模板"""
    t = db.get(Template, template_id)
    if not t:
        return err(404, "模板不存在")

    # 清除其他模板的默认标记
    db.query(Template).filter(Template.is_default == True).update({"is_default": False})
    # 设置当前模板为默认
    t.is_default = True
    db.commit()

    return ok({"template_id": template_id, "name": t.name}, "默认模板设置成功")
