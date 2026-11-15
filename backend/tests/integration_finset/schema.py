"""In-memory metadata from the pinned revision; never import or run a migration."""

import ast
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256

import sqlalchemy as sa

from .policy import BACKEND, REVISION, TABLES, SafetyError


SOURCE_SHA256 = "c231e71cdb1431e91216fa4a977cb248f5fd076a7fd4f9d84f964ff7b7f2fd99"
VIEW_COLUMNS = ("id", "name", "category_type", "archived_at", "created_at", "updated_at")
_CONSTRUCTORS = {
    name: getattr(sa, name) for name in (
        "Column", "Uuid", "String", "Text", "DateTime", "Integer", "CHAR",
        "SmallInteger", "LargeBinary", "Date", "BigInteger", "CheckConstraint",
        "PrimaryKeyConstraint", "UniqueConstraint", "ForeignKeyConstraint",
        "text", "literal_column",
    )
}


@dataclass(frozen=True)
class IndexSpec:
    table: str
    expressions: tuple[str, ...]
    unique: bool = False
    where: str | None = None
    nulls_not_distinct: bool = False


@dataclass(frozen=True)
class Manifest:
    tables: dict[str, sa.Table]
    functions: dict[str, tuple[str, str]]
    triggers: dict[tuple[str, str], str]
    immutable: dict[str, tuple[str, ...]]
    runtime_insert: dict[str, tuple[str, ...]]
    runtime_update: dict[str, tuple[str, ...]]
    indexes: dict[str, IndexSpec]


def _require(condition):
    if not condition:
        raise SafetyError("Frozen schema source is inconsistent.")


def canonical_source(source: bytes) -> bytes:
    """Normalize only CRLF in memory; BOM, whitespace, and final newlines remain pinned."""
    source = source.replace(b"\r\n", b"\n")
    _require(b"\r" not in source)
    return source


def _constructor(node):
    """Interpret only literal values and the reviewed SQLAlchemy constructors."""
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [_constructor(item) for item in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Call):
        function = node.func
        _require(isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name)
                 and function.value.id == "sa" and function.attr in _CONSTRUCTORS)
        _require(all(keyword.arg is not None for keyword in node.keywords))
        return _CONSTRUCTORS[function.attr](
            *(_constructor(item) for item in node.args),
            **{keyword.arg: _constructor(keyword.value) for keyword in node.keywords},
        )
    return ast.literal_eval(node)


def _operations(tree, function_name, operation):
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == function_name]
    _require(len(functions) == 1)
    for statement in functions[0].body:
        _require(isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call))
        call = statement.value
        _require(isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                 and call.func.value.id == "op" and call.func.attr == operation)
        _require(all(keyword.arg is not None for keyword in call.keywords))
        yield ([_constructor(item) for item in call.args],
               {keyword.arg: _constructor(keyword.value) for keyword in call.keywords})


