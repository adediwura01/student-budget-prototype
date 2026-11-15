"""The only live connector, with a rollback-only, exact-receipt DML facade."""

from contextlib import contextmanager
from datetime import datetime
from time import monotonic

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from .policy import (
    DATABASE, GROUPS, HOST, PORT, ROLES, TABLES, VIEW, SafetyError,
    load_credentials, safe_identifier, validate_identity,
)
from .scope import Record, Scope, validate_cleanup_scope
from .lifecycle import Deadline, Registry, cancel_handle, close_handle


# Captured before safety installs its permanent public-API connection blockers.
_CONNECT = psycopg.Connection.connect


def require_bounded_cancellation():
    __tracebackhide__ = True
    try:
        supported = psycopg.capabilities.has_cancel_safe()
    except Exception:
        raise SafetyError("Client cancellation capability could not be established.") from None
    if not supported:
        raise SafetyError("Runtime and built libpq 17+ cancellation support is required; legacy cancellation is prohibited.")


class DatabaseFailure(AssertionError):
    def __init__(self, error):
        self.sqlstate = getattr(error, "sqlstate", None)
        if not isinstance(self.sqlstate, str) or len(self.sqlstate) != 5:
            self.sqlstate = None
        self.constraint = safe_identifier(getattr(getattr(error, "diag", None), "constraint_name", None))
        super().__init__(f"PostgreSQL rejected the operation: SQLSTATE={self.sqlstate}, constraint={self.constraint}.")


def _authorize():
    __tracebackhide__ = True
    from .safety import execution_allowed
    if not execution_allowed():
        raise SafetyError("No reviewed, opted-in FinSet test is currently executing.")


def query(conn, statement, params=()):
    """Private trusted SQL path used by readiness and the scoped facade only."""
    __tracebackhide__ = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchall() if cursor.description is not None else []
    except psycopg.Error as error:
        raise DatabaseFailure(error) from None


def identity(conn, role, effective=None):
    __tracebackhide__ = True
    row = query(conn, """
        SELECT pg_catalog.current_database() AS database, session_user, current_user,
               pg_catalog.host(pg_catalog.inet_server_addr()) AS address,
               pg_catalog.inet_server_port() AS port,
               pg_catalog.current_setting('transaction_read_only') AS read_only
    """)[0]
    validate_identity(row, role, bool(conn.pgconn.used_password), effective=effective)
    return row


