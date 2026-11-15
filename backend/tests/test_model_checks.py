"""Freeze approved row-local CHECK expressions without executing SQL.

Expectations translate docs/database-schema-design.md sections 3.2-3.3 and
4.1-4.9, independently of model metadata. Do not regenerate them from models.
Migration-only guards and service policies remain outside these tests.
"""

import re

import pytest
import sqlalchemy as sa

from app.models import (
    AuthToken,
    BudgetAlert,
    BudgetLimit,
    Category,
    LoginSession,
    MonthlyBudget,
    Plan,
    Transaction,
    User,
)


EXPECTED_CHECKS = {
    User: {
        "ck_users_full_name_nonempty": "char_length(btrim(full_name)) > 0",
        "ck_users_email_normalized": "email = lower(btrim(email)) AND char_length(email) > 0",
        "ck_users_password_hash_length": "char_length(password_hash) BETWEEN 1 AND 1024",
        "ck_users_credential_version_positive": "credential_version >= 1",
        "ck_users_appearance": "appearance IN ('light', 'dark', 'system')",
        "ck_users_currency": "currency = 'NGN'",
        "ck_users_date_format": "date_format IN ('DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD')",
        "ck_users_week_start_day": "week_start_day IN (1, 7)",
        "ck_users_email_verified_at_finite": (
            "email_verified_at IS NULL OR isfinite(email_verified_at)"
        ),
        "ck_users_verification_order": (
            "email_verified_at IS NULL OR email_verified_at >= created_at"
        ),
        "ck_users_last_login_finite": (
            "last_successful_login_at IS NULL OR isfinite(last_successful_login_at)"
        ),
        "ck_users_created_at_finite": "isfinite(created_at)",
        "ck_users_updated_at_finite": "isfinite(updated_at)",
        "ck_users_update_order": "updated_at >= created_at",
    },
    Category: {
        "ck_categories_name_nonempty": "char_length(btrim(name)) > 0",
        "ck_categories_type": "category_type IN ('income', 'expense')",
        "ck_categories_archived_at_finite": "archived_at IS NULL OR isfinite(archived_at)",
        "ck_categories_created_at_finite": "isfinite(created_at)",
        "ck_categories_updated_at_finite": "isfinite(updated_at)",
        "ck_categories_update_order": "updated_at >= created_at",
    },
    Transaction: {
        "ck_transactions_type": "transaction_type IN ('income', 'expense')",
        "ck_transactions_amount_positive": "amount_kobo >= 1",
        "ck_transactions_date_finite": "isfinite(transaction_date)",
        "ck_transactions_expense_category": (
            "transaction_type <> 'expense' OR category_id IS NOT NULL"
        ),
        "ck_transactions_income_source": (
            "transaction_type <> 'income' OR "
            "(source IS NOT NULL AND char_length(btrim(source)) > 0)"
        ),
        "ck_transactions_version_positive": "version >= 1",
        "ck_transactions_deleted_at_finite": "deleted_at IS NULL OR isfinite(deleted_at)",
        "ck_transactions_recoverable_until_finite": (
            "recoverable_until IS NULL OR isfinite(recoverable_until)"
        ),
        "ck_transactions_recovery_state": (
            "(deleted_at IS NULL AND recoverable_until IS NULL) OR "
            "(deleted_at IS NOT NULL AND recoverable_until IS NOT NULL "
            "AND deleted_at >= created_at AND recoverable_until > deleted_at)"
        ),
        "ck_transactions_created_at_finite": "isfinite(created_at)",
        "ck_transactions_updated_at_finite": "isfinite(updated_at)",
        "ck_transactions_update_order": "updated_at >= created_at",
    },
    Plan: {
        "ck_plans_type": "plan_type IN ('income', 'expense')",
        "ck_plans_expected_amount_positive": "expected_amount_kobo >= 1",
        "ck_plans_expected_date_finite": "isfinite(expected_date)",
        "ck_plans_expense_category": "plan_type <> 'expense' OR category_id IS NOT NULL",
        "ck_plans_income_source": (
            "plan_type <> 'income' OR (source IS NOT NULL AND char_length(btrim(source)) > 0)"
        ),
        "ck_plans_status": "status IN ('pending', 'completed', 'cancelled')",
        "ck_plans_completed_at_finite": "completed_at IS NULL OR isfinite(completed_at)",
        "ck_plans_completion_state": (
            "(status = 'completed' AND completed_at IS NOT NULL AND completed_at >= created_at) OR "
            "(status IN ('pending', 'cancelled') AND completed_at IS NULL)"
        ),
        "ck_plans_result_generation_range": "result_generation BETWEEN 0 AND 2",
        "ck_plans_version_positive": "version >= 1",
        "ck_plans_created_at_finite": "isfinite(created_at)",
        "ck_plans_updated_at_finite": "isfinite(updated_at)",
        "ck_plans_update_order": "updated_at >= created_at",
    },
    MonthlyBudget: {
        "ck_monthly_budgets_month_finite": "isfinite(month_start)",
        "ck_monthly_budgets_month_start": "EXTRACT(DAY FROM month_start) = 1",
        "ck_monthly_budgets_allocation_positive": "allocation_kobo >= 1",
        "ck_monthly_budgets_warning_percent": "warning_percent = 80",
        "ck_monthly_budgets_archived_at_finite": "archived_at IS NULL OR isfinite(archived_at)",
        "ck_monthly_budgets_version_positive": "version >= 1",
        "ck_monthly_budgets_created_at_finite": "isfinite(created_at)",
        "ck_monthly_budgets_updated_at_finite": "isfinite(updated_at)",
        "ck_monthly_budgets_update_order": "updated_at >= created_at",
    },
    BudgetLimit: {
        "ck_budget_limits_period_type": "period_type IN ('daily', 'weekly')",
        "ck_budget_limits_start_date_finite": "isfinite(start_date)",
        "ck_budget_limits_end_date_finite": "isfinite(end_date)",
        "ck_budget_limits_date_order": "end_date > start_date",
        "ck_budget_limits_single_month": (
            "date_trunc('month', CAST(start_date AS timestamp)) = "
            "date_trunc('month', CAST(end_date - 1 AS timestamp))"
        ),
        "ck_budget_limits_window_shape": (
            "(period_type = 'daily' AND week_start_day IS NULL AND end_date = start_date + 1) OR "
            "(period_type = 'weekly' AND week_start_day IS NOT NULL AND week_start_day IN (1, 7) "
            "AND end_date - start_date BETWEEN 1 AND 7 "
            "AND (EXTRACT(ISODOW FROM start_date) = week_start_day "
            "OR EXTRACT(DAY FROM start_date) = 1) "
            "AND (EXTRACT(ISODOW FROM end_date) = week_start_day "
            "OR EXTRACT(DAY FROM end_date) = 1))"
        ),
        "ck_budget_limits_amount_positive": "limit_kobo >= 1",
        "ck_budget_limits_archived_at_finite": "archived_at IS NULL OR isfinite(archived_at)",
        "ck_budget_limits_version_positive": "version >= 1",
        "ck_budget_limits_created_at_finite": "isfinite(created_at)",
        "ck_budget_limits_updated_at_finite": "isfinite(updated_at)",
        "ck_budget_limits_update_order": "updated_at >= created_at",
    },
    BudgetAlert: {
        "ck_budget_alerts_type": "alert_type IN ('warning', 'over_budget')",
        "ck_budget_alerts_period_start_finite": "isfinite(period_start)",
        "ck_budget_alerts_period_end_finite": "isfinite(period_end)",
        "ck_budget_alerts_period_order": "period_end > period_start",
        "ck_budget_alerts_threshold": (
            "(alert_type = 'warning' AND threshold_percent = 80) OR "
            "(alert_type = 'over_budget' AND threshold_percent = 100)"
        ),
        "ck_budget_alerts_created_at_finite": "isfinite(created_at)",
        "ck_budget_alerts_read_at_finite": "read_at IS NULL OR isfinite(read_at)",
        "ck_budget_alerts_read_order": "read_at IS NULL OR read_at >= created_at",
        "ck_budget_alerts_resolved_at_finite": "resolved_at IS NULL OR isfinite(resolved_at)",
        "ck_budget_alerts_resolution_order": "resolved_at IS NULL OR resolved_at >= created_at",
    },
    LoginSession: {
        "ck_login_sessions_hash_length": "octet_length(token_hash) = 32",
        "ck_login_sessions_credential_version": "credential_version >= 1",
        "ck_login_sessions_created_at_finite": "isfinite(created_at)",
        "ck_login_sessions_last_activity_finite": "isfinite(last_activity_at)",
        "ck_login_sessions_idle_expiry_finite": "isfinite(idle_expires_at)",
        "ck_login_sessions_expiry_finite": "isfinite(expires_at)",
        "ck_login_sessions_revoked_at_finite": "revoked_at IS NULL OR isfinite(revoked_at)",
        "ck_login_sessions_activity_order": "last_activity_at >= created_at",
        "ck_login_sessions_idle_order": (
            "idle_expires_at > last_activity_at AND idle_expires_at <= expires_at"
        ),
        "ck_login_sessions_expiry_order": "expires_at > created_at",
        "ck_login_sessions_revocation_order": "revoked_at IS NULL OR revoked_at >= created_at",
    },
    AuthToken: {
        "ck_auth_tokens_hash_length": "octet_length(token_hash) = 32",
        "ck_auth_tokens_purpose": "purpose IN ('verify_email', 'reset_password', 'change_email')",
        "ck_auth_tokens_target_email": (
            "(purpose IN ('verify_email', 'change_email') AND target_email IS NOT NULL "
            "AND char_length(target_email) > 0 AND target_email = lower(btrim(target_email))) OR "
            "(purpose = 'reset_password' AND target_email IS NULL)"
        ),
        "ck_auth_tokens_credential_version": "credential_version >= 1",
        "ck_auth_tokens_created_at_finite": "isfinite(created_at)",
        "ck_auth_tokens_expiry_finite": "isfinite(expires_at)",
        "ck_auth_tokens_expiry_order": "expires_at > created_at",
        "ck_auth_tokens_consumed_at_finite": "consumed_at IS NULL OR isfinite(consumed_at)",
        "ck_auth_tokens_consumption_order": "consumed_at IS NULL OR consumed_at >= created_at",
        "ck_auth_tokens_revoked_at_finite": "revoked_at IS NULL OR isfinite(revoked_at)",
        "ck_auth_tokens_revocation_order": "revoked_at IS NULL OR revoked_at >= created_at",
        "ck_auth_tokens_terminal_state": "consumed_at IS NULL OR revoked_at IS NULL",
    },
}


