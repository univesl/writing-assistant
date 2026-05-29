from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    session_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    article_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    contents: Mapped[list["Content"]] = relationship(
        "Content",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    
    files: Mapped[list["SessionFile"]] = relationship(
        "SessionFile",
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Content(Base):
    __tablename__ = "contents"

    content_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_category: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    session: Mapped["Session"] = relationship("Session", back_populates="contents")


class SessionFile(Base):
    """会话级别的文件（临时文件，会话删除时连带删除）"""
    __tablename__ = "session_files"

    file_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    
    # 原始文件名
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # 存储的文件路径（相对路径）
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    # 文件类型
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    
    # 解析后的 Markdown 内容（可选，如果已解析）
    parsed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 字段提取结果（JSON格式）
    extracted_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 提取状态: pending, parsing, extracting, completed, failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # 错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    session: Mapped["Session"] = relationship("Session", back_populates="files")
