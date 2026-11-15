"""Fail-closed, read-only catalog attestation, not a migration or data probe.

Only the factory may authenticate/connect. Its private context supplies an identity-
checked SCRAM connection inside a read-only, force-rollback outer transaction.
EXPLAIN below never uses ANALYZE; only Alembic history, not application rows, is read.
"""

from collections import Counter
import re

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from .policy import DATABASE, GROUPS, HOST, PORT, REVISION, ROLES, TABLES, VIEW, SafetyError
from .schema import IndexSpec, VIEW_COLUMNS, manifest


_OWNER = "finset_owner"
_ALEMBIC = "alembic_version"
_TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN")
_COLUMN_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "REFERENCES")
_MAINTENANCE_INSERT = ("name", "category_type")
_MAINTENANCE_UPDATE = ("name", "archived_at", "updated_at")


def _require(condition):
    __tracebackhide__ = True
    if not condition:
        raise SafetyError("FinSet readiness metadata mismatch.")


def _rows(connection, statement, parameters=()):
    __tracebackhide__ = True
    with connection.execute(statement, parameters or None) as cursor:
        return cursor.fetchall()


def _command(connection, statement):
    __tracebackhide__ = True
    with connection.execute(statement):
        pass


def _identity(connection, role, effective=None):
    __tracebackhide__ = True
    rows = _rows(connection, """
        SELECT pg_catalog.current_database() AS database, session_user, current_user,
               pg_catalog.host(pg_catalog.inet_server_addr()) AS address, pg_catalog.inet_server_port() AS port,
               pg_catalog.current_setting('server_version_num')::integer AS version,
               pg_catalog.current_setting('transaction_read_only') AS read_only,
               pg_catalog.current_setting('default_transaction_read_only') AS default_read_only,
               pg_catalog.current_setting('session_replication_role') AS replication_role
    """)
    _require(len(rows) == 1)
    row = rows[0]
    _require(tuple(row[key] for key in ("database", "session_user", "current_user", "address", "port"))
             == (DATABASE, ROLES[role][1], effective or ROLES[role][1], HOST, PORT))
    _require(180000 <= row["version"] < 190000 and row["read_only"] == row["default_read_only"] == "on"
             and row["replication_role"] == "origin")


