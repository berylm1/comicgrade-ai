"""A small in-memory stand-in for the supabase-py client used by the routes.

Covers the query builder calls the backend makes (select, eq, in_, gte, order,
range, maybe_single, insert, upsert, update, delete), auth.get_user, and a
storage bucket. Behaves like postgrest-py 0.19 where it matters, for example
maybe_single() returning None when no row matches.
"""
from __future__ import annotations

import copy
import itertools
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Optional

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "profiles": ("id",),
    "comics": ("id",),
    "price_history": ("id",),
    "grade_reports": ("comic_id",),
    "portfolio_snapshots": ("user_id", "snapshot_date", "lens"),
    "series": ("id",),
    "series_issues": ("series_id", "issue_number"),
}

DEFAULTS: dict[str, dict[str, Any]] = {
    "comics": {"publisher": "Unknown", "grade_type": "raw", "cover_image_url": None,
               "estimated_grade": None, "current_market_value": None, "slab_cert_number": None,
               "year": None, "key_note": None, "series_id": None, "format": "single_issue"},
    "price_history": {"source": "manual"},
    "grade_reports": {"defects": [], "exterior_only": True, "source": "estimate", "photos_used": 1},
}


@dataclass
class Response:
    data: Any
    count: Optional[int] = None


class Query:
    def __init__(self, db: "FakeSupabase", table: str):
        self.db = db
        self.table = table
        self.filters: list = []
        self.orders: list[tuple[str, bool]] = []
        self.op = "select"
        self.payload: Any = None
        self.single = False
        self.window: Optional[tuple[int, int]] = None
        self.on_conflict: Optional[tuple[str, ...]] = None
        self.ignore_duplicates = False

    # ---- verbs
    def select(self, *_cols, **_kw):
        self.op = "select"
        return self

    def insert(self, payload, **_kw):
        self.op, self.payload = "insert", payload
        return self

    def upsert(self, payload, *, on_conflict: str = "", ignore_duplicates: bool = False, **_kw):
        self.op, self.payload = "upsert", payload
        if on_conflict:
            self.on_conflict = tuple(c.strip() for c in on_conflict.split(","))
        self.ignore_duplicates = ignore_duplicates
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    # ---- filters / modifiers
    def eq(self, col, value):
        self.filters.append(lambda r: str(r.get(col)) == str(value))
        return self

    def in_(self, col, values):
        allowed = {str(v) for v in values}
        self.filters.append(lambda r: str(r.get(col)) in allowed)
        return self

    def gte(self, col, value):
        self.filters.append(lambda r: r.get(col) is not None and str(r.get(col)) >= str(value))
        return self

    def order(self, col, desc: bool = False, **_kw):
        self.orders.append((col, desc))
        return self

    def range(self, start: int, end: int):
        self.window = (start, end)
        return self

    def maybe_single(self):
        self.single = True
        return self

    # ---- execution
    def _matches(self, row) -> bool:
        return all(f(row) for f in self.filters)

    def _key(self, row, cols=None):
        return tuple(str(row.get(c)) for c in (cols or PRIMARY_KEYS[self.table]))

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "select":
            out = [copy.deepcopy(r) for r in rows if self._matches(r)]
            for col, desc in reversed(self.orders):
                out.sort(key=lambda r: (r.get(col) is None, str(r.get(col))), reverse=desc)
            if self.window:
                out = out[self.window[0] : self.window[1] + 1]
            if self.single:
                if not out:
                    return None
                return Response(out[0])
            return Response(out)
        if self.op == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            saved = [self.db._new_row(self.table, item) for item in items]
            rows.extend(saved)
            return Response(copy.deepcopy(saved))
        if self.op == "upsert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            for item in items:
                cols = self.on_conflict or PRIMARY_KEYS[self.table]
                existing = next(
                    (r for r in rows if all(c in item for c in cols) and self._key(r, cols) == self._key(item, cols)),
                    None,
                )
                if existing is not None:
                    if not self.ignore_duplicates:
                        existing.update(copy.deepcopy(item))
                        out.append(copy.deepcopy(existing))
                else:
                    row = self.db._new_row(self.table, item)
                    rows.append(row)
                    out.append(copy.deepcopy(row))
            return Response(out)
        if self.op == "update":
            out = []
            for r in rows:
                if self._matches(r):
                    r.update(copy.deepcopy(self.payload))
                    out.append(copy.deepcopy(r))
            return Response(out)
        if self.op == "delete":
            gone = [r for r in rows if self._matches(r)]
            self.db.tables[self.table] = [r for r in rows if not self._matches(r)]
            if self.table == "comics":  # on delete cascade
                ids = {r["id"] for r in gone}
                for child in ("price_history", "grade_reports"):
                    self.db.tables[child] = [
                        r for r in self.db.tables.get(child, []) if r.get("comic_id") not in ids
                    ]
            return Response(copy.deepcopy(gone))
        raise AssertionError(self.op)


class _Bucket:
    def __init__(self, store: dict, name: str):
        self.store, self.name = store, name

    def upload(self, path, payload, _opts=None):
        self.store[(self.name, path)] = payload
        return SimpleNamespace(path=path)

    def get_public_url(self, path):
        return f"https://storage.test/{self.name}/{path}"


@dataclass
class FakeSupabase:
    tables: dict[str, list[dict]] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)  # access token -> user id
    objects: dict = field(default_factory=dict)

    def __post_init__(self):
        self._ids = itertools.count(1)
        fake = self

        class _Auth:
            def get_user(self, jwt):
                if jwt not in fake.tokens:
                    raise RuntimeError("invalid JWT")
                return SimpleNamespace(user=SimpleNamespace(id=fake.tokens[jwt]))

        class _Storage:
            def from_(self, name):
                return _Bucket(fake.objects, name)

        self.auth = _Auth()
        self.storage = _Storage()

    def table(self, name: str) -> Query:
        return Query(self, name)

    def _new_row(self, table: str, item: dict) -> dict:
        row = {**DEFAULTS.get(table, {}), **copy.deepcopy(item)}
        if table == "price_history":
            row.setdefault("id", next(self._ids))
        elif "id" in PRIMARY_KEYS.get(table, ()):
            row.setdefault("id", str(uuid.uuid4()))
        if table in ("comics", "grade_reports", "series"):
            row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        return row

    def rows(self, table: str) -> list[dict]:
        return self.tables.get(table, [])
