"""Add durable agent runs and public event timeline."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260822_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Older deployments use Base.metadata.create_all and may have created these
    # tables before Alembic was introduced. In that case this revision safely adopts them.
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "agent_runs" not in existing_tables:
        op.create_table(
            "agent_runs",
            sa.Column("run_id", sa.String(length=36), primary_key=True),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("task_type", sa.String(length=32), nullable=False),
            sa.Column("document_type", sa.String(length=32), nullable=False),
            sa.Column("model_profile_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column("current_stage", sa.String(length=64), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("request_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("state_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("draft_content", sa.Text(), nullable=False, server_default=""),
            sa.Column("final_article", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("references_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("issues_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("last_event_seq", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        )
        op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
        op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    if "agent_events" not in existing_tables:
        op.create_table(
            "agent_events",
            sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("stage", sa.String(length=64), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"], ondelete="CASCADE"),
            sa.UniqueConstraint("run_id", "seq", name="uq_agent_event_run_seq"),
        )
        op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "agent_events" in existing_tables:
        op.drop_index("ix_agent_events_run_id", table_name="agent_events")
        op.drop_table("agent_events")
    if "agent_runs" in existing_tables:
        op.drop_index("ix_agent_runs_status", table_name="agent_runs")
        op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
        op.drop_table("agent_runs")
