"""Optional tracking limits with explicit, half-open calendar windows."""

import sqlalchemy as sa

from ..extensions import db


class BudgetLimit(db.Model):
    __tablename__ = "budget_limits"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_budget_limits_user", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    budget_id = sa.Column(sa.Uuid(as_uuid=True), nullable=False)
    period_type = sa.Column(sa.String(6), nullable=False)
    start_date = sa.Column(sa.Date, nullable=False)
    end_date = sa.Column(sa.Date, nullable=False)
    week_start_day = sa.Column(sa.SmallInteger, nullable=True)
    limit_kobo = sa.Column(sa.BigInteger, nullable=False)
    archived_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    version = sa.Column(sa.Integer, nullable=False, server_default=sa.text("1"))
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_budget_limits", deferrable=False),
        sa.ForeignKeyConstraint(
            ["user_id", "budget_id"], ["monthly_budgets.user_id", "monthly_budgets.id"],
            name="fk_budget_limits_owned_budget", ondelete="RESTRICT", onupdate="RESTRICT",
            deferrable=False, match="SIMPLE",
        ),
        sa.UniqueConstraint(
            "user_id", "budget_id", "id", name="uq_budget_limits_user_budget_id", deferrable=False,
        ),
        sa.CheckConstraint("period_type IN ('daily', 'weekly')", name="ck_budget_limits_period_type"),
        sa.CheckConstraint("isfinite(start_date)", name="ck_budget_limits_start_date_finite"),
        sa.CheckConstraint("isfinite(end_date)", name="ck_budget_limits_end_date_finite"),
        sa.CheckConstraint("end_date > start_date", name="ck_budget_limits_date_order"),
        sa.CheckConstraint(
            "date_trunc('month', CAST(start_date AS timestamp)) = "
            "date_trunc('month', CAST(end_date - 1 AS timestamp))",
            name="ck_budget_limits_single_month",
        ),
        sa.CheckConstraint(
            "(period_type = 'daily' AND week_start_day IS NULL AND end_date = start_date + 1) OR "
            "(period_type = 'weekly' AND week_start_day IS NOT NULL AND week_start_day IN (1, 7) "
            "AND end_date - start_date BETWEEN 1 AND 7 "
            "AND (EXTRACT(ISODOW FROM start_date) = week_start_day OR EXTRACT(DAY FROM start_date) = 1) "
            "AND (EXTRACT(ISODOW FROM end_date) = week_start_day OR EXTRACT(DAY FROM end_date) = 1))",
            name="ck_budget_limits_window_shape",
        ),
        sa.CheckConstraint("limit_kobo >= 1", name="ck_budget_limits_amount_positive"),
        sa.CheckConstraint(
            "archived_at IS NULL OR isfinite(archived_at)", name="ck_budget_limits_archived_at_finite",
        ),
        sa.CheckConstraint("version >= 1", name="ck_budget_limits_version_positive"),
        sa.CheckConstraint("isfinite(created_at)", name="ck_budget_limits_created_at_finite"),
        sa.CheckConstraint("isfinite(updated_at)", name="ck_budget_limits_updated_at_finite"),
        sa.CheckConstraint("updated_at >= created_at", name="ck_budget_limits_update_order"),
        sa.Index(
            "uq_budget_limits_active_start", budget_id, period_type, start_date,
            unique=True, postgresql_where=archived_at.is_(None),
        ),
    )

    user = db.relationship(
        "User", back_populates="budget_limits", foreign_keys=[user_id], viewonly=True, cascade="",
    )
    budget = db.relationship(
        "MonthlyBudget", back_populates="limits", viewonly=True, cascade="",
        primaryjoin="and_(BudgetLimit.user_id == MonthlyBudget.user_id, BudgetLimit.budget_id == MonthlyBudget.id)",
        foreign_keys=[user_id, budget_id],
    )
    alerts = db.relationship(
        "BudgetAlert", back_populates="limit", viewonly=True, cascade="",
        primaryjoin="and_(BudgetLimit.user_id == BudgetAlert.user_id, BudgetLimit.budget_id == BudgetAlert.budget_id, BudgetLimit.id == BudgetAlert.budget_limit_id)",
        foreign_keys="[BudgetAlert.user_id, BudgetAlert.budget_id, BudgetAlert.budget_limit_id]",
    )
