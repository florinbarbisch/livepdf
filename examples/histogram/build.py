"""Histogram bin explorer: pick a dataset and a bin count, see how the shape changes.

Five distributions from small demo series (datasets.json, made by extract_data.py): a long tail, a narrow
bell, two groups, a near-constant series with a few outliers, and a zero-inflated one. Drag the knob (or use - / +)
to choose 2 to 60 bins; the orange and purple ticks mark the Sturges and Freedman-Diaconis rules.

Dragging works like the F1 slider: one zone per bin count takes mouse down (grab), mouse enter
(follow the pointer while the button is held) and mouse up (drop). Bars are 60 movable colour bars, resized with hide, set rect, show. All click zones come first in the field
order, so the knob and labels drawn above them never take a click. The start state is computed here too, so the
page looks right before (or without) JavaScript.

    python examples/histogram/build.py out/histogram.pdf
"""
import json
import math
import sys
from pathlib import Path

from livepdf import LivePdf
from livepdf.build import GREY, INK, YELLOW

HERE = Path(__file__).parent
DATA = json.loads((HERE / 'datasets.json').read_text(encoding='utf-8'))
W, H = 960, 540
CX, CTOP, CW, CH = 70, 100, 560, 280          # chart box (top-based)
KMIN, KMAX = 2, 60
TX, TTOP = CX, 440                            # bin-count track
STEP = CW / (KMAX - KMIN)
RX = 670                                      # right panel
BLUE, ORANGE, PURPLE = (0.22, 0.45, 0.85), (0.95, 0.55, 0.10), (0.55, 0.30, 0.75)
MUTED, DARKYEL = (0.35, 0.35, 0.35), (0.6, 0.45, 0)


def sturges(n):
    return min(KMAX, max(KMIN, math.ceil(math.log2(n)) + 1))


def quantile(s, q):
    p = (len(s) - 1) * q
    i = math.floor(p)
    return s[i] + (s[min(i + 1, len(s) - 1)] - s[i]) * (p - i)


def freedman_diaconis(values):
    s = sorted(values)
    iqr = quantile(s, 0.75) - quantile(s, 0.25)
    if iqr <= 0:
        return KMAX
    return min(KMAX, max(KMIN, math.ceil((s[-1] - s[0]) / (2 * iqr / len(s) ** (1 / 3)))))


def counts(values, k):
    lo, hi = min(values), max(values)
    c = [0] * k
    for v in values:
        c[min(k - 1, int((v - lo) / (hi - lo) * k)) if hi > lo else 0] += 1
    return c


def kx(k):                                    # bin count -> x on the track
    return TX + (k - KMIN) * STEP


g = LivePdf(W, H)
g.text(40, 22, 24, 'How many bins?', bold=True)
g.text(40, 56, 12, 'The same data, a different bin count, a different story. Drag the knob below the chart or use '
                   '- and +.', color=MUTED)
g.rect(CX, CTOP, CW, CH, fill=(0.985, 0.985, 0.985))
g.line(CX, CTOP + CH, CX + CW, CTOP + CH, INK, 1)
g.line(CX, CTOP, CX, CTOP + CH, GREY, 0.75)
g.text(CX - 14, CTOP + CH - 6, 9, '0', color=MUTED)
g.text(40, TTOP - 8, 11, 'bins', bold=True)
g.rect(TX, TTOP - 1.5, CW, 3, fill=(0.75, 0.75, 0.75))
for k in (2, 10, 20, 30, 40, 50, 60):
    g.text(kx(k) - 5, TTOP + 14, 9, str(k), color=MUTED)
g.text(RX, 100, 12, 'DATA', bold=True, color=DARKYEL)
g.text(RX, 360, 12, 'RULES OF THUMB', bold=True, color=DARKYEL)
g.circle(RX + 5, 386, 4, ORANGE)
g.circle(RX + 5, 406, 4, PURPLE)
g.text(40, 510, 9, 'Data: demo series in datasets.json. In Chrome the first click after opening only '
                   'activates the page.', color=(0.55, 0.55, 0.55))

# ---------- click zones first ----------
for k in range(KMIN, KMAX + 1):
    g.zone(f'z{k}', kx(k) - STEP / 2, TTOP - 16, STEP, 32, D=f'grab({k});', E=f'follow({k});', U='drop();')
