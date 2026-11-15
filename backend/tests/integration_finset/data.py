"""Synthetic INSERT helpers, not implementations of application financial policy."""

from datetime import date, timedelta
from secrets import token_bytes

from .policy import VIEW


class Data:
    def __init__(self, session):
        self.session = session
        self.case = session.case

    def user(self, **overrides):
        values = dict(full_name=self.case.label("student"), email=self.case.email(),
                      password_hash="synthetic-unusable-password-hash")
        return self.session.insert("users", **(values | overrides))

    def category(self, user, kind="expense", name=None, **overrides):
        values = dict(owner_user_id=user.id if user else None,
                      name=name or self.case.label("category"), category_type=kind)
        return self.session.insert("categories", **(values | overrides))

    def system_category(self, kind="expense", name=None, **overrides):
        values = dict(name=name or self.case.label("system"), category_type=kind)
        return self.session.insert(VIEW, **(values | overrides))

    def plan(self, user, kind="income", category=None, expected_amount=1000, **overrides):
        if category is None and kind == "expense":
            category = self.category(user)
        values = dict(user_id=user.id, plan_type=kind, expected_amount_kobo=expected_amount,
                      expected_date=date(2026, 11, 15), category_id=category.id if category else None,
                      source="synthetic allowance" if kind == "income" else None)
        return self.session.insert("plans", **(values | overrides))

    def transaction(self, user, kind="income", category=None, plan=None, amount=1000, **overrides):
        if category is None and kind == "expense":
            category = self.category(user)
        values = dict(user_id=user.id, transaction_type=kind, amount_kobo=amount,
                      transaction_date=date(2026, 11, 15), category_id=category.id if category else None,
                      source="synthetic allowance" if kind == "income" else None,
                      plan_id=plan.id if plan else None)
        return self.session.insert("transactions", **(values | overrides))

    def budget(self, user, category=None, month=None, allocation=50000, **overrides):
        category = category or self.category(user)
        values = dict(user_id=user.id, category_id=category.id,
                      month_start=month or date(2026, 11, 1), allocation_kobo=allocation)
        return self.session.insert("monthly_budgets", **(values | overrides))

    def limit(self, user, budget, kind="daily", start=None, end=None,
              week_start_day=None, amount=10000, **overrides):
        start = start or date(2026, 11, 2)
        values = dict(user_id=user.id, budget_id=budget.id, period_type=kind,
                      start_date=start, end_date=end or start + timedelta(days=7 if kind == "weekly" else 1),
                      week_start_day=(1 if week_start_day is None else week_start_day) if kind == "weekly" else week_start_day,
                      limit_kobo=amount)
        return self.session.insert("budget_limits", **(values | overrides))

    def alert(self, user, budget, limit=None, kind="warning", **overrides):
        start = budget.values["month_start"]
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
        values = dict(user_id=user.id, budget_id=budget.id,
                      budget_limit_id=limit.id if limit else None, alert_type=kind,
                      period_start=limit.values["start_date"] if limit else start,
                      period_end=limit.values["end_date"] if limit else end,
                      threshold_percent=80 if kind == "warning" else 100)
        return self.session.insert("budget_alerts", **(values | overrides))

    def login_session(self, user, **overrides):
        now = self.session.clock()
        values = dict(user_id=user.id, token_hash=token_bytes(32), credential_version=1,
                      idle_expires_at=now + timedelta(minutes=30), expires_at=now + timedelta(hours=8))
        return self.session.insert("login_sessions", **(values | overrides))

    def token(self, user, purpose="reset_password", **overrides):
        values = dict(user_id=user.id, token_hash=token_bytes(32), purpose=purpose,
                      target_email=user.values["email"] if purpose in ("verify_email", "change_email") else None,
                      credential_version=1, expires_at=self.session.clock() + timedelta(hours=1))
        return self.session.insert("auth_tokens", **(values | overrides))
