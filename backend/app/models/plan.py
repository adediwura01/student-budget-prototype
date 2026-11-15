"""Expected money and the declared result-generation bounds, not a recording service."""

import sqlalchemy as sa

from ..extensions import db


class Plan(db.Model):
    __tablename__ = "plans"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_plans_user", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    plan_type = sa.Column(sa.String(7), nullable=False)
    expected_amount_kobo = sa.Column(sa.BigInteger, nullable=False)
    expected_date = sa.Column(sa.Date, nullable=False)
    category_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("categories.id", name="fk_plans_category", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=True,
    )
    source = sa.Column(sa.String(120), nullable=True)
    description = sa.Column(sa.String(1000), nullable=True)
    status = sa.Column(sa.String(9), nullable=False, server_default=sa.text("'pending'"))
    completed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    result_generation = sa.Column(sa.SmallInteger, nullable=False, server_default=sa.text("0"))
    version = sa.Column(sa.Integer, nullable=False, server_default=sa.text("1"))
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_plans", deferrable=False),
        sa.UniqueConstraint("user_id", "id", "plan_type", name="uq_plans_user_id_type", deferrable=False),
        sa.CheckConstraint("plan_type IN ('income', 'expense')", name="ck_plans_type"),
        sa.CheckConstraint("expected_amount_kobo >= 1", name="ck_plans_expected_amount_positive"),
        sa.CheckConstraint("isfinite(expected_date)", name="ck_plans_expected_date_finite"),
        sa.CheckConstraint("plan_type <> 'expense' OR category_id IS NOT NULL", name="ck_plans_expense_category"),
        sa.CheckConstraint(
            "plan_type <> 'income' OR (source IS NOT NULL AND char_length(btrim(source)) > 0)",
            name="ck_plans_income_source",
        ),
        sa.CheckConstraint("status IN ('pending', 'completed', 'cancelled')", name="ck_plans_status"),
        sa.CheckConstraint(
            "completed_at IS NULL OR isfinite(completed_at)", name="ck_plans_completed_at_finite",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND completed_at IS NOT NULL AND completed_at >= created_at) OR "
            "(status IN ('pending', 'cancelled') AND completed_at IS NULL)",
            name="ck_plans_completion_state",
        ),
        sa.CheckConstraint("result_generation BETWEEN 0 AND 2", name="ck_plans_result_generation_range"),
        sa.CheckConstraint("version >= 1", name="ck_plans_version_positive"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_plans_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_plans_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_plans_update_order"),
        sa.Index("ix_plans_user_status_date", user_id, status, expected_date, id),
    )

    user = db.relationship(
        "User", back_populates="plans", foreign_keys=[user_id], viewonly=True, cascade="",
    )
    category = db.relationship(
        "Category", back_populates="plans", foreign_keys=[category_id], viewonly=True, cascade="",
    )
    transaction = db.relationship(
        "Transaction", back_populates="plan", uselist=False, viewonly=True, cascade="",
        primaryjoin=(
            "and_(Plan.user_id == Transaction.user_id, Plan.id == Transaction.plan_id, "
            "Plan.plan_type == Transaction.transaction_type)"
        ),
        foreign_keys="[Transaction.user_id, Transaction.plan_id, Transaction.transaction_type]",
    )
