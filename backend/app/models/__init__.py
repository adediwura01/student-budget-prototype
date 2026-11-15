"""Register schema metadata only; migration-only guards are documented separately.

Relationships are read-only navigation, including archived/deleted records.
Future services must assign scoped foreign keys and filter actual-money queries.
See docs/model-implementation-notes.md for deferred database enforcement.
"""

from .user import User
from .category import Category
from .plan import Plan
from .transaction import Transaction
from .monthly_budget import MonthlyBudget
from .budget_limit import BudgetLimit
from .budget_alert import BudgetAlert
from .login_session import LoginSession
from .auth_token import AuthToken


__all__ = [
    "User",
    "Category",
    "Transaction",
    "Plan",
    "MonthlyBudget",
    "BudgetLimit",
    "BudgetAlert",
    "LoginSession",
    "AuthToken",
]
