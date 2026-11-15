"""Notification scope and read state; no cached financial totals."""

import sqlalchemy as sa

from ..extensions import db


class BudgetAlert(db.Model):
    __tablename__ = "budget_alerts"

    id = sa.Column(
        sa.Uuid(as_uuid=True), primary_key=True, nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id = sa.Column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_budget_alerts_user", ondelete="RESTRICT",
                      onupdate="RESTRICT", deferrable=False, match="SIMPLE"),
        nullable=False,
    )
    budget_id = sa.Column(sa.Uuid(as_uuid=True), nullable=False)
    budget_limit_id = sa.Column(sa.Uuid(as_uuid=True), nullable=True)
    alert_type = sa.Column(sa.String(11), nullable=False)
    period_start = sa.Column(sa.Date, nullable=False)
    period_end = sa.Column(sa.Date, nullable=False)
    threshold_percent = sa.Column(sa.SmallInteger, nullable=False)
    created_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    read_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    resolved_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_budget_alerts", deferrable=False),
        sa.ForeignKeyConstraint(
            ["user_id", "budget_id"], ["monthly_budgets.user_id", "monthly_budgets.id"],
            name="fk_budget_alerts_owned_budget", ondelete="RESTRICT", onupdate="RESTRICT",
            deferrable=False, match="SIMPLE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "budget_id", "budget_limit_id"],
            ["budget_limits.user_id", "budget_limits.budget_id", "budget_limits.id"],
            name="fk_budget_alerts_owned_limit", ondelete="RESTRICT", onupdate="RESTRICT",
            deferrable=False, match="SIMPLE",
        ),
        sa.CheckConstraint("alert_type IN ('warning', 'over_budget')", name="ck_budget_alerts_type"),
        sa.CheckConstraint("isfinite(period_start)", name="ck_budget_alerts_period_start_finite"),
        sa.CheckConstraint("isfinite(period_end)", name="ck_budget_alerts_period_end_finite"),
        sa.CheckConstraint("period_end > period_start", name="ck_budget_alerts_period_order"),
        sa.CheckConstraint(
            "(alert_type = 'warning' AND threshold_percent = 80) OR "
            "(alert_type = 'over_budget' AND threshold_percent = 100)",
            name="ck_budget_alerts_threshold",
        ),
        sa.CheckConstraint("isfinite(created_at)", name="ck_budget_alerts_created_at_finite"),
        sa.CheckConstraint("read_at IS NULL OR isfinite(read_at)", name="ck_budget_alerts_read_at_finite"),
        sa.CheckConstraint("read_at IS NULL OR read_at >= created_at", name="ck_budget_alerts_read_order"),
        sa.CheckConstraint(
            "resolved_at IS NULL OR isfinite(resolved_at)", name="ck_budget_alerts_resolved_at_finite",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= created_at", name="ck_budget_alerts_resolution_order",
        ),
        sa.Index(
            "uq_budget_alerts_active_scope", budget_id, budget_limit_id, alert_type,
            unique=True, postgresql_where=resolved_at.is_(None),
            postgresql_nulls_not_distinct=True,
        ),
        sa.Index("ix_budget_alerts_user_created", user_id, created_at.desc(), id),
    )

    user = db.relationship(
        "User", back_populates="budget_alerts", foreign_keys=[user_id], viewonly=True, cascade="",
    )
    budget = db.relationship(
        "MonthlyBudget", back_populates="alerts", viewonly=True, cascade="",
        primaryjoin="and_(BudgetAlert.user_id == MonthlyBudget.user_id, BudgetAlert.budget_id == MonthlyBudget.id)",
        foreign_keys=[user_id, budget_id],
    )
    limit = db.relationship(
        "BudgetLimit", back_populates="alerts", viewonly=True, cascade="",
        primaryjoin="and_(BudgetAlert.user_id == BudgetLimit.user_id, BudgetAlert.budget_id == BudgetLimit.budget_id, BudgetAlert.budget_limit_id == BudgetLimit.id)",
        foreign_keys=[user_id, budget_id, budget_limit_id],
    )