def _roles(connection):
    __tracebackhide__ = True
    names = set(GROUPS) | {value[1] for value in ROLES.values()}
    _require(set(GROUPS) == {_OWNER, "finset_runtime", "finset_migrator", "finset_maintenance"}
             and set(ROLES) == {"runtime", "migrator", "maintenance"} and len(names) == 7)
    rows = _rows(connection, """
        SELECT oid, rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
        FROM pg_catalog.pg_roles WHERE rolname = ANY(%s)
    """, (sorted(names),))
    _require(len(rows) == 7 and {row["rolname"] for row in rows} == names)
    for row in rows:
        _require(row["rolcanlogin"] == (row["rolname"] not in GROUPS))
        _require(not any(row[key] for key in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls")))
    roles = {row["rolname"]: row["oid"] for row in rows}
    expected = {(roles[login], roles["finset_" + label], True, True, False)
                for label, (_, login) in ROLES.items()}
    expected.add((roles["finset_migrator"], roles[_OWNER], False, True, False))
    edges = _rows(connection, """
        SELECT member, roleid, inherit_option, set_option, admin_option
        FROM pg_catalog.pg_auth_members WHERE member = ANY(%s) OR roleid = ANY(%s)
    """, (list(roles.values()), list(roles.values())))
    _require(len(edges) == 4 and {tuple(row[key] for key in (
        "member", "roleid", "inherit_option", "set_option", "admin_option")) for row in edges} == expected)
    rights = _rows(connection, """
        SELECT member.oid AS member, target.oid AS target, permission,
               pg_catalog.pg_has_role(member.oid, target.oid, permission) AS allowed
        FROM pg_catalog.pg_roles AS member CROSS JOIN pg_catalog.pg_roles AS target
        CROSS JOIN unnest(ARRAY['MEMBER', 'USAGE', 'SET']) AS p(permission)
        WHERE member.oid = ANY(%s) AND target.oid = ANY(%s)
    """, (list(roles.values()), list(roles.values())))
    _require(len(rights) == 147)
    for row in rights:
        reachable = {row["member"]}
        for _ in range(7):
            reachable |= {target for member, target, inherit, assume, _ in expected
                          if member in reachable and (row["permission"] == "MEMBER"
                          or (inherit if row["permission"] == "USAGE" else assume))}
        _require(row["allowed"] == (row["target"] in reachable))
    return roles


def _expected(schema):
    tables = dict(schema.tables)
    tables[VIEW] = sa.Table(
        VIEW, sa.MetaData(), *(sa.Column(name, tables["categories"].c[name].type, nullable=True)
                              for name in VIEW_COLUMNS), schema="public",
    )
    tables[_ALEMBIC] = sa.Table(
        _ALEMBIC, sa.MetaData(), sa.Column("version_num", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("version_num", name="alembic_version_pkc"), schema="public",
    )
    indexes = dict(schema.indexes)
    for table in tables.values():
        for constraint in table.constraints:
            if isinstance(constraint, (sa.PrimaryKeyConstraint, sa.UniqueConstraint)) and constraint.columns:
                indexes[constraint.name] = IndexSpec(table.name, tuple(constraint.columns.keys()), True)
    _require(len(tables) == 11 and len(indexes) == 33)
    return tables, indexes


def _inventory(connection, roles, tables, indexes):
    __tracebackhide__ = True
    namespaces = _rows(connection, """
        SELECT oid, nspname, nspowner FROM pg_catalog.pg_namespace
        WHERE nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND nspname !~ '^pg_(toast_)?temp_[0-9]+$'
    """)
    _require(len(namespaces) == 1 and namespaces[0]["nspname"] == "public"
             and namespaces[0]["nspowner"] == roles[_OWNER])
    database = _rows(connection, """
        SELECT oid, datdba, datallowconn, datistemplate FROM pg_catalog.pg_database
        WHERE datname = pg_catalog.current_database()
    """)
    _require(len(database) == 1 and database[0]["datdba"] == roles[_OWNER]
             and database[0]["datallowconn"] and not database[0]["datistemplate"])
    extensions = _rows(connection, """
        SELECT e.extname, e.extversion, n.nspname AS schema
        FROM pg_catalog.pg_extension AS e JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
        ORDER BY e.extname
    """)
    _require(extensions == [{"extname": "plpgsql", "extversion": "1.0", "schema": "pg_catalog"}])
    rows = _rows(connection, """
        SELECT c.oid, c.relname, n.nspname, c.relkind, c.relowner, c.relpersistence,
               c.relrowsecurity, c.relforcerowsecurity, c.relispartition, c.relhassubclass,
               c.relreplident, c.reloftype, c.reltablespace, c.reloptions, c.relchecks,
               c.relhasrules, c.relhastriggers, c.relnatts, c.relacl IS NULL AS no_acl,
               am.amname
        FROM pg_catalog.pg_class AS c JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_am AS am ON am.oid = c.relam
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND n.nspname !~ '^pg_toast_temp_[0-9]+$'
    """)
    expected = {name: "v" if name == VIEW else "r" for name in tables}
    expected.update({name: "i" for name in indexes})
    _require(len(rows) == len(expected) == 44 and {row["relname"] for row in rows} == set(expected))
    relations = {row["relname"]: row["oid"] for row in rows}
    for row in rows:
        name, kind = row["relname"], row["relkind"]
        _require(row["nspname"] == "public" and kind == expected[name] and row["relowner"] == roles[_OWNER]
                 and row["relpersistence"] == "p" and not row["relrowsecurity"] and not row["relforcerowsecurity"]
                 and not row["relispartition"] and not row["relhassubclass"] and row["reloftype"] == 0
                 and row["reltablespace"] == 0)
        _require(row["amname"] == {"r": "heap", "i": "btree", "v": None}[kind])
        _require(row["relhasrules"] == (name == VIEW) and row["relhastriggers"] == (name in TABLES))
        _require(row["relnatts"] == (len(indexes[name].expressions) if kind == "i" else len(tables[name].c)))
        _require(row["relchecks"] == (sum(isinstance(item, sa.CheckConstraint) for item in tables[name].constraints)
                                      if kind == "r" else 0))
        if name == VIEW:
            _require(sorted(row["reloptions"] or []) == ["check_option=local", "security_barrier=true", "security_invoker=false"])
        else:
            _require(not row["reloptions"])
        if kind == "r":
            _require(row["relreplident"] == "d")
        if kind == "i":
            _require(row["no_acl"])

    # Implicit row/array types are the only non-system types. Their default USAGE
    # is a PostgreSQL type facility, not a grant to read or write the underlying rows.
    types = _rows(connection, """
        SELECT t.oid, t.typname, t.typtype, t.typrelid, t.typelem, t.typarray, t.typowner,
               t.typacl IS NULL AS no_acl, n.nspname
        FROM pg_catalog.pg_type AS t JOIN pg_catalog.pg_namespace AS n ON n.oid = t.typnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND n.nspname !~ '^pg_toast_temp_[0-9]+$'
    """)
    _require(len(types) == 2 * len(tables))
    by_name = {row["typname"]: row for row in types}
    _require(set(by_name) == set(tables) | {"_" + name for name in tables})
    for name in tables:
        composite, array = by_name[name], by_name["_" + name]
        for row in (composite, array):
            _require(row["nspname"] == "public" and row["typowner"] == roles[_OWNER] and row["no_acl"])
        _require(composite["typtype"] == "c" and composite["typrelid"] == relations[name]
                 and composite["typelem"] == 0 and composite["typarray"] == array["oid"])
        _require(array["typtype"] == "b" and array["typrelid"] == 0 and array["typelem"] == composite["oid"]
                 and array["typarray"] == 0)

    extras = _rows(connection, """
        SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_default_acl)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_inherits)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_policy)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_event_trigger)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_foreign_table)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_foreign_server)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_foreign_data_wrapper)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_publication)
            OR EXISTS (SELECT oid FROM pg_catalog.pg_subscription WHERE subdbid = %s)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_largeobject_metadata)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_statistic_ext)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_transform)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_extension WHERE extname <> 'plpgsql')
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_language WHERE lanname NOT IN ('internal', 'c', 'sql', 'plpgsql'))
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_cast WHERE oid >= 16384)
            OR EXISTS (SELECT 1 FROM pg_catalog.pg_am WHERE oid >= 16384)
            OR EXISTS (
                SELECT 1 FROM pg_catalog.pg_rewrite AS r
                JOIN pg_catalog.pg_class AS c ON c.oid = r.ev_class
                JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND NOT (c.oid = %s AND r.rulename = '_RETURN' AND r.ev_type = '1'
                           AND r.is_instead AND r.ev_enabled = 'O')
            ) AS unexpected
    """, (database[0]["oid"], relations[VIEW]))
    _require(len(extras) == 1 and not extras[0]["unexpected"])
    for catalog, namespace in (
        ("pg_operator", "oprnamespace"), ("pg_opclass", "opcnamespace"), ("pg_opfamily", "opfnamespace"),
        ("pg_collation", "collnamespace"), ("pg_conversion", "connamespace"), ("pg_ts_config", "cfgnamespace"),
        ("pg_ts_dict", "dictnamespace"), ("pg_ts_parser", "prsnamespace"), ("pg_ts_template", "tmplnamespace"),
    ):
        _require(not _rows(connection, f"""
            SELECT 1 FROM pg_catalog.{catalog} AS object
            JOIN pg_catalog.pg_namespace AS n ON n.oid = object.{namespace}
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        """))
    return relations


_TOKEN = re.compile(r"\s+|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z_0-9]*|"
                    r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|::|<=|>=|<>|!=|[()+*/%=,<>\-\[\].]")
_FUNCTIONS = {"least", "lower", "btrim", "char_length", "octet_length", "isfinite", "date_trunc", "gen_random_uuid"}
_EXPRESSION_WORDS = _FUNCTIONS | set("""
    and or not in is null between any all array true false cast as extract from day isodow
    current_timestamp text character varying bpchar timestamp with without time zone date
    integer smallint bigint numeric uuid bytea boolean pg_catalog
""".split())


def _safe_expression(expression, table):
    """Reject arbitrary SQL/function execution even during EXPLAIN constant folding."""
    __tracebackhide__ = True
    _require(isinstance(expression, str) and 0 < len(expression) <= 8192)
    _require(not any(marker in expression for marker in (";", "--", "/*", "*/", "\\", "$")))
    tokens, position = [], 0
    for match in _TOKEN.finditer(expression):
        _require(match.start() == position)
        position = match.end()
        if not match.group().isspace():
            tokens.append(match.group())
    _require(position == len(expression) and tokens)
    calls = _FUNCTIONS | {"cast", "extract", "in", "any", "all", "and", "or", "not", "varying", "character", "numeric"}
    for index, token in enumerate(tokens):
        word = token.strip('"').lower()
        if token[0].isalpha() or token[0] == '"':
            _require(word in _EXPRESSION_WORDS or word in table.c)
            if index + 1 < len(tokens) and tokens[index + 1] == "(":
                _require(word in calls)
        if token == ".":
            _require(index > 0 and tokens[index - 1].lower() == "pg_catalog"
                     and index + 1 < len(tokens) and tokens[index + 1].strip('"').lower() in _EXPRESSION_WORDS)
    return expression


def _expression(connection, table, expected, actual, cast_type=None):
    __tracebackhide__ = True
    _require(table.name in (*TABLES, _ALEMBIC) and table.schema == "public")
    outputs = []
    for expression in (expected, actual):
        expression = _safe_expression(expression, table)
        if cast_type is not None:
            expression = f"CAST(({expression}) AS {cast_type})"
        # Only a lexically restricted expression and a pinned identifier enter SQL.
        rows = _rows(connection, 'EXPLAIN (FORMAT JSON, VERBOSE, COSTS OFF) SELECT ('
                     + expression + ') FROM public."' + table.name + '"')
        _require(len(rows) == 1)
        document = rows[0]["QUERY PLAN"]
        _require(isinstance(document, list) and len(document) == 1)
        output = document[0]["Plan"].get("Output")
        _require(isinstance(output, list) and len(output) == 1 and isinstance(output[0], str))
        outputs.append(output[0])
    _require(outputs[0] == outputs[1])


def _type(column):
    value = str(column.type.compile(dialect=postgresql.dialect())).lower()
    if value.startswith("varchar"):
        value = value.replace("varchar", "character varying", 1)
    elif value.startswith("char("):
        value = value.replace("char(", "character(", 1)
    return value


def _columns(connection, tables, relations):
    __tracebackhide__ = True
    rows = _rows(connection, """
        SELECT c.relname, col.attname, col.attnum, col.attnotnull, col.attisdropped, col.attidentity,
               col.attgenerated, col.attislocal, col.attinhcount, col.attndims, col.atthasmissing,
               col.attoptions, col.attfdwoptions, col.attstorage, col.attcompression,
               col.attcollation, typ.typcollation, typ.typstorage, n.nspname AS type_schema,
               pg_catalog.format_type(col.atttypid, col.atttypmod) AS data_type,
               pg_catalog.pg_get_expr(d.adbin, d.adrelid, false) AS default_expression
        FROM pg_catalog.pg_attribute AS col JOIN pg_catalog.pg_class AS c ON c.oid = col.attrelid
        JOIN pg_catalog.pg_type AS typ ON typ.oid = col.atttypid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = typ.typnamespace
        LEFT JOIN pg_catalog.pg_attrdef AS d ON d.adrelid = col.attrelid AND d.adnum = col.attnum
        WHERE col.attrelid = ANY(%s) AND col.attnum > 0
    """, ([relations[name] for name in tables],))
    expected = {(name, column.name): (position, column) for name, table in tables.items()
                for position, column in enumerate(table.c, 1)}
    _require(len(rows) == len(expected) == 107 and {(row["relname"], row["attname"]) for row in rows} == set(expected))
    columns = {}
    for row in rows:
        key = row["relname"], row["attname"]
        position, column = expected[key]
        _require(row["attnum"] == position and row["attnotnull"] == (not column.nullable)
                 and not row["attisdropped"] and not row["attidentity"] and not row["attgenerated"]
                 and row["attislocal"] and row["attinhcount"] == row["attndims"] == 0
                 and not row["atthasmissing"] and not row["attoptions"] and not row["attfdwoptions"]
                 and row["attstorage"] == row["typstorage"] and not row["attcompression"]
                 and row["attcollation"] == row["typcollation"] and row["type_schema"] == "pg_catalog"
                 and row["data_type"] == _type(column))
        default = None if column.server_default is None else str(column.server_default.arg)
        if default is None:
            _require(row["default_expression"] is None)
        else:
            _expression(connection, tables[key[0]], default, row["default_expression"], _type(column))
        columns[key] = row
    return columns


def _functions(connection, schema, roles):
    __tracebackhide__ = True
    rows = _rows(connection, """
        SELECT p.oid, p.proname, n.nspname, p.proowner, l.lanname, p.prokind, p.prosecdef,
               p.proleakproof, p.proisstrict, p.proretset, p.provolatile, p.proparallel,
               p.pronargs, p.pronargdefaults, p.provariadic, p.prosupport, p.procost, p.prorows,
               p.proargtypes::text AS arguments, p.proallargtypes, p.proargmodes, p.proargnames,
               p.proconfig, p.prosrc, p.probin, p.prosqlbody IS NULL AS no_sql_body,
               t.typname AS return_type, tn.nspname AS return_schema
        FROM pg_catalog.pg_proc AS p JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
        JOIN pg_catalog.pg_language AS l ON l.oid = p.prolang
        JOIN pg_catalog.pg_type AS t ON t.oid = p.prorettype
        JOIN pg_catalog.pg_namespace AS tn ON tn.oid = t.typnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
    """)
    _require(len(rows) == 8 and {row["proname"] for row in rows} == set(schema.functions))
    for row in rows:
        mode, body = schema.functions[row["proname"]]
        _require(row["nspname"] == "public" and row["proowner"] == roles[_OWNER]
                 and row["lanname"] == "plpgsql" and row["prokind"] == "f"
                 and row["prosecdef"] == (mode == "DEFINER")
                 and row["prosecdef"] == (row["proname"] == "finset_allocate_plan_result")
                 and not row["proleakproof"] and not row["proisstrict"] and not row["proretset"]
                 and row["provolatile"] == "v" and row["proparallel"] == "u"
                 and row["pronargs"] == row["pronargdefaults"] == row["provariadic"] == row["prosupport"] == 0
                 and row["procost"] == 100 and row["prorows"] == 0 and row["arguments"] == ""
                 and row["proallargtypes"] is None and row["proargmodes"] is None and row["proargnames"] is None
                 and row["proconfig"] == ["search_path=pg_catalog, pg_temp"]
                 and row["prosrc"].strip() == body.strip() and row["probin"] is None and row["no_sql_body"]
                 and row["return_type"] == "trigger" and row["return_schema"] == "pg_catalog")
    return {row["proname"]: row["oid"] for row in rows}


def _constraints(connection, schema, tables, relations, columns):
    __tracebackhide__ = True
    expected = {}
    kinds = {sa.ForeignKeyConstraint: "f", sa.CheckConstraint: "c",
             sa.PrimaryKeyConstraint: "p", sa.UniqueConstraint: "u"}
    for name, table in tables.items():
        for constraint in table.constraints:
            if isinstance(constraint, sa.PrimaryKeyConstraint) and not constraint.columns:
                continue
            expected[name, constraint.name] = (kinds[type(constraint)], constraint)
        # PostgreSQL 18 catalogs NOT NULL separately; do not mistake these for
        # extra CHECK constraints or omit validation of their enforcement flags.
        for column in table.c:
            if not column.nullable:
                expected[name, f"{name}_{column.name}_not_null"] = ("n", column)
    for (name, trigger), definition in schema.triggers.items():
        if "DEFERRABLE INITIALLY DEFERRED" in definition:
            expected[name, trigger] = ("t", None)
    _require(Counter(kind for (table, _), (kind, _) in expected.items() if table in TABLES and kind in "fcpu")
             == Counter({"f": 15, "c": 99, "p": 9, "u": 8}))
    rows = _rows(connection, """
        SELECT con.oid, con.conname, c.relname, con.conrelid, con.contype, con.contypid,
               con.condeferrable, con.condeferred, con.conenforced, con.convalidated,
               con.conislocal, con.coninhcount, con.connoinherit, con.conparentid, con.conperiod,
               con.conkey, con.confkey, con.confrelid, con.confupdtype, con.confdeltype, con.confmatchtype,
               con.conindid, con.confdelsetcols, con.conexclop,
               pg_catalog.pg_get_expr(con.conbin, con.conrelid, false) AS expression
        FROM pg_catalog.pg_constraint AS con
        JOIN pg_catalog.pg_namespace AS n ON n.oid = con.connamespace
        LEFT JOIN pg_catalog.pg_class AS c ON c.oid = con.conrelid
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
    """)
    _require(len(rows) == len(expected) and {(row["relname"], row["conname"]) for row in rows} == set(expected))
    by_oid = {}
    for row in rows:
        name = row["relname"]
        kind, constraint = expected[name, row["conname"]]
        deferred = kind == "t"
        _require(row["contype"] == kind and row["conrelid"] == relations[name] and row["contypid"] == 0
                 and row["condeferrable"] == deferred and row["condeferred"] == deferred
                 and row["conenforced"] and row["convalidated"] and row["conislocal"]
                 and row["coninhcount"] == row["conparentid"] == 0 and not row["conperiod"]
                 and row["confdelsetcols"] is None and row["conexclop"] is None)
        keys = tuple(row["conkey"] or ())
        if kind == "c":
            _require(not row["connoinherit"])
            _expression(connection, tables[name], str(constraint.sqltext), row["expression"])
        else:
            expected_columns = ((constraint.name,) if kind == "n" else
                                tuple(constraint.columns.keys()) if kind in "fpu" else ())
            _require(keys == tuple(columns[name, column]["attnum"] for column in expected_columns))
            _require(row["expression"] is None)
        if kind == "n":
            _require(not row["connoinherit"])
        if kind == "f":
            reference = constraint.referred_table.name
            reference_columns = tuple(item.column.name for item in constraint.elements)
            _require(row["confrelid"] == relations[reference]
                     and tuple(row["confkey"] or ()) == tuple(columns[reference, item]["attnum"] for item in reference_columns)
                     and row["confupdtype"] == "r" and row["confmatchtype"] == "s"
                     and row["confdeltype"] == {"RESTRICT": "r", "CASCADE": "c"}[constraint.ondelete])
            backing = [item.name for item in tables[reference].constraints
                       if isinstance(item, (sa.PrimaryKeyConstraint, sa.UniqueConstraint))
                       and tuple(item.columns.keys()) == reference_columns]
            _require(len(backing) == 1 and row["conindid"] == relations[backing[0]])
        else:
            _require(row["confrelid"] == 0 and not row["confkey"])
            _require(row["conindid"] == (relations[row["conname"]] if kind in "pu" else 0))
        by_oid[row["oid"]] = row
    return by_oid


def _indexes(connection, tables, specs, relations, columns):
    __tracebackhide__ = True
    rows = _rows(connection, """
        SELECT idx.relname, i.indrelid, i.indnatts, i.indnkeyatts, i.indisunique, i.indnullsnotdistinct,
               i.indisprimary, i.indisexclusion, i.indimmediate, i.indisvalid, i.indcheckxmin,
               i.indisready, i.indislive, i.indisclustered, i.indisreplident,
               i.indkey::smallint[] AS keys, i.indoption::smallint[] AS options,
               i.indcollation::oid[] AS collations,
               pg_catalog.pg_get_expr(i.indexprs, i.indrelid, false) AS expression,
               pg_catalog.pg_get_expr(i.indpred, i.indrelid, false) AS predicate,
               ARRAY(SELECT opc.opcname FROM unnest(i.indclass::oid[]) WITH ORDINALITY AS k(oid, ord)
                     JOIN pg_catalog.pg_opclass AS opc ON opc.oid = k.oid ORDER BY k.ord) AS opclasses,
               ARRAY(SELECT n.nspname = 'pg_catalog' AND opc.opcdefault AND opc.opcmethod = idx.relam
                     FROM unnest(i.indclass::oid[]) WITH ORDINALITY AS k(oid, ord)
                     JOIN pg_catalog.pg_opclass AS opc ON opc.oid = k.oid
                     JOIN pg_catalog.pg_namespace AS n ON n.oid = opc.opcnamespace ORDER BY k.ord) AS standard_classes
        FROM pg_catalog.pg_index AS i JOIN pg_catalog.pg_class AS idx ON idx.oid = i.indexrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = idx.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND n.nspname !~ '^pg_toast_temp_[0-9]+$'
    """)
    _require(len(rows) == 33 and {row["relname"] for row in rows} == set(specs))
    for row in rows:
        name = row["relname"]
        spec, expressions = specs[name], []
        keys, options, collations, opclasses = [], [], [], []
        table = tables[spec.table]
        for field in spec.expressions:
            descending = field.endswith(" DESC")
            field = field.removesuffix(" DESC")
            options.append(3 if descending else 0)  # DESC's default is NULLS FIRST.
            if field in table.c:
                column = columns[spec.table, field]
                keys.append(column["attnum"])
                collations.append(column["attcollation"])
                data_type = _type(table.c[field])
                opclasses.append("text_ops" if data_type.startswith("character varying") else {
                    "uuid": "uuid_ops", "bytea": "bytea_ops", "date": "date_ops",
                    "timestamp with time zone": "timestamptz_ops", "smallint": "int2_ops",
                    "integer": "int4_ops", "bigint": "int8_ops",
                }[data_type])
            else:
                keys.append(0)
                expressions.append(field)
                if field.startswith("lower(btrim("):
                    collations.append(columns[spec.table, "name"]["attcollation"])
                    opclasses.append("text_ops")
                else:
                    _require(field.startswith("least("))
                    collations.append(0)
                    opclasses.append("timestamptz_ops")
        _require(row["indrelid"] == relations[spec.table] and row["indnatts"] == row["indnkeyatts"] == len(keys)
                 and row["indisunique"] == spec.unique and row["indnullsnotdistinct"] == spec.nulls_not_distinct
                 and row["indnullsnotdistinct"] == (name == "uq_budget_alerts_active_scope")
                 and row["indisprimary"] == (name == table.primary_key.name)
                 and not row["indisexclusion"] and row["indimmediate"] and row["indisvalid"]
                 and row["indisready"] and row["indislive"] and not row["indcheckxmin"]
                 and not row["indisclustered"] and not row["indisreplident"]
                 and list(row["keys"]) == keys and list(row["options"]) == options
                 and list(row["collations"]) == collations and row["opclasses"] == opclasses
                 and row["standard_classes"] == [True] * len(keys))
        _require(len(expressions) <= 1)
        if expressions:
            _expression(connection, table, expressions[0], row["expression"])
        else:
            _require(row["expression"] is None)
        if spec.where is None:
            _require(row["predicate"] is None)
        else:
            _expression(connection, table, spec.where, row["predicate"])


def _triggers(connection, schema, relations, functions, constraints):
    __tracebackhide__ = True
    rows = _rows(connection, """
        SELECT t.tgname, c.relname, t.tgrelid, t.tgfoid, t.tgtype, t.tgenabled, t.tgisinternal,
               t.tgdeferrable, t.tginitdeferred, t.tgconstraint, t.tgconstrrelid, t.tgconstrindid,
               t.tgparentid, t.tgattr::smallint[] AS columns, t.tgqual IS NULL AS no_when,
               t.tgnargs, t.tgargs, t.tgoldtable, t.tgnewtable, p.proname, pn.nspname AS function_schema
        FROM pg_catalog.pg_trigger AS t JOIN pg_catalog.pg_class AS c ON c.oid = t.tgrelid
        JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_proc AS p ON p.oid = t.tgfoid
        JOIN pg_catalog.pg_namespace AS pn ON pn.oid = p.pronamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND n.nspname !~ '^pg_toast_temp_[0-9]+$'
    """)
    custom = [row for row in rows if not row["tgisinternal"]]
    _require(len(custom) == 23 and {(row["relname"], row["tgname"]) for row in custom} == set(schema.triggers))
    internal_expected = set()
    for oid, constraint in constraints.items():
        if constraint["contype"] == "f":
            own, reference = constraint["conrelid"], constraint["confrelid"]
            for relation, other, function, kind in (
                (own, reference, "RI_FKey_check_ins", 5), (own, reference, "RI_FKey_check_upd", 17),
                (reference, own, "RI_FKey_restrict_upd", 17),
                (reference, own, "RI_FKey_" + ("cascade_del" if constraint["confdeltype"] == "c" else "restrict_del"), 9),
            ):
                internal_expected.add((oid, relation, other, function, kind, constraint["conindid"]))
    internal = []
    pattern = (r"(BEFORE|AFTER) ((?:INSERT|UPDATE|DELETE)(?: OR (?:INSERT|UPDATE|DELETE))*) "
               r"ON public\.([a-z_]+) (DEFERRABLE INITIALLY DEFERRED )?FOR EACH ROW "
               r"EXECUTE FUNCTION public\.([a-z_0-9]+)\((.*)\)")
    for row in rows:
        _require(row["tgenabled"] == "O" and row["tgparentid"] == 0 and not row["columns"]
                 and row["no_when"] and row["tgoldtable"] is None and row["tgnewtable"] is None)
        if row["tgisinternal"]:
            _require(row["function_schema"] == "pg_catalog" and not row["tgdeferrable"]
                     and not row["tginitdeferred"] and row["tgnargs"] == 0 and bytes(row["tgargs"]) == b"")
            internal.append(tuple(row[key] for key in ("tgconstraint", "tgrelid", "tgconstrrelid", "proname", "tgtype", "tgconstrindid")))
            continue
        match = re.fullmatch(pattern, schema.triggers[row["relname"], row["tgname"]])
        _require(match is not None)
        timing, events, table, deferred, function, arguments = match.groups()
        args = re.findall(r"'([a-z_]+)'", arguments)
        _require(arguments == ", ".join("'" + item + "'" for item in args))
        kind = 1 | (2 if timing == "BEFORE" else 0)
        for event in events.split(" OR "):
            kind |= {"INSERT": 4, "DELETE": 8, "UPDATE": 16}[event]
        constraint_oids = [oid for oid, item in constraints.items()
                           if item["contype"] == "t" and item["relname"] == table and item["conname"] == row["tgname"]]
        _require(row["tgrelid"] == relations[table] and row["tgtype"] == kind
                 and row["function_schema"] == "public" and row["tgfoid"] == functions[function]
                 and row["tgdeferrable"] == bool(deferred) and row["tginitdeferred"] == bool(deferred)
                 and row["tgconstrrelid"] == row["tgconstrindid"] == 0 and row["tgnargs"] == len(args)
                 and bytes(row["tgargs"]) == (b"".join(item.encode("ascii") + b"\0" for item in args)))
        _require((len(constraint_oids) == 1 and row["tgconstraint"] == constraint_oids[0]) if deferred
                 else (not constraint_oids and row["tgconstraint"] == 0))
    _require(len(internal) == len(internal_expected) == 60 and set(internal) == internal_expected)


def _view(connection, relations):
    __tracebackhide__ = True
    rows = _rows(connection, """
        SELECT pg_catalog.pg_get_viewdef(%s::oid, false) AS definition,
               pg_catalog.pg_relation_is_updatable(%s::regclass, false) AS updatable,
               (SELECT count(*) FROM pg_catalog.pg_rewrite WHERE ev_class = %s) AS rules
    """, (relations[VIEW], relations[VIEW], relations[VIEW]))
    expected = ("SELECT " + ", ".join("categories." + name for name in VIEW_COLUMNS)
                + " FROM public.categories WHERE (categories.owner_user_id IS NULL);")
    _require(len(rows) == 1 and " ".join(rows[0]["definition"].split()) == expected
             and rows[0]["updatable"] == 28 and rows[0]["rules"] == 1)


def _infrastructure_access(connection, roles):
    __tracebackhide__ = True
    rows = _rows(connection, """
        SELECT 'database' AS kind, a.grantor, a.grantee, a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_database AS d
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(d.datacl, pg_catalog.acldefault('d', d.datdba))) AS a
        WHERE d.datname = pg_catalog.current_database()
        UNION ALL
        SELECT 'schema', a.grantor, a.grantee, a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_namespace AS n
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl, pg_catalog.acldefault('n', n.nspowner))) AS a
        WHERE n.nspname = 'public'
    """)
    owner = roles[_OWNER]
    expected = {("database", owner, owner, privilege, False)
                for privilege in ("CONNECT", "CREATE", "TEMPORARY")}
    expected |= {("schema", owner, owner, privilege, False) for privilege in ("USAGE", "CREATE")}
    expected |= {("database", owner, roles[group], "CONNECT", False)
                 for group in GROUPS if group != _OWNER}
    expected |= {("schema", owner, roles[group], "USAGE", False)
                 for group in ("finset_runtime", "finset_maintenance")}
    fields = ("kind", "grantor", "grantee", "privilege_type", "is_grantable")
    _require(len(rows) == len(expected) and {tuple(row[field] for field in fields) for row in rows} == expected)
    rows = _rows(connection, """
        SELECT r.rolname, p.permission, pg_catalog.has_database_privilege(r.oid, d.oid, p.permission) AS allowed,
               pg_catalog.has_database_privilege(r.oid, d.oid, p.permission || ' WITH GRANT OPTION') AS grantable
        FROM pg_catalog.pg_roles AS r CROSS JOIN pg_catalog.pg_database AS d
        CROSS JOIN unnest(ARRAY['CONNECT', 'CREATE', 'TEMPORARY']) AS p(permission)
        WHERE r.oid = ANY(%s) AND d.datname = pg_catalog.current_database()
    """, (list(roles.values()),))
    _require(len(rows) == 21)
    for row in rows:
        owner = row["rolname"] == _OWNER
        _require(row["grantable"] == owner)
        _require(row["allowed"] == (owner or row["permission"] == "CONNECT"))
    rows = _rows(connection, """
        SELECT r.rolname, p.permission, pg_catalog.has_schema_privilege(r.oid, n.oid, p.permission) AS allowed,
               pg_catalog.has_schema_privilege(r.oid, n.oid, p.permission || ' WITH GRANT OPTION') AS grantable
        FROM pg_catalog.pg_roles AS r CROSS JOIN pg_catalog.pg_namespace AS n
        CROSS JOIN unnest(ARRAY['USAGE', 'CREATE']) AS p(permission)
        WHERE r.oid = ANY(%s) AND n.nspname = 'public'
    """, (list(roles.values()),))
    _require(len(rows) == 14)
    migrators = {"finset_migrator", ROLES["migrator"][1]}
    for row in rows:
        owner = row["rolname"] == _OWNER
        _require(row["grantable"] == owner)
        _require(row["allowed"] == (owner or row["permission"] == "USAGE" and row["rolname"] not in migrators))

    from .privileges import attest_platform_privileges
    attest_platform_privileges(connection, roles, query=_rows)


def _object_access(connection, schema, tables, relations, functions, roles):
    __tracebackhide__ = True
    owner = roles[_OWNER]
    expected = {("table", name, None, owner, owner, privilege, False)
                for name in tables for privilege in _TABLE_PRIVILEGES}
    for name in TABLES:
        for privilege in ("SELECT", "DELETE"):
            expected.add(("table", name, None, owner, roles["finset_runtime"], privilege, False))
        for privilege, fields in (("INSERT", schema.runtime_insert[name]), ("UPDATE", schema.runtime_update[name])):
            expected.update(("column", name, field, owner, roles["finset_runtime"], privilege, False) for field in fields)
    for privilege in ("SELECT", "DELETE"):
        expected.add(("table", VIEW, None, owner, roles["finset_maintenance"], privilege, False))
    for privilege, fields in (("INSERT", _MAINTENANCE_INSERT), ("UPDATE", _MAINTENANCE_UPDATE)):
        expected.update(("column", VIEW, field, owner, roles["finset_maintenance"], privilege, False) for field in fields)
    expected.update(("function", name, None, owner, owner, "EXECUTE", False) for name in functions)
    rows = _rows(connection, """
        SELECT 'table' AS kind, c.relname AS object, NULL::name AS field,
               a.grantor, a.grantee, a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_class AS c
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))) AS a
        WHERE c.oid = ANY(%s)
        UNION ALL
        SELECT 'column', c.relname, col.attname, a.grantor, a.grantee, a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_attribute AS col JOIN pg_catalog.pg_class AS c ON c.oid = col.attrelid
        CROSS JOIN LATERAL pg_catalog.aclexplode(col.attacl) AS a WHERE c.oid = ANY(%s)
        UNION ALL
        SELECT 'function', p.proname, NULL::name, a.grantor, a.grantee, a.privilege_type, a.is_grantable
        FROM pg_catalog.pg_proc AS p
        CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))) AS a
        WHERE p.oid = ANY(%s)
    """, ([relations[name] for name in tables], [relations[name] for name in tables], list(functions.values())))
    fields = ("kind", "object", "field", "grantor", "grantee", "privilege_type", "is_grantable")
    _require(len(rows) == len(expected) and {tuple(row[field] for field in fields) for row in rows} == expected)

    subjects = {name: name for name in GROUPS}
    subjects.update({login: "finset_" + label for label, (_, login) in ROLES.items()})
    rows = _rows(connection, """
        SELECT r.rolname, c.relname, p.privilege,
               pg_catalog.has_table_privilege(r.oid, c.oid, p.privilege) AS allowed,
               pg_catalog.has_table_privilege(r.oid, c.oid, p.privilege || ' WITH GRANT OPTION') AS grantable
        FROM pg_catalog.pg_roles AS r CROSS JOIN pg_catalog.pg_class AS c
        CROSS JOIN unnest(%s::text[]) AS p(privilege)
        WHERE r.oid = ANY(%s) AND c.oid = ANY(%s)
    """, (list(_TABLE_PRIVILEGES), list(roles.values()), [relations[name] for name in tables]))
    _require(len(rows) == 7 * len(tables) * len(_TABLE_PRIVILEGES))
    for row in rows:
        group, table, privilege = subjects[row["rolname"]], row["relname"], row["privilege"]
        allowed = (group == _OWNER or privilege in ("SELECT", "DELETE")
                   and (group == "finset_runtime" and table in TABLES or group == "finset_maintenance" and table == VIEW))
        _require(row["allowed"] == allowed and row["grantable"] == (group == _OWNER))
    rows = _rows(connection, """
        SELECT r.rolname, c.relname, col.attname, p.privilege,
               pg_catalog.has_column_privilege(r.oid, c.oid, col.attnum, p.privilege) AS allowed,
               pg_catalog.has_column_privilege(r.oid, c.oid, col.attnum, p.privilege || ' WITH GRANT OPTION') AS grantable
        FROM pg_catalog.pg_roles AS r CROSS JOIN pg_catalog.pg_class AS c
        JOIN pg_catalog.pg_attribute AS col ON col.attrelid = c.oid AND col.attnum > 0
        CROSS JOIN unnest(%s::text[]) AS p(privilege)
        WHERE r.oid = ANY(%s) AND c.oid = ANY(%s)
    """, (list(_COLUMN_PRIVILEGES), list(roles.values()), [relations[name] for name in tables]))
    _require(len(rows) == 7 * 107 * len(_COLUMN_PRIVILEGES))
    for row in rows:
        group, table, field, privilege = (subjects[row["rolname"]], row["relname"], row["attname"], row["privilege"])
        allowed = group == _OWNER
        if group == "finset_runtime" and table in TABLES:
            allowed = (privilege == "SELECT" or privilege == "INSERT" and field in schema.runtime_insert[table]
                       or privilege == "UPDATE" and field in schema.runtime_update[table])
        elif group == "finset_maintenance" and table == VIEW:
            allowed = (privilege == "SELECT" or privilege == "INSERT" and field in _MAINTENANCE_INSERT
                       or privilege == "UPDATE" and field in _MAINTENANCE_UPDATE)
        _require(row["allowed"] == allowed and row["grantable"] == (group == _OWNER))
    rows = _rows(connection, """
        SELECT r.rolname, p.proname, pg_catalog.has_function_privilege(r.oid, p.oid, 'EXECUTE') AS allowed,
               pg_catalog.has_function_privilege(r.oid, p.oid, 'EXECUTE WITH GRANT OPTION') AS grantable
        FROM pg_catalog.pg_roles AS r CROSS JOIN pg_catalog.pg_proc AS p
        WHERE r.oid = ANY(%s) AND p.oid = ANY(%s)
    """, (list(roles.values()), list(functions.values())))
    _require(len(rows) == 56)
    for row in rows:
        _require(row["allowed"] == row["grantable"] == (row["rolname"] == _OWNER))


def check_readiness(factory):
    """Attest the exact contract or raise a sanitized SafetyError; never repair it.

    This is an eventual, explicitly authorized runtime entry point. Importing the
    module performs no catalog checks, authentication, or connection attempts.
    """
    __tracebackhide__ = True
    stage = "frozen schema"
    try:
        schema = manifest()
        tables, indexes = _expected(schema)
        stage = "migrator identity"
        with factory._readiness_connection("migrator") as connection:
            _identity(connection, "migrator")
            _command(connection, "SET LOCAL search_path = pg_catalog, pg_temp")
            stage = "roles and memberships"
            roles = _roles(connection)
            stage = "owner assumption"
            _command(connection, "SET LOCAL ROLE finset_owner")
            _identity(connection, "migrator", _OWNER)
            stage = "object inventory and ownership"
            relations = _inventory(connection, roles, tables, indexes)
            stage = "function definitions"
            functions = _functions(connection, schema, roles)
            stage = "infrastructure privileges"
            _infrastructure_access(connection, roles)
            stage = "table column and function privileges"
            _object_access(connection, schema, tables, relations, functions, roles)
            stage = "columns and defaults"
            columns = _columns(connection, tables, relations)
            stage = "constraints"
            constraints = _constraints(connection, schema, tables, relations, columns)
            stage = "indexes"
            _indexes(connection, tables, indexes, relations, columns)
            stage = "triggers"
            _triggers(connection, schema, relations, functions, constraints)
            stage = "maintenance view"
            _view(connection, relations)
            stage = "Alembic revision"
            history = _rows(connection, "SELECT version_num FROM public.alembic_version LIMIT 2")
            _require(history == [{"version_num": REVISION}])
            stage = "owner reset"
            _command(connection, "RESET ROLE")
            _identity(connection, "migrator")
            # Errors before RESET leave cleanup to the factory's unconditional
            # outer rollback, including when a failed statement aborts the SQL transaction.
        for role in ("runtime", "maintenance"):
            stage = role + " identity"
            with factory._readiness_connection(role) as connection:
                _identity(connection, role)
        return {
            "ready": True, "database": DATABASE, "revision": REVISION, "read_only": True,
            "roles": 7, "tables": 9, "columns": 100, "views": 1,
            "constraints": {"foreign_keys": 15, "checks": 99, "primary_keys": 9, "unique": 8},
            "indexes": {"declared": 15, "backing": 17, "application": 32, "total": 33},
            "functions": 8, "triggers": 23, "deferred_triggers": 2,
            "runtime_insert_columns": 54, "runtime_update_columns": 51,
        }
    except Exception as error:
        state = getattr(error, "sqlstate", None)
        suffix = " (SQLSTATE " + state + ")" if isinstance(state, str) and re.fullmatch(r"[0-9A-Z]{5}", state) else ""
        raise SafetyError("FinSet readiness failed at " + stage + suffix + ".") from None
