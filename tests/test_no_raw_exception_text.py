"""Fail when leasegrid_sync copies exception text into buyer strings.

Allowlisted log-only uses. These are not sinks, so the scanner ignores them:

- ``app.log_exception`` writes ``traceback.format_exception(...)`` to
  ``logs/sync-ui.log``. ``type(exc)`` and ``exc`` appear only in that write.
- ``install_excepthook`` calls ``sys.__excepthook__`` and ``log_exception``,
  then ``show_unexpected``. The window text is ``unexpected_error``.

A line comment ``# raw-ok:`` skips that line. Use it only for a log write.

Every ``except ... as <name>`` binding is tainted inside that handler, whatever
the name is. ``redact_furl(...)`` is tainted too: its return value still carries
part of an invite, so it must not flow into buyer text.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "leasegrid_sync"

SINK_CALLS = {"SyncError", "setText", "setPlainText", "print"}
EXC_NAMES = {"e", "exc", "err", "error", "exception"}
USER_FIELDS = {"credit_error", "credit_recover_error"}


@dataclass(frozen=True)
class Hit:
    path: str
    line: int
    text: str


def _is_redact_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "redact_furl"
    if isinstance(func, ast.Attribute):
        return func.attr == "redact_furl"
    return False


def _is_type_of_exc(node: ast.AST, tainted: set[str], is_exc, is_text) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "type"
        and bool(node.args)
        and (
            is_exc(node.args[0])
            or (isinstance(node.args[0], ast.Name) and node.args[0].id in tainted)
            or is_text(node.args[0])
        )
    )


class _Scanner:
    def __init__(self, lines: list[str], filename: str) -> None:
        self.lines = lines
        self.filename = filename
        self.hits: list[Hit] = []
        # Direct uses of these names are exception text. Attribute access such
        # as ``exc.banner()`` stays allowed: that string is already buyer copy.
        self.exc_names = set(EXC_NAMES)

    def _is_exc_name(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Name) and node.id in self.exc_names

    def scan(self, tree: ast.AST) -> list[Hit]:
        self._block(getattr(tree, "body", []), set())
        return self.hits

    def _skip(self, node: ast.AST) -> bool:
        lineno = getattr(node, "lineno", 0) or 0
        if lineno < 1 or lineno > len(self.lines):
            return False
        return "raw-ok:" in self.lines[lineno - 1]

    def _add(self, node: ast.AST) -> None:
        if self._skip(node):
            return
        lineno = getattr(node, "lineno", 0) or 0
        text = self.lines[lineno - 1].strip() if 1 <= lineno <= len(self.lines) else ""
        hit = Hit(self.filename, lineno, text)
        if hit not in self.hits:
            self.hits.append(hit)

    def _is_text(self, node: ast.AST, tainted: set[str]) -> bool:
        if isinstance(node, ast.Name):
            return node.id in tainted
        if isinstance(node, ast.Call):
            if _is_redact_call(node):
                return True
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"str", "repr"} and node.args:
                arg = node.args[0]
                if self._is_exc_name(arg) or self._is_text(arg, tainted):
                    return True
                if (
                    isinstance(arg, ast.Attribute)
                    and arg.attr in {"reason", "args"}
                    and (self._is_exc_name(arg.value) or self._is_text(arg.value, tainted))
                ):
                    return True
            if isinstance(func, ast.Attribute):
                if func.attr == "read" and (
                    self._is_exc_name(func.value) or self._is_text(func.value, tainted)
                ):
                    return True
                if func.attr == "format" and any(
                    self._value_is_raw(arg, tainted) for arg in node.args
                ):
                    return True
                if self._is_text(func.value, tainted):
                    return True
            return False
        if isinstance(node, ast.Attribute):
            # proc.stderr / proc.stdout. sys.stderr is the CLI stream, not a leak.
            if node.attr in {"stderr", "stdout"} and not (
                isinstance(node.value, ast.Name) and node.value.id == "sys"
            ):
                return True
            if node.attr in {"args", "reason"} and (
                self._is_exc_name(node.value) or self._is_text(node.value, tainted)
            ):
                return True
            if node.attr == "__name__" and _is_type_of_exc(
                node.value, tainted, self._is_exc_name, lambda n: self._is_text(n, tainted)
            ):
                return True
            return self._is_text(node.value, tainted)
        if isinstance(node, ast.Subscript):
            return self._is_text(node.value, tainted)
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if not isinstance(part, ast.FormattedValue):
                    continue
                value = part.value
                if isinstance(value, ast.Name) and (
                    value.id in self.exc_names or value.id in tainted
                ):
                    return True
                if self._is_text(value, tainted):
                    return True
            return False
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return self._value_is_raw(node.right, tainted) or self._is_text(node.left, tainted)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self._is_text(node.left, tainted) or self._is_text(node.right, tainted)
        if isinstance(node, ast.BoolOp):
            return any(self._is_text(item, tainted) for item in node.values)
        if isinstance(node, ast.IfExp):
            return self._is_text(node.body, tainted) or self._is_text(node.orelse, tainted)
        return False

    def _value_is_raw(self, node: ast.AST, tainted: set[str]) -> bool:
        if isinstance(node, ast.Name) and (node.id in self.exc_names or node.id in tainted):
            return True
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return any(self._value_is_raw(elt, tainted) for elt in node.elts)
        return self._is_text(node, tainted)

    def _arg_is_raw(self, node: ast.AST, tainted: set[str]) -> bool:
        if isinstance(node, ast.Name) and node.id in self.exc_names:
            return True
        return self._is_text(node, tainted)

    def _flag_calls(self, expr: ast.AST, tainted: set[str]) -> None:
        for child in ast.walk(expr):
            if isinstance(child, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            else:
                continue
            if name not in SINK_CALLS:
                continue
            args = list(child.args) + [kw.value for kw in child.keywords]
            if any(self._arg_is_raw(arg, tainted) for arg in args):
                self._add(child)

    def _note_assign(self, stmt: ast.AST, tainted: set[str]) -> None:
        targets: list[ast.AST] = []
        value: ast.AST | None = None
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
            value = stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            targets = [stmt.target]
            value = stmt.value
        elif isinstance(stmt, ast.AugAssign):
            targets = [stmt.target]
            value = stmt.value
        if value is None:
            return
        raw = self._arg_is_raw(value, tainted)
        for target in targets:
            if isinstance(target, ast.Name) and raw:
                tainted.add(target.id)
                if target.id in USER_FIELDS:
                    self._add(stmt)
            elif isinstance(target, ast.Attribute) and target.attr in USER_FIELDS and raw:
                self._add(stmt)

    def _owned_exprs(self, stmt: ast.AST) -> list[ast.AST]:
        exprs: list[ast.AST] = []
        for name, field in ast.iter_fields(stmt):
            if name in {"body", "orelse", "finalbody"}:
                continue
            if isinstance(field, ast.AST) and not isinstance(field, ast.stmt):
                exprs.append(field)
            elif isinstance(field, list):
                for item in field:
                    if isinstance(item, ast.ExceptHandler):
                        if item.type is not None:
                            exprs.append(item.type)
                    elif isinstance(item, ast.AST) and not isinstance(item, ast.stmt):
                        exprs.append(item)
        return exprs

    def _inner_blocks(self, stmt: ast.AST) -> list[list[ast.stmt]]:
        blocks: list[list[ast.stmt]] = []
        for name in ("body", "orelse", "finalbody"):
            block = getattr(stmt, name, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                blocks.append(block)
        return blocks

    def _scan_handlers(self, stmt: ast.AST, tainted: set[str]) -> None:
        """Treat each ``except ... as <name>`` like ``exc`` inside that handler.

        The binding is exception text when it is interpolated. ``name.banner()``
        stays allowed. Python deletes the binding when the handler ends, so the
        name does not stay tainted. An assignment of that text still flows out.
        """
        for handler in getattr(stmt, "handlers", []) or []:
            added = None
            if handler.name and handler.name not in self.exc_names:
                self.exc_names.add(handler.name)
                added = handler.name
            self._block(handler.body, tainted)
            if added is not None:
                self.exc_names.discard(added)

    def _block(self, stmts: list[ast.stmt], tainted: set[str]) -> None:
        try_types = (ast.Try,)
        if hasattr(ast, "TryStar"):
            try_types = (ast.Try, ast.TryStar)
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._block(stmt.body, set())
                continue
            for expr in self._owned_exprs(stmt):
                self._flag_calls(expr, tainted)
            self._note_assign(stmt, tainted)
            if isinstance(stmt, try_types):
                for block in self._inner_blocks(stmt):
                    self._block(block, tainted)
                self._scan_handlers(stmt, tainted)
                continue
            for block in self._inner_blocks(stmt):
                self._block(block, tainted)


def scan_source(src: str, filename: str = "<src>") -> list[Hit]:
    tree = ast.parse(src)
    return _Scanner(src.splitlines(), filename).scan(tree)


def scan_package(root: Path) -> list[Hit]:
    hits: list[Hit] = []
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits.extend(scan_source(text, str(path.relative_to(ROOT))))
    return hits


def test_sync_package_has_no_raw_exception_text():
    hits = scan_package(PACKAGE)
    assert not hits, "\n".join("%s:%s: %s" % (hit.path, hit.line, hit.text) for hit in hits)


def test_scanner_flags_planted_exception_text():
    samples = [
        "def f(exc):\n    raise SyncError(f'bad {exc}', 'next')\n",
        "def f(e):\n    raise SyncError(f'bad {e}', 'next')\n",
        "def f(err):\n    raise SyncError(f'bad {err}', 'next')\n",
        "def f(exc):\n    raise SyncError('bad %s' % str(exc), 'next')\n",
        "def f(exc):\n    raise SyncError('Could not start Magic Folder: %s' % exc, 'next')\n",
        "def f(exc):\n    raise SyncError('bad %s' % repr(exc), 'next')\n",
        "def f(exc):\n    raise SyncError('bad %s' % type(exc).__name__, 'next')\n",
        "def f(exc):\n    raise SyncError('bad %s' % (exc.args,), 'next')\n",
        "def f(exc):\n    detail = str(exc.reason)\n    raise SyncError('bad', detail)\n",
        "def f(exc):\n    detail = exc.read().decode('utf-8')[:300]\n    raise SyncError('bad', detail)\n",
        "def f(proc):\n    err = (proc.stderr or proc.stdout or '').strip()\n"
        "    raise SyncError('bad %s' % err.split('\\n')[0], 'next')\n",
        "def f(exc):\n    credit_error = '%s' % str(exc)\n",
        "def f(exc):\n    self.status.setText(str(exc))\n",
        "def f():\n    try:\n        pass\n    except OSError as ex:\n"
        "        raise SyncError('bad %s' % ex, 'next')\n",
        "def f(furl):\n    raise SyncError('bad %s' % redact_furl(furl), 'next')\n",
        "def f(furl):\n    self.status.setText(redact_furl(furl))\n",
    ]
    for src in samples:
        hits = scan_source(src, "plant.py")
        assert hits, src


def test_scanner_allows_log_and_safe_banner():
    src = (
        "def log_exception(exc):\n"
        "    f.write(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))\n"
        "def show(exc):\n"
        "    self.status.setText(exc.banner())\n"
        "    print(exc.banner(), file=sys.stderr)\n"
        "    raise SyncError('Magic Folder API error (%s).' % exc.code, 'Retry.')\n"
        "def classify(proc):\n"
        "    raw = (proc.stderr or proc.stdout or '').strip()\n"
        "    raise join_process_failure(raw)\n"
        "def fixed():\n"
        "    try:\n"
        "        pass\n"
        "    except OSError as ex:\n"
        "        raise SyncError('fixed text', 'next')\n"
        "def logged(furl):\n"
        "    redacted = redact_furl(furl)\n"
        "    f.write(redacted)\n"
    )
    assert scan_source(src, "safe.py") == []
