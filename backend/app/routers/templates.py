"""
模板管理路由
支持上传 .docx 模板文件、列表查询、删除
"""

import os
import shutil
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    storage_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(TEMPLATES_DIR, storage_filename)

    # 保存文件
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    content = await file.read()
    with open(file_path, 'wb') as f:
        f.write(content)

    # 使用文件名（不含扩展名）作为模板名称
    template_name = name.strip() or os.path.splitext(file.filename)[0]

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

    # 删除文件
    file_path = os.path.join(TEMPLATES_DIR, t.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # 删除数据库记录
    db.delete(t)
    db.commit()

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