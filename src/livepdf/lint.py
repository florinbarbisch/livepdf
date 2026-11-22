"""Static checks for interactive PDFs: problems that are cheap to find before opening a browser."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .build import TOP_SUFFIX
from .inspect import GameDoc

_GETFIELD = re.compile(r'getField\(\s*(["\'])(.*?)\1\s*(\+)?')
_HELPER_DEF = re.compile(r'function\s+([A-Za-z_$][\w$]*)\s*\(\s*([A-Za-z_$][\w$]*)[^)]*\)\s*\{[^}]*?getField\(\s*\2\s*\)')
_FUNC_DEF = re.compile(r'\bfunction\s+([A-Za-z_$][\w$]*)\s*\(')
_VAR_FUNC = re.compile(r'\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*function\b')
_CALL = re.compile(r'(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(')
_PY_FORMAT = re.compile(r'%%|%(?:\d+)?(?:\.\d+)?[dfs](?![\w])')
_JS_KEYWORDS = {'if', 'for', 'while', 'switch', 'return', 'function', 'catch', 'typeof', 'new', 'with', 'String',
                'Number', 'Math', 'Date', 'Array', 'Object', 'isNaN', 'isFinite', 'parseInt', 'parseFloat', 'Boolean',
                'JSON', 'RegExp', 'Error', 'TypeError', 'encodeURIComponent', 'decodeURIComponent', 'getField',
                'eval', 'escape', 'unescape'}
CHROME_UNSUPPORTED = {
    'global.setPersistent': 'do not expect values to survive a reload in Chrome (untested); keep scores in a '
                            'form field instead (the user saves the PDF with Ctrl+S).',
    'addField': 'PDFium does not support adding fields at run time; create every field up front and hide it.',
    'removeField': 'PDFium does not support removing fields; hide them instead.',
    'getAnnots': 'not implemented by PDFium.',
    'app.popUpMenu': 'not implemented by PDFium.',
}


@dataclass
class Finding:
    code: str
    level: str          # error, warning, info
    where: str
    message: str

    def __str__(self) -> str:
        return f'{self.level.upper():7} {self.code} {self.where}: {self.message}'


def _all_js(doc: GameDoc):
    for name, src in doc.scripts:
        yield f'doc/{name}', src
    for f in doc.fields:
        for trig, src in f.actions.items():
            yield f'{f.name}/{trig}', src


def lint(doc: GameDoc, syntax: bool = True) -> list[Finding]:
    out: list[Finding] = []
    names = doc.names()
    add = lambda *a: out.append(Finding(*a))

    for msg in dict.fromkeys(doc.parse_errors):
        add('LP000', 'error', 'file', f'PDF syntax problem (a viewer may drop the object): {msg[:160]}')
    if not doc.scripts and not any(f.actions for f in doc.fields):
        add('LP001', 'info', 'document', 'no JavaScript at all')
    if doc.need_appearances:
        add('LP002', 'warning', 'AcroForm', '/NeedAppearances true: Chrome then draws its own look for fields and '
                                            'ignores custom appearance streams (round knobs come out square)')
    if syntax:
        from .sim import syntax_errors
        for e in syntax_errors(doc):
            add('LP003', 'error', e['where'], f'JavaScript syntax error: {e["message"]}')

    # field names used in scripts, directly or through helpers like  function fld(n) { return this.getField(n); }
    helpers = {m.group(1) for _, src in doc.scripts for m in _HELPER_DEF.finditer(src)}
    name_use = [_GETFIELD]
    if helpers:
        name_use.append(re.compile(r'(?<![\w$.])(?:' + '|'.join(map(re.escape, sorted(helpers))) +
                                   r')\(\s*(["\'])(.*?)\1\s*(\+)?'))
    for where, src in _all_js(doc):
        for rx in name_use:
            for m in rx.finditer(src):
                nm, concat = m.group(2), m.group(3)
                if concat:
                    if not any(n.startswith(nm) for n in names):
                        add('LP004', 'error', where, f'no field name starts with "{nm}" (used as "{nm}" + ...)')
                elif nm not in names:
                    add('LP004', 'error', where, f'field "{nm}" does not exist')
        for api, why in CHROME_UNSUPPORTED.items():
            if api in src:
                add('LP005', 'warning', where, f'{api}: {why}')
        if 'printf' not in src and (left := sorted(set(_PY_FORMAT.findall(src)))):
            add('LP006', 'warning', where, f'looks like unformatted Python template text {left[:4]}: a literal % in a '
                                           '%-formatted JS template must be written %%')

    # functions called from field actions must be defined in the document scripts
    defined = set()
    for _, src in doc.scripts:
        defined |= set(_FUNC_DEF.findall(src)) | set(_VAR_FUNC.findall(src))
    for f in doc.fields:
        for trig, src in f.actions.items():
            for fn in set(_CALL.findall(src)) - _JS_KEYWORDS:
                if fn not in defined and fn not in ('app', 'this', 'event', 'util', 'console'):
                    if not re.search(r'\b(?:var|let|const|function)\s+' + re.escape(fn) + r'\b', src):
                        add('LP007', 'error', f'{f.name}/{trig}', f'calls {fn}() but no document script defines it')

    for f in doc.fields:
        if f.type == 'button' and not f.has_ap and f.mk_bg is None and f.mk_ca is None:
            add('LP008', 'warning', f.name, 'push button without /AP or /MK: it is invisible')
        if f.type == 'text' and f.da:
            m = re.search(r'/(\w+)\s+[\d.]+\s+Tf', f.da)
            if m and doc.dr_fonts and m.group(1) not in doc.dr_fonts:
                add('LP009', 'error', f.name, f'/DA font /{m.group(1)} is not in /AcroForm /DR {doc.dr_fonts}')
        if f.mk_ca == 'l' and 'ZaDb' not in doc.dr_fonts and doc.dr_fonts:
            add('LP009', 'error', f.name, 'circle check box needs /ZaDb in /AcroForm /DR')
        if 'U' in f.actions and 'A' not in f.actions and 'D' not in f.actions:
            add('LP010', 'warning', f.name, 'only a mouse-up action: Chrome reports mouse-up late or to the wrong '
                                            'field; use /A or /AA /D (mouse down) instead')
        if 'E' in f.actions and 'A' in f.actions:
            add('LP014', 'warning', f.name, 'enter plus activate actions on one field: after a click Chrome kept '
                                            'sending enter and mouse-up events to the clicked field, wherever the '
                                            'pointer went. Use /AA /D, /E and /U (drag and drop) without /A')
        if f.type in ('text', 'button') and any(t in f.actions for t in ('E', 'X')) and not f.actions.keys() - {'E', 'X'}:
            add('LP011', 'info', f.name, 'hover-only interaction: Chrome sends no enter/exit to fields under a visible '
                                         'overlapping field that comes first')

    # Chrome gives a click on overlapping fields to the FIRST one in annotation order, Edge to the LAST one (drawn on
    # top). A zone's top copy (LivePdf.zone, name + '~top') exists for that; overlaps with it repeat the original's.
    clickable = [f for f in doc.fields if f.actions and not f.name.endswith(TOP_SUFFIX)]
    for i, a in enumerate(clickable):
        for b in clickable[i + 1:]:
            if _overlap(a.rect, b.rect) <= 0.5 * min(_area(a.rect), _area(b.rect)):
                continue
            if not a.hidden and not b.hidden:
                add('LP012', 'warning', b.name, f'overlaps "{a.name}": Chrome gives clicks on the shared area to the '
                                                f'first in the field order ("{a.name}"), Edge to the one drawn on top '
                                                f'("{b.name}")')
            if a.hidden != b.hidden and _click_js(a) != _click_js(b):
                # a swap pair: one is shown instead of the other on the same spot
                first = a if not a.hidden else b
                add('LP013', 'warning', f'{a.name}+{b.name}',
                    f'share a spot but run different actions. After "{first.name}" is hidden by a script, Chrome keeps '
                    f'giving it the clicks on that spot while it has the focus (until a click elsewhere). Give both one '
                    'handler that decides by the game state')
    # Edge gives a click to the field drawn on top, even one without actions (a label, a bar, a knob)
    tops = {f.name[:-len(TOP_SUFFIX)] for f in doc.fields if f.name.endswith(TOP_SUFFIX)}
    for a in clickable:
        if a.name in tops:
            continue
        for b in doc.fields[a.order + 1:]:
            if not b.actions and not b.hidden and _overlap(a.rect, b.rect) > 0.25 * min(_area(a.rect), _area(b.rect)):
                add('LP015', 'warning', a.name, f'covered by "{b.name}", which comes later in the field order: Edge gives '
                                                f'clicks there to "{b.name}". Use LivePdf.zone() (it adds a top copy) or '
                                                'move the clickable field after it')
                break
    return out


def _click_js(f) -> tuple:
    return tuple(f.actions.get(k, '') for k in ('A', 'D', 'U'))


def _area(r) -> float:
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def _overlap(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
