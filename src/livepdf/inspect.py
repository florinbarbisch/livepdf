"""Read the form fields and JavaScript of a PDF (any PDF, not only ones written by :mod:`livepdf.build`)."""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, StreamObject

TRIGGERS = ('E', 'X', 'D', 'U', 'Fo', 'Bl', 'K', 'F', 'V', 'C', 'PO', 'PC', 'PV', 'PI')


@dataclass
class Field:
    name: str
    type: str                     # text, button, checkbox, radiobutton, combobox, listbox, signature
    rect: list[float]             # PDF coordinates [x0, y0, x1, y1], bottom-left origin
    page: int
    order: int                    # annotation order: later = drawn on top; Chrome hits the first
    value: str = ''
    flags: int = 0                # /Ff field flags
    annot_flags: int = 0          # /F annotation flags (2 = hidden, 32 = noView)
    max_len: int | None = None
    export_value: str = 'Yes'
    has_ap: bool = False
    mk_bg: list[float] | None = None
    mk_ca: str | None = None
    mk_bc: list[float] | None = None
    da: str = ''
    align: int = 0                # /Q: 0 left, 1 centre, 2 right
    actions: dict[str, str] = field(default_factory=dict)   # 'A' plus /AA triggers -> JavaScript

    @property
    def hidden(self) -> bool:
        return bool(self.annot_flags & 2) or bool(self.annot_flags & 32)

    @property
    def readonly(self) -> bool:
        return bool(self.flags & 1)

    def to_json(self) -> dict:
        d = asdict(self)
        d['hidden'] = self.hidden
        return d


@dataclass
class GameDoc:
    path: Path
    width: float
    height: float
    fields: list[Field]
    scripts: list[tuple[str, str]]          # (name, source) document-level scripts, in name-tree order
    need_appearances: bool | None = None
    dr_fonts: list[str] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)   # what pypdf had to skip or repair

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)

    def names(self) -> set[str]:
        return {f.name for f in self.fields}

    def to_json(self) -> dict:
        return {'width': self.width, 'height': self.height, 'fields': [f.to_json() for f in self.fields],
                'scripts': [{'name': n, 'source': s} for n, s in self.scripts]}


def _r(o):
    return o.get_object() if isinstance(o, IndirectObject) else o


def _js(action) -> str | None:
    action = _r(action)
    if not isinstance(action, DictionaryObject) or action.get('/S') != '/JavaScript':
        return None
    js = _r(action.get('/JS'))
    if isinstance(js, StreamObject):
        return js.get_data().decode('latin-1')
    return None if js is None else str(js)


def _inherited(widget: DictionaryObject, key: str):
    node = widget
    while node is not None:
        if key in node:
            return _r(node[key])
        node = _r(node.get('/Parent'))
    return None


def _full_name(widget: DictionaryObject) -> str:
    parts, node = [], widget
    while node is not None:
        if '/T' in node:
            parts.append(str(node['/T']))
        node = _r(node.get('/Parent'))
    return '.'.join(reversed(parts))


def _field_type(ft, ff: int) -> str:
    if ft == '/Tx':
        return 'text'
    if ft == '/Btn':
        return 'button' if ff & 65536 else 'radiobutton' if ff & 32768 else 'checkbox'
    if ft == '/Ch':
        return 'combobox' if ff & 131072 else 'listbox'
    return 'signature' if ft == '/Sig' else 'unknown'


def _name_tree(node) -> list:
    node = _r(node)
    out = []
    if node is None:
        return out
    names = _r(node.get('/Names'))
    if isinstance(names, ArrayObject):
        out += [(str(names[i]), names[i + 1]) for i in range(0, len(names) - 1, 2)]
    for kid in _r(node.get('/Kids')) or []:
        out += _name_tree(kid)
    return out


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def load(path: str | Path) -> GameDoc:
    """Read a PDF's fields and scripts. Problems pypdf had to skip or repair end up in ``parse_errors``."""
    log = logging.getLogger('pypdf')
    handler = _Collect()
    log.addHandler(handler)
    old_propagate, log.propagate = log.propagate, False
    try:
        doc = _load(Path(path))
    finally:
        log.removeHandler(handler)
        log.propagate = old_propagate
    doc.parse_errors = handler.messages
    return doc


def _load(path: Path) -> GameDoc:
    reader = PdfReader(str(path))
    root = reader.trailer['/Root']
    fields: list[Field] = []
    for pno, page in enumerate(reader.pages):
        for order, annot in enumerate(_r(page.get('/Annots')) or []):
            w = _r(annot)
            if w.get('/Subtype') != '/Widget':
                continue
            ff = int(_inherited(w, '/Ff') or 0)
            ftype = _field_type(_inherited(w, '/FT'), ff)
            v = _inherited(w, '/V')
            value = '' if v is None else str(v).lstrip('/') if ftype in ('checkbox', 'radiobutton') else str(v)
            if ftype in ('checkbox', 'radiobutton') and v is None:
                value = 'Off'
            ap = _r(w.get('/AP'))
            export = 'Yes'
            if ap is not None and isinstance(_r(ap.get('/N')), DictionaryObject) and ftype != 'button':
                keys = [k.lstrip('/') for k in _r(ap['/N']).keys() if k != '/Off']
                export = keys[0] if keys else 'Yes'
            mk = _r(w.get('/MK')) or {}
            acts = {}
            if '/A' in w and (js := _js(w['/A'])) is not None:
                acts['A'] = js
            for k, a in (_r(w.get('/AA')) or {}).items():
                if (js := _js(a)) is not None:
                    acts[k.lstrip('/')] = js
            ml = _inherited(w, '/MaxLen')
            fields.append(Field(
                name=_full_name(w), type=ftype, rect=[float(x) for x in w['/Rect']], page=pno, order=order,
                value=value, flags=ff, annot_flags=int(w.get('/F', 0)), max_len=int(ml) if ml is not None else None,
                export_value=export, has_ap=ap is not None,
                mk_bg=[float(x) for x in mk['/BG']] if '/BG' in mk else None,
                mk_ca=str(mk['/CA']) if '/CA' in mk else None,
                mk_bc=[float(x) for x in mk['/BC']] if '/BC' in mk else None, da=str(_inherited(w, '/DA') or ''),
                align=int(_inherited(w, '/Q') or 0), actions=acts))
    scripts = []
    names = _r(root.get('/Names'))
    if names is not None and '/JavaScript' in names:
        for nm, a in _name_tree(names['/JavaScript']):
            if (js := _js(a)) is not None:
                scripts.append((nm, js))
    if '/OpenAction' in root and (js := _js(root['/OpenAction'])) is not None:
        scripts.append(('OpenAction', js))
    acro = _r(root.get('/AcroForm')) or {}
    na = acro.get('/NeedAppearances')
    dr = _r(acro.get('/DR')) or {}
    fonts = [k.lstrip('/') for k in (_r(dr.get('/Font')) or {}).keys()]
    box = reader.pages[0].mediabox
    return GameDoc(path, float(box.width), float(box.height), fields, scripts,
                   None if na is None else str(na).lower() == 'true', fonts)