class ConnectionFactory:
    def __init__(self):
        __tracebackhide__ = True
        _authorize()
        require_bounded_cancellation()
        from .safety import register_secrets
        self._targets = load_credentials()
        register_secrets(target._password for target in self._targets.values())
        self._registry = Registry()
        self.ready = False
        self.report = None

    def __repr__(self):
        return "<FinSetConnectionFactory credentials=redacted>"

    @property
    def _closing(self):
        return self._registry.closing

    @property
    def _active(self):
        return {handle.connection.info.backend_pid: (handle.connection, handle.case)
                for handle in self._registry.snapshot() if not handle.connection.closed}

    def _open(self, role, case=None, *, phase="readiness", deadline=None):
        __tracebackhide__ = True
        import os
        _authorize()
        if role not in ROLES:
            raise SafetyError("Unapproved connection role.")
        ticket = self._registry.begin(role, case, phase)
        conn = None
        try:
            # Clear libpq defaults before supplying the complete pinned parameter set.
            for name in tuple(os.environ):
                if name.upper().startswith("PG"):
                    os.environ.pop(name, None)
            target = self._targets[role]
            timeout = 3 if deadline is None else max(1, min(3, int(deadline.left(3))))
            conn = _CONNECT(
                host=HOST, hostaddr=HOST, port=PORT, dbname=DATABASE,
                user=target.login, password=target._password, passfile=os.devnull,
                require_auth="scram-sha-256", connect_timeout=timeout,
                autocommit=True, row_factory=dict_row,
                application_name="finset_stage_a_" + role,
                options="-c default_transaction_read_only=on -c search_path=pg_catalog,pg_temp "
                        "-c statement_timeout=15000 -c lock_timeout=10000 "
                        "-c idle_in_transaction_session_timeout=30000",
            )
            _, allowed = self._registry.attach(ticket, conn)
            if not allowed:
                raise SafetyError("Connection setup raced resource shutdown; no operation is permitted.")
            row = identity(conn, role)
            if row["read_only"] != "on":
                raise SafetyError("New connections must initially be read-only.")
            return conn
        except (psycopg.Error, OSError):
            if conn is not None:
                self._close(conn, deadline=deadline)
            raise SafetyError("Dedicated connection or SCRAM authentication failed; details withheld.") from None
        except BaseException:
            if conn is not None:
                self._close(conn, deadline=deadline)
            raise
        finally:
            self._registry.finish_open(ticket)

    def _close(self, conn, *, deadline=None):
        __tracebackhide__ = True
        handle = self._registry.get(conn)
        try:
            close_handle(handle, deadline or Deadline(5))
        except (psycopg.Error, OSError):
            raise SafetyError("A test connection could not be closed; registry retained.") from None
        self._registry.remove_closed(handle)

    @contextmanager
    def _readiness_connection(self, role, *, case=None, phase="readiness", deadline=None):
        __tracebackhide__ = True
        conn = self._open(role, case, phase=phase, deadline=deadline)
        try:
            with conn.transaction(force_rollback=True):
                yield conn
        except psycopg.Error as error:
            raise DatabaseFailure(error) from None
        finally:
            self._close(conn, deadline=deadline)

    def check_readiness(self):
        __tracebackhide__ = True
        _authorize()
        from .readiness import check_readiness
        self.report = check_readiness(self)
        self.ready = True
        return self.report

    @contextmanager
    def rollback(self, role, case, *, readonly=False):
        __tracebackhide__ = True
        _authorize()
        if not self.ready or not isinstance(case, Scope):
            raise SafetyError("Readiness and a synthetic case scope are required.")
        if role == "migrator" and not readonly:
            raise SafetyError("The migrator is read-only in Stage A.")
        conn = self._open(role, case, phase="transaction")
        session = Session(self, conn, role, case, readonly)
        try:
            with conn.transaction(force_rollback=True):
                if not readonly:
                    query(conn, "SET TRANSACTION READ WRITE")
                yield session
                # A test which merely rolls back would otherwise never exercise deferred checks.
                session.check_constraints()
        except psycopg.Error as error:
            raise DatabaseFailure(error) from None
        finally:
            cleanup = Deadline(8)
            self._close(conn, deadline=cleanup)
            session._closed = True
            self._assert_absent(role, session._created, case=case, deadline=cleanup)

    def _assert_absent(self, role, records, *, case, deadline=None):
        """Read exact INSERT receipts after rollback. Never delete leftover rows."""
        __tracebackhide__ = True
        if not records:
            return
        with self._readiness_connection(role, case=case, phase="verification", deadline=deadline) as conn:
            for table in {record.table for record in records}:
                ids = [record.id for record in records if record.table == table]
                statement = sql.SQL("SELECT count(*) AS count FROM public.{} WHERE id = ANY(%s)").format(sql.Identifier(table))
                if query(conn, statement, (ids,))[0]["count"] != 0:
                    raise SafetyError("Rollback left synthetic receipts present; stop without automatic cleanup.")

    def wait_until_blocked(self, case, blocker_pid, blocked_pid, *, timeout=5):
        """Observe only this case's own backends; no administrative cancellation SQL."""
        __tracebackhide__ = True
        from threading import Event
        if not 0 < timeout <= 5:
            raise SafetyError("Unbounded lock observation is prohibited.")
        deadline = monotonic() + timeout
        observer_budget = Deadline(timeout)
        with self._readiness_connection("runtime", case=case, phase="observer", deadline=observer_budget) as conn:
            while monotonic() < deadline:
                active = self._active
                if any(pid not in active or active[pid][1] is not case for pid in (blocker_pid, blocked_pid)):
                    raise SafetyError("Lock observation requires two active, case-owned connections.")
                blocked = query(conn, "SELECT %s = ANY(pg_catalog.pg_blocking_pids(%s)) AS blocked", (blocker_pid, blocked_pid))[0]["blocked"]
                if blocked:
                    return
                Event().wait(0.02)
        raise SafetyError("Expected unique-index blocking was not observed before the deadline.")

    def cancel_case(self, case, *, deadline=None):
        __tracebackhide__ = True
        if not isinstance(case, Scope):
            raise SafetyError("Cancellation requires an exact synthetic case.")
        require_bounded_cancellation()
        deadline = deadline or Deadline(5)
        handles = self._registry.cancel(case)
        failed = False
        for handle in handles:
            try:
                cancel_handle(handle, deadline)
            except (psycopg.Error, SafetyError):
                failed = True
        if failed:
            raise SafetyError("An owned worker could not be cancelled safely; all remaining cancellations were attempted.")

    def close_all(self, *, deadline=None):
        __tracebackhide__ = True
        self.ready = False
        handles, opening = self._registry.shutdown()
        deadline = deadline or Deadline(8)
        failed = False
        if handles:
            require_bounded_cancellation()
        for handle in handles:
            try:
                cancel_handle(handle, deadline)
            except (psycopg.Error, SafetyError):
                failed = True
            finally:
                try:
                    self._close(handle.connection, deadline=deadline)
                except SafetyError:
                    failed = True
        if handles or opening or self._registry.snapshot() or self._registry.opening or failed:
            raise SafetyError("Unexpected resources remained at teardown; shutdown is irreversible and verification incomplete.")


