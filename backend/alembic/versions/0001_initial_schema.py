"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-13 14:01:28.352993

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Needed so the exclusion constraint can combine `=` on a uuid with `&&` on a range in one
    # GiST index.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "resources",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), server_default="America/Mexico_City", nullable=False),
        sa.Column("slot_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint("slot_minutes > 0", name=op.f("ck_resources_slot_minutes_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resources")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), server_default="user", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'admin')", name=op.f("ck_users_role_valid")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "blackouts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("during", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name=op.f("fk_blackouts_resource_id_resources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blackouts")),
    )
    op.create_index(op.f("ix_blackouts_resource_id"), "blackouts", ["resource_id"], unique=False)
    op.create_table(
        "opening_hours",
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.CheckConstraint(
            "close_time > open_time", name=op.f("ck_opening_hours_closes_after_opening")
        ),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_opening_hours_weekday_valid")),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name=op.f("fk_opening_hours_resource_id_resources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("resource_id", "weekday", name=op.f("pk_opening_hours")),
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("during", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("status", sa.Text(), server_default="confirmed", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        postgresql.ExcludeConstraint(
            (sa.column("resource_id"), "="),
            (sa.column("during"), "&&"),
            where=sa.text("status = 'confirmed'"),
            using="gist",
            name="no_overlapping_confirmed",
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'cancelled')", name=op.f("ck_reservations_status_valid")
        ),
        sa.CheckConstraint(
            "NOT isempty(during) AND lower_inc(during) AND NOT upper_inc(during)"
            " AND NOT lower_inf(during) AND NOT upper_inf(during)",
            name=op.f("ck_reservations_during_bounded_half_open"),
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name=op.f("fk_reservations_resource_id_resources"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_reservations_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservations")),
    )
    op.create_index(op.f("ix_reservations_user_id"), "reservations", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema (btree_gist is left installed: it may be shared with other schemas)."""
    op.drop_index(op.f("ix_reservations_user_id"), table_name="reservations")
    op.drop_table("reservations")
    op.drop_table("opening_hours")
    op.drop_index(op.f("ix_blackouts_resource_id"), table_name="blackouts")
    op.drop_table("blackouts")
    op.drop_table("users")
    op.drop_table("resources")
