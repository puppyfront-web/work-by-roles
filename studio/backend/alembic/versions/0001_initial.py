"""工作室表与按工作区拆分的审计链。

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])

    op.create_table(
        "provider_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_provider_keys_workspace_id", "provider_keys", ["workspace_id"])

    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("template_name", sa.String(128), nullable=True),
        sa.Column("contracts", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_teams_workspace_id", "teams", ["workspace_id"])

    op.create_table(
        "audit_chains",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("hash_alg", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("token_budget", sa.Integer(), nullable=True),
        sa.Column("input_price", sa.Float(), nullable=True),
        sa.Column("output_price", sa.Float(), nullable=True),
        sa.Column("cached_input_price", sa.Float(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_total", sa.Float(), nullable=False),
        sa.Column("cost_baseline", sa.Float(), nullable=False),
        sa.Column("cost_savings", sa.Float(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_key_id"], ["provider_keys.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_runs_workspace_id", "runs", ["workspace_id"])
    op.create_index("ix_runs_team_id", "runs", ["team_id"])

    op.create_table(
        "audit_events",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("prev_hash", sa.Text(), nullable=False),
        sa.Column("event_hash", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("ts", sa.Double(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=True),
        sa.Column("event_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["audit_chains.workspace_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "seq"),
    )
    op.create_index("ix_audit_events_run", "audit_events", ["workspace_id", "run_id"])
    op.create_index("ix_audit_events_session", "audit_events", ["workspace_id", "session_id"])
    op.create_index("ix_audit_events_trace", "audit_events", ["workspace_id", "trace_id"])
    op.create_index("ix_audit_events_type_ts", "audit_events", ["workspace_id", "event_type", "ts"])
    op.create_index("ix_audit_events_ts", "audit_events", ["workspace_id", "ts"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("runs")
    op.drop_table("audit_chains")
    op.drop_table("teams")
    op.drop_table("provider_keys")
    op.drop_table("workspaces")
    op.drop_table("users")
