"""Write single-page interactive PDFs by hand: page drawing, form fields and document JavaScript.

Coordinates in this module are *top-based* (y grows downwards from the top edge of the page), which is how
layouts are usually designed. Rects stored in the PDF and everything the JavaScript sees are bottom-based PDF
coordinates; use :meth:`LivePdf.y` to convert.

The field helpers encode what works in Chrome's PDF viewer (PDFium):

* ``color_bar`` and ``dot`` survive ``field.rect`` moves. Chrome drops a field's custom ``/AP`` after a move
  and repaints it from ``/MK``; a push button with ``/MK /BG`` repaints as a filled rectangle and a check box with
  the ZapfDingbats circle ``/MK /CA (l)`` repaints as a dot.
* Every other field should stay where it is and only be shown or hidden.
* ``/NeedAppearances false``, so Chrome uses the appearance streams written here.
"""
from __future__ import annotations

import zlib
from pathlib import Path

INK = (0.10, 0.10, 0.10)
GREY = (0.55, 0.55, 0.55)
WHITE = (1, 1, 1)
YELLOW = (1, 0.90, 0)

# Annotation flags (/F): 4 = print, 2 = hidden. Field flags (/Ff) for buttons.
F_VISIBLE, F_HIDDEN = 4, 6
FF_READONLY, FF_PUSHBUTTON = 1, 65536
DOT_SCALE = 0.45   # Chrome draws the regenerated ZapfDingbats circle at about 0.45 of the field size

ACTION_KEYS = ('E', 'X', 'D', 'U', 'Fo', 'Bl', 'K', 'F', 'V', 'C')


def esc(s: str) -> str:
    """Escape a string for a PDF literal string ``( ... )``."""
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)').replace('\r', '\\r').replace('\n', '\\n')


def rgb(c, op: str) -> str:
    return f'{c[0]:.3f} {c[1]:.3f} {c[2]:.3f} {op}'


def circle_path(cx: float, cy: float, r: float) -> str:
    k = 0.5523 * r
    return (f'{cx + r:.2f} {cy:.2f} m {cx + r:.2f} {cy + k:.2f} {cx + k:.2f} {cy + r:.2f} {cx:.2f} {cy + r:.2f} c '
            f'{cx - k:.2f} {cy + r:.2f} {cx - r:.2f} {cy + k:.2f} {cx - r:.2f} {cy:.2f} c '
            f'{cx - r:.2f} {cy - k:.2f} {cx - k:.2f} {cy - r:.2f} {cx:.2f} {cy - r:.2f} c '
            f'{cx + k:.2f} {cy - r:.2f} {cx + r:.2f} {cy - k:.2f} {cx + r:.2f} {cy:.2f} c')


def js_action(js: str) -> str:
    return f'<< /S /JavaScript /JS ({esc(js)}) >>'


