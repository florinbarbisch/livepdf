"""Render a simulated game state to PNG with PyMuPDF (``pip install livepdf[render]``).

The page's static content is drawn as is. Fields are drawn on top from the simulated state, the way Chrome shows
them: text fields as their text (font and size from ``/DA``), ``/MK /BG`` bars as filled rectangles, ZapfDingbats
circle check boxes as dots, and push buttons with their own appearance stream as that appearance (placed at the
field's current rect). It is a cheap preview, not pixel-exact Chrome output; use :mod:`livepdf.chrome` for that.
"""
from __future__ import annotations

import re
from pathlib import Path

from .build import DOT_SCALE

_DA = re.compile(r'/(\w+)\s+([\d.]+)\s+Tf(?:.*?([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg|.*?([\d.]+)\s+g)?')


def _da(da: str):
    m = _DA.search(da or '')
    if not m:
        return 'Helv', 12.0, (0, 0, 0)
    font, size = m.group(1), float(m.group(2))
    if m.group(3):
        col = (float(m.group(3)), float(m.group(4)), float(m.group(5)))
    elif m.group(6):
        col = (float(m.group(6)),) * 3
    else:
        col = (0, 0, 0)
    return font, size, col


def render_state(pdf: str | Path, state: dict, out_png: str | Path, dpi: int = 96) -> Path:
    import pymupdf

    from .inspect import load

    doc = load(pdf)
    meta = {f.name: f for f in doc.fields}
    data = Path(pdf).read_bytes()
    src = pymupdf.open('pdf', data)
    xrefs = {w.field_name: w.xref for w in src[0].widgets()}
    out = pymupdf.open()
    page = out.new_page(width=doc.width, height=doc.height)
    page.show_pdf_page(page.rect, src, 0)            # static content only; widgets are not copied
    H = doc.height
    for name, st in state.items():
        f = meta.get(name)
        if f is None or not st.visible:
            continue
        x0, y0, x1, y1 = st.rect
        r = pymupdf.Rect(x0, H - y1, x1, H - y0)
        font, size, col = _da(f.da)
        if f.type == 'text':
            if f.mk_bg or f.mk_bc:
                page.draw_rect(r, color=f.mk_bc, fill=f.mk_bg, width=1.5 if f.mk_bc else 0)
            txt = str(st.value)
            if txt:
                fs = size or 12
                fontname = 'hebo' if font in ('HeBo', 'Helvetica-Bold') else 'helv'
                tw = pymupdf.get_text_length(txt, fontname=fontname, fontsize=fs)
                x = r.x0 + 2 if f.align == 0 else (r.x0 + r.x1 - tw) / 2 if f.align == 1 else r.x1 - 2 - tw
                page.insert_text((x, (r.y0 + r.y1) / 2 + fs * 0.35), txt, fontsize=fs, fontname=fontname, color=col)
        elif f.mk_ca == 'l' and str(st.value) not in ('Off', ''):
            d = min(r.width, r.height) * DOT_SCALE
            page.draw_circle(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2), d / 2, color=None, fill=col)
        elif f.mk_bg is not None and (f.readonly or not f.has_ap or st.moves):
            page.draw_rect(r, color=None, fill=f.mk_bg)
        elif f.has_ap and name in xrefs:
            _draw_ap(data, xrefs[name], page, r)
    pix = page.get_pixmap(dpi=dpi)
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_png))
    return out_png


def _draw_ap(data: bytes, xref: int, page, rect) -> None:
    """Draw one widget's normal appearance into ``rect``: render a copy of the page that has only that widget."""
    import pymupdf

    tmp = pymupdf.open('pdf', data)
    tp = tmp[0]
    tmp.xref_set_key(xref, 'F', '4')                      # visible and printable, whatever the original flags
    tmp.xref_set_key(tp.xref, 'Annots', f'[{xref} 0 R]')
    tp = tmp.reload_page(tp)
    clip = next(w.rect for w in tp.widgets())
    pix = tp.get_pixmap(clip=clip, dpi=192, annots=True)
    page.insert_image(rect, pixmap=pix, keep_proportion=False)
    tmp.close()
