from datetime import datetime
from sqlalchemy import Boolean, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    session_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    article_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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

    agent_runs: Mapped[list["AgentRun"]] = relationship(
        "AgentRun",
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


class AgentRun(Base):
    """A durable writing-agent execution associated with one writing session."""

    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default="quick")
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model_profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    draft_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_article: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="document")
    base_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proposal_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposal_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    applied_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activated_skills_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    workflow_plan_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    references_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    issues_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    last_event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    session: Mapped["Session"] = relationship("Session", back_populates="agent_runs")
    events: Mapped[list["AgentEvent"]] = relationship(
        "AgentEvent",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AgentEvent.seq",
    )


class AgentEvent(Base):
    """Persisted, replayable public event. Never stores hidden model reasoning."""

    __tablename__ = "agent_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_agent_event_run_seq"),)

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="events")


class DocumentRevision(Base):
    """Immutable snapshot created by a user save or completed Agent run."""

    __tablename__ = "document_revisions"
    __table_args__ = (UniqueConstraint("session_id", "version", name="uq_document_revision_version"),)

    revision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    article_content: Mapped[str] = mapped_column(Text, nullable=False)
    source_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agent_runs.run_id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
