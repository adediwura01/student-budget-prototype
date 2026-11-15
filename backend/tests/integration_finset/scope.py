"""An in-memory receipt registry, not a committed-data cleanup mechanism."""

from dataclasses import dataclass, field
from threading import RLock
from uuid import UUID, uuid4

from .policy import ROLES, SafetyError, TABLES, VIEW


@dataclass(frozen=True)
class Record:
    table: str
    id: UUID
    owner_id: UUID | None
    role: str
    values: dict = field(repr=False, compare=False)


class Scope:
    def __init__(self):
        self.token = uuid4().hex
        self._records = {}
        self._lock = RLock()

    def label(self, label="row"):
        if not label.replace("_", "").replace("-", "").isalnum() or len(label) > 16:
            raise SafetyError("Invalid synthetic fixture label.")
        return f"fsit_{self.token}_{uuid4().hex[:8]}_{label}"

    def email(self, label="user"):
        return self.label(label).lower() + "@example.invalid"

    def register(self, table, row, role):
        if table not in (*TABLES, VIEW) or role not in ROLES or not isinstance(row.get("id"), UUID):
            raise SafetyError("Unexpected synthetic insert receipt.")
        owner = row["id"] if table == "users" else row.get("owner_user_id", row.get("user_id"))
        with self._lock:
            if owner is not None and table != "users" and ("users", owner) not in self._records:
                raise SafetyError("A synthetic receipt has an unregistered parent.")
            visible = {name: value for name, value in row.items() if name not in ("password_hash", "token_hash")}
            record = Record(table, row["id"], owner, role, visible)
            existing = self._records.get((table, record.id))
            if existing is not None:
                raise SafetyError("An insert attempted to adopt an existing receipt.")
            self._records[(table, record.id)] = record
            return record

    def require(self, record):
        if not isinstance(record, Record):
            raise SafetyError("An exact registered record is required.")
        with self._lock:
            found = self._records.get((record.table, record.id))
            if found is None or (found.owner_id, found.role) != (record.owner_id, record.role):
                raise SafetyError("Unknown, cross-scope, or rebound synthetic record.")
            return found

    def records(self, table=None):
        with self._lock:
            return tuple(record for record in self._records.values() if table is None or record.table == table)


def validate_cleanup_scope(scope, table, ids):
    """Validate exact receipts for scoped DELETE/rollback checks; never execute cleanup."""
    if table not in (*TABLES, VIEW):
        raise SafetyError("Unapproved cleanup table.")
    ids = tuple(ids)
    if not ids or any(not isinstance(value, UUID) for value in ids) or len(set(ids)) != len(ids):
        raise SafetyError("Cleanup requires a nonempty, unique UUID allowlist.")
    records = {record.id: record for record in scope.records(table)}
    if not set(ids) <= set(records):
        raise SafetyError("Cleanup may not adopt unknown records or use broad selectors.")
    return tuple(scope.require(records[value]) for value in ids)