def normalize_sql(expression):
    """Ignore layout, not quoted content, grouping, or multi-character operators."""
    return tuple(re.findall(
        r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|<>|<=|>=|!=|\w+|[^\s]",
        expression,
    ))


def declared_checks(model):
    table = model.__table__
    # Include column-local checks so an extra cap cannot hide outside table.constraints.
    constraints = [
        constraint
        for parent in (table, *table.columns)
        for constraint in parent.constraints
        if isinstance(constraint, sa.CheckConstraint)
    ]
    checks = {constraint.name: constraint for constraint in constraints}
    assert len(checks) == len(constraints), f"{table.name}: duplicate CHECK names"
    return checks


@pytest.mark.parametrize("model", EXPECTED_CHECKS, ids=lambda model: model.__name__)
def test_check_catalogue_has_no_missing_or_extra_constraints(model):
    # Exact inventories also reject new hardcoded caps or time-dependent row policies.
    assert declared_checks(model).keys() == EXPECTED_CHECKS[model].keys()


@pytest.mark.parametrize("model,check_name,expected", [
    pytest.param(model, name, expression, id=name)
    for model, checks in EXPECTED_CHECKS.items()
    for name, expression in checks.items()
])
def test_full_check_expression_matches_approved_schema(model, check_name, expected):
    constraint = declared_checks(model)[check_name]
    assert normalize_sql(str(constraint.sqltext)) == normalize_sql(expected)