class Session:
    """No raw cursor, arbitrary SQL, commit, DDL, or broad DELETE API is exposed."""

    def __init__(self, factory, conn, role, case, readonly):
        self._factory = factory
        self._conn = conn
        self.role = role
        self.case = self.scope = case
        self.readonly = readonly
        self._closed = False
        self._negative_depth = 0
        self._owner_active = False
        self._role_broken = False
        self._created = []

    def __repr__(self):
        return f"<FinSetSession role={self.role} rollback_only=True>"

    @property
    def backend_pid(self):
        self._check()
        return self._conn.info.backend_pid

    def _check(self, *, write=False):
        __tracebackhide__ = True
        _authorize()
        if (self._closed or self._role_broken or self._factory._closing
                or self._conn.info.transaction_status != TransactionStatus.INTRANS):
            raise SafetyError("Test operations require a healthy, active rollback transaction.")
        if write and (self.readonly or self._owner_active):
            raise SafetyError("This session may not perform application writes.")

    def _columns(self, table):
        from .schema import manifest
        if table == VIEW:
            return ("id", "name", "category_type", "archived_at", "created_at", "updated_at")
        if table not in TABLES:
            raise SafetyError("Unapproved application relation.")
        return tuple(manifest().tables[table].columns.keys())

    def _table(self, table, *, write=False):
        self._check(write=write)
        columns = self._columns(table)
        allowed = table in TABLES if self.role == "runtime" else table == VIEW if self.role == "maintenance" else False
        if not allowed and not self._negative_depth:
            raise SafetyError("The role-specific data interface excludes this relation.")
        return columns

    def _projection(self, table):
        return sql.SQL(", ").join(sql.Identifier(name) for name in self._columns(table)
                                  if name not in ("password_hash", "token_hash"))

    def _where_record(self, record):
        self.case.require(record)
        validate_cleanup_scope(self.case, record.table, [record.id])
        clause = sql.SQL("id = %s")
        params = [record.id]
        if record.table in TABLES and record.table != "users":
            column = "owner_user_id" if record.table == "categories" else "user_id"
            clause += sql.SQL(" AND {} IS NOT DISTINCT FROM %s").format(sql.Identifier(column))
            params.append(record.owner_id)
        return clause, params

    def insert(self, table, *, ignore_conflict=False, **values):
        __tracebackhide__ = True
        columns = self._table(table, write=True)
        if not values or not set(values) <= set(columns):
            raise SafetyError("Unexpected insert columns.")
        if not self._negative_depth:
            if ignore_conflict or {"id", "created_at"} & set(values):
                raise SafetyError("Fixture insertion must use new server-generated identities.")
            if table == "users":
                email = values.get("email", "")
                if not isinstance(email, str) or self.case.token not in email or not email.endswith(".invalid"):
                    raise SafetyError("A unique synthetic .invalid account is required.")
            elif table != VIEW:
                owner = values.get("owner_user_id" if table == "categories" else "user_id")
                if not any(record.id == owner for record in self.case.records("users")):
                    raise SafetyError("Fixture records require a registered synthetic parent.")
        statement = sql.SQL("INSERT INTO public.{} ({}) VALUES ({})").format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, values)),
            sql.SQL(", ").join(sql.Placeholder() for _ in values),
        )
        if ignore_conflict:
            if not self._negative_depth:
                raise SafetyError("Conflict probes must be inside a forced-rollback rejection case.")
            statement += sql.SQL(" ON CONFLICT DO NOTHING")
        rows = query(self._conn, statement + sql.SQL(" RETURNING ") + self._projection(table), tuple(values.values()))
        if not rows:
            return None
        record = self.case.register(table, rows[0], self.role)
        self._created.append(record)
        return record

    def update(self, record, **values):
        __tracebackhide__ = True
        columns = self._table(record.table, write=True)
        if not values or not set(values) <= set(columns):
            raise SafetyError("Unexpected update columns.")
        where, params = self._where_record(record)
        statement = sql.SQL("UPDATE public.{} SET {} WHERE {} RETURNING {}").format(
            sql.Identifier(record.table),
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(name)) for name in values),
            where, self._projection(record.table),
        )
        rows = query(self._conn, statement, [*values.values(), *params])
        if len(rows) != 1 or rows[0]["id"] != record.id:
            raise SafetyError("A scoped update changed or failed to match its exact receipt.")
        owner = rows[0]["id"] if record.table == "users" else rows[0].get("owner_user_id", rows[0].get("user_id"))
        if owner != record.owner_id:
            raise SafetyError("A scoped update changed its immutable owner binding.")
        return Record(record.table, record.id, record.owner_id, record.role, rows[0])

    def delete(self, record):
        __tracebackhide__ = True
        self._table(record.table, write=True)
        where, params = self._where_record(record)
        if record.table == "users":
            for table in ("auth_tokens", "login_sessions"):
                statement = sql.SQL("SELECT count(*) AS count FROM public.{} WHERE user_id = %s").format(sql.Identifier(table))
                if query(self._conn, statement, (record.id,))[0]["count"]:
                    raise SafetyError("Delete credential children explicitly; cascading user deletion is prohibited.")
        statement = sql.SQL("DELETE FROM public.{} WHERE {} RETURNING id").format(sql.Identifier(record.table), where)
        rows = query(self._conn, statement, params)
        if len(rows) > 1 or any(row["id"] != record.id for row in rows):
            raise SafetyError("A scoped deletion affected an unexpected identity.")
        return len(rows)

    def get(self, record):
        self._table(record.table)
        where, params = self._where_record(record)
        statement = sql.SQL("SELECT {} FROM public.{} WHERE {}").format(self._projection(record.table), sql.Identifier(record.table), where)
        rows = query(self._conn, statement, params)
        if len(rows) > 1:
            raise SafetyError("An exact-ID read returned multiple records.")
        return rows[0] if rows else None

    def _selection(self, table, filters):
        columns = self._table(table)
        if not set(filters) <= set(columns):
            raise SafetyError("Unexpected scoped query columns.")
        ids = [record.id for record in self.case.records(table)]
        clauses = [sql.SQL("id = ANY(%s)")]
        params = [ids]
        for name, value in filters.items():
            clauses.append(sql.SQL("{} IS NOT DISTINCT FROM %s").format(sql.Identifier(name)))
            params.append(value)
        return sql.SQL(" AND ").join(clauses), params

    def rows(self, table, **filters):
        where, params = self._selection(table, filters)
        return query(self._conn, sql.SQL("SELECT {} FROM public.{} WHERE {} ORDER BY id").format(
            self._projection(table), sql.Identifier(table), where), params)

    def count(self, table, **filters):
        where, params = self._selection(table, filters)
        return query(self._conn, sql.SQL("SELECT count(*) AS value FROM public.{} WHERE {}").format(sql.Identifier(table), where), params)[0]["value"]

    def sum(self, table, column, **filters):
        if column not in self._columns(table) or not column.endswith("_kobo"):
            raise SafetyError("Only a known integer-kobo aggregate is supported.")
        where, params = self._selection(table, filters)
        value = query(self._conn, sql.SQL("SELECT sum({}) AS value FROM public.{} WHERE {}").format(
            sql.Identifier(column), sql.Identifier(table), where), params)[0]["value"]
        if value is None:
            return 0
        if value != int(value):
            raise SafetyError("The integer-kobo aggregate was not integral.")
        return int(value)

    def clock(self):
        self._check()
        value = query(self._conn, "SELECT CURRENT_TIMESTAMP AS value")[0]["value"]
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise SafetyError("A timezone-aware server transaction timestamp is required.")
        return value

    def identity(self):
        self._check()
        return identity(self._conn, self.role, "finset_owner" if self._owner_active else None)

    def check_constraints(self):
        self._check()
        query(self._conn, "SET CONSTRAINTS ALL IMMEDIATE")
        query(self._conn, "SET CONSTRAINTS ALL DEFERRED")

    @contextmanager
    def rejects(self, sqlstate, constraint=None):
        __tracebackhide__ = True
        self._check()
        self.check_constraints()
        caught = None
        try:
            with self._conn.transaction(force_rollback=True):
                self._negative_depth += 1
                try:
                    yield
                    self.check_constraints()
                finally:
                    self._negative_depth -= 1
        except DatabaseFailure as error:
            caught = (error.sqlstate, error.constraint)
        except psycopg.Error as error:
            failure = DatabaseFailure(error)
            caught = (failure.sqlstate, failure.constraint)
        self._check()
        self.check_constraints()
        if caught is None:
            raise AssertionError("Expected PostgreSQL rejection did not occur; the savepoint was rolled back.")
        if caught[0] != sqlstate or (constraint is not None and caught[1] != constraint):
            raise AssertionError(f"Unexpected rejection: SQLSTATE={caught[0]}, constraint={caught[1]}.")

    def _probe(self):
        self._check()
        if not self._negative_depth:
            raise SafetyError("Permission probes require a forced-rollback rejection context.")

    def read_probe(self, table):
        self._probe()
        self._columns(table)
        query(self._conn, sql.SQL("SELECT 1 FROM public.{} LIMIT 0").format(sql.Identifier(table)))
        raise AssertionError("The prohibited relation read unexpectedly succeeded.")

    def function_probe(self, name):
        from .schema import manifest
        self._probe()
        if name not in manifest().functions:
            raise SafetyError("Unapproved function probe.")
        query(self._conn, sql.SQL("SELECT public.{}()").format(sql.Identifier(name)))
        raise AssertionError("The prohibited function call unexpectedly succeeded.")

    def role_probe(self, role):
        self._probe()
        if role not in GROUPS:
            raise SafetyError("Unapproved role probe.")
        query(self._conn, sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        raise AssertionError("The prohibited role assumption unexpectedly succeeded.")

    @contextmanager
    def owner(self):
        __tracebackhide__ = True
        self._check()
        if self.role != "migrator" or not self.readonly or self._owner_active:
            raise SafetyError("Owner assumption is limited to a read-only migrator probe.")
        try:
            with self._conn.transaction(force_rollback=True):
                query(self._conn, "SET LOCAL ROLE finset_owner")
                self._owner_active = True
                try:
                    self.identity()
                    yield self
                finally:
                    try:
                        if self._conn.info.transaction_status == TransactionStatus.INTRANS:
                            query(self._conn, "RESET ROLE")
                    finally:
                        self._owner_active = False
        except BaseException:
            self._owner_active = False
            self._role_broken = True
            raise
        self.identity()
