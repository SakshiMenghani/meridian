import json
from dataclasses import dataclass, field
from datetime import datetime

import duckdb

from app.security import json_safe

MAX_ROWS = 200


class SqlRejected(ValueError):
    pass


@dataclass(frozen=True)
class Link:
    left_table: str
    left_column: str
    right_table: str
    right_column: str

    def matches(self, a: tuple[str, str], b: tuple[str, str]) -> bool:
        left = (self.left_table.lower(), self.left_column.lower())
        right = (self.right_table.lower(), self.right_column.lower())
        pair = {(a[0].lower(), a[1].lower()), (b[0].lower(), b[1].lower())}
        return pair == {left, right}

    def label(self) -> str:
        return f'"{self.left_table}"."{self.left_column}" = "{self.right_table}"."{self.right_column}"'


@dataclass
class Checked:
    sql: str
    tables: list[str]
    links_used: list[Link] = field(default_factory=list)


@dataclass
class _Walk:
    base_tables: list[dict] = field(default_factory=list)
    ctes: dict[str, set[str]] = field(default_factory=dict)
    equalities: list[tuple[list[str], list[str], list[str] | None]] = field(default_factory=list)
    strong: list[tuple[list[str], list[str], list[str] | None]] = field(default_factory=list)
    joins: list[dict] = field(default_factory=list)
    table_functions: list[str] = field(default_factory=list)


def check_sql(sql: str, tables, links: list[Link]) -> Checked:
    """Parse with DuckDB and enforce read-only, known tables, and confirmed cross-source joins."""
    stripped = (sql or "").strip().rstrip(";").strip()
    if not stripped:
        raise SqlRejected("The plan did not include a query.")
    conn = duckdb.connect(":memory:")
    try:
        tree = json.loads(conn.execute("SELECT json_serialize_sql(?)", [stripped]).fetchone()[0])
    finally:
        conn.close()
    if tree.get("error"):
        raise SqlRejected(f"Only one read-only SELECT is allowed. {tree.get('error_message', '')}".strip())
    statements = tree.get("statements") or []
    if len(statements) != 1:
        raise SqlRejected("Send exactly one SELECT statement.")

    walk = _Walk()
    _visit(statements[0], walk)
    if walk.table_functions:
        raise SqlRejected(f"Table functions are not allowed: {', '.join(sorted(set(walk.table_functions)))}.")

    known = {table.sql_name.lower(): table for table in tables}
    cte_names = set(walk.ctes)
    used: list[str] = []
    for ref in walk.base_tables:
        name = ref["table_name"].lower()
        if name in cte_names:
            continue
        if name not in known:
            available = ", ".join(sorted(known))
            raise SqlRejected(f'Unknown table "{ref["table_name"]}". Available tables: {available}.')
        if name not in used:
            used.append(name)

    source_of = {name: known[name].source_name for name in known}
    aliases = _aliases(walk.base_tables)
    columns = {name: {column.lower() for column, _ in known[name].columns} for name in known}

    def expand(name: str) -> list[str]:
        if name in known:
            return [name]
        return sorted(item for item in walk.ctes.get(name, set()) if item in known)

    def resolve(parts: list[str], scope: list[str] | None) -> tuple[str, str] | None:
        lowered = [part.lower() for part in parts]
        column = lowered[-1]
        if len(lowered) >= 2:
            pool = expand(aliases.get(lowered[-2], lowered[-2]))
        else:
            names = scope if scope is not None else used
            pool = sorted({base for name in names for base in expand(aliases.get(name.lower(), name.lower()))})
        matches = [name for name in pool if column in columns.get(name, set())]
        if len(matches) == 1:
            return matches[0], column
        return None

    multi_source = len({source_of[name] for name in used}) > 1

    def pairs(equalities) -> list[tuple[tuple[str, str], tuple[str, str]]]:
        out = []
        for left, right, right_scope in equalities:
            a, b = resolve(left, None), resolve(right, right_scope)
            if (a is None or b is None) and multi_source and right_scope is not None:
                raise SqlRejected("Qualify the columns in IN (SELECT ...) with their table names so the link can be checked.")
            if a is None or b is None or a[0] == b[0]:
                continue
            out.append((a, b))
        return out

    resolved_pairs = pairs(walk.equalities)
    strong_pairs = pairs(walk.strong)

    links_used: list[Link] = []
    for a, b in resolved_pairs:
        if source_of[a[0]] == source_of[b[0]]:
            continue
        link = next((item for item in links if item.matches(a, b)), None)
        if link is None:
            raise SqlRejected(
                f'"{a[0]}"."{a[1]}" = "{b[0]}"."{b[1]}" connects {source_of[a[0]]} and {source_of[b[0]]} '
                "without a confirmed link. Use only the confirmed links."
            )
        if link not in links_used:
            links_used.append(link)

    for join in walk.joins:
        left_sources = _sources(join["left"], walk.ctes, source_of)
        right_sources = _sources(join["right"], walk.ctes, source_of)
        if not left_sources or not right_sources or left_sources == right_sources:
            continue
        left_tables = {base for name in _subtree_tables(join["left"], walk.ctes) for base in expand(name)}
        right_tables = {base for name in _subtree_tables(join["right"], walk.ctes) for base in expand(name)}
        bridged = any(
            (a[0] in left_tables and b[0] in right_tables) or (a[0] in right_tables and b[0] in left_tables)
            for a, b in strong_pairs
        )
        if not bridged:
            raise SqlRejected(
                f"This query combines {', '.join(sorted(left_sources | right_sources))} without joining on a confirmed link. "
                "Join the base tables directly with JOIN ... ON a confirmed link."
            )
    return Checked(sql=stripped, tables=used, links_used=links_used)