def _trigger_value(node, names):
    """Small literal/comprehension interpreter, with no eval, imports, or op calls."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return names[node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        values = [_trigger_value(item, names) for item in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _trigger_value(node.left, names) + _trigger_value(node.right, names)
    if isinstance(node, ast.JoinedStr):
        return "".join(_trigger_value(item, names) for item in node.values)
    if isinstance(node, ast.FormattedValue):
        _require(node.conversion == -1 and node.format_spec is None)
        return str(_trigger_value(node.value, names))
    if isinstance(node, (ast.ListComp, ast.GeneratorExp)):
        _require(len(node.generators) == 1)
        generator = node.generators[0]
        _require(not generator.ifs and not generator.is_async)
        target = generator.target
        targets = target.elts if isinstance(target, ast.Tuple) else [target]
        _require(all(isinstance(item, ast.Name) for item in targets))
        result = []
        for value in _trigger_value(generator.iter, names):
            values = value if isinstance(target, ast.Tuple) else [value]
            _require(len(targets) == len(values))
            local = dict(names, **{item.id: item_value for item, item_value in zip(targets, values)})
            result.append(_trigger_value(node.elt, local))
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        _require(not node.keywords)
        function = node.func
        if (function.attr == "items" and isinstance(function.value, ast.Name)
                and function.value.id == "IMMUTABLE_COLUMNS" and not node.args):
            return names["IMMUTABLE_COLUMNS"].items()
        if (function.attr == "join" and isinstance(function.value, ast.Constant)
                and isinstance(function.value.value, str) and len(node.args) == 1):
            return function.value.value.join(_trigger_value(node.args[0], names))
    raise SafetyError("Unsupported frozen trigger expression.")


@lru_cache(maxsize=1)
def manifest():
    """Return the nine frozen base tables and their integrity/permission contract."""
    __tracebackhide__ = True
    try:
        source = canonical_source(
            (BACKEND / "migrations" / "versions" / "0001_initial_finset_schema.py").read_bytes()
        )
        _require(sha256(source).hexdigest() == SOURCE_SHA256)
        tree = ast.parse(source, filename="0001_initial_finset_schema.py")
        assignments = {node.targets[0].id: node.value for node in tree.body
                       if isinstance(node, ast.Assign) and len(node.targets) == 1
                       and isinstance(node.targets[0], ast.Name)}
        values = {name: ast.literal_eval(assignments[name]) for name in (
            "revision", "down_revision", "TABLE_ORDER", "FUNCTIONS", "IMMUTABLE_COLUMNS",
            "RUNTIME_INSERT_COLUMNS", "RUNTIME_UPDATE_COLUMNS",
        )}
        _require(values["revision"] == REVISION and values["down_revision"] is None)
        _require(set(values["TABLE_ORDER"]) == set(TABLES) and len(TABLES) == 9)
        metadata = sa.MetaData()
        tables = {}
        for args, kwargs in _operations(tree, "_create_tables", "create_table"):
            name, *elements = args
            _require(name in TABLES and name not in tables and kwargs == {"schema": "public"})
            tables[name] = sa.Table(name, metadata, *elements, **kwargs)
        _require(set(tables) == set(TABLES) and sum(len(table.c) for table in tables.values()) == 100)

        indexes = {}
        for args, kwargs in _operations(tree, "_create_indexes", "create_index"):
            name, table, expressions = args
            _require(table in tables and name not in indexes and kwargs.pop("schema") == "public")
            _require(set(kwargs) <= {"unique", "postgresql_where", "postgresql_nulls_not_distinct"})
            predicate = kwargs.get("postgresql_where")
            indexes[name] = IndexSpec(
                table, tuple(str(item) for item in expressions), kwargs.get("unique", False),
                None if predicate is None else str(predicate),
                kwargs.get("postgresql_nulls_not_distinct", False),
            )
        _require(len(indexes) == 15)

        immutable = values["IMMUTABLE_COLUMNS"]
        triggers = []
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "TRIGGERS"):
                triggers = _trigger_value(node.value, {"IMMUTABLE_COLUMNS": immutable})
            elif (isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name)
                  and node.target.id == "TRIGGERS"):
                _require(isinstance(node.op, ast.Add))
                triggers += _trigger_value(node.value, {"IMMUTABLE_COLUMNS": immutable})
        trigger_map = {(table, name): definition for table, name, definition in triggers}
        _require(len(triggers) == len(trigger_map) == 23 and len(values["FUNCTIONS"]) == 8)
        for mapping in (immutable, values["RUNTIME_INSERT_COLUMNS"], values["RUNTIME_UPDATE_COLUMNS"]):
            _require(set(mapping) == set(TABLES))
            for table, columns in mapping.items():
                _require(len(set(columns)) == len(columns) and set(columns) <= set(tables[table].c.keys()))
        _require(sum(map(len, values["RUNTIME_INSERT_COLUMNS"].values())) == 54)
        _require(sum(map(len, values["RUNTIME_UPDATE_COLUMNS"].values())) == 51)
        for table in TABLES:
            _require(not set(values["RUNTIME_UPDATE_COLUMNS"][table]) & set(immutable[table]))
            for mapping in ("RUNTIME_INSERT_COLUMNS", "RUNTIME_UPDATE_COLUMNS"):
                _require(not {"id", "created_at", "result_generation"} & set(values[mapping][table]))

        return Manifest(tables, values["FUNCTIONS"], trigger_map, immutable,
                        values["RUNTIME_INSERT_COLUMNS"], values["RUNTIME_UPDATE_COLUMNS"], indexes)
    except Exception:
        raise SafetyError("Frozen schema manifest is unavailable or inconsistent.") from None
