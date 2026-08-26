"""Add document versions and Agent proposals."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260822_0002"
down_revision: Union[str, None] = "20260822_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "sessions" in tables and "article_version" not in _columns("sessions"):
        op.add_column("sessions", sa.Column("article_version", sa.Integer(), nullable=False, server_default="0"))

    if "agent_runs" in tables:
        existing = _columns("agent_runs")
        additions = (
            ("outcome", sa.String(length=32), "document", False),
            ("base_version", sa.Integer(), "0", False),
            ("proposal_content", sa.Text(), None, True),
            ("proposal_status", sa.String(length=32), "none", False),
            ("applied_version", sa.Integer(), None, True),
            ("activated_skills_json", sa.Text(), "[]", False),
            ("workflow_plan_json", sa.Text(), "{}", False),
        )
        for name, type_, default, nullable in additions:
            if name not in existing:
                op.add_column(
                    "agent_runs",
                    sa.Column(name, type_, nullable=nullable, server_default=default),
                )

    if "document_revisions" not in tables:
        op.create_table(
            "document_revisions",
            sa.Column("revision_id", sa.String(length=36), primary_key=True),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("article_content", sa.Text(), nullable=False),
            sa.Column("source_run_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=16), nullable=False, server_default="user"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.run_id"], ondelete="SET NULL"),
            sa.UniqueConstraint("session_id", "version", name="uq_document_revision_version"),
        )
        op.create_index("ix_document_revisions_session_id", "document_revisions", ["session_id"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "document_revisions" in tables:
        op.drop_index("ix_document_revisions_session_id", table_name="document_revisions")
        op.drop_table("document_revisions")
    if "agent_runs" in tables:
        for name in (
            "workflow_plan_json", "activated_skills_json", "applied_version", "proposal_status",
            "proposal_content", "base_version", "outcome",
        ):
            if name in _columns("agent_runs"):
                op.drop_column("agent_runs", name)
    if "sessions" in tables and "article_version" in _columns("sessions"):
        op.drop_column("sessions", "article_version")