g.zone('minusZ', CX + CW + 14, TTOP - 14, 28, 28, D='setBins(bins - 1);')
g.zone('plusZ', CX + CW + 48, TTOP - 14, 28, 28, D='setBins(bins + 1);')
for i in range(len(DATA)):
    g.zone(f'dsZ{i}', RX, 116 + i * 40, 250, 34, D=f'setData({i});')
g.zone('sturZ', RX + 14, 378, 236, 18, D='setBins(sturgesK);')
g.zone('fdZ', RX + 14, 398, 236, 18, D='setBins(fdK);')

# ---------- drawing layers (start state: first dataset, Sturges bin count) ----------
k0 = sturges(len(DATA[0]['values']))
c0 = counts(DATA[0]['values'], k0)
for i in range(KMAX):
    bw = CW / k0
    if i < k0 and c0[i]:                       # same whole-point rounding as place() in histogram.js
        h = c0[i] / max(c0) * CH
        left, right = round(CX + i * bw + 0.75), round(CX + i * bw + bw - 0.75)
        bottom, top = round(H - CTOP - CH), round(H - CTOP - CH + h)
        g.color_bar(f'bar{i}', left, H - top, right - left, top - bottom, BLUE)
    else:
        g.color_bar(f'bar{i}', CX, CTOP + CH - 1, 1, 1, BLUE, hidden=True)
for name, x in (('minusBg', CX + CW + 14), ('plusBg', CX + CW + 48)):
    g.color_bar(name, x, TTOP - 14, 28, 28, YELLOW)
g.text_field('minusTxt', CX + CW + 14, TTOP - 10, 28, 22, '-', size=18, bold=True, align=1)
g.text_field('plusTxt', CX + CW + 48, TTOP - 10, 28, 22, '+', size=18, bold=True, align=1)
for i, d in enumerate(DATA):
    g.color_bar(f'dsBg{i}', RX, 116 + i * 40, 250, 34, (0.94, 0.94, 0.94), hidden=i == 0)
    g.color_bar(f'dsSel{i}', RX, 116 + i * 40, 250, 34, YELLOW, hidden=i != 0)
    g.text_field(f'ds{i}', RX + 10, 124 + i * 40, 236, 18, d['title'], size=13, bold=True)
fd0 = freedman_diaconis(DATA[0]['values'])
g.color_bar('mS', kx(k0) - 1.5, TTOP - 12, 3, 9, ORANGE)
g.color_bar('mF', kx(fd0) - 1.5, TTOP + 3, 3, 9, PURPLE)
g.dot('knob', kx(k0), TTOP, 20, INK)
g.text_field('ymax', 20, CTOP - 4, 46, 12, str(max(c0)), size=9, align=2, color=MUTED)
g.text_field('xmin', CX, CTOP + CH + 4, 160, 14, '', size=10, color=MUTED)
g.text_field('xmax', CX + CW - 160, CTOP + CH + 4, 160, 14, '', size=10, align=2, color=MUTED)
g.text_field('title', CX, CTOP - 22, 400, 18, DATA[0]['title'], size=14, bold=True)
g.text_field('info', CX + CW - 220, CTOP - 22, 220, 18, '', size=12, bold=True, align=2)
g.text_field('note', RX, 314, 270, 40, DATA[0]['note'], size=10, color=MUTED, multiline=True)
g.text_field('lS', RX + 16, 380, 236, 14, f'Sturges: {k0} bins', size=11)
g.text_field('lF', RX + 16, 400, 236, 14, f'Freedman-Diaconis: {fd0} bins', size=11)
g.text_field('kTxt', 40, TTOP + 4, 28, 14, str(k0), size=11, bold=True)

CFG = {'CX': CX, 'CB': g.y(CTOP + CH), 'CW': CW, 'CH': CH, 'KMIN': KMIN, 'KMAX': KMAX, 'TX': TX,
       'TY': g.y(TTOP), 'STEP': STEP, 'start': k0}
g.script(f'var CFG = {json.dumps(CFG)};\nvar DATA = {json.dumps(DATA, separators=(",", ":"))};\n'
         + (HERE / 'histogram.js').read_text(encoding='utf-8'), name='histogram')

if __name__ == '__main__':
    out = g.save(sys.argv[1] if len(sys.argv) > 1 else 'histogram.pdf')
    print(f'{out}: {len(DATA)} datasets, {len(g.fields)} fields, {out.stat().st_size} bytes')
