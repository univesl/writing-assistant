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


class Template(Base):
    """导出模板（docx 格式，用于 pandoc --reference-doc）"""
    __tablename__ = "templates"

    template_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)       # 模板名称
    filename: Mapped[str] = mapped_column(String(512), nullable=False)    # 文件在 format/ 下的存储名
    description: Mapped[str | None] = mapped_column(String(500), nullable=True, default="")  # 模板描述
    is_default: Mapped[bool] = mapped_column(Integer, nullable=False, default=False)  # 是否为默认模板

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