@pytest.mark.parametrize("model,column_name", [
    pytest.param(Transaction, "amount_kobo", id="transaction-money"),
    pytest.param(Plan, "expected_amount_kobo", id="plan-money"),
    pytest.param(MonthlyBudget, "allocation_kobo", id="monthly-allocation"),
    pytest.param(BudgetLimit, "limit_kobo", id="tracking-limit"),
])
def test_positive_money_checks_use_required_integer_storage(model, column_name):
    column = model.__table__.c[column_name]
    assert isinstance(column.type, sa.BigInteger)
    assert column.nullable is False


@pytest.mark.parametrize("original,changed,equivalent", [
    pytest.param(
        "week_start_day IN (1, 7)", " \nweek_start_day\tIN( 1,7 )\r\n", True,
        id="layout-only",
    ),
    pytest.param(
        "currency = 'NGN'", "currency = ' NGN'", False,
        id="literal-whitespace",
    ),
    pytest.param(
        "name = 'a''  b'", "name = 'a'' b'", False,
        id="escaped-literal-whitespace",
    ),
    pytest.param(
        'isfinite("created at")', 'isfinite("created  at")', False,
        id="quoted-identifier-whitespace",
    ),
    pytest.param(
        "amount_kobo >= 1", "amount_kobo > = 1", False,
        id="split-operator",
    ),
    pytest.param(
        "consumed_at IS NULL OR revoked_at IS NULL",
        "consumed_at IS NULL OR revoked_at IS NULL OR TRUE", False,
        id="added-bypass",
    ),
])
def test_sql_normalization_only_ignores_harmless_whitespace(original, changed, equivalent):
    assert (normalize_sql(original) == normalize_sql(changed)) is equivalent