class LivePdf:
    """One page, its static drawing, its form fields and its document-level JavaScript."""

    def __init__(self, width: float = 960, height: float = 540):
        self.W, self.H = width, height
        self.objs: list[bytes] = []
        self.content: list[str] = []
        self.fields: list[tuple[str, float, float, float, float, str]] = []   # name, x0, y0, x1, y1 (PDF), extra
        self.scripts: list[tuple[str, str]] = []
        self._forms: dict = {}
        self.helv = self.add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
        self.helvb = self.add('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>')
        self.zadb = self.add('<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>')

    # ---------- low level ----------
    def add(self, body: str | bytes) -> int:
        self.objs.append(body if isinstance(body, bytes) else body.encode('latin-1'))
        return len(self.objs)

    @staticmethod
    def stream(data: str, extra: str = '', compress: bool = True) -> bytes:
        b = data.encode('latin-1')
        if compress:
            b = zlib.compress(b, 9)
            extra += '/Filter /FlateDecode '
        return f'<< /Length {len(b)} {extra}>>\nstream\n'.encode('latin-1') + b + b'\nendstream'

    def y(self, top: float) -> float:
        """Top-based y to PDF y."""
        return self.H - top

    def form_xobject(self, content: str, bbox: tuple[float, float, float, float], fonts: bool = False) -> int:
        """Appearance stream; identical ones are written once and shared."""
        key = (content, tuple(bbox), fonts)
        if key in self._forms:
            return self._forms[key]
        res = f'/Resources << /Font << /F1 {self.helv} 0 R /F2 {self.helvb} 0 R >> >> ' if fonts else ''
        self._forms[key] = self.add(self.stream(content, f'/Type /XObject /Subtype /Form /BBox [{" ".join(map(str, bbox))}] {res}',
                                               False))
        return self._forms[key]

    # ---------- static page drawing ----------
    def raw(self, ops: str) -> None:
        self.content.append(ops)

    def text(self, x: float, top: float, size: float, s: str, bold: bool = False, color=INK) -> None:
        """Text whose top edge (roughly the cap height) is at ``top``."""
        self.content.append(f'BT /{"F2" if bold else "F1"} {size} Tf {rgb(color, "rg")} {x:.1f} {self.y(top) - size:.1f} Td '
                            f'({esc(s)}) Tj ET')

    def line(self, x1: float, t1: float, x2: float, t2: float, color=GREY, width: float = 0.75) -> None:
        self.content.append(f'{rgb(color, "RG")} {width} w {x1:.1f} {self.y(t1):.1f} m {x2:.1f} {self.y(t2):.1f} l S')

    def rect(self, x: float, top: float, w: float, h: float, fill=None, stroke=None, width: float = 0.75) -> None:
        r = f'{x:.1f} {self.y(top) - h:.1f} {w:.1f} {h:.1f} re'
        if fill is not None:
            self.content.append(f'{rgb(fill, "rg")} {r} f')
        if stroke is not None:
            self.content.append(f'{rgb(stroke, "RG")} {width} w {r} S')

    def circle(self, cx: float, ctop: float, r: float, fill=INK) -> None:
        self.content.append(f'{rgb(fill, "rg")} {circle_path(cx, self.y(ctop), r)} f')

    # ---------- fields ----------
    def widget(self, name: str, x: float, top: float, w: float, h: float, extra: str) -> None:
        """Raw widget; ``extra`` is the rest of the annotation dictionary."""
        if any(f[0] == name for f in self.fields):
            raise ValueError(f'duplicate field name {name!r}')
        self.fields.append((name, x, self.y(top) - h, x + w, self.y(top), extra))

    @staticmethod
    def actions(on_click: str | None = None, **aa: str | None) -> str:
        """``/A`` for ``on_click`` (activate, after mouse up) plus ``/AA`` for the other triggers.

        Triggers: E enter, X exit, D mouse down, U mouse up, Fo focus, Bl blur, K keystroke, F format,
        V validate, C calculate. In Chrome only ``D`` (mouse down) and ``A`` arrive reliably for clicks.
        """
        out = f'/A {js_action(on_click)} ' if on_click else ''
        unknown = set(aa) - set(ACTION_KEYS)
        if unknown:
            raise ValueError(f'unknown trigger(s) {sorted(unknown)}; use {ACTION_KEYS}')
        parts = ' '.join(f'/{k} {js_action(v)}' for k, v in aa.items() if v)
        return out + (f'/AA << {parts} >>' if parts else '')

    def text_field(self, name: str, x: float, top: float, w: float, h: float, value: str = '', *, size: float = 12,
                   bold: bool = False, color=INK, align: int = 0, readonly: bool = True, max_len: int | None = None,
                   bg=None, border=None, border_width: float = 1, hidden: bool = False, multiline: bool = False,
                   on_click: str | None = None, **triggers: str | None) -> None:
        """Text field. ``readonly=True`` makes an output label that scripts write to; ``align`` 0/1/2 = left/centre/right;
        ``multiline`` wraps long text inside the field."""
        mk = ''
        if bg is not None or border is not None:
            mk = '/MK << ' + (f'/BG [{" ".join(map(str, bg))}] ' if bg is not None else '') + \
                 (f'/BC [{" ".join(map(str, border))}] ' if border is not None else '') + '>> '
            if border is not None:
                mk += f'/BS << /W {border_width} >> '
        ff = (1 if readonly else 0) | (4096 if multiline else 0)
        extra = (f'/FT /Tx {f"/Ff {ff} " if ff else ""}/F {F_HIDDEN if hidden else F_VISIBLE} '
                 f'{f"/MaxLen {max_len} " if max_len else ""}/V ({esc(value)}) '
                 f'/DA (/{"HeBo" if bold else "Helv"} {size} Tf {rgb(color, "rg")}) /Q {align} {mk}'
                 + self.actions(on_click, **triggers))
        self.widget(name, x, top, w, h, extra)

    def button_appearance(self, w: float, h: float, label: str, fill=YELLOW, text_color=INK, size: float = 15) -> int:
        """Filled rectangle with a centred bold label (Helvetica-Bold width estimate)."""
        body = (f'{rgb(fill, "rg")} 0 0 {w} {h} re f BT /F2 {size} Tf {rgb(text_color, "rg")} '
                f'{w / 2 - len(label) * size * 0.287:.1f} {h / 2 - size / 3:.1f} Td ({esc(label)}) Tj ET')
        return self.form_xobject(body, (0, 0, w, h), fonts=True)

    def push_button(self, name: str, x: float, top: float, w: float, h: float, label: str | None = None, *,
                    fill=YELLOW, text_color=INK, size: float = 15, appearance: int | None = None,
                    hidden: bool = False, readonly: bool = False, on_click: str | None = None,
                    **triggers: str | None) -> None:
        """Clickable button with its own appearance. Do not move it with ``field.rect``: Chrome drops the look."""
        ap = appearance if appearance is not None else self.button_appearance(w, h, label or '', fill, text_color, size)
        ff = FF_PUSHBUTTON | (FF_READONLY if readonly else 0)
        extra = f'/FT /Btn /Ff {ff} /F {F_HIDDEN if hidden else F_VISIBLE} /AP << /N {ap} 0 R >> ' + \
                self.actions(on_click, **triggers)
        self.widget(name, x, top, w, h, extra)

    def zone(self, name: str, x: float, top: float, w: float, h: float, *, on_click: str | None = None,
             **triggers: str | None) -> None:
        """Invisible clickable area (push button with an empty appearance)."""
        ap = self.form_xobject('', (0, 0, w, h))
        self.push_button(name, x, top, w, h, appearance=ap, on_click=on_click, **triggers)

    def color_bar(self, name: str, x: float, top: float, w: float, h: float, color=INK, *, hidden: bool = False) -> None:
        """Filled rectangle that scripts may move (``field.rect``) and show or hide. Not clickable."""
        ap = self.form_xobject(f'{rgb(color, "rg")} 0 0 {w} {h} re f', (0, 0, w, h))
        self.widget(name, x, top, w, h, f'/FT /Btn /Ff {FF_PUSHBUTTON | FF_READONLY} /F {F_HIDDEN if hidden else F_VISIBLE} '
                                        f'/MK << /BG [{" ".join(map(str, color))}] >> /AP << /N {ap} 0 R >>')

    def dot(self, name: str, cx: float, ctop: float, size: float = 14, color=INK, *, hidden: bool = False) -> None:
        """Round marker that scripts may move and show or hide (ZapfDingbats circle check box).

        The field is ``size`` wide; the visible dot is about ``DOT_SCALE * size`` across, the same before and
        after Chrome regenerates it.
        """
        h, r = size / 2, size * DOT_SCALE / 2
        ap = self.form_xobject(f'{rgb(color, "rg")} {circle_path(h, h, r)} f', (0, 0, size, size))
        self.widget(name, cx - h, ctop - h, size, size,
                    f'/FT /Btn /Ff {FF_READONLY} /V /Yes /AS /Yes /F {F_HIDDEN if hidden else F_VISIBLE} '
                    f'/MK << /CA (l) >> /DA (/ZaDb 0 Tf {rgb(color, "rg")}) /AP << /N << /Yes {ap} 0 R >> >>')

    # ---------- scripts and output ----------
    def script(self, js: str, name: str | None = None) -> None:
        """Document-level JavaScript; runs once when the document opens, in the same global scope as field actions."""
        self.scripts.append((name or f'js{len(self.scripts)}', js))

    def to_bytes(self) -> bytes:
        objs = list(self.objs)

        def add(body: str | bytes) -> int:
            objs.append(body if isinstance(body, bytes) else body.encode('latin-1'))
            return len(objs)

        content = add(self.stream('\n'.join(self.content)))
        page_no = len(objs) + 1 + len(self.fields)
        widget_nos = [add(f'<< /Type /Annot /Subtype /Widget /T ({esc(n)}) /Rect [{x0:.2f} {y0:.2f} {x1:.2f} {y1:.2f}] '
                          f'/P {page_no} 0 R {extra} >>') for n, x0, y0, x1, y1, extra in self.fields]
        assert len(objs) + 1 == page_no
        refs = ' '.join(f'{n} 0 R' for n in widget_nos)
        add(f'<< /Type /Page /Parent {page_no + 1} 0 R /MediaBox [0 0 {self.W} {self.H}] /Contents {content} 0 R '
            f'/Resources << /Font << /F1 {self.helv} 0 R /F2 {self.helvb} 0 R >> >> /Annots [{refs}] >>')
        add(f'<< /Type /Pages /Kids [{page_no} 0 R] /Count 1 >>')
        names = ''
        if self.scripts:
            entries = []
            for nm, js in sorted(self.scripts):
                js_no = add(self.stream(js, compress=False))
                entries.append(f'({esc(nm)}) {add(f"<< /S /JavaScript /JS {js_no} 0 R >>")} 0 R')
            names = f'/Names {add("<< /JavaScript << /Names [" + " ".join(entries) + "] >> >>")} 0 R '
        acro = add(f'<< /Fields [{refs}] /NeedAppearances false /DR << /Font << /Helv {self.helv} 0 R '
                   f'/HeBo {self.helvb} 0 R /ZaDb {self.zadb} 0 R >> >> /DA (/Helv 12 Tf 0 g) >>')
        catalog = add(f'<< /Type /Catalog /Pages {page_no + 1} 0 R /AcroForm {acro} 0 R {names}>>')

        out = bytearray(b'%PDF-1.7\n%\xe2\xe3\xcf\xd3\n')
        offs = []
        for i, body in enumerate(objs, 1):
            offs.append(len(out))
            out += f'{i} 0 obj\n'.encode() + body + b'\nendobj\n'
        xref = len(out)
        out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
        for o in offs:
            out += f'{o:010d} 00000 n \n'.encode()
        out += f'trailer\n<< /Size {len(objs) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
        return bytes(out)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.to_bytes())
        return path