def run_sql(sql: str, tables, max_rows: int = MAX_ROWS) -> tuple[list[dict], list[str], bool]:
    conn = duckdb.connect(":memory:")
    try:
        for table in tables:
            conn.register(table.sql_name, table.frame)
        conn.execute("SET enable_external_access = false")
        conn.execute("SET lock_configuration = true")
        result = conn.execute(sql)
        keys = [item[0] for item in result.description]
        fetched = result.fetchmany(max_rows + 1)
    except duckdb.Error as exc:
        raise SqlRejected(f"DuckDB could not run the query: {str(exc).splitlines()[0]}") from exc
    finally:
        conn.close()
    rows = [{key: _cell(value) for key, value in zip(keys, row, strict=True)} for row in fetched[:max_rows]]
    return rows, keys, len(fetched) > max_rows


def _cell(value):
    if isinstance(value, datetime) and (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
        return value.date().isoformat()
    return json_safe(value)


def _visit(node, walk: _Walk) -> None:
    if isinstance(node, list):
        for item in node:
            _visit(item, walk)
        return
    if not isinstance(node, dict):
        return
    kind = node.get("type")
    if kind == "BASE_TABLE":
        walk.base_tables.append(node)
    elif kind == "TABLE_FUNCTION":
        function = node.get("function") or {}
        walk.table_functions.append(str(function.get("function_name") or "table function"))
    elif kind == "JOIN":
        walk.joins.append(node)
        left = _subtree_tables_raw(node.get("left"))
        right = _subtree_tables_raw(node.get("right"))
        for column in node.get("using_columns") or []:
            for a in left:
                for b in right:
                    pair = ([a, column], [b, column], None)
                    walk.equalities.append(pair)
                    walk.strong.append(pair)
        walk.strong.extend(item for item in map(_equality, _conjuncts(node.get("condition"))) if item)
    if node.get("where_clause"):
        walk.strong.extend(item for item in map(_equality, _conjuncts(node["where_clause"])) if item)
    found = _equality(node)
    if found:
        walk.equalities.append(found)
    cte_map = (node.get("cte_map") or {}).get("map") or []
    for entry in cte_map:
        inner = _Walk()
        _visit(entry.get("value"), inner)
        walk.ctes[str(entry.get("key")).lower()] = {ref["table_name"].lower() for ref in inner.base_tables}
    for key, value in node.items():
        if key == "cte_map":
            for entry in cte_map:
                _visit(entry.get("value"), walk)
            continue
        if isinstance(value, (dict, list)):
            _visit(value, walk)


def _conjuncts(node) -> list[dict]:
    if not isinstance(node, dict):
        return []
    if node.get("class") == "CONJUNCTION" and node.get("type") == "CONJUNCTION_AND":
        return [part for child in node.get("children") or [] for part in _conjuncts(child)]
    return [node]


def _equality(node) -> tuple[list[str], list[str], list[str] | None] | None:
    if not isinstance(node, dict):
        return None
    if node.get("class") == "COMPARISON" and node.get("type") == "COMPARE_EQUAL":
        left, right = node.get("left") or {}, node.get("right") or {}
        if left.get("class") == "COLUMN_REF" and right.get("class") == "COLUMN_REF":
            return left["column_names"], right["column_names"], None
    if node.get("class") == "SUBQUERY" and node.get("subquery_type") == "ANY":
        child = node.get("child") or {}
        select_node = (node.get("subquery") or {}).get("node") or {}
        inner = select_node.get("select_list") or []
        if child.get("class") == "COLUMN_REF" and len(inner) == 1 and inner[0].get("class") == "COLUMN_REF":
            return child["column_names"], inner[0]["column_names"], _subtree_tables_raw(select_node.get("from_table"))
    return None


def _aliases(base_tables: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for ref in base_tables:
        name = ref["table_name"].lower()
        out[name] = name
        if ref.get("alias"):
            out[ref["alias"].lower()] = name
    return out


def _subtree_tables_raw(node) -> list[str]:
    found: list[str] = []

    def walk(item):
        if isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            if item.get("type") == "BASE_TABLE":
                found.append(item.get("alias") or item["table_name"])
                return
            if item.get("type") == "SUBQUERY":
                return
            for value in item.values():
                if isinstance(value, (dict, list)):
                    walk(value)

    walk(node)
    return found


def _subtree_tables(node, ctes: dict[str, set[str]]) -> set[str]:
    out: set[str] = set()

    def walk(item):
        if isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            if item.get("type") == "BASE_TABLE":
                name = item["table_name"].lower()
                out.add(name)
                return
            for value in item.values():
                if isinstance(value, (dict, list)):
                    walk(value)

    walk(node)
    return out


def _sources(node, ctes: dict[str, set[str]], source_of: dict[str, str]) -> set[str]:
    sources: set[str] = set()
    for name in _subtree_tables(node, ctes):
        if name in ctes:
            sources.update(source_of[item] for item in ctes[name] if item in source_of)
        elif name in source_of:
            sources.add(source_of[name])
    return sources
