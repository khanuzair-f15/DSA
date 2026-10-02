#!/usr/bin/env python3
"""Structural time/space complexity analysis (standard library only).

How it works (per language):
  C++:    a small hand-written scanner + recursive-descent parser builds a
          statement-level IR (loops with init/cond/incr slices, if/else,
          decls with types, calls with receivers and argument slices) for the
          methods of ``class Solution`` only.  Complexity is then derived
          from that IR: nesting multiplies trip counts, sequential code
          takes the dominant term, real call operations contribute their
          documented cost.  No keyword counting.
  Python: the stdlib ``ast`` module is the parser; a scoped visitor builds
          the same kind of loop/call/allocation model.

Reported complexities always describe the SUBMITTED implementation
(worst case).  ``break``/``return`` never reduce a bound.  Confidence is
High/Medium/Low; callers display Low as ``Unknown``.

Never add per-problem special cases here: every rule must be a general
language/library rule.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Complexity vocabulary + algebra
# --------------------------------------------------------------------------

TIME_ORDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(m + n)", "O(mn)",
              "O(n^2)", "O(n^2 log n)", "O(n^3)", "O(2^n)", "Unknown"]
SPACE_ORDER = ["O(1)", "O(log n)", "O(n)", "O(m + n)", "O(mn)", "O(n^2)",
               "Unknown"]

_HIGH, _MED, _LOW = "High", "Medium", "Low"


def _worse(a: str, b: str) -> str:
    order = {_HIGH: 2, _MED: 1, _LOW: 0}
    return a if order[a] <= order[b] else b


class T:
    """One monomial: product of size vars with exponents, log factors, 2^n."""
    __slots__ = ("pows", "logs", "exp2", "src")

    def __init__(self, pows=(), logs: int = 0, exp2: bool = False,
                 src=frozenset()):
        self.pows = tuple(sorted(pows))
        self.logs = logs
        self.exp2 = exp2
        self.src = frozenset(src) or frozenset(v for v, _ in self.pows)

    def vars(self):
        return set(v for v, _ in self.pows)

    def deg(self):
        return sum(e for _, e in self.pows)

    def rank(self):
        return (1 if self.exp2 else 0, self.deg(), self.logs)

    def shape(self):
        return (tuple(sorted(e for _, e in self.pows)), self.logs, self.exp2)


def _tdisplay(t: T):
    pows, logs, exp2 = t.pows, t.logs, t.exp2
    if exp2:
        return "O(2^n)"
    if not pows:
        if logs <= 0:
            return "O(1)"
        return "O(log n)"
    if len(pows) == 1 and pows[0][1] == 1:
        if logs <= 0:
            return "O(n)"
        if logs == 1:
            return "O(n log n)"
        return None
    if len(pows) == 1 and pows[0][1] == 2 and logs <= 0:
        return "O(n^2)"
    if len(pows) == 1 and pows[0][1] == 2 and logs == 1:
        return "O(n^2 log n)"
    if len(pows) == 1 and pows[0][1] == 3 and logs <= 0:
        return "O(n^3)"
    if len(pows) == 2 and all(e == 1 for _, e in pows) and logs <= 0:
        return "O(mn)"
    return None


def _subsumed(a: T, b: T) -> bool:
    return (b.rank() > a.rank()
            and a.vars() <= (b.vars() | set(b.src)))


def _reduce(terms):
    """Reduce a sum of terms; return tuple or None if inexpressible."""
    terms = list(dict.fromkeys(
        (t.pows, t.logs, t.exp2, tuple(sorted(t.src))) for t in terms))
    ts = [T(p, l, e, s) for p, l, e, s in terms]
    # Merge same-shape superlinear terms over different input vars
    # (e.g. sort(s) + sort(t) -> a single n log n term).  Linear terms are
    # never merged: distinct linear vars display as O(m + n).
    groups: dict = {}
    for t in ts:
        if (t.deg() + t.logs > 1 or t.exp2) and not t.exp2:
            groups.setdefault(t.shape(), []).append(t)
    merged = []
    used = set()
    for shape, g in groups.items():
        varsets = {frozenset(t.vars()) for t in g}
        # Only single-var superlinear shapes merge (e.g. sort(s)+sort(t)
        # -> one n log n term).  Multi-var shapes stay distinct.
        if len(varsets) > 1 and all(len(t.pows) == 1 for t in g):
            allv = sorted({v for t in g for v in t.vars()})
            fresh = "mgd:" + "|".join(allv)
            rep = g[0]
            exps = sorted(e for _, e in rep.pows)
            nt = T(tuple([(fresh, e) for e in exps]), rep.logs, rep.exp2,
                   frozenset(allv))
            if _tdisplay(nt) is not None:
                merged.append(nt)
                used.update(id(t) for t in g)
    ts = [t for t in ts if id(t) not in used] + merged
    # Drop subsumed terms.
    kept = []
    for t in ts:
        if any(_subsumed(t, o) for o in ts if o is not t):
            continue
        kept.append(t)
    # Same-container-dim absorption: terms spanning only the dimensions
    # of one container (in:X#0, in:X#1, ...) are assumed to be the same
    # order (documented same-order-dim assumption).  A concentrated term
    # of rank >= absorbs a spread-out one of the same base, so
    # O(n^2) + O(mn) over a single matrix reports O(n^2) instead of
    # becoming inexpressible.  Purely linear distinct dims are never
    # merged here (O(m + n) stays expressible and precise).
    def _absorbs(a, b):
        ba = {_strip_base(v) for v in a.vars()}
        bb = {_strip_base(v) for v in b.vars()}
        if len(ba) != 1 or ba != bb:
            return False
        if a.rank() < b.rank():
            return False
        if a.rank() > b.rank():
            return True
        return len(b.vars()) > len(a.vars())
    absorbed = set()
    for a in kept:
        for b in kept:
            if a is b or id(b) in absorbed:
                continue
            if _absorbs(a, b):
                absorbed.add(id(b))
    kept = [t for t in kept if id(t) not in absorbed]
    if len(kept) > 8:
        return None
    if len(kept) == 1 and _tdisplay(kept[0]) is None:
        return None
    return tuple(kept)


def _all_linear_singletons(terms):
    return all(len(t.pows) == 1 and t.pows[0][1] == 1 and t.logs <= 0
               and not t.exp2 for t in terms)


def _display(terms) -> str | None:
    if terms is None or len(terms) == 0:
        return None
    if len(terms) == 1:
        return _tdisplay(terms[0])
    if all(t.logs > 0 and not t.pows and not t.exp2 for t in terms):
        return "O(log n)"
    if _all_linear_singletons(terms):
        varsets = {frozenset(t.vars()) for t in terms}
        if len(varsets) > 1:
            return "O(m + n)"
        return "O(n)"
    dom = max(terms, key=lambda t: t.rank())
    if all(t is dom or _subsumed(t, dom) for t in terms):
        return _tdisplay(dom)
    return None


class Cost:
    """A reduced sum of terms; None-terms means unanalyzable."""
    __slots__ = ("terms",)

    def __init__(self, terms):
        self.terms = terms  # tuple[T,...] or None

    def ok(self):
        return self.terms is not None


def _cost(*terms) -> Cost:
    r = _reduce(list(terms))
    return Cost(r)


C_ONE = _cost(T(()))
C_LOG = _cost(T((), 1))


def c_lin(v) -> Cost:
    return _cost(T(((v, 1),)))


def c_log(v) -> Cost:
    return _cost(T((), 1, False, frozenset((v,))))


def c_sort(v) -> Cost:
    return _cost(T(((v, 1),), 1))


def c_prod(vs) -> Cost:
    vs = list(dict.fromkeys(vs))
    if len(vs) == 1:
        return c_lin(vs[0])
    return _cost(T(tuple(sorted((v, 1) for v in vs))))


def seq(*costs) -> Cost:
    terms = []
    for c in costs:
        if c is None or not c.ok():
            return Cost(None)
        terms.extend(c.terms)
    return _cost(*terms)


def _add_var(t: T, v) -> T | None:
    d = dict(t.pows)
    d[v] = d.get(v, 0) + 1
    if sum(d.values()) > 3:
        return None
    if len(d) > 2:
        return None
    if t.exp2:
        return T(t.pows, t.logs, True, t.src | {v})
    nt = T(tuple(sorted(d.items())), t.logs, False, t.src | {v})
    return nt if _tdisplay(nt) is not None else None


def nest(trips, body: Cost) -> Cost:
    """Cost of running `body` once per trip of an enclosing loop."""
    kind = trips[0]
    if kind == "const":
        return body
    if body is None or not body.ok():
        return Cost(None)
    if kind == "lin":
        v = trips[1]
        out = []
        for t in body.terms:
            nt = _add_var(t, v)
            if nt is None:
                return Cost(None)
            out.append(nt)
        return _cost(*out)
    if kind == "prod":
        cur = body
        for v in trips[1]:
            cur = nest(("lin", v), cur)
            if not cur.ok():
                return Cost(None)
        return cur
    if kind == "log":
        for t in body.terms:
            if t.pows or t.exp2:
                return Cost(None)
        return seq(body, c_log(trips[1]))
    return Cost(None)


def show(cost: Cost):
    if cost is None or not cost.ok():
        return None
    return _display(cost.terms)

# --------------------------------------------------------------------------
# C++ frontend: scanner + recursive-descent parser -> statement IR
# --------------------------------------------------------------------------

_CPP_KW = {
    'if', 'else', 'for', 'while', 'do', 'return', 'break', 'continue',
    'switch', 'case', 'default', 'new', 'delete', 'class', 'struct',
    'public', 'private', 'protected', 'const', 'static', 'void', 'int',
    'long', 'short', 'char', 'bool', 'float', 'double', 'unsigned',
    'signed', 'size_t', 'auto', 'true', 'false', 'nullptr', 'NULL',
    'template', 'typename', 'namespace', 'using', 'sizeof', 'this',
    'operator', 'try', 'catch', 'throw', 'typedef', 'enum', 'extern',
    'inline', 'virtual', 'volatile', 'constexpr', 'decltype', 'noexcept',
    'goto', 'wchar_t', 'char16_t', 'char32_t',
}
_CPP_TYPES = {
    'void', 'int', 'long', 'short', 'char', 'bool', 'float', 'double',
    'unsigned', 'signed', 'size_t', 'string', 'vector', 'map', 'set',
    'unordered_map', 'unordered_set', 'stack', 'queue', 'priority_queue',
    'pair', 'list', 'deque', 'array', 'multimap', 'multiset',
    'unordered_multiset', 'unordered_multimap', 'string_view', 'auto',
}
_CPP_SCALAR_TYPES = {
    'void', 'int', 'long', 'short', 'char', 'bool', 'float', 'double',
    'unsigned', 'signed', 'size_t', 'wchar_t', 'char16_t', 'char32_t',
}

_ORDERED_ASSOC = {'map', 'set', 'multimap', 'multiset'}
_HASH_ASSOC = {'unordered_map', 'unordered_set', 'unordered_multimap',
               'unordered_multiset'}


class _PError(Exception):
    pass


def _scan_cpp(text):
    toks = []
    i, n = 0, len(text)
    at_bol = True
    while i < n:
        c = text[i]
        if c == '\n':
            at_bol = True
            i += 1
            continue
        if c in ' \t\r\v\f':
            i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == '#' and at_bol:
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        at_bol = False
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == '\\' else 1
            toks.append(('lit', '""'))
            i = min(j + 1, n)
            continue
        if c == "'":
            j = i + 1
            while j < n and text[j] != "'":
                j += 2 if text[j] == '\\' else 1
            toks.append(('lit', "'c'"))
            i = min(j + 1, n)
            continue
        if c.isalpha() or c == '_' or c == '$':
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in '_$'):
                j += 1
            toks.append(('id', text[i:j]))
            i = j
            continue
        if c.isdigit() or (c == '.' and i + 1 < n and text[i + 1].isdigit()):
            j = i + 1
            if c == '0' and j < n and text[j] in 'xX':
                j += 1
                while j < n and (text[j].isalnum() or text[j] == "'"):
                    j += 1
            else:
                while j < n and (text[j].isalnum() or text[j] in "._'"):
                    j += 1
            toks.append(('num', text[i:j]))
            i = j
            continue
        for op in ('<<=', '>>=', '->*', '->', '::', '<<', '>>', '<=', '>=',
                   '==', '!=', '&&', '||', '++', '--', '+=', '-=', '*=',
                   '/=', '%=', '&=', '|=', '^=', '.*'):
            if text.startswith(op, i):
                toks.append(('sym', op))
                i += len(op)
                break
        else:
            toks.append(('sym', c))
            i += 1
    return toks


def _split_top(toks, sep):
    """Split token list on `sep` at depth 0 (all bracket kinds)."""
    parts, cur, depth = [], [], 0
    for t in toks:
        k, v = t
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1
        elif k == 'sym' and v == '>>' and depth > 0:
            depth -= 2  # template close, not shift
        if depth == 0 and k == 'sym' and v == sep:
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    parts.append(cur)
    return parts


class _Cur:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else ('eof', '')

    def nxt(self):
        t = self.peek()
        self.i += 1
        return t

    def at(self, v):
        return self.peek()[1] == v and self.peek()[0] == 'sym'

    def atid(self, v=None):
        k, val = self.peek()
        return k == 'id' and (v is None or val == v)

    def accept(self, v):
        if self.at(v):
            self.i += 1
            return True
        return False

    def expect(self, v):
        if not self.accept(v):
            raise _PError('expected %r' % v)


def _capture_balanced(cur, open_):
    match = {'(': ')', '[': ']', '{': '}'}[open_]
    depth = 1
    out = []
    while True:
        k, v = cur.nxt()
        if k == 'eof':
            raise _PError('unbalanced brackets')
        if k == 'sym' and v == open_:
            depth += 1
        elif k == 'sym' and v == match:
            depth -= 1
            if depth == 0:
                return out
        out.append((k, v))


def _find_call_paren(toks):
    """Index of '(' starting a call/decl paren at depth 0, or -1."""
    depth = 0
    for i, (k, v) in enumerate(toks):
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1
        elif depth == 0 and k == 'sym' and v == '(':
            return i
    return -1


def _parse_type_prefix(cur):
    """Consume a type prefix; return type tokens or None (with rewind)."""
    save = cur.i
    if cur.atid('const'):
        cur.nxt()
    parts = []
    while True:
        k, v = cur.peek()
        if k == 'id' and (v in _CPP_TYPES or v in _CPP_KW and v in (
                'unsigned', 'signed', 'long', 'short', 'int', 'char',
                'bool', 'float', 'double', 'void', 'const')):
            parts.append(cur.nxt())
            if cur.at('::'):
                parts.append(cur.nxt())
                if cur.peek()[0] == 'id':
                    parts.append(cur.nxt())
                continue
            if cur.at('<'):
                parts.append(cur.nxt())
                # manual template-arg capture (no '<' in _capture map);
                # '>>' may close two levels at once.
                depth = 1
                while True:
                    kk, vv = cur.nxt()
                    if kk == 'eof':
                        raise _PError('unbalanced <>')
                    parts.append((kk, vv))
                    if kk == 'sym' and vv == '<':
                        depth += 1
                    elif kk == 'sym' and vv == '>>':
                        depth -= 2
                        if depth <= 0:
                            break
                    elif kk == 'sym' and vv == '>':
                        depth -= 1
                        if depth == 0:
                            break
            continue
        break
    while cur.peek()[1] in ('*', '&') and cur.peek()[0] == 'sym':
        parts.append(cur.nxt())
    if not parts:
        cur.i = save
        return None
    return parts


def _parse_declarators(cur):
    """Parse `name [dims] [=init | (args) | {braced}] (, ...)`; no ';'."""
    decls = []
    while True:
        if cur.peek()[0] != 'id':
            raise _PError('expected declarator')
        name = cur.nxt()[1]
        dims = []
        while cur.at('['):
            cur.nxt()
            dims.append(_capture_balanced(cur, '['))
        init = None
        if cur.at('='):
            cur.nxt()
            if cur.at('{'):
                cur.nxt()
                init = ('brace', _capture_balanced(cur, '{'))
            else:
                init = ('expr', _parse_expr_to_semi(cur, stop=(';', ',')))
        elif cur.at('('):
            cur.nxt()
            init = ('call', _capture_balanced(cur, '('))
        elif cur.at('{'):
            cur.nxt()
            init = ('brace', _capture_balanced(cur, '{'))
        decls.append((name, dims, init))
        if cur.at(','):
            cur.nxt()
            continue
        return decls


def _parse_expr_to_semi(cur, stop=(';',)):
    """Capture expression tokens up to one of `stop` at depth 0."""
    out, depth = [], 0
    while True:
        k, v = cur.peek()
        if k == 'eof':
            raise _PError('unterminated expression')
        if depth == 0 and k == 'sym' and v in stop:
            return out
        cur.nxt()
        out.append((k, v))
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1


def _parse_expr_toks(toks):
    """Build an Expr node from a token slice (calls found at all depths)."""
    e = {'toks': toks, 'calls': [], 'assign': None, 'incs': set()}
    # assignment at depth 0?
    depth = 0
    comp_at = plain_at = -1
    comp_op = None
    i = 0
    while i < len(toks):
        k, v = toks[i]
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1
        elif depth == 0 and k == 'sym' and v in (
                '+=', '-=', '*=', '/=', '%=', '<<=', '>>=', '&=', '|=',
                '^=') and comp_at < 0:
            comp_at, comp_op = i, v
        elif depth == 0 and k == 'sym' and v == '=' and plain_at < 0:
            if toks[i - 1][1] not in ('=', '!', '<', '>') and (
                    i + 1 >= len(toks) or toks[i + 1][1] != '='):
                plain_at = i
        i += 1
    if comp_at >= 0:
        lhs, rhs = toks[:comp_at], toks[comp_at + 1:]
        e['assign'] = (_parse_target(lhs), comp_op,
                       _parse_expr_toks(rhs) if rhs else None)
        return e
    if plain_at >= 0:
        lhs, rhs = toks[:plain_at], toks[plain_at + 1:]
        e['assign'] = (_parse_target(lhs), '=',
                       _parse_expr_toks(rhs) if rhs else None)
        return e
    _collect_calls(toks, 0, len(toks), e['calls'])
    # ++ / -- on plain idents
    for j, (k, v) in enumerate(toks):
        if k == 'sym' and v in ('++', '--'):
            if j + 1 < len(toks) and toks[j + 1][0] == 'id':
                e['incs'].add(toks[j + 1][1])
            elif j > 0 and toks[j - 1][0] == 'id':
                e['incs'].add(toks[j - 1][1])
    return e


def _parse_target(lhs):
    """Classify an assignment LHS; return (base_var, kind)."""
    toks = [t for t in lhs if not (t[0] == 'sym' and t[1] in ('*', '&', '(', ')'))]
    base = None
    for k, v in toks:
        if k == 'id' and v not in _CPP_KW:
            base = v
            break
    text = ''.join(v for _, v in toks)
    if '[' in text:
        kind = 'index'
    elif '.' in text or '->' in text:
        kind = 'member'
    else:
        kind = 'plain'
    return (base, kind)


def _skip_balanced(toks, open_idx, hi):
    """Index just past the bracket group opened at open_idx, or None."""
    match = {'(': ')', '[': ']', '{': '}'}[toks[open_idx][1]]
    depth = 0
    m = open_idx
    while m < hi:
        k, v = toks[m]
        if k == 'sym' and v == toks[open_idx][1]:
            depth += 1
        elif k == 'sym' and v == match:
            depth -= 1
            if depth == 0:
                return m
        m += 1
    return None


def _skip_template(toks, lt_idx, hi):
    """Index of the token closing the template list, or None."""
    depth = 0
    m = lt_idx
    while m < hi:
        k, v = toks[m]
        if k == 'sym' and v == '<':
            depth += 1
        elif k == 'sym' and v == '>>':
            depth -= 2
            if depth <= 0:
                return m
        elif k == 'sym' and v == '>':
            depth -= 1
            if depth == 0:
                return m
        m += 1
    return None


def _parse_call_args(toks, paren_idx, hi):
    """Split balanced call args; return (arg_slices, close_idx)."""
    openers = {'(': ')', '[': ']', '{': '}'}
    closers = {')', ']', '}'}
    args, start = [], paren_idx + 1
    stack = ['(']
    m = paren_idx + 1
    while m < hi:
        k, v = toks[m]
        if k == 'sym' and v in openers:
            stack.append(v)
        elif k == 'sym' and v in closers:
            if stack and v == openers.get(stack[-1], None):
                stack.pop()
            elif stack:
                stack.pop()  # tolerate mismatch, keep scanning
            if not stack:
                args.append(toks[start:m])
                break
        elif len(stack) == 1 and k == 'sym' and v == ',':
            args.append(toks[start:m])
            start = m + 1
        m += 1
    else:
        return None, None
    if len(args) == 1 and not args[0]:
        args = []  # f() takes no arguments
    return args, m


def _scan_call_chain(toks, i, hi, out):
    """Parse one id-led call chain; emit every call; return resume index.

    Returns None only when nothing was consumed (plain identifier), so
    the caller must advance by one itself.  Otherwise returns the index
    to resume scanning from (past everything consumed, including
    intermediate chained calls such as ``strs.back()`` in
    ``strs.back().size()``).
    """
    base = toks[i][1]
    j = i
    recv = {'base': base, 'indexed': False, 'subcall': False}
    linked = False
    func = base
    static = False
    while True:
        if j + 1 < hi and toks[j + 1] == ('sym', '['):
            e = _skip_balanced(toks, j + 1, hi)
            if e is None:
                return j + 1 if linked else None
            j = e
            recv['indexed'] = True
            linked = True
            continue
        if (j + 2 < hi and toks[j + 1] == ('sym', '::')
                and toks[j + 2][0] == 'id'):
            func = toks[j + 2][1]
            j += 2
            static = True
            linked = True
            continue
        if (j + 2 < hi and toks[j + 1][0] == 'sym'
                and toks[j + 1][1] in ('.', '->')
                and toks[j + 2][0] == 'id'):
            func = toks[j + 2][1]
            j += 2
            linked = True
            if j + 1 < hi and toks[j + 1] == ('sym', '<'):
                e = _skip_template(toks, j + 1, hi)
                if e is None:
                    return j + 1
                j = e
            if j + 1 < hi and toks[j + 1] == ('sym', '('):
                args, e = _parse_call_args(toks, j + 1, hi)
                if e is None:
                    return j + 1
                out.append({'recv': None if static else dict(recv),
                            'func': func, 'args': args})
                for a in args:
                    _collect_calls(a, 0, len(a), out)
                # keep the original base: a later .size() on the result
                # still denotes an element of that container
                recv = {'base': base, 'indexed': True, 'subcall': True}
                static = False
                j = e
                continue
            continue
        break
    if not linked and j + 1 < hi and toks[j + 1] == ('sym', '<'):
        # construction call such as vector<int>(m)
        e = _skip_template(toks, j + 1, hi)
        if e is not None and e + 1 < hi and toks[e + 1] == ('sym', '('):
            args, e2 = _parse_call_args(toks, e + 1, hi)
            if e2 is not None:
                out.append({'recv': None, 'func': func, 'args': args,
                            'ctor': True})
                for a in args:
                    _collect_calls(a, 0, len(a), out)
                return e2 + 1
        return None
    if linked and j + 1 < hi and toks[j + 1] == ('sym', '<'):
        e = _skip_template(toks, j + 1, hi)
        if e is None:
            return j + 1
        j = e
    if j + 1 < hi and toks[j + 1] == ('sym', '('):
        args, e = _parse_call_args(toks, j + 1, hi)
        if e is None:
            return j + 1 if linked else None
        out.append({'recv': None if (static or not linked) else dict(recv),
                    'func': func, 'args': args})
        for a in args:
            _collect_calls(a, 0, len(a), out)
        return e + 1
    return j + 1 if linked else None


def _collect_calls(toks, lo, hi, out):
    """Find calls in toks[lo:hi] at any bracket depth (each call once).

    Handles receiver chains (``v.size()``, ``matrix[i].size()``,
    ``strs.back().size()``, ``std::sort(...)``) and template argument
    lists (``greater<int>()``).  Lambda bodies ``[...]...{...}`` never
    start with an identifier so they are skipped structurally.
    """
    i = lo
    while i < hi:
        k, v = toks[i]
        if k == 'id' and v not in _CPP_KW:
            e = _scan_call_chain(toks, i, hi, out)
            if e is not None:
                i = e
                continue
        i += 1


def _parse_block(cur):
    cur.expect('{')
    stmts = []
    while not cur.at('}'):
        if cur.peek()[0] == 'eof':
            raise _PError('unbalanced {')
        if cur.atid('case') or cur.atid('default'):
            # stray case label outside switch handling: skip to ':'
            while not cur.at(':') and cur.peek()[0] != 'eof':
                cur.nxt()
            cur.accept(':')
            continue
        if cur.atid('public') or cur.atid('private') or cur.atid('protected'):
            if cur.peek(1)[1] == ':':
                cur.nxt()
                cur.nxt()
                continue
        stmts.append(_parse_stmt(cur))
    cur.expect('}')
    return ('block', stmts)


def _parse_stmt(cur):
    if cur.at('{'):
        return _parse_block(cur)
    if cur.atid('for'):
        return _parse_for(cur)
    if cur.atid('while'):
        cur.nxt()
        cur.expect('(')
        cond = _capture_balanced(cur, '(')
        body = _parse_stmt(cur)
        return ('loop', {'form': 'while', 'cond': cond,
                         'init': None, 'incr': None}, body)
    if cur.atid('do'):
        cur.nxt()
        body = _parse_stmt(cur)
        if not cur.atid('while'):
            raise _PError('do without while')
        cur.nxt()
        cur.expect('(')
        cond = _capture_balanced(cur, '(')
        cur.expect(';')
        return ('loop', {'form': 'do', 'cond': cond,
                         'init': None, 'incr': None}, body)
    if cur.atid('if'):
        cur.nxt()
        cur.expect('(')
        cond = _capture_balanced(cur, '(')
        then = _parse_stmt(cur)
        els = None
        if cur.atid('else'):
            cur.nxt()
            els = _parse_stmt(cur)
        return ('if', cond, then, els)
    if cur.atid('return'):
        cur.nxt()
        if cur.at(';'):
            cur.nxt()
            return ('return', [])
        e = _parse_expr_to_semi(cur)
        cur.expect(';')
        return ('return', e)
    if cur.atid('switch'):
        cur.nxt()
        cur.expect('(')
        cond = _capture_balanced(cur, '(')
        cur.expect('{')
        groups, cur_group = [], []
        while not cur.at('}'):
            if cur.peek()[0] == 'eof':
                raise _PError('unbalanced switch')
            if cur.atid('case'):
                if cur_group:
                    groups.append(cur_group)
                    cur_group = []
                cur.nxt()
                while not cur.at(':') and cur.peek()[0] != 'eof':
                    cur.nxt()
                cur.accept(':')
                continue
            if cur.atid('default'):
                if cur_group:
                    groups.append(cur_group)
                    cur_group = []
                cur.nxt()
                cur.accept(':')
                continue
            cur_group.append(_parse_stmt(cur))
        if cur_group:
            groups.append(cur_group)
        cur.expect('}')
        return ('switch', cond, groups)
    if cur.atid('try'):
        cur.nxt()
        body = _parse_block(cur)
        while cur.atid('catch'):
            cur.nxt()
            if cur.at('('):
                cur.nxt()
                _capture_balanced(cur, '(')
            _parse_block(cur)  # handlers parsed but ignored for cost
        return body
    if cur.peek()[0] == 'id' and cur.peek()[1] in (
            'break', 'continue', 'goto'):
        cur.nxt()
        _parse_expr_to_semi(cur)
        cur.expect(';')
        return ('flow',)
    if cur.at(';'):
        cur.nxt()
        return ('empty',)
    save = cur.i
    while cur.atid() and cur.peek()[1] in (
            'const', 'static', 'constexpr', 'inline', 'virtual',
            'mutable', 'extern', 'register'):
        cur.nxt()
    try:
        t = _parse_type_prefix(cur)
        if t is not None and cur.peek()[0] == 'id':
            decls = _parse_declarators(cur)
            cur.expect(';')
            return ('decl', t, decls)
    except _PError:
        pass
    cur.i = save
    e = _parse_expr_to_semi(cur)
    cur.expect(';')
    return ('expr', e)


def _parse_for(cur):
    cur.nxt()  # for
    cur.expect('(')
    head = _capture_balanced(cur, '(')
    # range-for has a top-level ':'
    depth = 0
    colon = -1
    for i, (k, v) in enumerate(head):
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1
        elif depth == 0 and k == 'sym' and v == ':':
            colon = i
            break
    if colon >= 0:
        info = {'form': 'range', 'decl': head[:colon],
                'container': head[colon + 1:]}
    else:
        parts = _split_top(head, ';')
        while len(parts) < 3:
            parts.append([])
        info = {'form': 'classic', 'init': parts[0], 'cond': parts[1],
                'incr': parts[2]}
    body = _parse_stmt(cur)
    return ('loop', info, body)


def _parse_params(toks):
    parts = _split_top(toks, ',')
    out = []
    for p in parts:
        p = [t for t in p if not (t == ('sym', '[') or t == ('sym', ']'))]
        if len(p) == 1 and p[0] == ('id', 'void'):
            continue
        if not p:
            continue
        name = None
        for k, v in reversed(p):
            if k == 'id' and v not in _CPP_KW:
                name = v
                break
        is_ref = any(t == ('sym', '&') for t in p)
        out.append((name, p, is_ref))
    return [x for x in out if x[0] is not None]


def _parse_solution_methods(toks):
    """Return (methods, freefuncs): name -> {'params', 'body'}."""
    cur = _Cur(toks)
    methods, free = {}, {}

    def parse_fn_at():
        # header ... '(' params ')' ('{' body | ';')
        start = cur.i
        depth = 0
        header = []
        while True:
            k, v = cur.peek()
            if k == 'eof':
                return None
            if k == 'sym' and v in (';', '{', '}'):
                return None
            if k == 'sym' and v == '(' and depth == 0:
                break
            if k == 'sym' and v in '[<':
                depth += 1
            elif k == 'sym' and v in ']>':
                depth -= 1
            elif k == 'sym' and v == '>>' and depth > 0:
                # template close `>>` (e.g. vector<vector<int>>)
                depth -= 2
            header.append(cur.nxt())
        # name = last id before '('
        name = None
        is_op = False
        for j in range(len(header) - 1, -1, -1):
            if header[j][0] == 'id':
                name = header[j][1]
                if j > 0 and header[j - 1] == ('id', 'operator'):
                    is_op = True
                break
        if name is None or name in _CPP_KW and name not in ('operator',):
            # not a function (e.g. `if (...)` handled elsewhere); bail
            if name in ('if', 'for', 'while', 'switch', 'catch'):
                return None
        cur.expect('(')
        params = _capture_balanced(cur, '(')
        if cur.at('{'):
            body = _parse_block(cur)
            return (('operator ' + name if is_op else name),
                    _parse_params(params), body)
        if cur.at(';'):
            cur.nxt()
            return None  # prototype
        return None

    # find class Solution
    while cur.peek()[0] != 'eof':
        if cur.atid('class') or cur.atid('struct'):
            cur.nxt()
            if cur.atid('Solution'):
                cur.nxt()
                # skip bases `: public ...`
                while not cur.at('{') and cur.peek()[0] != 'eof':
                    cur.nxt()
                if cur.peek()[0] == 'eof':
                    break
                cur.expect('{')
                while not cur.at('}'):
                    if cur.peek()[0] == 'eof':
                        raise _PError('unbalanced class')
                    if cur.peek()[0] == 'id' and cur.peek()[1] in (
                            'public', 'private', 'protected') and \
                            cur.peek(1)[1] == ':':
                        cur.nxt()
                        cur.nxt()
                        continue
                    save = cur.i
                    try:
                        r = parse_fn_at()
                    except _PError:
                        r = 'fail'
                    if r is None or r == 'fail':
                        # field or something else: skip to ';' or balanced
                        cur.i = save
                        skipped_brace = False
                        while cur.peek()[0] != 'eof':
                            if cur.at(';'):
                                cur.nxt()
                                break
                            if cur.at('{'):
                                cur.nxt()
                                _capture_balanced(cur, '{')
                                skipped_brace = True
                                if cur.at(';'):
                                    cur.nxt()
                                break
                            if cur.at('}'):
                                break
                            cur.nxt()
                        continue
                    fname, fparams, fbody = r
                    methods[fname] = {'params': fparams, 'body': fbody}
                return methods, free
            continue
        # top-level free function?
        if cur.peek()[0] == 'id':
            save = cur.i
            try:
                r = parse_fn_at()
            except _PError:
                r = None
            if r is not None:
                fname, fparams, fbody = r
                if not fname.startswith('operator'):
                    free[fname] = {'params': fparams, 'body': fbody}
                continue
            cur.i = save
            # skip to ';' or balanced block
            while cur.peek()[0] != 'eof':
                if cur.at(';'):
                    cur.nxt()
                    break
                if cur.at('{'):
                    cur.nxt()
                    try:
                        _capture_balanced(cur, '{')
                    except _PError:
                        break
                    break
                if cur.peek()[0] == 'id' and cur.peek()[1] in (
                        'class', 'struct'):
                    break
                cur.nxt()
            continue
        cur.nxt()
    return methods, free


# --------------------------------------------------------------------------
# C++ analysis: size variables, loop classification, costs
# --------------------------------------------------------------------------

_LINEAR_SUSPECT = {'find', 'search', 'count', 'remove', 'erase', 'substr',
                   'substring', 'contains', 'linear', 'indexOf',
                   'lastIndexOf', 'find_first_of', 'find_last_of'}

_CPP_O1_FREE = {
    'swap', 'min', 'max', 'abs', 'labs', 'llabs', 'fabs', 'fabsl',
    'move', 'forward', 'make_pair', 'make_tuple', 'tie', 'ignore',
    'assert', 'static_assert', 'sizeof', 'greater', 'less', 'equal_to',
    'plus', 'minus', 'multiplies', 'to_string', 'to_wstring', 'stoi',
    'stol', 'stoll', 'stof', 'stod', 'stoul', 'stoull', 'printf',
    'scanf', 'puts', 'getchar', 'fflush', 'srand', 'rand', 'exit',
    'isalnum', 'isalpha', 'isdigit', 'isspace', 'tolower', 'toupper',
}

_CPP_O1_METHODS = {
    'size', 'length', 'empty', 'begin', 'end', 'front', 'back', 'top',
    'data', 'capacity', 'cbegin', 'cend', 'rbegin', 'rend', 'at',
    'get', 'key', 'value', 'count',  # count handled per-ctype below
}


def _strip_scope(name):
    return name.split('::')[-1]


def _new_var(kind, **kw):
    e = {'kind': kind, 'ctype': None, 'nested': False, 'size': C_ONE,
         'sizevar': None, 'sval': ('unknown',), 'returned': False,
         'sources': set(), 'input': False, 'ddepth': -1, 'bounded': False}
    e.update(kw)
    return e


def _template_has(typetoks, name):
    depth = 0
    for k, v in typetoks:
        if (k, v) == ('sym', '<'):
            depth += 1
        elif (k, v) == ('sym', '>>'):
            depth -= 2
        elif (k, v) == ('sym', '>'):
            depth -= 1
        elif k == 'id' and v == name and depth > 0:
            return True
    return False


def _char_bounded(ctype, typetoks):
    """Assoc containers keyed by char hold at most 256 entries: O(1)."""
    return ctype in _ORDERED_ASSOC | _HASH_ASSOC and _template_has(
        typetoks, 'char')


def _init_cpp_params(params):
    st = {}
    for name, typetoks, _is_ref in params:
        base = None
        nested = False
        for k, v in typetoks:
            if k == 'id' and v in _CPP_TYPES and v != 'auto':
                if base is None:
                    base = v
        if base in _CPP_SCALAR_TYPES or base in (
                'void', 'bool', 'size_t'):
            st[name] = _new_var('scalar', sizevar='val:' + name,
                                sval=('size', 'val:' + name), input=True)
        elif base in _CPP_TYPES:
            nested = _nested_ctype(typetoks, base)
            sv = 'in:' + name
            if nested:
                d0, d1 = sv + '#0', sv + '#1'
                size = _cost(T(((d0, 1), (d1, 1)),))
                entry = _new_var('cont', ctype=base, nested=True,
                                 size=size, sizevar=d0, input=True)
            else:
                size = c_lin(sv)
                entry = _new_var('cont', ctype=base, nested=False,
                                 size=size, sizevar=sv, input=True)
            entry['sources'] = {entry['sizevar']}
            entry['bounded'] = _char_bounded(base, typetoks)
            st[name] = entry
        else:
            st[name] = _new_var('unknown', input=True)
    return st


def _unsub(v):
    if '|' in v or v.startswith('mgd:'):
        return v
    if v.endswith('#1'):
        return v[:-2]
    return v


# patch subsumption for sub-dim vars (element size <= total size)
_orig_subsumed = _subsumed


def _subsumed(a, b):  # noqa: F811
    if _orig_subsumed(a, b):
        return True
    amap = {_unsub(v) for v in a.vars()}
    bset = set(b.vars()) | {_unsub(v) for v in b.src} | set(b.src)
    bmap = {_unsub(v) for v in bset}
    return b.rank() > a.rank() and amap <= bmap


def _trip_var_of(entry):
    """Size identity for trip counts: single-var siv, const, or fallback.

    A loop over a container that is itself O(V) runs O(V) trips, so the
    trip variable is V (not the container's fresh declaration name).
    This keeps separately-analyzed loops over the same data combinable.
    """
    if entry is None or entry.get('kind') != 'cont':
        return None
    sz = entry.get('size')
    if sz is not None and sz.ok() and len(sz.terms) == 1:
        t = sz.terms[0]
        if t.deg() == 0 and t.logs == 0 and not t.exp2:
            return ('const',)
        if len(t.pows) == 1 and t.logs == 0 and not t.exp2:
            return ('size', t.pows[0][0])
    sv = entry.get('sizevar')
    if sv is not None:
        return ('size', sv)
    return ('unknown',)


def _sval_of_ident(name, st):
    e = st.get(name)
    if e is None:
        return ('size', 'in:' + name), _MED  # undeclared: assume input
    if e['kind'] == 'cont':
        siv = _trip_var_of(e)
        if siv is not None and siv[0] != 'unknown':
            return siv, _HIGH
        return ('unknown',), _LOW
    if e['kind'] == 'scalar':
        return e['sval'], _HIGH
    return ('unknown',), _MED


def _outer_call(toks):
    """If toks are exactly `name(args)`, return (name, arg_slices)."""
    if len(toks) >= 3 and toks[0][0] == 'id' \
            and toks[1] == ('sym', '(') and toks[-1] == ('sym', ')'):
        depth = 0
        for i in range(1, len(toks)):
            k, v = toks[i]
            if k == 'sym' and v == '(':
                depth += 1
            elif k == 'sym' and v == ')':
                depth -= 1
                if depth == 0 and i != len(toks) - 1:
                    return None
        if depth != 0:
            return None
        return toks[0][1], _split_top(toks[2:-1], ',')
    return None


def _minmax_siv(marg, st):
    vs, conf, anyk = [], _HIGH, False
    for a in marg:
        s, cc = _sizeinfo(a, st)
        conf = _worse(conf, cc)
        anyk = True
        if s[0] == 'size':
            vs.append(s[1])
        elif s[0] in ('min', 'prod'):
            vs.extend(s[1])
        elif s[0] != 'const':
            return ('unknown',), _LOW
    vs = list(dict.fromkeys(vs))
    if not anyk:
        return ('unknown',), _LOW
    if not vs:
        return ('const',), conf
    return ('min', vs), conf


def _sizeinfo(toks, st):
    """Classify a bound/size expression. Returns siv + confidence."""
    toks = _strip_parens_casts(toks)
    if not toks:
        return ('unknown',), _LOW
    if len(toks) == 1:
        k, v = toks[0]
        if k == 'num':
            return ('const',), _HIGH
        if k == 'lit':
            return ('const',), _HIGH
        if k == 'id':
            if v in ('true', 'false'):
                return ('const',), _HIGH
            return _sval_of_ident(v, st)
    # ident op const  (E +/- c, E / c, c * E, E * c)
    if len(toks) == 3 and toks[1][0] == 'sym':
        l_, op, r = toks[0], toks[1][1], toks[2]
        if op in ('+', '-') and r[0] == 'num':
            s, c = _sizeinfo([l_], st)
            return (s, c) if s[0] in ('size', 'min', 'const') else (
                ('unknown',), _LOW)
        if op == '/' and r[0] == 'num':
            s, c = _sizeinfo([l_], st)
            return (s, c) if s[0] in ('size', 'min', 'const') else (
                ('unknown',), _LOW)
        if op == '*' and l_[0] == 'num':
            return _sizeinfo([r], st)
        if op == '*' and r[0] == 'num':
            return _sizeinfo([l_], st)
    # products: E * F
    parts = _split_top(toks, '*')
    if len(parts) > 1:
        vs, conf = [], _HIGH
        for p in parts:
            s, c = _sizeinfo(p, st)
            conf = _worse(conf, c)
            if s[0] == 'size':
                vs.append(s[1])
            elif s[0] == 'min':
                vs.extend(s[1])
            elif s[0] == 'prod':
                vs.extend(s[1])
            elif s[0] != 'const':
                return ('unknown',), _LOW
        vs = list(dict.fromkeys(vs))
        if not vs:
            return ('const',), conf
        if len(vs) == 1:
            return ('size', vs[0]), conf
        return ('prod', vs), conf
    # single call: size()/length()/min()/max()/len()
    # (min/max first: their arguments contain further calls)
    oc = _outer_call(toks)
    if oc is not None and oc[0] in ('min', 'max'):
        return _minmax_siv(oc[1], st)
    # A + B of sizes: sum of the size variables (e.g. loop bounds)
    plus = _split_top(toks, '+')
    if len(plus) > 1 and all(p for p in plus):
        vs, conf = [], _HIGH
        for p in plus:
            s, cc = _sizeinfo(p, st)
            conf = _worse(conf, cc)
            if s[0] == 'size':
                vs.append(s[1])
            elif s[0] in ('min', 'prod', 'sum'):
                vs.extend(s[1])
            elif s[0] != 'const':
                return ('unknown',), _LOW
        vs = list(dict.fromkeys(vs))
        if not vs:
            return ('const',), conf
        if len(vs) == 1:
            return ('size', vs[0]), conf
        return ('sum', vs), conf
    calls = []
    _collect_calls(toks, 0, len(toks), calls)
    if len(calls) >= 1:
        for c in reversed(calls):
            fn = _strip_scope(c['func'])
            if fn not in ('size', 'length') or c['recv'] is None:
                continue
            others = [o for o in calls if o is not c]
            if any(o['args'] for o in others):
                continue  # size nested in a real call: not a bound
            return _recv_size(c, st)
    # bare container var
    if len(toks) == 1 and toks[0][0] == 'id':
        return _sval_of_ident(toks[0][1], st)
    return ('unknown',), _LOW


def _recv_size(c, st):
    """Size variable denoted by an X.size()/length() call + confidence."""
    base = c['recv']['base']
    if base is None:
        return ('unknown',), _LOW
    e = st.get(base)
    sub = c['recv']['indexed'] or c['recv']['subcall']
    if e is not None and e['kind'] == 'cont':
        if sub and e.get('nested'):
            return ('size', e['sizevar'] + '#1'
                    if not e['sizevar'].endswith('#0')
                    else e['sizevar'][:-2] + '#1'), _HIGH
        if sub and not e.get('nested'):
            return ('unknown',), _LOW  # .size() on scalar element
        siv = _trip_var_of(e)
        if siv is not None and siv[0] != 'unknown':
            return siv, _HIGH
        return ('unknown',), _LOW
    if e is None:
        v = 'in:' + base
        return ('size', v + '#1' if sub else v), _MED
    return ('unknown',), _LOW


def _strip_parens_casts(toks):
    changed = True
    while changed and len(toks) >= 2:
        changed = False
        if toks[0] == ('sym', '(') and toks[-1] == ('sym', ')'):
            depth = 0
            ok = True
            for i, (k, v) in enumerate(toks):
                if k == 'sym' and v == '(':
                    depth += 1
                elif k == 'sym' and v == ')':
                    depth -= 1
                    if depth == 0 and i != len(toks) - 1:
                        ok = False
                        break
            if ok and depth == 0:
                toks = toks[1:-1]
                changed = True
    return toks


def _siv_vars(siv):
    if siv[0] == 'size':
        return {siv[1]}
    if siv[0] in ('min', 'prod', 'sum'):
        return set(siv[1])
    return set()


def _trips_of_siv(siv, conf):
    if siv[0] == 'const':
        return ('const',), conf
    if siv[0] == 'size':
        return ('lin', siv[1]), conf
    if siv[0] == 'min':
        # min(a, b, ...) <= each source: any single source is an upper bound
        return ('lin', siv[1][0]), conf
    if siv[0] == 'prod':
        return ('prod', siv[1]), conf
    if siv[0] == 'sum':
        return ('sum', siv[1]), conf
    return ('unk',), _LOW


def _trips_size(trips):
    if trips[0] == 'const':
        return C_ONE
    if trips[0] == 'lin':
        return c_lin(trips[1])
    if trips[0] == 'log':
        return c_log(trips[1])
    if trips[0] == 'prod':
        return c_prod(trips[1])
    if trips[0] == 'sum':
        return seq(*[c_lin(v) for v in trips[1]])
    return Cost(None)


class _Ctx:
    def __init__(self, st, funcs):
        self.st = st
        self.funcs = funcs  # all known functions (methods + free)
        self.loop_stack = []
        self.amortized = set()
        self.tconf = _HIGH
        self.sconf = _HIGH
        self.tmps = []
        self.selfcalls = []
        self.in_loop = False
        self.func_name = None
        self.active = frozenset()
        self.memo = {}

    def down_t(self, c):
        self.tconf = _worse(self.tconf, c)

    def down_s(self, c):
        self.sconf = _worse(self.sconf, c)


def _resolve_recv(recv, st):
    """Resolve a call receiver to a var entry (or None)."""
    if recv is None or recv.get('base') is None:
        return None
    return st.get(recv['base'])


def _container_size_cost(entry):
    if entry is None or entry['kind'] != 'cont':
        return None
    return entry['size']


def _strip_base(v):
    if v.endswith('#0'):
        return v[:-2]
    if v.endswith('#1'):
        return v[:-2]
    return v


def _rename_var(v, basemap):
    if v.startswith('mgd:'):
        parts = v[4:].split('|')
        return 'mgd:' + '|'.join(_rename_var(p, basemap) for p in parts)
    for tb, cb in basemap.items():
        if v == tb or v.startswith(tb + '#'):
            return cb + v[len(tb):]
    return v


def _rename_cost(cost, basemap):
    if cost is None or not cost.ok() or not basemap:
        return cost
    out = []
    for t in cost.terms:
        pows = tuple(sorted((_rename_var(v, basemap), e)
                            for v, e in t.pows))
        src = frozenset(_rename_var(v, basemap) for v in t.src)
        out.append(T(pows, t.logs, t.exp2, src))
    return _cost(*out)


def _arg_basemap(tgt_params, call_args, tgt_st, caller_st):
    """Map callee input-size bases to caller size bases."""
    pairs = []
    for (pname, _pt, _ref), arg in zip(tgt_params, call_args):
        te = tgt_st.get(pname)
        if te is None:
            continue
        tsize = te.get('sizevar')
        if tsize is None:
            if te['kind'] == 'scalar':
                tsize = 'val:' + pname
            else:
                continue
        s, _c = _sizeinfo(arg, caller_st)
        if s[0] == 'size':
            pairs.append((_strip_base(tsize), _strip_base(s[1])))
        elif s[0] == 'min' and s[1]:
            pairs.append((_strip_base(tsize), _strip_base(s[1][0])))
    mp = {}
    for tb, cb in pairs:
        if tb in mp and mp[tb] != cb:
            continue  # conflicting; keep the first (upper bound stands)
        mp[tb] = cb
    return mp


def _known_summary(tgt, ctx):
    funcs = ctx.funcs
    res = _analyze_cpp_function(tgt, funcs[tgt], funcs, ctx.memo,
                                ctx.active)
    return res


def _known_result_size(call, ctx):
    """Output size of a known-function call (None = unknown)."""
    fn = _strip_scope(call['func'])
    tgt = None
    if fn in ctx.funcs:
        tgt = fn
    elif 'free::' + fn in ctx.funcs:
        tgt = 'free::' + fn
    if tgt is None:
        return None
    res = _known_summary(tgt, ctx)
    if res is None:
        return None
    mp = _arg_basemap(ctx.funcs[tgt]['params'], call['args'],
                      res.get('st', {}), ctx.st)
    tot = C_ONE
    bad = False
    for o in res.get('out', []):
        if o is None or not o.ok():
            bad = True
            continue
        tot = seq(tot, _rename_cost(o, mp))
    if bad and not tot.ok():
        return None
    if bad:
        ctx.down_s(_MED)
    return tot if tot.ok() else None


# ---- call knowledge base ----

def _sort_container(call, st):
    """Container whose elements are sorted by a sort-like call."""
    if not call['args']:
        return None
    a0 = call['args'][0]
    calls = []
    _collect_calls(a0, 0, len(a0), calls)
    for c in calls:
        fn = _strip_scope(c['func'])
        if fn in ('begin', 'end') and c['recv'] is not None \
                and c['recv'].get('base'):
            e = st.get(c['recv']['base'])
            if e is not None and e['kind'] == 'cont':
                return e
    if len(a0) == 1 and a0[0][0] == 'id':
        e = st.get(a0[0][1])
        if e is not None and e['kind'] == 'cont':
            return e
    return None


def _call_cost(call, ctx, expr_toks=None):
    """Return (time Cost, conf, effects). Effects applied by the caller."""
    st = ctx.st
    fn = _strip_scope(call['func'])
    recv_e = _resolve_recv(call['recv'], st)
    unknown_callee = False

    def _unk():
        ctx.down_t(_MED)
        return C_ONE, _MED, []

    # member call on a tracked container
    if recv_e is not None and recv_e['kind'] == 'cont':
        ctype = recv_e.get('ctype')
        size = recv_e['size']
        v = _count_var_of(recv_e)
        const_sz = (v == 'const')
        if const_sz:
            v = None
        if fn in _CPP_O1_METHODS and fn not in ('count',):
            return C_ONE, _HIGH, []
        if fn == 'count':
            if ctype in _ORDERED_ASSOC:
                if v is not None:
                    return c_log(v), _HIGH, []
                if const_sz:
                    return C_ONE, _HIGH, []
                ctx.down_t(_LOW)
                return Cost(None), _LOW, []
            if ctype in _HASH_ASSOC:
                ctx.down_t(_MED)
                return C_ONE, _MED, []
            # vector/string count: linear scan over the element count
            if v is not None:
                return c_lin(v), _HIGH, []
            if const_sz:
                return C_ONE, _HIGH, []
            if size.ok():
                return size, _HIGH, []
            return Cost(None), _LOW, []
        if fn in ('push_back', 'emplace_back', 'append', 'push',
                  'emplace', 'push_front', 'enqueue'):
            piece = call['args'][0] if call['args'] else None
            return C_ONE, _HIGH, [('grow', recv_e, piece)]
        if fn in ('pop_back', 'pop', 'pop_front', 'dequeue'):
            return C_ONE, _HIGH, []
        if fn in ('insert', 'erase'):
            # assoc: log/avg-1 (+ growth for insert); sequence: linear
            if ctype in _ORDERED_ASSOC:
                piece = call['args'][0] if call['args'] else None
                eff = [('grow', recv_e, piece)] if fn == 'insert' else []
                if v is not None:
                    return c_log(v), _HIGH, eff
                if const_sz:
                    return C_ONE, _HIGH, eff
                ctx.down_t(_LOW)
                return Cost(None), _LOW, eff
            if ctype in _HASH_ASSOC:
                piece = call['args'][0] if call['args'] else None
                eff = [('grow', recv_e, piece)] if fn == 'insert' else []
                ctx.down_t(_MED)
                return C_ONE, _MED, eff
            # sequence insert/erase by position: linear; range form adds
            # the range size.
            extra = C_ONE
            rng = _range_size(call, st)
            if rng is not None:
                extra = rng
            return (seq(size, extra) if size.ok() else extra), \
                _HIGH if size.ok() else _MED, \
                ([('growsize', recv_e, rng)] if fn == 'insert'
                 and rng is not None else [])
        if fn in ('find', 'find_first_of', 'find_last_of', 'rfind',
                  'find_first_not_of', 'find_last_not_of'):
            if ctype in _ORDERED_ASSOC:
                if v is not None:
                    return c_log(v), _HIGH, []
                if const_sz:
                    return C_ONE, _HIGH, []
                ctx.down_t(_LOW)
                return Cost(None), _LOW, []
            if ctype in _HASH_ASSOC:
                ctx.down_t(_MED)
                return C_ONE, _MED, []
            if call['recv'].get('base') is not None and \
                    _amortized_hit(call, ctx):
                ctx.down_t(_MED)
                return C_ONE, _MED, []
            # whole-range scan scales with the element count
            if recv_e.get('sizevar') is not None:
                return c_lin(recv_e['sizevar']), _HIGH, []
            return (size if size.ok() else Cost(None),
                    _HIGH if size.ok() else _LOW, [])
        if fn in ('substr', 'compare'):
            return (size if size.ok() else Cost(None),
                    _HIGH if size.ok() else _LOW, [])
        if fn in ('lower_bound', 'upper_bound', 'equal_range'):
            if v is not None:
                return c_log(v), _MED, []
            if const_sz:
                return C_ONE, _HIGH, []
            ctx.down_t(_LOW)
            return Cost(None), _LOW, []
        if fn in ('clear',):
            return (size if size.ok() else C_ONE), _HIGH, \
                [('reset', recv_e)]
        if fn in ('assign', 'resize'):
            rng = _range_size(call, st)
            sz = rng if rng is not None else C_ONE
            return sz, _HIGH, [('growsizeset', recv_e, sz)]
        if fn in ('reverse', 'sort'):
            # member sort/reverse (rare in C++; kept for completeness)
            if fn == 'sort':
                if v is None:
                    if const_sz:
                        return C_ONE, _HIGH, []
                    ctx.down_t(_LOW)
                    return Cost(None), _LOW, []
                return c_sort(v), _HIGH, []
            if _amortized_hit(call, ctx):
                ctx.down_t(_MED)
                return C_ONE, _MED, []
            if v is None:
                if const_sz:
                    return C_ONE, _HIGH, []
                ctx.down_t(_LOW)
                return Cost(None), _LOW, []
            return c_lin(v), _HIGH, []
        # unknown method on a known container
        if ctx.in_loop and fn in _LINEAR_SUSPECT:
            ctx.down_t(_LOW)
            return Cost(None), _LOW, []
        ctx.down_t(_MED)
        return C_ONE, _MED, []
    if recv_e is not None and recv_e['kind'] != 'cont':
        # method call on a scalar/unknown value
        ctx.down_t(_MED)
        return C_ONE, _MED, []

    # free / static calls
    if fn in _CPP_O1_FREE:
        return C_ONE, _HIGH, []
    if fn in ('sort', 'stable_sort', 'partial_sort', 'nth_element'):
        e = _sort_container(call, st)
        v = _count_var_of(e)
        if e is None or v is None:
            ctx.down_t(_LOW)
            return Cost(None), _LOW, []
        if v == 'const':
            return C_ONE, _HIGH, []
        # whole-range ordering scales with the element COUNT;
        # per-comparison work on nested elements (e.g. strings) is
        # treated as O(1), the standard simplification (documented).
        conf = _MED if e.get('nested') else _HIGH
        ctx.down_t(conf)
        return c_sort(v), conf, []
    if fn in ('reverse',):
        e = _sort_container(call, st)
        v = _count_var_of(e)
        if e is None or v is None:
            # reverse(it1, it2) with iterator args we cannot resolve
            ctx.down_t(_LOW)
            return Cost(None), _LOW, []
        if v == 'const':
            return C_ONE, _HIGH, []
        if _amortized_hit(call, ctx):
            ctx.down_t(_MED)
            return C_ONE, _MED, []
        return (c_lin(v), _HIGH, [])
    if fn in ('find', 'find_if', 'count', 'count_if', 'max_element',
              'min_element', 'is_sorted_until', 'adjacent_find',
              'search', 'find_end'):
        tot = C_ONE
        for a in call['args']:
            v = _arg_count_var(a, st)
            if v is not None and v != 'const':
                tot = seq(tot, c_lin(v))
        if _amortized_hit(call, ctx):
            ctx.down_t(_MED)
            return C_ONE, _MED, []
        return tot, _HIGH, []
    if fn in ('lower_bound', 'upper_bound', 'binary_search',
              'equal_range'):
        for a in call['args']:
            v = _arg_count_var(a, st)
            if v is None:
                continue
            if v == 'const':
                return C_ONE, _HIGH, []
            return c_log(v), _MED, []
        ctx.down_t(_LOW)
        return Cost(None), _LOW, []
    if fn in ('set_intersection', 'set_union', 'set_difference',
              'merge', 'inplace_merge', 'copy', 'copy_n', 'copy_if',
              'transform', 'fill', 'fill_n', 'remove_copy', 'replace'):
        tot = C_ONE
        for a in call['args']:
            s = _arg_container_size(a, st)
            if s is not None:
                tot = seq(tot, s)
        return tot, _MED, []
    if fn in ('strlen', 'strcmp', 'strncmp', 'strcpy', 'strcat'):
        ctx.down_t(_LOW)
        return Cost(None), _LOW, []
    if fn in ('memcpy', 'memmove', 'memset'):
        ctx.down_t(_MED)
        return C_ONE, _MED, []
    if fn in ('getline',):
        for a in call['args']:
            s = _arg_container_size(a, st)
            if s is not None:
                return s, _MED, []
        return C_ONE, _MED, []
    if fn in ('min', 'max'):
        # scalar min/max only (initializer lists of scalars are O(1));
        # min/max over an iterator range would be linear but those spell
        # min_element/max_element.
        return C_ONE, _HIGH, []
    # scalar construction / casts: int(x), long long(..), pair<..>(..)
    if fn in _CPP_SCALAR_TYPES or fn in ('pair', 'tuple'):
        tot, conf = C_ONE, _HIGH
        for a in call['args']:
            e2 = _parse_expr_toks(a)
            c2, c2c = _expr_cost(e2, ctx)
            tot = seq(tot, c2)
            conf = _worse(conf, c2c)
        return tot, conf, []
    # known Solution / free function: inline its summary with argument
    # size substitution (e.g. rotate(mat) costs what rotate costs).
    tgt = None
    if fn in ctx.funcs:
        tgt = fn
    elif 'free::' + fn in ctx.funcs:
        tgt = 'free::' + fn
    if tgt is not None:
        res = _known_summary(tgt, ctx)
        if res is None:
            ctx.down_t(_MED)
            return C_ONE, _MED, []
        mp = _arg_basemap(ctx.funcs[tgt]['params'], call['args'],
                          res.get('st', {}), ctx.st)
        t = _rename_cost(res['time'], mp)
        ctx.down_t(res['tconf'])
        ctx.down_s(res['sconf'])
        for a in res.get('aux', []):
            if a is None or not a.ok():
                ctx.down_s(_LOW)
                continue
            ctx.tmps.append(('aux', _rename_cost(a, mp)))
        if t is None or not t.ok():
            ctx.down_t(_LOW)
            return Cost(None), _LOW, []
        return t, res['tconf'], []
    # unknown free function / API (isBadVersion, guess, ...): assume O(1)
    # but never High confidence.
    tot, conf = C_ONE, _MED
    ctx.down_t(_MED)
    for a in call['args']:
        e2 = _parse_expr_toks(a)
        c2, c2c = _expr_cost(e2, ctx)
        tot = seq(tot, c2)
        conf = _worse(conf, c2c)
    return tot, conf, []


def _amortized_hit(call, ctx):
    recv = call.get('recv') or {}
    base = recv.get('base')
    return base is not None and base in ctx.amortized


def _count_var_of(entry):
    """Count variable for whole-range algorithms, 'const', or None."""
    if entry is None:
        return None
    siv = _trip_var_of(entry)
    if siv[0] == 'const':
        return 'const'
    if siv[0] == 'size':
        return siv[1]
    return None


def _count_cost(v, log=False):
    """Cost from a _count_var_of result (None propagates Low upstream)."""
    if v is None or v == 'const':
        return C_ONE
    return c_log(v) if log else c_lin(v)


def _arg_count_var(arg, st):
    """Element-count variable an algorithm argument iterates over.

    Returns a variable id, 'const' for constant-size containers (scans
    are O(1)), or None when unresolvable.
    """
    calls = []
    _collect_calls(arg, 0, len(arg), calls)
    for c in calls:
        if _strip_scope(c['func']) in ('begin', 'end') and \
                c['recv'] is not None and c['recv'].get('base'):
            return _count_var_of(st.get(c['recv']['base']))
    if len(arg) == 1 and arg[0][0] == 'id':
        return _count_var_of(st.get(arg[0][1]))
    return None


def _arg_container_size(arg, st):
    """Size of the container an algorithm argument refers to."""
    calls = []
    _collect_calls(arg, 0, len(arg), calls)
    for c in calls:
        if _strip_scope(c['func']) in ('begin', 'end') and \
                c['recv'] is not None and c['recv'].get('base'):
            e = st.get(c['recv']['base'])
            if e is not None and e['kind'] == 'cont':
                return e['size']
    if len(arg) == 1 and arg[0][0] == 'id':
        e = st.get(arg[0][1])
        if e is not None and e['kind'] == 'cont':
            return e['size']
    return None


def _range_size(call, st):
    """Size denoted by a (begin, end) argument pair, or None."""
    bases = []
    for a in call['args']:
        calls = []
        _collect_calls(a, 0, len(a), calls)
        for c in calls:
            if _strip_scope(c['func']) in ('begin', 'end') and \
                    c['recv'] is not None and c['recv'].get('base'):
                bases.append(c['recv']['base'])
    bases = list(dict.fromkeys(bases))
    if len(bases) == 1:
        e = st.get(bases[0])
        if e is not None and e['kind'] == 'cont':
            return e['size']
    if len(call['args']) == 1:
        return _arg_container_size(call['args'][0], st)
    return None


def _operand_size(slice_, st):
    """Size of an operand if it denotes a whole container; else O(1)."""
    sl = [t for t in slice_]
    calls = []
    _collect_calls(sl, 0, len(sl), calls)
    if len(sl) == 1 and sl[0][0] == 'id':
        e = st.get(sl[0][1])
        if e is not None and e['kind'] == 'cont':
            return e['size']
        return C_ONE
    for c in calls:
        fn = _strip_scope(c['func'])
        if fn in ('substr', 'lower', 'upper', 'sorted', 'copy'):
            r = _resolve_recv(c['recv'], st)
            if r is not None and r['kind'] == 'cont':
                return r['size']
    return C_ONE


def _expr_cost(expr, ctx):
    """Cost of an expression; applies growth side effects inline."""
    c, conf = _expr_cost_inner(expr, ctx)
    ctx.down_t(conf)
    return c, conf


def _expr_cost_inner(expr, ctx):
    """Cost of an expression; applies growth side effects inline."""
    st = ctx.st
    if expr is None:
        return C_ONE, _HIGH
    total, conf = C_ONE, _HIGH
    skip_tail_plus = False
    if expr.get('assign'):
        (base, kind), op, rhs = expr['assign']
        if rhs is not None:
            c, cc = _expr_cost(rhs, ctx)
            total, conf = seq(total, c), _worse(conf, cc)
        # self-concatenation through a rebuilt temporary:
        #   buf = buf + piece   (NOT buf += piece, which amortizes)
        if op == '=' and base is not None and rhs is not None and \
                _mentions(rhs, base):
            e = st.get(base)
            if e is not None and e['kind'] == 'cont' and \
                    _has_top_plus(rhs['toks']):
                piece = _rhs_minus_self(rhs, base, st)
                if ctx.in_loop and ctx.loop_stack:
                    trips = ctx.loop_stack[-1]['trips']
                    if trips[0] == 'unk':
                        ctx.down_t(_LOW)
                        return Cost(None), _LOW
                    # per-execution cost is the current buffer sizes; the
                    # enclosing loop applies the trip count exactly once
                    cur = e['size'] if e['size'].ok() else Cost(None)
                    if not cur.ok():
                        ctx.down_t(_LOW)
                        return Cost(None), _LOW
                    per = seq(cur, piece)
                    total = seq(total, per)
                    conf = _worse(conf, _MED)
                    # space only ever reaches the final buffer size, so
                    # the growth here is the piece content, unscaled by
                    # an extra trip factor (loop scaling applies below).
                    _grow_accum(base, piece, rhs, ctx)
                else:
                    cur = e['size'] if e['size'].ok() else C_ONE
                    total = seq(total, cur, _operand_size(rhs['toks'], st))
                _note_assign(base, kind, op, rhs, ctx, replace=False)
            else:
                _note_assign(base, kind, op, rhs, ctx, replace=True)
        else:
            _note_assign(base, kind, op, rhs, ctx,
                         replace=(op == '=' and kind == 'plain'))
            if op == '+=' and base is not None:
                e = st.get(base)
                if e is not None and e['kind'] == 'cont':
                    # amortized append (documented assumption); the generic
                    # concatenation tail below must not recharge it.
                    conf = _worse(conf, _MED)
                    _grow_accum(base, _piece_growth(rhs, ctx), rhs, ctx)
                    skip_tail_plus = True
    else:
        for call in expr.get('calls', []):
            c, cc, eff = _call_cost(call, ctx)
            total = seq(total, c)
            conf = _worse(conf, cc)
            for e in eff:
                _apply_effect(e, ctx)
    # string/sequence concatenation and whole-container comparison
    if not skip_tail_plus:
        total = seq(total, _plus_eq_cost(expr['toks'], st, ctx))
    # subscripts on ordered maps: logarithmic lookup
    for (k, v) in _subscript_bases(expr['toks']):
        e = st.get(v)
        if e is not None and e['kind'] == 'cont':
            if e.get('ctype') in _ORDERED_ASSOC:
                total = seq(total, _log_of_size(e['size']))
            elif e.get('ctype') in _HASH_ASSOC:
                ctx.down_t(_MED)
    # map-style subscript store growth: m[k]++ / ++m[k]
    for v in expr.get('incs', set()):
        pass  # plain-ident incs need no cost
    _map_subscript_growth(expr['toks'], st, ctx)
    return total, conf


def _log_of_size(size):
    if size.ok() and len(size.terms) == 1:
        t = size.terms[0]
        if len(t.pows) == 1 and t.pows[0][1] == 1 and t.logs == 0:
            return c_log(t.pows[0][0])
    return Cost(None)


def _mentions(rhs, base):
    return any(k == 'id' and v == base for k, v in rhs['toks'])


def _has_top_plus(toks):
    depth = 0
    for i, (k, v) in enumerate(toks):
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1
        elif depth == 0 and k == 'sym' and v == '+':
            return True
    return False


def _rhs_minus_self(rhs, base, st):
    """Size contributed by the non-self part of `base = base + piece`."""
    parts = _split_top(rhs['toks'], '+')
    tot = C_ONE
    found = False
    for p in parts:
        if any(k == 'id' and v == base for k, v in p):
            continue
        tot = seq(tot, _operand_size(p, st))
        found = True
    return tot if found else C_ONE


_CPP_SCALAR_CALLS = {
    'min', 'max', 'abs', 'labs', 'llabs', 'fabs', 'size', 'length',
    'to_string', 'stoi', 'stol', 'stoll', 'count', 'at', 'front',
    'back', 'top', 'get', 'hash', 'empty',
}


def _is_scalar_piece(expr, st):
    """True if an appended piece is O(1) per execution (not content)."""
    toks = expr['toks']
    if len(toks) == 1:
        k, v = toks[0]
        if k in ('num', 'lit'):
            return True
        if k == 'id':
            e = st.get(v)
            return e is None or e.get('kind') != 'cont'
        return True
    # concatenation stays content-sized unless both sides are scalar
    if _has_top_plus(toks):
        for i, (k, v) in enumerate(toks):
            if k == 'sym' and v == '+':
                l_ = _parse_expr_toks(toks[:i])
                r = _parse_expr_toks(toks[i + 1:])
                return _is_scalar_piece(l_, st) and _is_scalar_piece(r, st)
        return True
    for call in expr.get('calls', []):
        fn = _strip_scope(call['func'])
        if fn in _CPP_SCALAR_CALLS:
            continue
        r = _resolve_recv(call.get('recv'), st)
        if r is not None and r.get('kind') == 'cont':
            return False
        # unknown calls are assumed scalar (documented)
    # element stores: scalar unless the element itself is a container.
    # one subscript level into a nested container still yields a
    # container (v[i] of vector<string>); deeper indexing is scalar.
    for _i, base in _subscript_bases(toks):
        e = st.get(base)
        if isinstance(e, dict) and e.get('kind') == 'cont' and \
                e.get('nested'):
            depth = 0
            for kk, vv in toks:
                if kk == 'sym' and vv == '[':
                    depth += 1
            if depth <= 1:
                return False
    return True


def _piece_growth(rhs, ctx):
    """Growth amount for one accumulating append of rhs (per execution)."""
    if rhs is None:
        return C_ONE
    st = ctx.st
    if _is_scalar_piece(rhs, st):
        return C_ONE  # trips account for it via loop scaling
    # whole-container / slice / element pieces carry their source size
    srcs = _sources_of(rhs, st)
    ins = [s for s in srcs if s in _input_vars(st)]
    if ins:
        return seq(*[c_lin(s) for s in sorted(ins)])
    return C_ONE


def _input_vars(st):
    out = set()
    for e in st.values():
        if e.get('input') and e.get('sizevar'):
            out.add(e['sizevar'])
            out.update(e.get('sources', set()))
    return out


def _sources_of(expr, st):
    if expr is None:
        return set()
    srcs = set()
    for k, v in expr['toks']:
        if k != 'id' or v in _CPP_KW:
            continue
        e = st.get(v)
        if e is None:
            continue
        if e.get('sources'):
            srcs.update(e['sources'])
        elif e.get('kind') == 'cont' and e.get('input'):
            srcs.add(e['sizevar'])
        elif e.get('elem_of'):
            # a loop element carries its container's sources, so buffers
            # accumulated from elements partition the input
            c = st.get(e['elem_of'])
            if isinstance(c, dict):
                srcs.update(c.get('sources', set()))
                if c.get('sizevar'):
                    srcs.add(c['sizevar'])
    for call in expr.get('calls', []):
        r = _resolve_recv(call.get('recv'), st)
        if r is not None and r.get('sources'):
            srcs.update(r['sources'])
        for a in call.get('args', []):
            ae = _parse_expr_toks(a)
            srcs.update(_sources_of(ae, st))
    return srcs


def _cost_vars(cost):
    out = set()
    if cost is not None and cost.ok():
        for t in cost.terms:
            out.update(t.vars())
    return out


def _rhs_info(rhs, ctx):
    """(sources, element_names) feeding a growth RHS.

    Accepts a C++ Expr dict, or a precomputed (sources, eltnames) tuple
    (used by the Python analyzer, which shares the growth machinery).
    """
    if rhs is None:
        return set(), set()
    if isinstance(rhs, tuple):
        if len(rhs) > 2:
            return rhs[0], rhs[1]
        return rhs[0], rhs[1] if len(rhs) == 2 else (set(), set())
    st = ctx.st
    return _sources_of(rhs, st), {
        v for k, v in rhs['toks'] if k == 'id' and v not in _CPP_KW}


def _direct_assign_targets(body, is_py=False):
    """Variables assigned at the direct body level (not nested loops)."""
    if is_py:
        return {b for (b, _k, _v) in _py_assigns(body)}
    if isinstance(body, tuple) and body and body[0] == 'block':
        stmts = [body]
    else:
        stmts = [('block', [body])]
    return {b for (b, _k, _op, _r) in _stmt_assigns(stmts)}


def _loop_index_names(body, condvars, is_py=False):
    """Loop-variable names for the tight distinct-values growth rule."""
    if is_py:
        direct = {b for (b, _k, _v) in _py_assigns(body)}
        nested = set()

        def walk(ss):
            for s in ss:
                if isinstance(s, (_ast.For, _ast.While)):
                    for ch in _ast.walk(s):
                        if isinstance(ch, _ast.Name) and isinstance(
                                ch.ctx, _ast.Store):
                            nested.add(ch.id)
                elif isinstance(s, _ast.If):
                    walk(s.body)
                    walk(s.orelse)
        walk(body)
        return (set(condvars) | direct) - nested
    if isinstance(body, tuple) and body and body[0] == 'block':
        bl = [body]
    else:
        bl = [('block', [body])]
    direct = {b for (b, _k, _op, _r) in _stmt_assigns(bl)}
    allin = {b for (b, _k, _op, _r) in _stmt_assigns(bl, into_loops=True)}
    nested_only = allin - direct
    return (set(condvars) | direct) - nested_only


def _fresh_piece_base(rhs, ctx):
    """Bare container variable declared inside the innermost loop level."""
    if not ctx.loop_stack:
        return None
    base = None
    if isinstance(rhs, tuple):
        base = rhs[2] if len(rhs) > 2 else None
    elif isinstance(rhs, dict):
        toks = rhs['toks']
        if len(toks) == 1 and toks[0][0] == 'id':
            base = toks[0][1]
    if base is None:
        return None
    e = ctx.st.get(base)
    if e is None or e.get('kind') != 'cont':
        return None
    if e.get('ddepth', -1) == len(ctx.loop_stack):
        return base
    return None


def _tight_level(base, ctx):
    """Innermost loop level binding base as a loop variable, or None."""
    if base is None:
        return None
    e = ctx.st.get(base)
    if isinstance(e, dict) and e.get('kind') == 'cont':
        return None  # container pieces use the content rule
    for lvl in reversed(ctx.loop_stack):
        if base in lvl.get('index', ()):
            return lvl
    return None


def _rhs_base_name(rhs):
    if isinstance(rhs, tuple):
        return rhs[2] if len(rhs) > 2 else None
    if isinstance(rhs, dict):
        toks = rhs.get('toks', [])
        if len(toks) == 1 and toks[0][0] == 'id':
            return toks[0][1]
    return None


def _body_preserves_var(body, var):
    """Loop-body writes to var are all monotonic steps (or none)."""
    for (b, _k, op, rhs) in _stmt_assigns(
            [('block', [body])] if not (
                isinstance(body, tuple) and body and body[0] == 'block')
            else [body]):
        if b != var:
            continue
        if op in ('+=', '-='):
            continue
        if op == '=' and rhs is not None and _is_step(rhs['toks'], var):
            continue
        return False
    return True


def _grow_accum(base, amount, rhs, ctx):
    """Accumulate growth into a tracked container (upper bound)."""
    st = ctx.st
    e = st.get(base)
    if e is None or e['kind'] != 'cont' or e.get('input'):
        return
    if e.get('bounded'):
        # char-keyed assoc containers cannot exceed 256 entries
        ctx.down_s(_MED)
        return
    if amount is None or not amount.ok():
        e['size'] = Cost(None)
        ctx.down_s(_LOW)
        return
    srcs, elts = _rhs_info(rhs, ctx)
    levels = list(reversed(ctx.loop_stack))
    # tight loop-variable rule: a bare scalar loop variable takes at
    # most its binding loop's trip count of distinct values, however
    # often the inner nest re-inserts it.
    tlv = _tight_level(_rhs_base_name(rhs), ctx)
    if tlv is not None:
        # A loop variable takes at most its binding loop's trip count of
        # distinct values: outer re-execution reproduces values from the
        # same input-bounded domain, so no outer scaling applies.  (Trip
        # counts that themselves depend on outer levels resolve to
        # input-dimension variables, never to outer loop variables.)
        total = _trips_size(tlv['trips'])
        if not total.ok():
            e['size'] = Cost(None)
            ctx.down_s(_LOW)
            return
        e['size'] = seq(e['size'], total)
        e['sources'].update(srcs)
        return
    fresh = _fresh_piece_base(rhs, ctx)
    total = amount
    if fresh is not None:
        # a per-iteration fresh buffer contributes its own size once
        # per trip of the innermost level (e.g. building rows of a
        # matrix); outer levels still scale normally below.
        fe = st[fresh]
        if not fe['size'].ok():
            e['size'] = Cost(None)
            ctx.down_s(_LOW)
            return
        total = nest(levels[0]['trips'], fe['size'])
        if not total.ok():
            e['size'] = Cost(None)
            ctx.down_s(_LOW)
            return
        levels = levels[1:]
    # scale by enclosing loops, except levels whose own container is
    # already covered by the amount (pieces partitioning that input).
    inner = _piece_loop_index(srcs, elts, ctx)
    amt_vars = _cost_vars(total)
    for lvl in levels:
        if inner is not None and lvl['depth'] <= inner \
                and set(lvl.get('cvars', ())) <= amt_vars:
            continue
        total = nest(lvl['trips'], total)
        if not total.ok():
            e['size'] = Cost(None)
            ctx.down_s(_LOW)
            return
    e['size'] = seq(e['size'], total)
    if rhs is not None and not isinstance(rhs, tuple):
        e['sources'].update(_sources_of(rhs, st))
    else:
        e['sources'].update(srcs)


def _piece_loop_index(srcs, elts, ctx):
    """Innermost loop level whose own container feeds the piece."""
    best = None
    for lvl in ctx.loop_stack:
        cvars = set(lvl.get('cvars', ()))
        if srcs & cvars:
            best = lvl['depth']
    for lvl in ctx.loop_stack:
        el = lvl.get('element')
        if el is not None and el in elts:
            if best is None or lvl['depth'] > best:
                best = lvl['depth']
    return best


def _apply_effect(eff, ctx):
    kind = eff[0]
    if kind == 'grow':
        _, entry, piece = eff
        base = _base_of_entry(ctx.st, entry)
        if base is None:
            return
        rexpr = _parse_expr_toks(piece) if piece else None
        _grow_accum(base, C_ONE, rexpr, ctx)
    elif kind == 'growsize':
        _, entry, sz = eff
        base = _base_of_entry(ctx.st, entry)
        if base is None:
            return
        _grow_accum(base, sz, None, ctx)
    elif kind == 'growsizeset':
        _, entry, sz = eff
        base = _base_of_entry(ctx.st, entry)
        if base is None:
            return
        e = ctx.st.get(base)
        if e is not None and not e.get('input'):
            e['size'] = sz if sz.ok() else Cost(None)
            if not sz.ok():
                ctx.down_s(_LOW)
    elif kind == 'reset':
        _, entry = eff
        base = _base_of_entry(ctx.st, entry)
        if base is None:
            return
        e = ctx.st.get(base)
        if e is not None and not e.get('input'):
            e['size'] = C_ONE
            e['sources'] = set()


def _base_of_entry(st, entry):
    for name, e in st.items():
        if e is entry:
            return name
    return None


def _note_assign(base, bkind, op, rhs, ctx, replace):
    st = ctx.st
    if base is None:
        return
    e = st.get(base)
    if e is None:
        return
    if e['kind'] == 'scalar':
        # value-class bookkeeping only; cost (if any) was counted with
        # the RHS.  An unresolvable class never downgrades here: if the
        # variable later bounds a loop, the use site reports Low itself.
        if op == '=' and rhs is not None:
            s, _c = _sizeinfo_of_expr(rhs, st)
            e['sval'] = s
        return
    if e['kind'] != 'cont' or e.get('input'):
        return
    if bkind != 'plain':
        # indexed / member stores never replace the container size
        # (vector v[i] = x; map growth is tracked separately)
        return
    if op == '=' and rhs is not None:
        # plain assignment REPLACES unless handled as accumulation above;
        # resets (x = "") shrink back to O(1).
        if _mentions(rhs, base):
            return  # accumulation handled by the caller
        sz = _contentsize_of(rhs, ctx)
        if sz is None:
            e['size'] = Cost(None)
            ctx.down_s(_LOW)
        else:
            e['size'] = sz
            e['sources'] = _sources_of(rhs, st)


def _sizeinfo_of_expr(expr, st):
    if expr is None:
        return ('unknown',), _LOW
    return _sizeinfo(expr['toks'], st)


def _contentsize_of(expr, ctx):
    """Upper size of the value an expression produces (None = unknown)."""
    st = ctx.st
    if expr is None:
        return C_ONE
    toks = [t for t in expr['toks']]
    if len(toks) == 1 and toks[0][0] == 'id':
        e = st.get(toks[0][1])
        if e is not None and e['kind'] == 'cont':
            return e['size']
        return C_ONE
    if len(toks) == 1 and toks[0][0] in ('num', 'lit'):
        return C_ONE
    for call in expr.get('calls', []):
        fn = _strip_scope(call['func'])
        if fn in ('substr', 'sorted', 'lower', 'upper', 'copy', 'join',
                  'split', 'strip', 'c_str'):
            r = _resolve_recv(call.get('recv'), st)
            if r is not None and r['kind'] == 'cont':
                return r['size']
            for a in call.get('args', []):
                s, _ = _sizeinfo(a, st)
                if s[0] == 'size':
                    return c_lin(s[1])
                if s[0] == 'prod':
                    return c_prod(s[1])
        if fn in ('list', 'set', 'dict', 'sorted', 'vector', 'string'):
            for a in call.get('args', []):
                s, _ = _sizeinfo(a, st)
                if s[0] == 'size':
                    return c_lin(s[1])
                if s[0] == 'prod':
                    return c_prod(s[1])
        # a known function returning a container: use its output size
        known = _known_result_size(call, ctx)
        if known is not None:
            return known
    return None


def _plus_eq_cost(toks, st, ctx):
    """Cost of top-level + (sequence concat) and == (container compare)."""
    total = C_ONE
    # string/sequence concatenation: O(sum of operand sizes)
    for i, (k, v) in enumerate(toks):
        if k == 'sym' and v == '+':
            if i > 0 and toks[i - 1][1] in ('++',):
                continue
            left = toks[:i]
            # find matching right operand end at this depth: next top '+'
            total = seq(total, _operand_size(left, st))
            break
    else:
        left = None
    if left is not None:
        # charge remaining +-segments too
        depth = 0
        cur = []
        segs = []
        rest = toks[i + 1:]
        for t in rest:
            kk, vv = t
            if kk == 'sym' and vv in '([{':
                depth += 1
            elif kk == 'sym' and vv in ')]}':
                depth -= 1
            if depth == 0 and kk == 'sym' and vv == '+':
                segs.append(cur)
                cur = []
            else:
                cur.append(t)
        segs.append(cur)
        for s_ in segs:
            total = seq(total, _operand_size(s_, st))
    # whole-container == / != : a single linear traversal (plus an O(1)
    # size check), so charge the dominant side only, not the sum.
    depth = 0
    for i, (k, v) in enumerate(toks):
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1
        elif depth == 0 and k == 'sym' and v in ('==', '!='):
            lsize = _operand_size(toks[:i], st)
            rsize = _operand_size(toks[i + 1:], st)
            total = seq(total, _maxc(lsize, rsize))
            break
    return total


def _subscript_bases(toks):
    """Yield (index, base_var) for `base[...]` occurrences."""
    out = []
    i = 0
    while i + 1 < len(toks):
        if toks[i][0] == 'id' and toks[i + 1] == ('sym', '['):
            out.append((i, toks[i][1]))
        i += 1
    return out


def _map_subscript_growth(toks, st, ctx):
    """m[k]++/m[k]=x on assoc containers grows with trip count."""
    i = 0
    while i < len(toks):
        if toks[i][0] == 'id' and i + 1 < len(toks) and \
                toks[i + 1] == ('sym', '['):
            base = toks[i][1]
            e = st.get(base)
            if e is not None and e.get('ctype') in (
                    _ORDERED_ASSOC | _HASH_ASSOC):
                # find matching ] then check for ++/-- or = (store)
                depth = 0
                m = i + 1
                while m < len(toks):
                    kk, vv = toks[m]
                    if kk == 'sym' and vv == '[':
                        depth += 1
                    elif kk == 'sym' and vv == ']':
                        depth -= 1
                        if depth == 0:
                            break
                    m += 1
                after = toks[m + 1] if m + 1 < len(toks) else ('', '')
                before = toks[i - 1] if i > 0 else ('', '')
                grows = (after in (('sym', '++'), ('sym', '--'),
                                   ('sym', '=')) or before in (
                    ('sym', '++'), ('sym', '--')))
                is_assign = after == ('sym', '=')
                # plain read m[k] does not grow; check it is a store/inc
                if grows or (is_assign and _in_store_position(toks, m)):
                    key = toks[i + 2:m]
                    rexpr = _parse_expr_toks(key) if key else None
                    _grow_accum(base, C_ONE, rexpr, ctx)
                    if e.get('ctype') in _ORDERED_ASSOC:
                        pass
                    else:
                        ctx.down_t(_MED)
                        ctx.down_s(_MED)
            i += 1
        else:
            i += 1


def _in_store_position(toks, close_idx):
    nxt = toks[close_idx + 1] if close_idx + 1 < len(toks) else ('', '')
    return nxt == ('sym', '=')


# ---- declarations ----

def _base_type_of(typetoks):
    for k, v in typetoks:
        if k == 'id' and v in _CPP_TYPES and v != 'auto':
            return v
    for k, v in typetoks:
        if k == 'id' and v not in _CPP_KW:
            return v
    return None


def _analyze_decl(typetoks, decls, ctx):
    total, conf = _analyze_decl_inner(typetoks, decls, ctx)
    ctx.down_t(conf)
    return total, conf


def _analyze_decl_inner(typetoks, decls, ctx):
    st = ctx.st
    base = _base_type_of(typetoks)
    is_auto = any(t == ('id', 'auto') for t in typetoks)
    total, conf = C_ONE, _HIGH
    for name, dims, init in decls:
        if base in _CPP_SCALAR_TYPES or base in ('void', 'bool', 'size_t'):
            e = _new_var('scalar')
            e['ddepth'] = len(ctx.loop_stack)
            if dims:
                s, _c = _sizeinfo(dims[0], st)
                # const-sized arrays are O(1); an unresolvable dynamic
                # dimension affects space confidence, never time
                if s[0] == 'unknown':
                    ctx.down_s(_LOW)
                e['array_const'] = (s[0] == 'const')
            if init is not None:
                kind, payload = init
                if kind == 'expr':
                    ex = _parse_expr_toks(payload)
                    c, cc = _expr_cost(ex, ctx)
                    total, conf = seq(total, c), _worse(conf, cc)
                    s, _sc = _sizeinfo(payload, st)
                    # value-class bookkeeping only: a non-size value is
                    # normal for scalars and never lowers confidence here
                    # (a later use as a bound reports Low itself if needed)
                    e['sval'] = s if s[0] != 'unknown' else ('unknown',)
                elif kind == 'call':
                    e['sval'] = ('unknown',)
                    ctx.down_t(_MED)
                else:
                    e['sval'] = ('const',)
            st[name] = e
        elif base in _CPP_TYPES or is_auto or base is None:
            ctype = base if base in _CPP_TYPES else None
            if is_auto or ctype is None:
                # infer from initializer
                ctype, isz, isrc = _infer_auto(init, ctx)
                if ctype is None:
                    st[name] = _new_var('unknown')
                    ctx.down_t(_MED)
                    continue
            else:
                isz, isrc = _init_size(init, ctx, ctype)
            nested = _nested_ctype(typetoks, ctype)
            sv = _fresh_sizevar(name, st, nested)
            size = isz if isz is not None and isz.ok() else Cost(None)
            if not size.ok():
                ctx.down_s(_LOW)
            e = _new_var('cont', ctype=ctype, nested=nested, size=size,
                         sizevar=sv)
            e['ddepth'] = len(ctx.loop_stack)
            e['bounded'] = _char_bounded(ctype, typetoks)
            e['sources'] = isrc
            if dims:
                s, c = _sizeinfo(dims[0], st)
                if s[0] != 'const':
                    e['size'] = _dims_size(s)
                    e['sizevar'] = s[1] if s[0] == 'size' else sv
                    conf = _worse(conf, c)
            st[name] = e
            # construction visits every element (copy/fill/range), so a
            # sized initializer also costs its size in time
            if init is not None and e['size'].ok() \
                    and _cost_vars(e['size']):
                total = seq(total, e['size'])
                if ctype in _HASH_ASSOC:
                    # hash-based construction averages linear (documented)
                    conf = _worse(conf, _MED)
                    ctx.down_t(_MED)
                    ctx.down_s(_MED)
            if init is not None:
                kind, payload = init
                if kind == 'expr':
                    ex = _parse_expr_toks(payload)
                    c, cc = _expr_cost(ex, ctx)
                    total, conf = seq(total, c), _worse(conf, cc)
                elif kind == 'call':
                    for a in _split_top(payload, ','):
                        ex = _parse_expr_toks(a)
                        c, cc = _expr_cost(ex, ctx)
                        total, conf = seq(total, c), _worse(conf, cc)
        else:
            st[name] = _new_var('unknown')
            ctx.down_t(_MED)
    return total, conf


_NESTED_ELEM = {'string', 'vector', 'map', 'set', 'unordered_map',
                'unordered_set', 'list', 'deque', 'array', 'multimap',
                'multiset', 'stack', 'queue'}


def _nested_ctype(typetoks, ctype):
    if ctype in ('map', 'set', 'unordered_map', 'unordered_set',
                 'multimap', 'multiset', 'stack', 'queue',
                 'priority_queue', 'pair'):
        return False
    # drop pair<...> groups: pair elements are fixed-size, so a
    # vector<pair<string, int>> is still one-dimensional
    toks = []
    i = 0
    while i < len(typetoks):
        k, v = typetoks[i]
        if k == 'id' and v == 'pair' and i + 1 < len(typetoks) and \
                typetoks[i + 1] == ('sym', '<'):
            skip = 1
            i += 2
            while i < len(typetoks) and skip > 0:
                kk, vv = typetoks[i]
                if (kk, vv) == ('sym', '<'):
                    skip += 1
                elif (kk, vv) == ('sym', '>'):
                    skip -= 1
                elif (kk, vv) == ('sym', '>>'):
                    skip -= 2
                i += 1
            continue
        toks.append((k, v))
        i += 1
    # nested iff a container name occurs *inside* template arguments
    depth = 0
    for k, v in toks:
        if (k, v) == ('sym', '<'):
            depth += 1
        elif (k, v) == ('sym', '>>'):
            depth -= 2
        elif (k, v) == ('sym', '>'):
            depth -= 1
        elif k == 'id' and v in _NESTED_ELEM and depth > 0:
            return True
    return False


def _fresh_sizevar(name, st, nested):
    sv = 'in:' + name
    if nested:
        return sv + '#0'
    return sv


def _dims_size(siv):
    if siv[0] == 'const':
        return C_ONE
    if siv[0] == 'size':
        return c_lin(siv[1])
    if siv[0] == 'prod':
        return c_prod(siv[1])
    return Cost(None)


def _init_size(init, ctx, ctype):
    """Size + sources of a container initializer. Returns (Cost, set)."""
    st = ctx.st
    if init is None:
        return C_ONE, set()
    kind, payload = init
    if kind == 'brace':
        return C_ONE, set()
    if kind == 'call':
        args = _split_top(payload, ',')
        # range construction: s(a.begin(), a.end())
        if len(args) == 2:
            b0 = _recv_base_of_arg(args[0])
            b1 = _recv_base_of_arg(args[1])
            if b0 is not None and b0 == b1:
                e = st.get(b0)
                if e is not None and e['kind'] == 'cont':
                    return e['size'], set(e.get('sources', set()))
        sizes = []
        for a in args:
            ex = _parse_expr_toks(a)
            # inner construction vector<int>(m): recurse into its args
            inner = None
            for c in ex['calls']:
                if c.get('ctor') and c['recv'] is None:
                    for aa in c['args']:
                        s, _cc = _sizeinfo(aa, st)
                        if s[0] == 'size':
                            sizes.append(s[1])
                        elif s[0] == 'prod':
                            sizes.extend(s[1])
            s, _cc = _sizeinfo(a, st)
            if s[0] == 'size':
                sizes.append(s[1])
            elif s[0] == 'prod':
                sizes.extend(s[1])
            elif s[0] == 'min':
                sizes.extend(s[1])
        sizes = list(dict.fromkeys(sizes))
        if not sizes:
            # constant / scalar args only (v(26), v(n, 0))
            return C_ONE, set()
        if len(sizes) == 1:
            return c_lin(sizes[0]), set(sizes)
        return c_prod(sizes), set(sizes)
    # kind == 'expr'
    ex = _parse_expr_toks(payload)
    srcs = _sources_of(ex, st)
    ins = sorted(s for s in srcs if s in _input_vars(st))
    if ins:
        return seq(*[c_lin(s) for s in ins]), set(ins)
    if len(payload) == 1 and payload[0][0] in ('num', 'lit'):
        return C_ONE, set()
    return C_ONE, set()


def _recv_base_of_arg(arg):
    calls = []
    _collect_calls(arg, 0, len(arg), calls)
    for c in calls:
        if c['recv'] is not None and c['recv'].get('base'):
            return c['recv']['base']
    return None


def _infer_auto(init, ctx):
    if init is None:
        return None, C_ONE, set()
    kind, payload = init
    if kind == 'expr':
        ex = _parse_expr_toks(payload)
        srcs = _sources_of(ex, ctx.st)
        for call in ex['calls']:
            fn = _strip_scope(call['func'])
            if fn in ('list', 'set', 'dict', 'sorted', 'vector', 'string',
                      'map'):
                return 'vector', _contentsize_of(ex, ctx) or C_ONE, srcs
        return None, C_ONE, set()
    if kind == 'call':
        return 'vector', C_ONE, set()
    return None, C_ONE, set()


# ---- statements ----

def _maxc(a, b):
    if a is None or not a.ok():
        return b
    if b is None or not b.ok():
        return a
    ra = max((t.rank() for t in a.terms), default=(0, 0, 0))
    rb = max((t.rank() for t in b.terms), default=(0, 0, 0))
    return a if ra >= rb else b


_ABSENT = object()


def _scoped_decl_names(stmts):
    """Names declared at the direct level (not in nested loops)."""
    out = set()

    def walk(s):
        tag = s[0]
        if tag == 'decl':
            for name, _d, _i in s[2]:
                out.add(name)
        elif tag == 'block':
            for x in s[1]:
                walk(x)
        elif tag == 'if':
            walk(s[2])
            if s[3] is not None:
                walk(s[3])
        elif tag == 'switch':
            for g in s[2]:
                for x in g:
                    walk(x)
        elif tag == 'loop':
            pass  # nested loop targets belong to that scope
    for s in stmts:
        walk(s)
    return out


def _scoped_run(st, names, fn):
    """Run fn() with shadowing declarations restored afterwards.

    Growth applied to OUTER variables persists (entries mutate in
    place); only the shadowed bindings themselves are restored, so a
    loop-local `s` never clobbers the outer `s` it shadows.
    """
    saved = {n: st.get(n, _ABSENT) for n in names}
    try:
        return fn()
    finally:
        for n, v in saved.items():
            if v is _ABSENT:
                st.pop(n, None)
            else:
                st[n] = v


def _init_decl_names(init):
    """Names declared by a classic-for init clause (shadowing scope)."""
    out = set()
    for part in _split_top(init, ','):
        if len(part) >= 2 and part[0][0] == 'id' and part[1][0] == 'id' \
                and (part[0][1] in _CPP_TYPES or part[0][1] == 'const'):
            out.add(part[1][1])
    return out


def _analyze_stmts(stmts, ctx):
    total = C_ONE
    for s in stmts:
        c = _analyze_stmt(s, ctx)
        total = seq(total, c)
    return total


def _analyze_stmt(s, ctx):
    tag = s[0]
    if tag == 'block':
        return _scoped_run(ctx.st, _scoped_decl_names(s[1]),
                           lambda: _analyze_stmts(s[1], ctx))
    if tag == 'empty' or tag == 'flow':
        return C_ONE
    if tag == 'expr':
        c, _cc = _expr_cost(_parse_expr_toks(s[1]), ctx)
        return c
    if tag == 'decl':
        c, _cc = _analyze_decl(s[1], s[2], ctx)
        return c
    if tag == 'return':
        if not s[1]:
            return C_ONE
        e = _parse_expr_toks(s[1])
        c, _cc = _expr_cost(e, ctx)
        _mark_output(e, ctx)
        return c
    if tag == 'if':
        _cond, then, els = s[1], s[2], s[3]
        ce = _parse_expr_toks(_cond)
        c0, _c0 = _expr_cost(ce, ctx)
        # branch-local analysis so one arm's growth does not leak:
        # (upper bound needs the union; sequential max is fine because
        # sizes only grow monotonically in our model)
        ct = _analyze_stmt(then, ctx)
        ce2 = _analyze_stmt(els, ctx) if els is not None else C_ONE
        return seq(c0, _maxc(ct, ce2))
    if tag == 'switch':
        _cond, groups = s[1], s[2]
        ce = _parse_expr_toks(_cond)
        c0, _c0 = _expr_cost(ce, ctx)
        best = C_ONE
        for g in groups:
            best = _maxc(best, _analyze_stmts(g, ctx))
        return seq(c0, best)
    if tag == 'loop':
        return _analyze_loop(s[1], s[2], ctx)
    return C_ONE


def _mark_output(expr, ctx):
    st = ctx.st
    toks = expr['toks']
    # only a bare returned variable is output (v[k] merely reads v)
    if len(toks) == 1 and toks[0][0] == 'id':
        e = st.get(toks[0][1])
        if e is not None and e['kind'] == 'cont':
            e['returned'] = True
    for call in expr.get('calls', []):
        # returned temporaries (return s.lower()) count as output space
        fn = _strip_scope(call['func'])
        if fn in ('substr', 'lower', 'upper', 'sorted', 'copy', 'join',
                  'split', 'c_str'):
            r = _resolve_recv(call.get('recv'), st)
            if r is not None and r['kind'] == 'cont':
                ctx.tmps.append(('out', r['size']))


def _calls_in_stmts(stmts):
    out = set()

    def walk(s):
        tag = s[0]
        if tag == 'block':
            for x in s[1]:
                walk(x)
        elif tag == 'loop':
            walk(s[2])
        elif tag == 'if':
            walk(s[2])
            if s[3] is not None:
                walk(s[3])
        elif tag == 'switch':
            for g in s[2]:
                for x in g:
                    walk(x)
        elif tag == 'expr':
            e = _parse_expr_toks(s[1])
            for c in e['calls']:
                out.add(_strip_scope(c['func']))
                for a in c['args']:
                    _calls_in_toks(a, out)
        elif tag == 'decl':
            for _n, _d, init in s[2]:
                if init is not None:
                    _calls_in_toks(init[1], out)
        elif tag == 'return' and s[1]:
            e = _parse_expr_toks(s[1])
            for c in e['calls']:
                out.add(_strip_scope(c['func']))
    for s in stmts:
        walk(s)
    return out


def _calls_in_toks(toks, out):
    calls = []
    _collect_calls(toks, 0, len(toks), calls)
    for c in calls:
        out.add(_strip_scope(c['func']))


# ---- loops ----

def _stmt_assigns(stmts, into_loops=False):
    """All (target, op, rhs_expr) in stmts (and nested ifs)."""
    out = []

    def walk(s):
        tag = s[0]
        if tag == 'block':
            for x in s[1]:
                walk(x)
        elif tag == 'if':
            walk(s[2])
            if s[3] is not None:
                walk(s[3])
        elif tag == 'switch':
            for g in s[2]:
                for x in g:
                    walk(x)
        elif tag == 'loop':
            if into_loops:
                walk(s[2])
        elif tag == 'expr':
            e = _parse_expr_toks(s[1])
            if e.get('assign'):
                (base, kind), op, rhs = e['assign']
                out.append((base, kind, op, rhs))
        elif tag == 'decl':
            for name, _d, init in s[2]:
                if init is not None:
                    k, payload = init
                    if k == 'expr':
                        out.append((name, 'plain', '=',
                                    _parse_expr_toks(payload)))
                    else:
                        out.append((name, 'plain', '=init', None))
    for s in stmts:
        walk(s)
    return out


def _resets_in(stmts):
    """Vars plain-assigned (non-append) or decl-initialized, by block id."""
    out = {}

    def walk(s, bid):
        tag = s[0]
        if tag == 'block':
            for x in s[1]:
                walk(x, bid)
        elif tag == 'if':
            walk(s[2], bid + 'T')
            if s[3] is not None:
                walk(s[3], bid + 'E')
        elif tag == 'switch':
            for g in s[2]:
                for x in g:
                    walk(x, bid + 'S')
        elif tag == 'loop':
            pass  # resets inside nested loops belong to another context
        elif tag == 'expr':
            e = _parse_expr_toks(s[1])
            if e.get('assign'):
                (base, _k), op, rhs = e['assign']
                # plain rebinding resets the buffer, except
                # self-accumulation (buf = buf + piece), which grows it
                if op == '=' and base is not None and not (
                        rhs is not None and _mentions(rhs, base)):
                    out.setdefault(bid, set()).add(base)
        elif tag == 'decl':
            for name, _d, init in s[2]:
                if init is not None:
                    out.setdefault(bid, set()).add(name)
    for s in stmts:
        walk(s, 'B')
    return out


def _algo_arg_base(call, st=None):
    """Container base a free algorithm call operates on, if resolvable."""
    for a in call.get('args', []):
        calls = []
        _collect_calls(a, 0, len(a), calls)
        for c in calls:
            if _strip_scope(c['func']) in ('begin', 'end') and \
                    c['recv'] is not None and c['recv'].get('base'):
                return c['recv']['base']
    if len(call.get('args', [])) == 1:
        a = call['args'][0]
        if len(a) == 1 and a[0][0] == 'id':
            return a[0][1]
    return None


def _linearbuf_in(stmts):
    """(base, block_id) of linear-size buffer ops (reverse/find/scan)."""
    out = []

    def walk(s, bid):
        tag = s[0]
        if tag == 'block':
            for x in s[1]:
                walk(x, bid)
        elif tag == 'if':
            walk(s[2], bid + 'T')
            if s[3] is not None:
                walk(s[3], bid + 'E')
        elif tag == 'switch':
            for g in s[2]:
                for x in g:
                    walk(x, bid + 'S')
        elif tag == 'loop':
            pass  # ops inside nested loops belong to another context
        elif tag in ('expr', 'return'):
            toks = s[1]
            if toks:
                e = _parse_expr_toks(toks)
                for c in e['calls']:
                    fn = _strip_scope(c['func'])
                    if fn in ('reverse', 'find', 'count', 'search',
                              'max_element', 'min_element'):
                        r = c.get('recv') or {}
                        base = r.get('base')
                        if base is None:
                            base = _algo_arg_base(c)
                        if base:
                            out.append((base, bid))
    for s in stmts:
        walk(s, 'B')
    return out


def _cond_idents(cond):
    return {v for k, v in cond if k == 'id' and v not in _CPP_KW}


def _split_and(cond):
    return _split_top(cond, '&&')


def _cmp_pair(part):
    """Parse `A <op> B`; return (A_toks, op, B_toks) or None."""
    depth = 0
    for i, (k, v) in enumerate(part):
        if k == 'sym' and v in '([{':
            depth += 1
        elif k == 'sym' and v in ')]}':
            depth -= 1
        elif depth == 0 and k == 'sym' and v in (
                '<', '<=', '>', '>=', '!=', '=='):
            return part[:i], v, part[i + 1:]
    return None


def _is_plain_ident(toks):
    return len(toks) == 1 and toks[0][0] == 'id'


def _assigns_to(var, assigns):
    return [(b, k, op, r) for (b, k, op, r) in assigns if b == var]


def _rhs_has(toks, *names):
    ids = {v for k, v in toks if k == 'id'}
    return any(n in ids for n in names)


def _rhs_div2(toks):
    """True if tokens divide by two (mid computation)."""
    for i, (k, v) in enumerate(toks):
        if k == 'sym' and v == '/' and i + 1 < len(toks) and \
                toks[i + 1][0] == 'num':
            try:
                if float(toks[i + 1][1].rstrip('uUlLfF')) == 2:
                    return True
            except ValueError:
                pass
        if k == 'sym' and v == '>>' and i + 1 < len(toks) and \
                toks[i + 1] == ('num', '1'):
            return True
    return False


def _classify_while(cond, stmts, ctx):
    st = ctx.st
    assigns = _stmt_assigns([('block', list(stmts))])
    parts = _split_and(cond)
    # 1. halving search: two scalar vars, mid definition, narrowing updates
    if len(parts) == 1:
        pr = _cmp_pair(parts[0])
        if pr is not None:
            l_, op, r = pr
            if op in ('<=', '<', '>=', '>'):
                ids = [t[1] for t in l_ + r if t[0] == 'id'
                       and t[1] not in _CPP_KW]
                scal = [x for x in dict.fromkeys(ids)
                        if st.get(x) is not None and
                        st[x]['kind'] == 'scalar']
                if len(scal) >= 2:
                    L, H = scal[0], scal[1]
                    if _halving_evidence(L, H, assigns) is not None:
                        for cand_v in (st[H]['sval'], st[L]['sval']):
                            if cand_v[0] == 'size':
                                return ('log', cand_v[1]), _MED, {cand_v[1]}
                        hv, lv = st[H]['sval'], st[L]['sval']
                        if hv[0] == 'const' and lv[0] == 'const':
                            return ('const',), _HIGH, set()
                        # scalar int bounds (val:n) still bound the search
                        return ('log', 'in:search'), _MED, set()
    # 2. digit shrink: single var, divide-out update
    ids = [t for t in _cond_idents(cond)]
    if len(ids) == 1:
        X = ids[0]
        ups = _assigns_to(X, assigns)
        if ups and all(_is_shrink(u, X) for u in ups):
            sv, _c = _sval_of_ident(X, st)
            v = sv[1] if sv[0] == 'size' else ('val:' + X)
            return ('log', v), _MED, {v}
    # 3. index advance: every bound var incremented on all paths
    adv = _advance_vars(parts, stmts, st)
    if adv is not None:
        varlist, mconf = adv
        if len(varlist) == 1:
            return ('lin', varlist[0]), mconf, set(varlist)
        if len(varlist) > 1:
            return ('sum', varlist), mconf, set(varlist)
        return ('const',), mconf, set()  # all-const bounds, verified
    # 4. cycle chase: p = cont[p[...]], termination on equality
    cyc = _cycle_var(cond, assigns, st)
    if cyc is not None:
        return ('lin', cyc), _MED, {cyc}
    return ('unk',), _LOW, set()


def _halving_evidence(L, H, assigns):
    """Mid definition plus narrowing-only updates to [L, H]; else None."""
    mid = None
    for (b, _k, op, rhs) in assigns:
        if b in (L, H) or op not in ('=', '=init') or rhs is None:
            continue
        if _rhs_has(rhs['toks'], L, H) and _rhs_div2(rhs['toks']):
            mid = b
            break
    if mid is None:
        return None
    for (b, _k, op, rhs) in assigns:
        if b not in (L, H):
            continue
        if not (op == '=' and rhs is not None
                and _rhs_has(rhs['toks'], mid)):
            return None  # any other write to the bounds breaks halving
    return (mid, True)


def _is_shrink(u, X):
    _b, _k, op, rhs = u
    if rhs is None:
        return False
    t = rhs['toks']
    if op in ('/=', '%=', '>>='):
        return True
    if op == '=' and len(t) == 3 and t[0] == ('id', X) and \
            t[1][0] == 'sym' and t[1][1] in ('/', '%') and t[2][0] == 'num':
        return True
    if op == '=' and _rhs_has(t, X) and _rhs_div2(t):
        return True
    return False


def _advance_vars(parts, body, st):
    """Bound vars all incremented on every path; return (vars, conf)."""
    # disjunctive bounds cannot be bounded this way
    for p in parts:
        if len(_split_top(p, '||')) > 1:
            return None
    pairs = []
    for p in _split_top_many(parts):
        pr = _cmp_pair(p)
        if pr is None:
            return None
        l_, op, r = pr
        if op in ('<', '<=') and _is_plain_ident(l_):
            pairs.append((l_[0][1], r))
        elif op in ('>', '>=') and _is_plain_ident(r):
            pairs.append((r[0][1], l_))
        else:
            return None
    if not pairs:
        return None
    idxs = set()
    varlist = []
    for var, bound in pairs:
        e = st.get(var)
        if e is None or e['kind'] != 'scalar':
            return None
        idxs.add(var)
        s, c = _sizeinfo(bound, st)
        if s[0] == 'size':
            varlist.append(s[1])
        elif s[0] == 'min':
            varlist.append(s[1][0])
        elif s[0] == 'const':
            continue
        else:
            return None
    # every path must advance at least one of the indices
    if not _advances_some(body, idxs):
        return None
    varlist = list(dict.fromkeys(varlist))
    if not varlist:
        return [], _HIGH
    return varlist, _MED


def _split_top_many(parts):
    out = []
    for p in parts:
        out.extend(_split_top(p, '||'))
    return out


def _advances_some(stmts, idxs):
    """Every execution path increments >= 1 of idxs (else False).

    Overwriting an index, or a path that advances nothing (a missing
    else-branch, a nested loop), fails the proof.  Sequential statements
    compose disjunctively: progress in any one of them suffices.
    """
    if isinstance(stmts, tuple):
        stmts = stmts[1] if stmts[0] == 'block' else [stmts]
    for s in stmts:
        if _advances_some_1(s, idxs):
            return True
    return False


def _is_step(toks, var):
    """Tokens of the form `var +/- const` (a linear index step)."""
    return len(toks) == 3 and toks[0] == ('id', var) and \
        toks[1][0] == 'sym' and toks[1][1] in ('+', '-') and \
        toks[2][0] == 'num'


def _advances_some_1(s, idxs):
    tag = s[0]
    if tag == 'loop':
        return False  # too complex to verify inside
    if tag == 'if':
        if s[3] is None:
            return False  # fall-through path may advance nothing
        return _advances_some(s[2], idxs) and _advances_some(s[3], idxs)
    if tag == 'switch':
        return all(_advances_some(g, idxs) for g in s[2])
    if tag == 'expr':
        e = _parse_expr_toks(s[1])
        if e.get('assign'):
            (b, _k), op, rhs = e['assign']
            if b in idxs:
                if op in ('+=', '-='):
                    return True
                # i = i +/- const is a linear step as well
                if op == '=' and rhs is not None and \
                        _is_step(rhs['toks'], b):
                    return True
                return False
            return False
        return any(v in e.get('incs', set()) for v in idxs)
    if tag in ('return', 'flow'):
        return True  # path ends: the loop exits, adding no trips
    if tag == 'decl':
        for name, _d, _i in s[2]:
            if name in idxs:
                return False
        return False
    if tag == 'block':
        return _advances_some(s[1], idxs)
    return False


def _advances_on_all_paths(stmts, var):
    return _advances_some(stmts, {var})


def _cycle_var(cond, assigns, st):
    prs = _split_and(cond)
    if len(prs) != 1:
        return None
    pr = _cmp_pair(prs[0])
    if pr is None or pr[1] not in ('!=', '=='):
        return None
    l_, _op, r = pr
    if not (_is_plain_ident(l_) and _is_plain_ident(r)):
        return None
    P, Q = l_[0][1], r[0][1]
    ok = 0
    cont = None
    for V in (P, Q):
        for (b, _k, op, rhs) in assigns:
            if b != V or rhs is None or op != '=':
                continue
            t = rhs['toks']
            # V = C[V...] with 1-2 levels of subscript
            if t and t[0][0] == 'id':
                C = t[0][1]
                rest = t[1:]
                if rest and rest[0] == ('sym', '['):
                    e = st.get(C)
                    if e is not None and e['kind'] == 'cont':
                        ok += 1
                        cont = C
    if ok >= 1 and cont is not None:
        e = st.get(cont)
        if e['sizevar'] is not None:
            return e['sizevar']
        if e['size'].ok() and len(e['size'].terms) == 1:
            vs = list(e['size'].terms[0].vars())
            if len(vs) == 1:
                return vs[0]
    return None


def _classify_classic(init, cond, incr, ctx, outer_vars):
    st = ctx.st
    # loop variable from the condition
    pr = _cmp_pair(cond)
    if pr is None:
        # empty condition: for(;;) or for(x;y;)? -> unknown unless range
        if not cond:
            return ('unk',), _LOW, set()
        return ('unk',), _LOW, set()
    l_, op, r = pr
    if op in ('<', '<=', '!=') and _is_plain_ident(l_):
        var, bound = l_[0][1], r
    elif op in ('>', '>=') and _is_plain_ident(r):
        var, bound = r[0][1], l_
    else:
        return ('unk',), _LOW, set()
    # the increment must actually move the loop variable; an empty or
    # unrelated increment cannot be bounded structurally.
    if not incr:
        return ('unk',), _LOW, set()
    if not any(k == 'id' and v == var for k, v in incr):
        return ('unk',), _LOW, set()
    # init must establish var (anything except a widening mystery is fine)
    # multiplicative step -> logarithmic trips
    mult = False
    for t in incr:
        if t == ('sym', '*=') or t == ('sym', '/='):
            mult = True
    if not mult and len(incr) >= 3:
        # var = var * c / var = var / c
        if incr[0][0] == 'id' and incr[0][1] == var:
            ops = [v for k, v in incr if k == 'sym']
            if '*' in ops or '/' in ops:
                mult = True
    siv, sc = _sizeinfo(bound, st)
    if mult:
        if siv[0] in ('size', 'min'):
            v = siv[1] if siv[0] == 'size' else siv[1][0]
            return ('log', v), _MED, _siv_vars(siv)
        return ('unk',), _LOW, set()
    t, c = _trips_of_siv(siv, sc)
    return t, c, _siv_vars(siv)


def _cond_var(cond):
    """The compared loop variable of a classic-for condition, if any."""
    pr = _cmp_pair(cond)
    if pr is None:
        return None
    l_, op, r = pr
    if op in ('<', '<=', '!=') and _is_plain_ident(l_):
        return l_[0][1]
    if op in ('>', '>=') and _is_plain_ident(r):
        return r[0][1]
    return None


def _classify_range(decl_toks, cont_toks, ctx):
    st = ctx.st
    calls = []
    _collect_calls(cont_toks, 0, len(cont_toks), calls)
    elem = None
    dt = [t for t in decl_toks if t[0] == 'id' and t[1] not in _CPP_KW]
    if dt:
        elem = dt[-1][1]
    if len(cont_toks) == 1 and cont_toks[0][0] == 'id':
        base = cont_toks[0][1]
        e = st.get(base)
        if e is not None and e['kind'] == 'cont':
            siv = _trip_var_of(e)
            if siv[0] == 'const':
                return ('const',), _HIGH, base, elem
            if siv[0] == 'size':
                return ('lin', siv[1]), _HIGH, base, elem
            return ('unk',), _LOW, base, elem
        if e is None:
            return ('lin', 'in:' + base), _MED, base, elem
        return ('unk',), _LOW, base, elem
    # arbitrary container expression: try its size
    s, c = _sizeinfo(cont_toks, st)
    if s[0] == 'size':
        return ('lin', s[1]), c, None, elem
    return ('unk',), _LOW, None, elem


def _declare_range_elem(elem, decl_toks, cont, ctx):
    """Declare a range-for element linked to its container."""
    st = ctx.st
    e = st.get(cont) if cont is not None else None
    if e is not None and e['kind'] == 'cont' and e.get('nested'):
        sv = e['sizevar']
        sub = sv[:-2] + '#1' if sv.endswith('#0') else sv + '#1'
        ne = _new_var('cont', ctype='string', nested=False,
                      size=c_lin(sub), sizevar=sub)
        ne['sources'] = set(e.get('sources', set())) | _cost_vars(e['size'])
        if not ne['sources'] and e.get('sizevar'):
            ne['sources'] = {e['sizevar']}
        ne['elem_of'] = cont
        ne['ddepth'] = len(ctx.loop_stack)
        st[elem] = ne
        return
    e2 = _new_var('scalar')
    e2['ddepth'] = len(ctx.loop_stack)
    e2['elem_of'] = cont
    st[elem] = e2


def _analyze_loop(info, body, ctx):
    st = ctx.st
    form = info['form']
    # amortization pre-scan: linear buffer ops paired with a reset of the
    # same buffer in the same block execute in amortized O(1) per trip.
    resets = _resets_in([body])
    linbuf = _linearbuf_in([body])
    amort = set()
    for base, bid in linbuf:
        if base in resets.get(bid, set()):
            amort.add(base)
    saved_amort = ctx.amortized
    ctx.amortized = amort
    elem = None
    cont = None
    try:
        if form == 'classic':
            trips, tconf, bvars = _classify_classic(
                info['init'], info['cond'], info['incr'], ctx, set())
            condvar = _cond_var(info['cond'])
            if trips[0] != 'unk' and condvar is not None \
                    and not _body_preserves_var(body, condvar):
                trips, tconf = ('unk',), _LOW
            frame = {'trips': trips, 'container': None,
                     'boundvars': bvars, 'cvars': set(bvars),
                     'element': None, 'depth': len(ctx.loop_stack),
                     'index': _loop_index_names(
                         body, {condvar} if condvar else set())}
        elif form == 'range':
            trips, tconf, cont, elem = _classify_range(
                info['decl'], info['container'], ctx)
            cvars = set()
            if cont is not None:
                e = st.get(cont)
                if e is not None and e.get('kind') == 'cont':
                    cvars = set(e.get('sources', set())) | \
                        _cost_vars(e['size'])
                    if not cvars and e.get('sizevar'):
                        cvars = {e['sizevar']}
            frame = {'trips': trips, 'container': cont,
                     'boundvars': set(), 'cvars': cvars, 'element': elem,
                     'depth': len(ctx.loop_stack),
                     'index': _loop_index_names(
                         body, {elem} if elem else set())}
            # (element declared inside run_body, under scope save/restore)
        else:  # while / do
            blk = body[1] if isinstance(body, tuple) and body[0] == 'block' \
                else [body]
            trips, tconf, cvars = _classify_while(info['cond'], blk, ctx)
            condvars = {v for k, v in info['cond'] if k == 'id'
                        and v not in _CPP_KW and st.get(v) is not None
                        and st.get(v)['kind'] == 'scalar'}
            frame = {'trips': trips, 'container': None, 'boundvars': set(),
                     'cvars': set(cvars), 'element': None,
                     'depth': len(ctx.loop_stack),
                     'index': _loop_index_names(body, condvars)}
        scope = _scoped_decl_names([body])
        if form == 'classic':
            scope |= _init_decl_names(info['init'])
        elif form == 'range' and elem:
            scope.add(elem)

        def run_body():
            if trips[0] == 'unk':
                ctx.down_t(_LOW)
                ctx.loop_stack.append(dict(frame, trips=('unk',)))
                ctx.in_loop = True
                try:
                    _analyze_stmt(body, ctx)
                finally:
                    ctx.loop_stack.pop()
                    ctx.in_loop = bool(ctx.loop_stack)
                return Cost(None)
            if elem is not None and form == 'range':
                _declare_range_elem(elem, info['decl'], cont, ctx)
            ctx.loop_stack.append(frame)
            ctx.in_loop = True
            try:
                return _analyze_stmt(body, ctx)
            finally:
                ctx.loop_stack.pop()
                ctx.in_loop = bool(ctx.loop_stack)

        bcost = _scoped_run(st, scope, run_body)
        if trips[0] == 'unk':
            return bcost
        if trips[0] == 'sum':
            tot = C_ONE
            for v in trips[1]:
                tot = seq(tot, nest(('lin', v), bcost))
            ctx.down_t(tconf)
            return tot
        ctx.down_t(tconf)
        return nest(trips, bcost)
    finally:
        ctx.amortized = saved_amort


# ---- functions ----

def _analyze_cpp_function(name, fn, ctx_all, memo, active):
    if name in memo:
        return memo[name]
    if name in active:
        return None  # recursive re-entry: call site assumes O(1)
    active = active | {name}
    st = _init_cpp_params(fn['params'])
    ctx = _Ctx(st, ctx_all)
    ctx.func_name = _strip_scope(name)
    ctx.active = active
    ctx.memo = memo
    body = fn['body']
    stmts = body[1] if isinstance(body, tuple) and body[0] == 'block' \
        else [body]
    calls_here = _calls_in_stmts(stmts)
    time = _analyze_stmts(stmts, ctx)
    # recursion depth from self calls
    if _strip_scope(name) in calls_here:
        depth = _recursion_depth(_strip_scope(name), stmts, st, ctx)
        if depth is not None:
            dcost, dconf = depth
            time = seq(time, dcost)
            ctx.down_t(dconf)
            ctx.tmps.append(('aux', dcost))
    aux_terms = []
    out_terms = []
    for _n, e in st.items():
        if e['kind'] != 'cont':
            continue
        if e.get('input'):
            continue  # the input itself is never auxiliary/output space
        if not e['size'].ok():
            (out_terms if e['returned'] else aux_terms).append(None)
            continue
        if e['returned']:
            out_terms.append(e['size'])
        else:
            aux_terms.append(e['size'])
    for kind, sz in ctx.tmps:
        (out_terms if kind == 'out' else aux_terms).append(sz)
    res = {'time': time, 'tconf': ctx.tconf, 'sconf': ctx.sconf,
           'aux': aux_terms, 'out': out_terms, 'st': st}
    memo[name] = res
    return res


def _recursion_depth(name, stmts, st, ctx):
    """Depth cost of direct self-recursion; None if not recursive."""
    sites = []

    def walk(s):
        tag = s[0]
        if tag == 'block':
            for x in s[1]:
                walk(x)
        elif tag == 'loop':
            walk(s[2])
        elif tag == 'if':
            walk(s[2])
            if s[3] is not None:
                walk(s[3])
        elif tag == 'switch':
            for g in s[2]:
                for x in g:
                    walk(x)
        elif tag in ('expr', 'return') and s[1]:
            e = _parse_expr_toks(s[1])
            for c in e['calls']:
                if _strip_scope(c['func']) == name:
                    sites.append(c)
        elif tag == 'decl':
            for _n, _d, init in s[2]:
                if init is not None:
                    calls = []
                    _collect_calls(init[1], 0, len(init[1]), calls)
                    for c in calls:
                        if _strip_scope(c['func']) == name:
                            sites.append(c)
    for s in stmts:
        walk(s)
    if not sites:
        return None
    if len(sites) >= 2:
        # branching recursion: exponential in the first size argument
        v = _first_size_arg(sites[0], st) or 'in:n'
        return _cost(T((), 0, True, frozenset((v,)))), _MED
    v = _first_size_arg(sites[0], st)
    args = sites[0]['args']
    if args:
        a0 = args[0]
        minus = [t for t in a0 if t == ('sym', '-')]
        plus = [t for t in a0 if t == ('sym', '+')]
        div = [t for t in a0 if t == ('sym', '/')]
        if minus or plus:
            # shrinking by a constant (n - c): linear depth
            if v is None:
                return Cost(None), _LOW
            return c_lin(v), _MED
        if div:
            # shrinking by division (n / c, mid): logarithmic depth
            if v is None:
                return Cost(None), _LOW
            return c_log(v), _MED
    if v is None:
        return Cost(None), _LOW
    return c_lin(v), _LOW


def _first_size_arg(call, st):
    if not call['args']:
        return None
    s, _c = _sizeinfo(call['args'][0], st)
    if s[0] == 'size':
        return s[1]
    if s[0] == 'min':
        return s[1][0]
    return None


def analyze_cpp(text):
    """Analyze C++ source; return (time, tconf, space, sconf)."""
    try:
        toks = _scan_cpp(text)
        methods, free = _parse_solution_methods(toks)
    except Exception:
        return "Unknown", "Low", "Unknown", "Low"
    if not methods:
        return "Unknown", "Low", "Unknown", "Low"
    funcs = dict(methods)
    funcs.update({('free::' + k): v for k, v in free.items()})
    # static call graph between methods
    try:
        callees = {m: _calls_in_stmts(
            f['body'][1] if isinstance(f['body'], tuple) else [f['body']])
            for m, f in methods.items()}
    except Exception:
        return "Unknown", "Low", "Unknown", "Low"
    called = set()
    for m, cs in callees.items():
        for c in cs:
            if c in methods and c != m:
                called.add(c)
    entries = [m for m in methods if m not in called] or list(methods)
    memo = {}
    time = C_ONE
    tconf = _HIGH
    sconf = _HIGH
    aux_all = []
    out_all = []
    try:
        for m in entries:
            res = _analyze_cpp_function(m, methods[m], funcs, memo, set())
            if res is None:
                continue
            time = seq(time, res['time'])
            tconf = _worse(tconf, res['tconf'])
            sconf = _worse(sconf, res['sconf'])
            aux_all.extend(res['aux'])
            out_all.extend(res['out'])
    except Exception:
        return "Unknown", "Low", "Unknown", "Low"
    if any(t is None or not t.ok() for t in aux_all + out_all):
        space_cost = Cost(None)
        sconf = _LOW
    else:
        terms = []
        for t in aux_all + out_all:
            terms.extend(t.terms)
        space_cost = _cost(*terms) if terms else C_ONE
    tlabel = show(time)
    slabel = show(space_cost)
    if tlabel is None:
        tlabel, tconf = "Unknown", "Low"
    if slabel is None:
        slabel, sconf = "Unknown", "Low"
    return tlabel, tconf, slabel, sconf


# --------------------------------------------------------------------------
# Python analysis (stdlib ast -> same cost model)
# --------------------------------------------------------------------------

import ast as _ast


_PY_CHAR_METHODS = {
    'isalnum', 'isalpha', 'isdigit', 'isspace', 'islower', 'isupper',
    'istitle', 'isnumeric', 'isdecimal', 'isidentifier',
}
_PY_LINEAR_SUSPECT = {
    'find', 'search', 'count', 'remove', 'substr', 'indexOf',
    'linear', 'scan', 'index', 'rindex',
}


def _py_new_param(name):
    e = _new_var('unknown', sizevar='in:' + name, input=True)
    e['size'] = c_lin('in:' + name)
    e['sval'] = ('unknown',)
    e['sources'] = {'in:' + name}
    return e


def _py_init_params(args):
    st = {}
    for a in args:
        if a.arg in ('self', 'cls'):
            continue
        st[a.arg] = _py_new_param(a.arg)
    return st


def _py_sval_of(name, st):
    e = st.get(name)
    if e is None:
        return ('size', 'in:' + name), _MED
    if e['kind'] == 'cont':
        siv = _trip_var_of(e)
        if siv is not None and siv[0] != 'unknown':
            return siv, _HIGH
        return ('unknown',), _LOW
    if e['kind'] == 'scalar':
        return e['sval'], _HIGH
    # unknown: expose the size variable (assumes a sized value)
    if e.get('sizevar'):
        return ('size', e['sizevar']), _MED
    return ('unknown',), _LOW


def _py_sizeinfo(node, st):
    if isinstance(node, _ast.Constant):
        return ('const',), _HIGH
    if isinstance(node, _ast.Name):
        return _py_sval_of(node.id, st)
    if isinstance(node, _ast.Call):
        fn, recv = _py_func_name(node.func)
        if fn == 'len' and node.args:
            return _py_sizeinfo(node.args[0], st)
        if fn in ('min', 'max') and node.args:
            vs, conf, anyk = [], _HIGH, False
            for a in node.args:
                if isinstance(a, _ast.Starred):
                    return ('unknown',), _LOW
                s, cc = _py_sizeinfo(a, st)
                conf = _worse(conf, cc)
                anyk = True
                if s[0] == 'size':
                    vs.append(s[1])
                elif s[0] in ('min', 'prod'):
                    vs.extend(s[1])
                elif s[0] != 'const':
                    return ('unknown',), _LOW
            vs = list(dict.fromkeys(vs))
            if not anyk:
                return ('unknown',), _LOW
            if not vs:
                return ('const',), conf
            return ('min', vs), conf
        if fn in ('abs', 'ord', 'chr', 'round', 'hash') and len(node.args) == 1:
            return ('const',), _HIGH
        return ('unknown',), _LOW
    if isinstance(node, _ast.BinOp):
        if isinstance(node.op, (_ast.Mult,)):
            l_, lc = _py_sizeinfo(node.left, st)
            r, rc = _py_sizeinfo(node.right, st)
            vs = []
            for s in (l_, r):
                if s[0] == 'size':
                    vs.append(s[1])
                elif s[0] in ('min', 'prod'):
                    vs.extend(s[1])
                elif s[0] != 'const':
                    return ('unknown',), _LOW
            vs = list(dict.fromkeys(vs))
            if not vs:
                return ('const',), _worse(lc, rc)
            if len(vs) == 1:
                return ('size', vs[0]), _worse(lc, rc)
            return ('prod', vs), _worse(lc, rc)
        if isinstance(node.op, (_ast.Add, _ast.Sub)):
            other = node.right if isinstance(
                node.left, _ast.Constant) else node.left
            const_side = node.left if isinstance(
                node.right, _ast.Constant) else node.right
            if isinstance(const_side, _ast.Constant):
                s, c = _py_sizeinfo(other, st)
                if s[0] in ('size', 'min', 'const'):
                    return s, c
            return ('unknown',), _LOW
        if isinstance(node.op, (_ast.FloorDiv, _ast.Div, _ast.Mod)):
            return ('unknown',), _LOW
        return ('unknown',), _LOW
    if isinstance(node, _ast.UnaryOp):
        return _py_sizeinfo(node.operand, st)
    if isinstance(node, _ast.Subscript):
        if isinstance(node.slice, _ast.Slice):
            return _py_sizeinfo(node.value, st)
        return ('unknown',), _LOW
    if isinstance(node, _ast.IfExp):
        return ('unknown',), _LOW
    return ('unknown',), _LOW


def _py_func_name(func):
    """Return (name, receiver_node_or_None)."""
    if isinstance(func, _ast.Name):
        return func.id, None
    if isinstance(func, _ast.Attribute):
        return func.attr, func.value
    return None, None


def _py_recv_entry(recv, st):
    if recv is None:
        return None
    if isinstance(recv, _ast.Name):
        return st.get(recv.id)
    return 'complex'


def _py_container_size(entry):
    if entry is None or entry == 'complex':
        return None
    if isinstance(entry, dict) and entry.get('kind') == 'cont':
        return entry['size']
    return None


def _py_ensure_kind(entry, kind, ctype):
    if entry is not None and isinstance(entry, dict) and \
            entry.get('kind') == 'unknown':
        entry['kind'] = 'cont'
        entry['ctype'] = ctype
        if entry['size'] is None or not entry['size'].ok():
            entry['size'] = C_ONE
    return entry


def _py_base(node):
    if isinstance(node, _ast.Name):
        return node.id
    return None


_PY_STR_METHODS = {
    'lower', 'upper', 'capitalize', 'title', 'swapcase', 'strip',
    'lstrip', 'rstrip', 'split', 'rsplit', 'splitlines', 'replace',
    'find', 'rfind', 'index', 'rindex', 'count', 'partition',
    'rpartition', 'removeprefix', 'removesuffix', 'zfill', 'center',
    'ljust', 'rjust', 'expandtabs', 'join', 'startswith', 'endswith',
    'format',
}
_PY_LIST_METHODS = {
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'copy',
    'index', 'count', 'sort', 'reverse',
}
_PY_SET_METHODS = {
    'add', 'discard', 'remove', 'pop', 'clear', 'copy', 'update',
    'union', 'intersection', 'difference', 'symmetric_difference',
}
_PY_DICT_METHODS = {
    'get', 'setdefault', 'pop', 'keys', 'values', 'items', 'update',
    'copy', 'clear', 'fromkeys',
}


def _py_infer_recv(fn, recv_e, st):
    """Infer a container type from an unambiguous method name."""
    if recv_e is None or not isinstance(recv_e, dict):
        return None
    if recv_e.get('kind') == 'cont':
        return recv_e
    if recv_e.get('kind') != 'unknown':
        return None
    ctype = None
    if fn in _PY_STR_METHODS:
        ctype = 'str'
    elif fn in _PY_LIST_METHODS:
        ctype = 'list'
    elif fn in _PY_SET_METHODS:
        ctype = 'set'
    elif fn in _PY_DICT_METHODS:
        ctype = 'dict'
    if ctype is None:
        return None
    recv_e['kind'] = 'cont'
    recv_e['ctype'] = ctype
    if recv_e['size'] is None or not recv_e['size'].ok():
        recv_e['size'] = C_ONE
    return recv_e


def _py_call_cost(fn, recvnode, args, keywords, ctx):
    """Python call cost with inline growth effects. Returns (Cost, conf)."""
    st = ctx.st
    recv_e = _py_recv_entry(recvnode, st)
    if recv_e == 'complex':
        recv_e = None
    # usage-based type inference: an unambiguous method name identifies
    # the receiver's container type (documented general rule; ambiguous
    # names resolve toward the linear-time category as a valid upper
    # bound, never toward a cheaper one).
    if fn is not None:
        _py_infer_recv(fn, recv_e, st)

    def _sizes_of(nodes):
        tot = C_ONE
        for a in nodes:
            if isinstance(a, _ast.Starred):
                s = _py_contentsize(a.value, ctx)
            else:
                s = _py_contentsize(a, ctx)
            if s is None:
                return None
            tot = seq(tot, s)
        return tot

    def _size0():
        if args:
            return _py_contentsize(args[0], ctx)
        return C_ONE

    # method on a tracked container
    if isinstance(recv_e, dict) and recv_e.get('kind') == 'cont':
        ctype = recv_e.get('ctype')
        size = recv_e['size']
        v = _single_var(size)
        if fn in ('append', 'add', 'put'):
            _grow_accum(_vname(st, recv_e), C_ONE,
                        (_py_sources(args[0], ctx) if args else set(),
                         _py_eltnames(args[0]) if args else set(),
                         _py_base(args[0]) if args else None), ctx)
            return C_ONE, _HIGH
        if fn in ('extend', 'update', 'union'):
            amt = _sizes_of(args)
            if amt is None or not amt.ok():
                ctx.down_s(_LOW)
                _grow_accum(_vname(st, recv_e), Cost(None),
                            (set(), set(), None), ctx)
                return amt if amt is not None else Cost(None), _LOW
            _grow_accum(_vname(st, recv_e), amt,
                        (_py_sources(args[0], ctx) if args else set(),
                         set(),
                         _py_base(args[0]) if args else None), ctx)
            ctx.down_s(_py_size_conf(amt, st))
            return amt, _HIGH
        if fn in ('pop', 'popitem', 'discard', 'remove', 'popleft'):
            if ctype == 'list':
                if fn == 'pop' and not args:
                    return C_ONE, _HIGH
                # pop(i) / remove(v) scan the list
                return (size if size.ok() else Cost(None),
                        _HIGH if size.ok() else _LOW)
            ctx.down_t(_MED)  # hash average case
            return C_ONE, _MED
        if fn in ('clear',):
            if not recv_e.get('input'):
                recv_e['size'] = C_ONE
                recv_e['sources'] = set()
            return (size if size.ok() else C_ONE), _HIGH
        if fn in ('insert',):
            _grow_accum(_vname(st, recv_e), C_ONE, (set(), set()), ctx)
            return (size if size.ok() else Cost(None),
                    _HIGH if size.ok() else _LOW)
        if fn in ('sort',):
            base = _vname(st, recv_e)
            if base is not None and base in ctx.amortized:
                ctx.down_t(_MED)
                return C_ONE, _MED
            if v is not None:
                ctx.tmps.append(('aux', c_lin(v)))
                return c_sort(v), _HIGH
            ctx.down_t(_LOW)
            return Cost(None), _LOW
        if fn in ('reverse',):
            return (size if size.ok() else Cost(None),
                    _HIGH if size.ok() else _LOW)
        if fn in ('index', 'count'):
            if ctype in ('list', 'tuple', 'str'):
                return (size if size.ok() else Cost(None),
                        _HIGH if size.ok() else _LOW)
            ctx.down_t(_MED)
            return C_ONE, _MED
        if fn in ('get', 'setdefault', 'keys', 'values', 'items',
                  'copy', 'peek', 'front', 'back', 'top', 'empty',
                  'size', '__len__'):
            if fn == 'setdefault':
                _grow_accum(_vname(st, recv_e), C_ONE, (set(), set()), ctx)
            return C_ONE, _HIGH
        if fn in _PY_STR_METHODS:
            if fn == 'join':
                amt = _sizes_of(args)
                if amt is None or not amt.ok():
                    ctx.down_t(_LOW)
                    return Cost(None), _LOW
                ctx.tmps.append(('aux', amt))
                return amt, _HIGH
            if fn in ('find', 'rfind', 'index', 'rindex', 'count',
                      'startswith', 'endswith'):
                # pure scans: no allocation
                return (size if size.ok() else Cost(None),
                        _HIGH if size.ok() else _LOW)
            # allocating string ops: the new string peaks in aux space
            if size.ok():
                ctx.tmps.append(('aux', size))
            return (size if size.ok() else Cost(None),
                    _HIGH if size.ok() else _LOW)
        if fn in _PY_CHAR_METHODS:
            return C_ONE, _HIGH
        if fn in ('startswith', 'endswith'):
            if args and isinstance(args[0], _ast.Constant):
                return C_ONE, _HIGH
            ctx.down_t(_MED)
            return (size if size.ok() else C_ONE), _MED
        if fn in ('format',):
            return (size if size.ok() else C_ONE), _MED
        if ctx.in_loop and fn in _PY_LINEAR_SUSPECT:
            ctx.down_t(_LOW)
            return Cost(None), _LOW
        ctx.down_t(_MED)
        return C_ONE, _MED

    # constructors / builtins by name
    if recvnode is None and fn in ('sorted', 'list', 'set', 'dict',
                                   'tuple', 'frozenset', 'Counter',
                                   'defaultdict', 'deque'):
        amt = _sizes_of(args) if args else C_ONE
        if amt is None or not amt.ok():
            ctx.down_t(_LOW)
            ctx.down_s(_LOW)
            return Cost(None), _LOW
        # hash-based construction averages linear time (documented)
        if args and fn in ('set', 'frozenset', 'dict', 'defaultdict',
                           'Counter'):
            ctx.down_t(_MED)
            ctx.down_s(_MED)
        if fn == 'sorted':
            ctx.tmps.append(('aux', amt))
            ctx.down_s(_py_size_conf(amt, st))
            sv = _single_var(amt)
            if sv is not None:
                return c_sort(sv), _HIGH
            # multi-var sorted: merge to a single linearithmic term
            ctx.down_t(_MED)
            return _cost(T((('mgd:py', 1),), 1)), _MED
        ctx.down_s(_py_size_conf(amt, st))
        return amt, _HIGH
    if recvnode is None and fn in ('len', 'range', 'enumerate', 'zip',
                                   'reversed', 'iter', 'isinstance',
                                   'hasattr', 'callable', 'id', 'ord',
                                   'chr', 'abs', 'round', 'divmod', 'pow'):
        return C_ONE, _HIGH
    if recvnode is None and fn == 'hash':
        if args:
            s = _py_contentsize(args[0], ctx)
            if s is not None and s.ok() and len(s.terms) == 1:
                return s, _HIGH
        return C_ONE, _MED
    if recvnode is None and fn in ('min', 'max', 'sum', 'any', 'all'):
        if len(args) == 1 and not keywords:
            s = _py_contentsize(args[0], ctx)
            if s is None or not s.ok():
                ctx.down_t(_LOW)
                return Cost(None), _LOW
            return s, _HIGH
        # several scalar arguments: O(1); anything bigger: first size
        big = None
        for a in args:
            s = _py_contentsize(a, ctx)
            if s is None:
                ctx.down_t(_LOW)
                return Cost(None), _LOW
            if s.ok() and len(s.terms) == 1 and len(s.terms[0].pows) > 0 \
                    and big is None:
                big = s
        if big is not None:
            ctx.down_t(_MED)
            return big, _MED
        return C_ONE, _HIGH
    if recvnode is None and fn in ('map', 'filter'):
        amt = _sizes_of(args[1:2]) if len(args) > 1 else C_ONE
        ctx.down_t(_MED)
        return amt if amt is not None and amt.ok() else C_ONE, _MED
    if recvnode is None and fn in ('print',):
        amt = _sizes_of(args)
        ctx.down_t(_MED)
        return (amt if amt is not None and amt.ok() else C_ONE), _MED
    if recvnode is None and fn in ('int', 'float', 'bool', 'complex',
                                   'str', 'repr', 'bytes', 'bytearray'):
        # int('123') scans digits; str(3.14) is bounded
        if args and fn in ('int', 'float'):
            a0 = args[0]
            if isinstance(a0, _ast.Name):
                e0 = st.get(a0.id)
                if isinstance(e0, dict) and e0.get('kind') == 'cont':
                    return (e0['size'] if e0['size'].ok()
                            else Cost(None)), _MED
        return C_ONE, _HIGH
    if recvnode is None and fn in ('open', 'input', 'super'):
        ctx.down_t(_MED)
        return C_ONE, _MED
    # "...".join(items): linear in the joined items
    if fn == 'join' and isinstance(recvnode, _ast.Constant) and \
            isinstance(recvnode.value, str):
        amt = _sizes_of(args)
        if amt is None or not amt.ok():
            ctx.down_t(_LOW)
            return Cost(None), _LOW
        ctx.tmps.append(('aux', amt))
        return amt, _HIGH
    if recvnode is None and fn is not None and fn[:1].isupper():
        # ClassName(...) construction of an unknown class
        ctx.down_t(_MED)
        return C_ONE, _MED    # unknown call: assume O(1), never High
    ctx.down_t(_MED)
    tot, conf = C_ONE, _MED
    for a in list(args) + [k.value for k in keywords]:
        c, cc = _py_expr_cost(a, ctx)
        tot = seq(tot, c)
        conf = _worse(conf, cc)
    return tot, conf


def _vname(st, entry):
    for name, e in st.items():
        if e is entry:
            return name
    return None


def _single_var(cost):
    if cost.ok() and len(cost.terms) == 1:
        t = cost.terms[0]
        if len(t.pows) == 1 and t.pows[0][1] == 1 and t.logs == 0 \
                and not t.exp2:
            return t.pows[0][0]
    return None


def _py_eltnames(node):
    if isinstance(node, _ast.Name):
        return {node.id}
    out = set()
    for ch in _ast.walk(node):
        if isinstance(ch, _ast.Name):
            out.add(ch.id)
    return out


def _py_sources(node, ctx):
    st = ctx.st
    if node is None:
        return set()
    if isinstance(node, _ast.Constant):
        return set()
    if isinstance(node, _ast.Name):
        e = st.get(node.id)
        if e is None:
            return set()
        if e.get('sources'):
            return set(e['sources'])
        if e.get('input'):
            return {e.get('sizevar', 'in:' + node.id)}
        if e.get('elem_of'):
            # a loop element carries its container's sources, so buffers
            # accumulated from elements partition the input
            c = st.get(e['elem_of'])
            if isinstance(c, dict):
                out = set(c.get('sources', set()))
                if c.get('sizevar'):
                    out.add(c['sizevar'])
                return out
        return set()
    if isinstance(node, _ast.Attribute):
        return _py_sources(node.value, ctx)
    if isinstance(node, _ast.Subscript):
        return _py_sources(node.value, ctx)
    if isinstance(node, (_ast.BinOp, _ast.BoolOp)):
        out = set()
        for ch in _ast.iter_child_nodes(node):
            out.update(_py_sources(ch, ctx))
        return out
    if isinstance(node, _ast.UnaryOp):
        return _py_sources(node.operand, ctx)
    if isinstance(node, _ast.Call):
        fn, recv = _py_func_name(node.func)
        out = _py_sources(recv, ctx) if recv is not None else set()
        for a in node.args:
            out.update(_py_sources(a, ctx))
        return out
    if isinstance(node, _ast.IfExp):
        return _py_sources(node.body, ctx) | _py_sources(node.orelse, ctx)
    if isinstance(node, (_ast.ListComp, _ast.SetComp, _ast.GeneratorExp,
                         _ast.DictComp)):
        out = set()
        for gen in node.generators:
            out.update(_py_sources(gen.iter, ctx))
        return out
    if isinstance(node, (_ast.List, _ast.Tuple, _ast.Set, _ast.Dict,
                         _ast.JoinedStr, _ast.Starred)):
        out = set()
        for ch in _ast.iter_child_nodes(node):
            if isinstance(ch, _ast.expr):
                out.update(_py_sources(ch, ctx))
        return out
    return set()


def _py_size_conf(cost, st):
    """High unless the size flows through unknown-typed values."""
    if cost is None or not cost.ok():
        return _LOW
    for t in cost.terms:
        for v in t.vars():
            base = v[3:] if v.startswith('in:') else None
            if base is None and '|' not in v and not v.startswith('mgd:'):
                base = v
            e = st.get(base) if base else None
            if isinstance(e, dict) and e.get('kind') == 'unknown':
                return _MED
    return _HIGH


def _py_contentsize(node, ctx):
    st = ctx.st
    if node is None:
        return C_ONE
    if isinstance(node, _ast.Constant):
        return C_ONE
    if isinstance(node, _ast.Name):
        e = st.get(node.id)
        if isinstance(e, dict) and e.get('kind') == 'cont':
            return e['size']
        if isinstance(e, dict) and e.get('sizevar'):
            # opaque sized value (e.g. an untyped parameter): its own
            # size variable is a valid upper bound for derived sizes
            return c_lin(e['sizevar'])
        if e is None:
            return c_lin('in:' + node.id)
        return C_ONE
    if isinstance(node, _ast.Subscript):
        if isinstance(node.slice, _ast.Slice):
            return _py_contentsize(node.value, ctx)
        return C_ONE
    if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Add):
        l_ = _py_contentsize(node.left, ctx)
        r = _py_contentsize(node.right, ctx)
        if l_ is None or r is None:
            return None
        return seq(l_, r)
    if isinstance(node, _ast.BinOp) and isinstance(node.op, _ast.Mult):
        l_ = _py_contentsize(node.left, ctx)
        r = _py_contentsize(node.right, ctx)
        if l_ is None or r is None:
            return None
        # str repetition: size scales with the repeat count variable
        return seq(l_, r)
    if isinstance(node, _ast.Call):
        fn, recv = _py_func_name(node.func)
        if fn in ('sorted', 'list', 'set', 'tuple', 'frozenset',
                  'Counter', 'dict', 'defaultdict', 'deque', 'reversed',
                  'map', 'filter'):
            tot = C_ONE
            for a in node.args:
                s = _py_contentsize(a, ctx)
                if s is None:
                    return None
                tot = seq(tot, s)
            return tot
        if fn in ('join', 'split', 'replace', 'strip', 'lstrip',
                  'rstrip', 'lower', 'upper', 'capitalize', 'title'):
            r = _py_recv_entry(recv, st)
            if isinstance(r, dict) and r.get('kind') == 'cont':
                return r['size']
            if fn == 'join' and node.args:
                return _py_contentsize(node.args[0], ctx)
            return C_ONE
        if fn in ('keys', 'values', 'items'):
            return C_ONE
        if isinstance(recv, _ast.Constant) and isinstance(recv.value, str):
            # "...".join(c): the joined size
            if fn == 'join' and node.args:
                return _py_contentsize(node.args[0], ctx)
            return C_ONE
        return C_ONE
    if isinstance(node, (_ast.List, _ast.Tuple, _ast.Set)):
        tot = C_ONE
        for e in node.elts:
            if isinstance(e, _ast.Starred):
                s = _py_contentsize(e.value, ctx)
                if s is None:
                    return None
                tot = seq(tot, s)
        return tot
    if isinstance(node, _ast.Dict):
        return C_ONE
    if isinstance(node, _ast.IfExp):
        l_ = _py_contentsize(node.body, ctx)
        r = _py_contentsize(node.orelse, ctx)
        if l_ is None or r is None:
            return None
        return _maxc(l_, r)
    if isinstance(node, (_ast.ListComp, _ast.SetComp, _ast.GeneratorExp)):
        t, _c = _py_comp(node, ctx, dry=True)
        return t
    if isinstance(node, _ast.JoinedStr):
        return C_ONE
    return C_ONE


def _py_operand_size(node, ctx):
    s = _py_contentsize(node, ctx)
    if s is None:
        ctx.down_t(_LOW)
        return Cost(None)
    # scalars collapse to O(1): only container sizes charge
    if s.ok() and len(s.terms) == 1 and len(s.terms[0].pows) == 0:
        return C_ONE
    return s


def _py_expr_cost(node, ctx):
    c, conf = _py_expr_cost_inner(node, ctx)
    ctx.down_t(conf)
    return c, conf


def _py_expr_cost_inner(node, ctx):
    st = ctx.st
    if node is None:
        return C_ONE, _HIGH
    if isinstance(node, _ast.Constant):
        return C_ONE, _HIGH
    if isinstance(node, _ast.Name):
        return C_ONE, _HIGH
    if isinstance(node, _ast.Attribute):
        return C_ONE, _HIGH
    if isinstance(node, _ast.BinOp):
        l_, lc = _py_expr_cost(node.left, ctx)
        r, rc = _py_expr_cost(node.right, ctx)
        tot = seq(l_, r)
        conf = _worse(lc, rc)
        if isinstance(node.op, _ast.Add):
            tot = seq(tot, _py_operand_size(node.left, ctx),
                      _py_operand_size(node.right, ctx))
        return tot, conf
    if isinstance(node, _ast.BoolOp):
        tot, conf = C_ONE, _HIGH
        for v in node.values:
            c, cc = _py_expr_cost(v, ctx)
            tot = seq(tot, c)
            conf = _worse(conf, cc)
        return tot, conf
    if isinstance(node, _ast.UnaryOp):
        return _py_expr_cost(node.operand, ctx)
    if isinstance(node, _ast.Compare):
        tot, conf = C_ONE, _HIGH
        parts = [node.left] + list(node.comparators)
        for v in parts:
            c, cc = _py_expr_cost(v, ctx)
            tot = seq(tot, c)
            conf = _worse(conf, cc)
        for op, right in zip(node.ops, node.comparators):
            if isinstance(op, (_ast.In, _ast.NotIn)):
                tot = seq(tot, _py_membership(right, ctx))
        return tot, conf
    if isinstance(node, _ast.Subscript):
        tot, conf = _py_expr_cost(node.value, ctx)
        sl = node.slice
        if isinstance(sl, _ast.Slice):
            for part in (sl.lower, sl.upper, sl.step):
                if part is not None:
                    c, cc = _py_expr_cost(part, ctx)
                    tot = seq(tot, c)
                    conf = _worse(conf, cc)
            base = _py_recv_entry(node.value, st)
            if isinstance(base, dict) and base.get('kind') == 'cont':
                tot = seq(tot, base['size'])
            else:
                tot = seq(tot, C_ONE)
            ctx.tmps.append(('aux', _py_contentsize(node, ctx) or C_ONE))
        else:
            c, cc = _py_expr_cost(sl, ctx)
            tot = seq(tot, c)
            conf = _worse(conf, cc)
        return tot, conf
    if isinstance(node, _ast.Call):
        fn, recv = _py_func_name(node.func)
        # argument evaluation first
        tot, conf = C_ONE, _HIGH
        for a in list(node.args) + [k.value for k in node.keywords]:
            c, cc = _py_expr_cost(a, ctx)
            tot = seq(tot, c)
            conf = _worse(conf, cc)
        c, cc = _py_call_cost(fn, recv, node.args, node.keywords, ctx)
        return seq(tot, c), _worse(conf, cc)
    if isinstance(node, _ast.IfExp):
        c, cc = _py_expr_cost(node.test, ctx)
        l_, lc = _py_expr_cost(node.body, ctx)
        r, rc = _py_expr_cost(node.orelse, ctx)
        return seq(c, _maxc(l_, r)), _worse(cc, _worse(lc, rc))
    if isinstance(node, (_ast.ListComp, _ast.SetComp, _ast.GeneratorExp,
                         _ast.DictComp)):
        t, cc = _py_comp(node, ctx, dry=False)
        return t, cc
    if isinstance(node, (_ast.List, _ast.Tuple, _ast.Set)):
        tot, conf = C_ONE, _HIGH
        for e in node.elts:
            c, cc = _py_expr_cost(e, ctx)
            tot = seq(tot, c)
            conf = _worse(conf, cc)
        return tot, conf
    if isinstance(node, _ast.Dict):
        tot, conf = C_ONE, _HIGH
        for k, v in zip(node.keys, node.values):
            for e in (k, v):
                if e is not None:
                    c, cc = _py_expr_cost(e, ctx)
                    tot = seq(tot, c)
                    conf = _worse(conf, cc)
        return tot, conf
    if isinstance(node, _ast.JoinedStr):
        tot, conf = C_ONE, _MED
        for v in node.values:
            c, cc = _py_expr_cost(v, ctx) if isinstance(
                v, _ast.expr) else (C_ONE, _HIGH)
            tot = seq(tot, c)
            conf = _worse(conf, cc)
        return tot, conf
    if isinstance(node, _ast.Starred):
        return _py_expr_cost(node.value, ctx)
    if isinstance(node, _ast.NamedExpr):
        c, cc = _py_expr_cost(node.value, ctx)
        _py_assign_name(node.target, node.value, ctx)
        return c, cc
    if isinstance(node, _ast.Lambda):
        return C_ONE, _MED  # comparators etc: creation is O(1)
    if isinstance(node, (_ast.Await, _ast.Yield, _ast.YieldFrom)):
        return C_ONE, _MED
    return C_ONE, _MED


def _py_membership(node, ctx):
    st = ctx.st
    base = node
    while isinstance(base, _ast.Subscript) and not isinstance(
            base.slice, _ast.Slice):
        base = base.value
    if isinstance(base, _ast.Name):
        e = st.get(base.id)
        if isinstance(e, dict) and e.get('kind') == 'cont':
            if e.get('ctype') in ('set', 'dict', 'frozenset',
                                  'Counter', 'defaultdict'):
                ctx.down_t(_MED)
                return C_ONE
            if e.get('ctype') in ('list', 'str', 'tuple'):
                return e['size'] if e['size'].ok() else Cost(None)
    if isinstance(base, _ast.Constant) and isinstance(base.value, str):
        return C_ONE
    ctx.down_t(_LOW)
    return Cost(None)


def _py_comp(node, ctx, dry):
    """Comprehension cost; dry=True returns only the produced size."""
    st = ctx.st
    gens = node.generators
    if not gens:
        return C_ONE, _HIGH
    # comprehension targets are function-scoped in py3: save/restore
    saved = {}
    for g in gens:
        for t in _py_targets(g.target):
            if t not in saved:
                saved[t] = st.get(t, _ABSENT)
    try:
        return _py_comp_inner(node, ctx, dry)
    finally:
        for t, v in saved.items():
            if v is _ABSENT:
                st.pop(t, None)
            else:
                st[t] = v


def _py_comp_inner(node, ctx, dry):
    first = gens[0]
    iterc, itercf = _py_expr_cost(first.iter, ctx)
    trips, tconf, cbase = _py_iter_trips(first.iter, ctx)
    # declare target(s) as scalars linked to the container
    for t in _py_targets(first.target):
        if t not in st:
            e = _new_var('scalar')
            e['elem_of'] = cbase
            st[t] = e
    frame = {'trips': trips, 'container': cbase, 'boundvars': set(),
             'cvars': set(), 'element': None, 'depth': len(ctx.loop_stack)}
    if cbase is not None:
        e = st.get(cbase)
        if isinstance(e, dict) and e.get('kind') == 'cont':
            frame['cvars'] = set(e.get('sources', set())) | {e['sizevar']}
        else:
            frame['cvars'] = {'in:' + cbase}
    tgts = _py_targets(first.target)
    if len(tgts) == 1:
        frame['element'] = tgts[0]
    inner = C_ONE
    iconf = _HIGH
    rest = gens[1:]
    if rest:
        # nested generators: approximate by nesting trip counts
        for g in rest:
            gc, gcc = _py_expr_cost(g.iter, ctx)
            inner = seq(inner, gc)
            iconf = _worse(iconf, gcc)
            gt, gtc = _py_iter_trips(g.iter, ctx)
            iconf = _worse(iconf, gtc)
            if gt[0] == 'unk':
                ctx.down_t(_LOW)
                return Cost(None), _LOW
            inner = nest(gt, inner)
            for t in _py_targets(g.target):
                if t not in st:
                    st[t] = _new_var('scalar')
    for cond in first.ifs:
        cc, ccf = _py_expr_cost(cond, ctx)
        inner = seq(inner, cc)
        iconf = _worse(iconf, ccf)
    if isinstance(node, _ast.DictComp):
        kc, kcf = _py_expr_cost(node.key, ctx)
        vc, vcf = _py_expr_cost(node.value, ctx)
        inner = seq(inner, kc, vc)
        iconf = _worse(_worse(iconf, kcf), vcf)
    else:
        ec, ecf = _py_expr_cost(node.elt, ctx)
        inner = seq(inner, ec)
        iconf = _worse(iconf, ecf)
    if trips[0] == 'unk':
        ctx.down_t(_LOW)
        return Cost(None), _LOW
    ctx.loop_stack.append(frame)
    ctx.in_loop = True
    total_inner = inner
    ctx.loop_stack.pop()
    ctx.in_loop = bool(ctx.loop_stack)
    body = nest(trips, total_inner)
    total = seq(iterc, body)
    conf = _worse(_worse(itercf, tconf), iconf)
    if not dry and not isinstance(node, _ast.GeneratorExp):
        ctx.tmps.append(('aux', _trips_size(trips)))
    return (body if dry else total), conf


def _py_targets(target):
    if isinstance(target, _ast.Name):
        return [target.id]
    if isinstance(target, _ast.Starred):
        return _py_targets(target.value)
    if isinstance(target, (_ast.Tuple, _ast.List)):
        out = []
        for e in target.elts:
            out.extend(_py_targets(e))
        return out
    return []


def _py_iter_trips(iternode, ctx):
    """Trip count of a for-iterable; returns (trips, conf, base_or_None)."""
    st = ctx.st
    node = iternode
    if isinstance(node, _ast.Call):
        fn, recv = _py_func_name(node.func)
        if fn == 'range' and recv is None:
            args = node.args
            if len(args) == 1:
                bound = args[0]
            elif len(args) >= 2:
                bound = args[1]
            else:
                return ('unk',), _LOW, None
            s, c = _py_sizeinfo(bound, st)
            if s[0] == 'const':
                return ('const',), c, None
            if s[0] == 'size':
                return ('lin', s[1]), c, None
            if s[0] == 'min':
                return ('lin', s[1][0]), c, None
            return ('unk',), _LOW, None
        if fn in ('enumerate', 'zip', 'reversed', 'iter', 'list',
                  'tuple', 'set', 'frozenset', 'sorted', 'map',
                  'filter') and recv is None and node.args:
            return _py_iter_trips(node.args[0], ctx)
        if fn == 'items' and recv is not None and \
                isinstance(recv, _ast.Name):
            base = recv.id
            e = st.get(base)
            if isinstance(e, dict) and e.get('kind') == 'cont':
                return ('lin', e['sizevar']), _HIGH, base
            return ('lin', 'in:' + base), _MED, base
        return ('unk',), _LOW, None
    if isinstance(node, _ast.Name):
        e = st.get(node.id)
        if isinstance(e, dict) and e.get('kind') == 'cont':
            siv = _trip_var_of(e)
            if siv[0] == 'const':
                return ('const',), _HIGH, node.id
            if siv[0] == 'size':
                return ('lin', siv[1]), _HIGH, node.id
            return ('unk',), _LOW, node.id
        if e is None or e.get('kind') == 'unknown':
            return ('lin', 'in:' + node.id), _MED, node.id
        return ('unk',), _LOW, node.id
    if isinstance(node, _ast.Constant):
        return ('const',), _HIGH, None
    if isinstance(node, (_ast.List, _ast.Tuple, _ast.Set)):
        if any(isinstance(e, _ast.Starred) for e in node.elts):
            return ('unk',), _LOW, None
        return ('const',), _HIGH, None
    if isinstance(node, (_ast.ListComp, _ast.SetComp, _ast.GeneratorExp,
                         _ast.DictComp)):
        t, _c = _py_comp(node, ctx, dry=True)
        if t is not None and t.ok() and len(t.terms) == 1:
            vs = list(t.terms[0].vars())
            if len(vs) == 1:
                return ('lin', vs[0]), _MED, None
        return ('unk',), _LOW, None
    return ('unk',), _LOW, None


def _py_infer_kind(value, ctx):
    """Infer (kind, ctype) of an assigned value; (None, None) = scalar."""
    st = ctx.st
    if isinstance(value, _ast.Constant):
        if isinstance(value.value, str):
            return 'cont', 'str'
        return None, None
    if isinstance(value, _ast.Name):
        e = st.get(value.id)
        if isinstance(e, dict) and e.get('kind') == 'cont':
            return 'cont', e.get('ctype')
        return None, None
    if isinstance(value, _ast.Call):
        fn, recv = _py_func_name(value.func)
        if fn in ('list', 'sorted', 'tuple', 'deque'):
            return 'cont', 'list'
        if fn in ('set', 'frozenset'):
            return 'cont', 'set'
        if fn in ('dict', 'defaultdict', 'Counter'):
            return 'cont', 'dict'
        if fn in ('str',):
            return 'cont', 'str'
        return None, None
    if isinstance(value, _ast.ListComp):
        return 'cont', 'list'
    if isinstance(value, _ast.SetComp):
        return 'cont', 'set'
    if isinstance(value, (_ast.DictComp, _ast.Dict)):
        return 'cont', 'dict'
    if isinstance(value, (_ast.List, _ast.Tuple, _ast.Set)):
        if any(isinstance(e, _ast.Starred) for e in value.elts):
            return 'cont', 'list'
        return None, None
    if isinstance(value, _ast.Subscript):
        if isinstance(value.slice, _ast.Slice):
            base = value.value
            if isinstance(base, _ast.Name):
                e = st.get(base.id)
                if isinstance(e, dict) and e.get('kind') == 'cont':
                    return 'cont', e.get('ctype')
            return 'cont', 'list'
        return None, None
    if isinstance(value, _ast.BinOp) and isinstance(value.op, _ast.Add):
        k1, _c1 = _py_infer_kind(value.left, ctx)
        k2, _c2 = _py_infer_kind(value.right, ctx)
        if k1 == 'cont':
            return 'cont', _py_ctype_of(value.left, ctx)
        if k2 == 'cont':
            return 'cont', _py_ctype_of(value.right, ctx)
        return None, None
    if isinstance(value, _ast.IfExp):
        k1, c1 = _py_infer_kind(value.body, ctx)
        if k1 == 'cont':
            return k1, c1
        return _py_infer_kind(value.orelse, ctx)
    return None, None


def _py_ctype_of(node, ctx):
    if isinstance(node, _ast.Name):
        e = ctx.st.get(node.id)
        if isinstance(e, dict):
            return e.get('ctype')
    return None


def _py_assign_name(name, value, ctx):
    """Bind a name to an assigned value (replace semantics)."""
    st = ctx.st
    kind, ctype = _py_infer_kind(value, ctx)
    size = _py_contentsize(value, ctx)
    srcs = _py_sources(value, ctx)
    if kind == 'cont':
        e = _new_var('cont', ctype=ctype or 'list', nested=False,
                      size=size if size is not None and size.ok()
                      else Cost(None),
                      sizevar='in:' + name)
        e['sources'] = srcs
        e['ddepth'] = len(ctx.loop_stack)
        if size is None:
            ctx.down_s(_LOW)
        else:
            ctx.down_s(_py_size_conf(size, st))
        st[name] = e
        return
    # scalar (or unknown shape): track the value class for bounds;
    # stale container sizes/sources are dropped on scalar reassignment.
    e = st.get(name)
    if e is None:
        e = _new_var('scalar')
        st[name] = e
    else:
        e['kind'] = 'scalar'
        e['ctype'] = None
        e['sources'] = set()
    if isinstance(value, _ast.Constant):
        e['sval'] = ('const',)
    elif isinstance(value, _ast.Name):
        src = st.get(value.id)
        e['sval'] = src['sval'] if isinstance(src, dict) and \
            src.get('kind') == 'scalar' else ('unknown',)
        if isinstance(src, dict) and src.get('kind') == 'cont':
            e['sval'] = ('size', src['sizevar'])
    elif isinstance(value, _ast.Call):
        fn, _r = _py_func_name(value.func)
        if fn == 'len' and value.args:
            s, _c = _py_sizeinfo(value.args[0], st)
            e['sval'] = s if s[0] != 'unknown' else ('unknown',)
        elif fn in ('min', 'max'):
            s, _c = _py_sizeinfo(value, st)
            e['sval'] = s if s[0] != 'unknown' else ('unknown',)
        else:
            e['sval'] = ('unknown',)
    elif isinstance(value, _ast.BinOp) and isinstance(
            value.op, (_ast.Add, _ast.Sub)):
        s, _c = _py_sizeinfo(value, st)
        e['sval'] = s if s[0] != 'unknown' else ('unknown',)
    else:
        e['sval'] = ('unknown',)


def _py_store_subscript(target, value, ctx):
    """Handle `base[...] = value` (dict growth, slice assign, usage)."""
    st = ctx.st
    base = target.value
    while isinstance(base, _ast.Subscript) and not isinstance(
            base.slice, _ast.Slice):
        base = base.value
    if not isinstance(base, _ast.Name):
        return C_ONE, _HIGH
    e = st.get(base.id)
    if e is None or (isinstance(e, dict) and e.get('kind') == 'unknown'):
        # usage inference: subscript store on unknown -> dict
        ne = _new_var('cont', ctype='dict', nested=False, size=C_ONE,
                      sizevar='in:' + base.id)
        ne['sources'] = set()
        st[base.id] = ne
        e = ne
    if not isinstance(e, dict) or e.get('kind') != 'cont':
        return C_ONE, _HIGH
    if isinstance(target.slice, _ast.Slice):
        # nums[:] = x : O(x) memmove; inputs do not gain aux space
        s = _py_contentsize(value, ctx)
        if s is None or not s.ok():
            ctx.down_t(_LOW)
            return Cost(None), _LOW
        return s, _HIGH
    if e.get('ctype') in ('dict', 'Counter', 'defaultdict', 'set'):
        _grow_accum(base.id, C_ONE,
                    (_py_sources(value, ctx), _py_eltnames(value),
                     _py_base(value)), ctx)
        return C_ONE, _HIGH
    return C_ONE, _HIGH


def _py_assign(target, value, ctx):
    if isinstance(target, _ast.Name):
        _py_assign_name(target.id, value, ctx)
        return
    if isinstance(target, _ast.Starred):
        _py_assign(target.value, value, ctx)
        return
    if isinstance(target, (_ast.Tuple, _ast.List)):
        for e in target.elts:
            _py_assign(e, value, ctx)
        return
    if isinstance(target, _ast.Subscript):
        _py_store_subscript(target, value, ctx)
        return
    if isinstance(target, _ast.Attribute):
        # self.x stores: assume O(1) auxiliary (documented)
        ctx.down_t(_MED)
        ctx.down_s(_MED)
        return


def _py_stmts(stmts, ctx):
    total = C_ONE
    for s in stmts:
        total = seq(total, _py_stmt(s, ctx))
    return total


def _py_stmt(s, ctx):
    st = ctx.st
    if isinstance(s, _ast.Expr):
        c, _cc = _py_expr_cost(s.value, ctx)
        return c
    if isinstance(s, (_ast.Assign, _ast.AnnAssign)):
        c, _cc = _py_expr_cost(s.value, ctx)
        targets = s.targets if isinstance(s, _ast.Assign) else [s.target]
        # rebuilt-temporary self-concatenation (d = d + piece) rebuilds
        # the whole buffer per execution: quadratic in a loop.
        if isinstance(s, _ast.Assign) and len(targets) == 1 and \
                isinstance(targets[0], _ast.Name) and \
                isinstance(s.value, _ast.BinOp) and \
                isinstance(s.value.op, _ast.Add):
            d = targets[0].id
            e = st.get(d)
            if isinstance(e, dict) and e.get('kind') == 'cont' and \
                    d in _py_test_names(s.value):
                parts = [s.value.left, s.value.right]
                piece = C_ONE
                for p in parts:
                    if not (isinstance(p, _ast.Name) and p.id == d):
                        piece = seq(piece, _py_operand_size(p, ctx))
                if ctx.in_loop and ctx.loop_stack:
                    trips = ctx.loop_stack[-1]['trips']
                    if trips[0] == 'unk':
                        ctx.down_t(_LOW)
                        return Cost(None)
                    # per-execution cost is the current buffer sizes; the
                    # enclosing loop applies the trip count exactly once
                    e2 = st.get(d)
                    cur = e2['size'] if isinstance(e2, dict) and \
                        e2.get('kind') == 'cont' and e2['size'].ok() \
                        else C_ONE
                    if not cur.ok():
                        ctx.down_t(_LOW)
                        return Cost(None)
                    per = seq(cur, piece)
                    c = seq(c, per)
                    ctx.down_t(_MED)
                    _grow_accum(d, piece,
                                (_py_sources(s.value, ctx),
                                 _py_eltnames(s.value),
                                 _py_base(s.value)), ctx)
                    return c
                c = seq(c, _py_operand_size(s.value, ctx))
        for t in targets:
            _py_assign(t, s.value, ctx)
        return c
    if isinstance(s, _ast.AugAssign):
        c, _cc = _py_expr_cost(s.value, ctx)
        t = s.target
        if isinstance(t, _ast.Name):
            e = st.get(t.id)
            if isinstance(e, dict) and e.get('kind') == 'cont' and \
                    isinstance(s.op, _ast.Add):
                # amortized append; the generic tail must not recharge
                ctx.down_t(_MED)
                _grow_accum(t.id, _py_piece(s.value, ctx),
                            (_py_sources(s.value, ctx),
                             _py_eltnames(s.value),
                             _py_base(s.value)), ctx)
                return c
            _py_assign_name(t.id, s.value, ctx)
        elif isinstance(t, (_ast.Subscript, _ast.Attribute)):
            _py_assign(t, s.value, ctx)
        return c
    if isinstance(s, _ast.Return):
        if s.value is None:
            return C_ONE
        c, _cc = _py_expr_cost(s.value, ctx)
        _py_mark_output(s.value, ctx)
        return c
    if isinstance(s, _ast.If):
        c0, _c0 = _py_expr_cost(s.test, ctx)
        ct = _py_stmts(s.body, ctx)
        ce = _py_stmts(s.orelse, ctx) if s.orelse else C_ONE
        return seq(c0, _maxc(ct, ce))
    if isinstance(s, (_ast.For, _ast.AsyncFor)):
        return _py_for(s, ctx)
    if isinstance(s, _ast.While):
        return _py_while(s, ctx)
    if isinstance(s, _ast.FunctionDef):
        # nested function: analyze separately, memoize by name
        sub = _py_method(s, ctx)
        ctx.memo['pyfn:' + s.name] = sub
        return C_ONE
    if isinstance(s, (_ast.Try, _ast.TryStar)):
        tot = _py_stmts(s.body, ctx)
        if s.finalbody:
            tot = seq(tot, _py_stmts(s.finalbody, ctx))
        return tot
    if isinstance(s, _ast.With):
        tot, conf = C_ONE, _HIGH
        for it in s.items:
            c, cc = _py_expr_cost(it.context_expr, ctx)
            tot = seq(tot, c)
            conf = _worse(conf, cc)
        return seq(tot, _py_stmts(s.body, ctx))
    if isinstance(s, _ast.Assert):
        c, _cc = _py_expr_cost(s.test, ctx)
        return c
    if isinstance(s, _ast.Delete):
        tot = C_ONE
        for t in s.targets:
            if isinstance(t, _ast.Subscript) and not isinstance(
                    t.slice, _ast.Slice):
                base = _py_recv_entry(t.value, st)
                if isinstance(base, dict) and base.get('kind') == 'cont' \
                        and base.get('ctype') == 'list':
                    tot = seq(tot, base['size'])
        return tot
    if isinstance(s, (_ast.Break, _ast.Continue, _ast.Pass,
                      _ast.Raise, _ast.Global, _ast.Nonlocal,
                      _ast.Import, _ast.ImportFrom)):
        return C_ONE
    ctx.down_t(_MED)
    return C_ONE


def _py_scalar_piece(node, ctx):
    """True if an appended piece is O(1) per execution (not content)."""
    st = ctx.st
    if isinstance(node, _ast.Constant):
        return True
    if isinstance(node, _ast.Name):
        e = st.get(node.id)
        return not (isinstance(e, dict) and e.get('kind') == 'cont')
    if isinstance(node, _ast.BinOp):
        if isinstance(node.op, _ast.Add):
            return _py_scalar_piece(node.left, ctx) and \
                _py_scalar_piece(node.right, ctx)
        return True
    if isinstance(node, _ast.Subscript):
        # elements are scalar unless proven otherwise (documented)
        return True
    if isinstance(node, _ast.Call):
        fn, _r = _py_func_name(node.func)
        if fn in ('sorted', 'list', 'set', 'tuple', 'dict', 'join',
                  'split', 'copy'):
            return False
        return True
    if isinstance(node, _ast.Attribute):
        return True  # field access: fixed-size
    if isinstance(node, _ast.IfExp):
        return _py_scalar_piece(node.body, ctx) and \
            _py_scalar_piece(node.orelse, ctx)
    if isinstance(node, (_ast.ListComp, _ast.SetComp, _ast.GeneratorExp,
                         _ast.DictComp, _ast.JoinedStr)):
        return False
    if isinstance(node, (_ast.List, _ast.Tuple, _ast.Set)):
        return not any(isinstance(e, _ast.Starred) for e in node.elts)
    return True


def _py_piece(value, ctx):
    """Growth of one accumulating append (per execution)."""
    if _py_scalar_piece(value, ctx):
        return C_ONE  # trips account for it via loop scaling
    srcs = _py_sources(value, ctx)
    ins = sorted(s for s in srcs if s in _input_vars(ctx.st))
    if ins:
        return seq(*[c_lin(x) for x in ins])
    return C_ONE


def _py_mark_output(value, ctx):
    st = ctx.st
    # only a bare returned variable is output (x[i] merely reads x)
    if isinstance(value, _ast.Name):
        e = st.get(value.id)
        if isinstance(e, dict) and e.get('kind') == 'cont':
            e['returned'] = True
    # returned temporaries (return s.lower()) count as output space
    s = _py_contentsize(value, ctx)
    if s is not None and s.ok() and len(s.terms) == 1 and \
            len(s.terms[0].pows) > 0:
        ctx.tmps.append(('out', s))


def _py_for(s, ctx):
    st = ctx.st
    iterc, itercf = _py_expr_cost(s.iter, ctx)
    trips, tconf, cbase = _py_iter_trips(s.iter, ctx)
    frame = {'trips': trips, 'container': cbase, 'boundvars': set(),
             'cvars': set(), 'element': None,
             'depth': len(ctx.loop_stack)}
    if cbase is not None:
        e = st.get(cbase)
        if isinstance(e, dict) and e.get('kind') == 'cont':
            frame['cvars'] = set(e.get('sources', set())) | {e['sizevar']}
        else:
            frame['cvars'] = {'in:' + cbase}
    tgts = _py_targets(s.target)
    if len(tgts) == 1:
        frame['element'] = tgts[0]
    frame['index'] = _loop_index_names(s.body, tgts, is_py=True)
    for t in tgts:
        if t not in st:
            e = _new_var('scalar')
            e['elem_of'] = cbase
            st[t] = e
    # amortization pre-scan (mirror of the C++ rule, linear ops only)
    resets = _py_resets(s.body)
    linbuf = _py_linbuf(s.body)
    amort = {b for b, bid in linbuf if b in resets.get(bid, set())}
    saved = ctx.amortized
    ctx.amortized = amort
    if trips[0] == 'unk':
        ctx.down_t(_LOW)
        ctx.loop_stack.append(dict(frame, trips=('unk',)))
        ctx.in_loop = True
        try:
            _py_stmts(s.body, ctx)
            if s.orelse:
                _py_stmts(s.orelse, ctx)
        finally:
            ctx.loop_stack.pop()
            ctx.in_loop = bool(ctx.loop_stack)
            ctx.amortized = saved
        return Cost(None)
    ctx.loop_stack.append(frame)
    ctx.in_loop = True
    try:
        bcost = _py_stmts(s.body, ctx)
        if s.orelse:
            bcost = seq(bcost, _py_stmts(s.orelse, ctx))
    finally:
        ctx.loop_stack.pop()
        ctx.in_loop = bool(ctx.loop_stack)
        ctx.amortized = saved
    ctx.down_t(tconf)
    return seq(iterc, nest(trips, bcost))


def _py_resets(stmts):
    out = {}

    def walk(ss, bid):
        for s in ss:
            if isinstance(s, _ast.Assign):
                for t in s.targets:
                    for n in _py_targets(t) if not isinstance(
                            t, (_ast.Subscript, _ast.Attribute)) else []:
                        out.setdefault(bid, set()).add(n)
            elif isinstance(s, (_ast.AnnAssign,)) and s.value is not None \
                    and isinstance(s.target, _ast.Name):
                out.setdefault(bid, set()).add(s.target.id)
            elif isinstance(s, _ast.If):
                walk(s.body, bid + 'T')
                walk(s.orelse, bid + 'E')
            elif isinstance(s, (_ast.For, _ast.While)):
                pass  # resets inside nested loops: another context
    walk(stmts, 'B')
    return out


def _py_linbuf(stmts):
    out = []

    def walk(ss, bid):
        for s in ss:
            if isinstance(s, _ast.If):
                walk(s.body, bid + 'T')
                walk(s.orelse, bid + 'E')
            elif isinstance(s, (_ast.For, _ast.While)):
                pass  # ops inside nested loops belong to another context
            else:
                for ch in _ast.walk(s):
                    if isinstance(ch, _ast.Call):
                        fn, recv = _py_func_name(ch.func)
                        if fn in ('reverse', 'sort', 'find', 'count',
                                  'index'):
                            if isinstance(recv, _ast.Name):
                                out.append((recv.id, bid))
    walk(stmts, 'B')
    return out


def _py_while(s, ctx):
    st = ctx.st
    trips, tconf = _py_classify_while(s.test, s.body, ctx)
    frame = {'trips': trips, 'container': None, 'boundvars': set(),
             'element': None, 'depth': len(ctx.loop_stack),
             'index': _loop_index_names(
                 s.body, _py_test_names(s.test), is_py=True)}
    if trips[0] == 'unk':
        ctx.down_t(_LOW)
        ctx.loop_stack.append(dict(frame, trips=('unk',)))
        ctx.in_loop = True
        try:
            _py_stmts(s.body, ctx)
        finally:
            ctx.loop_stack.pop()
            ctx.in_loop = bool(ctx.loop_stack)
        return Cost(None)
    ctx.loop_stack.append(frame)
    ctx.in_loop = True
    try:
        bcost = _py_stmts(s.body, ctx)
        if s.orelse:
            bcost = seq(bcost, _py_stmts(s.orelse, ctx))
    finally:
        ctx.loop_stack.pop()
        ctx.in_loop = bool(ctx.loop_stack)
    if trips[0] == 'sum':
        tot = C_ONE
        for v in trips[1]:
            tot = seq(tot, nest(('lin', v), bcost))
        ctx.down_t(tconf)
        return tot
    ctx.down_t(tconf)
    return nest(trips, bcost)


def _py_test_names(test):
    return {ch.id for ch in _ast.walk(test)
            if isinstance(ch, _ast.Name)}


def _py_assigns(stmts):
    """(target_name, kind, value_node) for plain stores (not nested loops)."""
    out = []

    def walk(ss):
        for s in ss:
            if isinstance(s, _ast.Assign):
                for t in s.targets:
                    for n in _py_targets(t):
                        out.append((n, 'plain', s.value))
            elif isinstance(s, _ast.AnnAssign) and s.value is not None \
                    and isinstance(s.target, _ast.Name):
                out.append((s.target.id, 'plain', s.value))
            elif isinstance(s, _ast.AugAssign) and isinstance(
                    s.target, _ast.Name):
                out.append((s.target.id, type(s.op).__name__, s.value))
            elif isinstance(s, _ast.If):
                walk(s.body)
                walk(s.orelse)
            elif isinstance(s, (_ast.For, _ast.While)):
                pass  # assigns inside nested loops: another context
    walk(stmts)
    return out


def _py_classify_while(test, body, ctx):
    st = ctx.st
    assigns = _py_assigns(body)
    # 1. halving search
    if isinstance(test, _ast.Compare) and len(test.ops) == 1 and \
            isinstance(test.ops[0],
                       (_ast.Lt, _ast.LtE, _ast.Gt, _ast.GtE)):
        sides = [test.left, test.comparators[0]]
        if all(isinstance(x, _ast.Name) for x in sides):
            L, H = sides[0].id, sides[1].id
            if (st.get(L) is not None and st[L].get('kind') == 'scalar'
                    and st.get(H) is not None
                    and st[H].get('kind') == 'scalar'):
                mid = None
                for (b, _k, v) in assigns:
                    if b in (L, H) or not isinstance(v, _ast.BinOp):
                        continue
                    names = _py_test_names(v)
                    if L in names and H in names and \
                            _py_div2(v):
                        mid = b
                        break
                if mid is not None:
                    narrow = False
                    ok = True
                    for (b, _k, v) in assigns:
                        if b not in (L, H):
                            continue
                        if mid in _py_test_names(v):
                            narrow = True
                        else:
                            ok = False
                    if narrow and ok:
                        for cand in (st[H]['sval'], st[L]['sval']):
                            if cand[0] == 'size':
                                return ('log', cand[1]), _MED
                        if st[H]['sval'][0] == 'const' and \
                                st[L]['sval'][0] == 'const':
                            return ('const',), _HIGH
                        return ('log', 'in:search'), _MED
    # 2. digit shrink
    names = _py_test_names(test)
    if len(names) == 1:
        X = next(iter(names))
        ups = [(b, k, v) for (b, k, v) in assigns if b == X]
        if ups and all(_py_is_shrink(k, v, X) for (b, k, v) in ups):
            sv, _c = _py_sval_of(X, st)
            v = sv[1] if sv[0] == 'size' else 'val:' + X
            return ('log', v), _MED
    # 3. index advance
    adv = _py_advance(test, body, st)
    if adv is not None:
        varlist, mconf = adv
        if len(varlist) == 1:
            return ('lin', varlist[0]), mconf
        if len(varlist) > 1:
            return ('sum', varlist), mconf
        return ('const',), mconf
    # 4. cycle chase
    if isinstance(test, _ast.Compare) and len(test.ops) == 1 and \
            isinstance(test.ops[0], (_ast.NotEq, _ast.Eq)):
        sides = [test.left, test.comparators[0]]
        if all(isinstance(x, _ast.Name) for x in sides):
            P, Q = sides[0].id, sides[1].id
            for V in (P, Q):
                for (b, _k, v) in assigns:
                    if b == V and isinstance(v, _ast.Subscript):
                        base = v.value
                        while isinstance(base, _ast.Subscript) and \
                                not isinstance(base.slice, _ast.Slice):
                            base = base.value
                        if isinstance(base, _ast.Name):
                            e = st.get(base.id)
                            if isinstance(e, dict) and \
                                    e.get('kind') == 'cont':
                                return ('lin', e['sizevar']), _MED
    return ('unk',), _LOW


def _py_div2(node):
    for ch in _ast.walk(node):
        if isinstance(ch, _ast.BinOp) and isinstance(
                ch.op, (_ast.Div, _ast.FloorDiv)):
            if isinstance(ch.right, _ast.Constant) and ch.right.value == 2:
                return True
    return False


def _py_is_shrink(kind, value, X):
    if value is None:
        return False
    if kind in ('Div', 'FloorDiv', 'Mod'):
        return True
    if kind == 'plain' and isinstance(value, _ast.BinOp) and \
            isinstance(value.op, (_ast.Div, _ast.FloorDiv, _ast.Mod)):
        if isinstance(value.left, _ast.Name) and value.left.id == X:
            return True
    return False


def _py_advance(test, body, st):
    if isinstance(test, _ast.BoolOp) and isinstance(test.op, _ast.And):
        parts = test.values
    else:
        parts = [test]
    pairs = []
    for p in parts:
        if not (isinstance(p, _ast.Compare) and len(p.ops) == 1):
            return None
        op = p.ops[0]
        l_, r = p.left, p.comparators[0]
        if isinstance(op, (_ast.Lt, _ast.LtE)) and \
                isinstance(l_, _ast.Name):
            pairs.append((l_.id, r))
        elif isinstance(op, (_ast.Gt, _ast.GtE)) and \
                isinstance(r, _ast.Name):
            pairs.append((r.id, l_))
        else:
            return None
    if not pairs:
        return None
    varlist = []
    for var, bound in pairs:
        e = st.get(var)
        if not isinstance(e, dict) or e.get('kind') != 'scalar':
            return None
        s, c = _py_bound_size(bound, st)
        if s[0] == 'size':
            varlist.append(s[1])
        elif s[0] == 'min':
            varlist.append(s[1][0])
        elif s[0] == 'const':
            continue
        else:
            return None
        if not _py_advances(body, var):
            return None
    return list(dict.fromkeys(varlist)), _MED


def _py_bound_size(bound, st):
    if isinstance(bound, _ast.Call):
        fn, _r = _py_func_name(bound.func)
        if fn == 'len' and bound.args:
            return _py_sizeinfo(bound.args[0], st)
    return _py_sizeinfo(bound, st)


def _py_is_step(value, var):
    """`var +/- const`: a linear index step."""
    return isinstance(value, _ast.BinOp) and \
        isinstance(value.op, (_ast.Add, _ast.Sub)) and \
        isinstance(value.left, _ast.Name) and value.left.id == var and \
        isinstance(value.right, _ast.Constant)


def _py_advances_some(stmts, idxs):
    if isinstance(stmts, tuple):
        stmts = stmts[1] if stmts[0] == 'block' else [stmts]
    for s in stmts:
        if _py_advances_some_1(s, idxs):
            return True
    return False


def _py_advances_some_1(s, idxs):
    if isinstance(s, (_ast.For, _ast.While)):
        return False
    if isinstance(s, _ast.If):
        if not s.orelse:
            return False
        return _py_advances_some(s.body, idxs) and \
            _py_advances_some(s.orelse, idxs)
    if isinstance(s, _ast.AugAssign) and isinstance(
            s.target, _ast.Name) and s.target.id in idxs:
        # += / -= advance linearly; *= and friends change scale
        # (logarithmic families handled by their own patterns)
        return isinstance(s.op, (_ast.Add, _ast.Sub))
    if isinstance(s, (_ast.Assign, _ast.AnnAssign)):
        targets = s.targets if isinstance(s, _ast.Assign) else [s.target]
        for t in targets:
            for n in _py_targets(t):
                if n in idxs:
                    # i = i +/- const is a linear step; anything else
                    # written to an index breaks the progress proof
                    if len(targets) == 1 and _py_is_step(s.value, n):
                        return True
                    return False
        return False
    if isinstance(s, (_ast.Return, _ast.Break)):
        return True
    return False


def _py_advances(stmts, var):
    return _py_advances_some(stmts, {var})


def _py_method(fnnode, ctx_all):
    name = fnnode.name
    st = _py_init_params(fnnode.args.args)
    ctx = _Ctx(st, ctx_all)
    ctx.func_name = name
    ctx.active = frozenset((name,))
    ctx.memo = {}
    time = _py_stmts(fnnode.body, ctx)
    # self-recursion depth
    sites = [ch for ch in _ast.walk(fnnode)
             if isinstance(ch, _ast.Call)
             and isinstance(ch.func, _ast.Name)
             and ch.func.id == name]
    if sites:
        if len(sites) >= 2:
            v = _py_first_arg_var(sites[0], st) or 'in:n'
            dcost = _cost(T((), 0, True, frozenset((v,))))
            time = seq(time, dcost)
            ctx.down_t(_MED)
            ctx.tmps.append(('aux', dcost))
        else:
            a0 = sites[0].args[0] if sites[0].args else None
            v = _py_first_arg_var(sites[0], st)
            if isinstance(a0, _ast.BinOp) and isinstance(
                    a0.op, (_ast.Sub, _ast.Add)):
                dcost = c_lin(v) if v else Cost(None)
                dconf = _MED if v else _LOW
            elif isinstance(a0, _ast.BinOp) and isinstance(
                    a0.op, (_ast.Div, _ast.FloorDiv)):
                dcost = c_log(v) if v else Cost(None)
                dconf = _MED if v else _LOW
            else:
                dcost = c_lin(v) if v else Cost(None)
                dconf = _LOW
            time = seq(time, dcost)
            ctx.down_t(dconf)
            ctx.tmps.append(('aux', dcost))
    aux_terms, out_terms = [], []
    for _n, e in st.items():
        if not isinstance(e, dict) or e.get('kind') != 'cont':
            continue
        if e.get('input'):
            continue  # the input itself is never auxiliary/output space
        if not e['size'].ok():
            (out_terms if e['returned'] else aux_terms).append(None)
            continue
        if e['returned']:
            out_terms.append(e['size'])
        else:
            aux_terms.append(e['size'])
    for kind, sz in ctx.tmps:
        (out_terms if kind == 'out' else aux_terms).append(sz)
    return {'time': time, 'tconf': ctx.tconf, 'sconf': ctx.sconf,
            'aux': aux_terms, 'out': out_terms, 'st': st}


def _py_first_arg_var(call, st):
    if not call.args:
        return None
    s, _c = _py_sizeinfo(call.args[0], st)
    if s[0] == 'size':
        return s[1]
    if s[0] == 'min':
        return s[1][0]
    return None


def analyze_py(text):
    """Analyze Python source; return (time, tconf, space, sconf)."""
    try:
        tree = _ast.parse(text)
    except Exception:
        return "Unknown", "Low", "Unknown", "Low"
    methods = {}
    for node in tree.body:
        if isinstance(node, _ast.ClassDef) and node.name == 'Solution':
            for item in node.body:
                if isinstance(item, (_ast.FunctionDef,
                                     _ast.AsyncFunctionDef)):
                    methods[item.name] = item
    if not methods:
        # fall back to any module-level function
        for node in tree.body:
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                methods[node.name] = node
    if not methods:
        return "Unknown", "Low", "Unknown", "Low"
    # entries: methods not called by other methods
    called = set()
    for m, fn in methods.items():
        for ch in _ast.walk(fn):
            if isinstance(ch, _ast.Call):
                fn2, _r = _py_func_name(ch.func)
                if fn2 in methods and fn2 != m:
                    called.add(fn2)
    entries = [m for m in methods if m not in called] or list(methods)
    time, tconf, sconf = C_ONE, _HIGH, _HIGH
    aux_all, out_all = [], []
    try:
        for m in entries:
            res = _py_method(methods[m], dict(methods))
            time = seq(time, res['time'])
            tconf = _worse(tconf, res['tconf'])
            sconf = _worse(sconf, res['sconf'])
            aux_all.extend(res['aux'])
            out_all.extend(res['out'])
    except Exception:
        return "Unknown", "Low", "Unknown", "Low"
    if any(t is None or not t.ok() for t in aux_all + out_all):
        space_cost, sconf = Cost(None), _LOW
    else:
        terms = []
        for t in aux_all + out_all:
            terms.extend(t.terms)
        space_cost = _cost(*terms) if terms else C_ONE
    tlabel = show(time)
    slabel = show(space_cost)
    if tlabel is None:
        tlabel, tconf = "Unknown", "Low"
    if slabel is None:
        slabel, sconf = "Unknown", "Low"
    return tlabel, tconf, slabel, sconf


def analyze_file(path, lang):
    """Return (time, time_conf, space, space_conf). Never raises."""
    from pathlib import Path as _Path
    try:
        text = _Path(path).read_text(encoding='utf-8', errors='ignore')
    except OSError:
        return "Unknown", "Low", "Unknown", "Low"
    if not text.strip():
        return "Unknown", "Low", "Unknown", "Low"
    try:
        if lang == 'Python':
            return analyze_py(text)
        return analyze_cpp(text)
    except Exception:
        return "Unknown", "Low", "Unknown", "Low"




