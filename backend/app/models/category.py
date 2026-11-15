"""Shared and user-owned category declarations; access guards need migrations."""

import sqlalchemy as sa

from ..extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    owner_user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_categories_owner", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=True,
    )
    name = sa.Column(sa.String(80), nullable=False)
    category_type = sa.Column(sa.String(7), nullable=False)
    archived_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_categories", deferrable=False),
        sa.CheckConstraint("char_length(btrim(name)) > 0", name="ck_categories_name_nonempty"),
        sa.CheckConstraint("category_type IN ('income', 'expense')", name="ck_categories_type"),
        sa.CheckConstraint(
            "archived_at IS NULL OR isfinite(archived_at)", name="ck_categories_archived_at_finite",
        ),
        sa.CheckConstraint("isfinite(created_at)", name="ck_categories_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_categories_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_categories_update_order"),
        sa.Index(
            "uq_categories_system_name_type", sa.func.lower(sa.func.btrim(name)), category_type,
            unique=True, postgresql_where=owner_user_id.is_(None),
        ),
        sa.Index(
            "uq_categories_custom_owner_name", owner_user_id, sa.func.lower(sa.func.btrim(name)),
            unique=True, postgresql_where=owner_user_id.is_not(None),
        ),
    )

    owner = db.relationship(
        "User", back_populates="categories", foreign_keys=[owner_user_id], viewonly=True, cascade="",
    )
    transactions = db.relationship(
        "Transaction", back_populates="category", foreign_keys="Transaction.category_id",
        viewonly=True, cascade="",
    )
    plans = db.relationship(
        "Plan", back_populates="category", foreign_keys="Plan.category_id", viewonly=True, cascade="",
    )
    monthly_budgets = db.relationship(
        "MonthlyBudget", back_populates="category", foreign_keys="MonthlyBudget.category_id",
        viewonly=True, cascade="",
    )
