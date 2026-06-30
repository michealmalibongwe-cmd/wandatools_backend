"""add PWA tables: push_subscriptions and pwa_events

Revision ID: 0002_add_pwa_tables
Revises: 0001_add_missing_cols
Create Date: 2026-06-30

Adds two tables required for PWA support:
  push_subscriptions — Web Push API subscription per user/device
  pwa_events         — service-worker and PWA lifecycle event log
"""

from alembic import op
import sqlalchemy as sa

revision     = "0002_add_pwa_tables"
down_revision = "0001_add_missing_cols"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── push_subscriptions ───────────────────────────────────
    op.create_table(
        "push_subscriptions",
        sa.Column("id",         sa.Integer(),      nullable=False, autoincrement=True),
        sa.Column("user_id",    sa.Integer(),      nullable=False),
        sa.Column("endpoint",   sa.String(2000),   nullable=False),
        sa.Column("p256dh",     sa.String(500),    nullable=False),
        sa.Column("auth",       sa.String(200),    nullable=False),
        sa.Column("user_agent", sa.String(500),    nullable=True),
        sa.Column("created_at", sa.DateTime(),     nullable=False, server_default=sa.text("now()")),
        sa.Column("last_used",  sa.DateTime(),     nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_push_subscriptions_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )
    op.create_index("ix_push_subscriptions_id",      "push_subscriptions", ["id"],      unique=False)
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"], unique=False)

    # ── pwa_events ───────────────────────────────────────────
    op.create_table(
        "pwa_events",
        sa.Column("id",         sa.Integer(),    nullable=False, autoincrement=True),
        sa.Column("user_id",    sa.Integer(),    nullable=True),
        sa.Column("event_type", sa.String(50),   nullable=False),
        sa.Column("data",       sa.JSON(),       nullable=True),
        sa.Column("ip_address", sa.String(45),   nullable=True),
        sa.Column("user_agent", sa.String(500),  nullable=True),
        sa.Column("created_at", sa.DateTime(),   nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_pwa_events_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pwa_events_id",         "pwa_events", ["id"],         unique=False)
    op.create_index("ix_pwa_events_user_id",    "pwa_events", ["user_id"],    unique=False)
    op.create_index("ix_pwa_events_event_type", "pwa_events", ["event_type"], unique=False)
    op.create_index("ix_pwa_events_created_at", "pwa_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pwa_events_created_at",    table_name="pwa_events")
    op.drop_index("ix_pwa_events_event_type",    table_name="pwa_events")
    op.drop_index("ix_pwa_events_user_id",       table_name="pwa_events")
    op.drop_index("ix_pwa_events_id",            table_name="pwa_events")
    op.drop_table("pwa_events")

    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_index("ix_push_subscriptions_id",      table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
