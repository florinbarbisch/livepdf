"""Reaction test: wait for green, then click as fast as you can. Five tries make a series.

One big pad is the start button, the target and the result display at once, so no buttons swap places. The
click is taken at mouse down (the event Chrome always delivers, and the earliest one). Timers: app.setTimeOut
for the random wait. Times include the viewer's repaint delay, so they read a little slower than a native app.

    python examples/reaction/build.py out/reaction.pdf
"""
import json
import sys
from pathlib import Path

from livepdf import LivePdf
from livepdf.build import GREY, INK

W, H = 720, 480
PAD = (40, 90, 420, 340)                 # x, top, w, h
MUTED = (0.35, 0.35, 0.35)
TRIES = 5

g = LivePdf(W, H)
g.text(40, 28, 24, 'Reaction test', bold=True)
g.text(40, 62, 12, f'Click the pad to start. When it turns green, click as fast as you can. {TRIES} tries make a series.',
       color=MUTED)
x, top, w, h = PAD
g.rect(x, top, w, h, stroke=GREY)
g.text(490, 96, 12, 'THIS SERIES', bold=True, color=(0.6, 0.45, 0))
g.text(490, 300, 12, 'BEST SERIES AVERAGE', bold=True, color=(0.6, 0.45, 0))
g.text(40, 446, 9, 'Times include the PDF viewer\'s repaint delay. In Chrome the first click after opening only '
                   'activates the page.', color=(0.55, 0.55, 0.55))

g.zone('pad', x, top, w, h, D='tap();')   # first in the field order: it gets every click on the pad
for name, col, hidden in (('padIdle', (0.90, 0.90, 0.90), False), ('padWait', (0.85, 0.20, 0.20), True),
                          ('padGo', (0.15, 0.70, 0.30), True), ('padEarly', (0.98, 0.60, 0.10), True)):
    g.color_bar(name, x + 1, top + 1, w - 2, h - 2, col, hidden=hidden)
g.text_field('padText', x, top + 120, w, 50, 'Click to start', size=34, bold=True, align=1)
g.text_field('padSub', x, top + 180, w, 24, '', size=14, align=1, color=INK)
for i in range(TRIES):
    g.text_field(f'try{i}', 490, 122 + i * 30, 190, 26, f'{i + 1}.  -', size=16, color=MUTED)
g.text_field('avg', 490, 276 - 6, 190, 22, '', size=14, bold=True)
g.text_field('best', 490, 322, 190, 34, '-', size=26, bold=True)

CFG = {'tries': TRIES, 'minWait': 1500, 'maxWait': 4000}
g.script(f'var CFG = {json.dumps(CFG)};\n' + (Path(__file__).parent / 'reaction.js').read_text(encoding='utf-8'),
         name='reaction')

if __name__ == '__main__':
    out = g.save(sys.argv[1] if len(sys.argv) > 1 else 'reaction.pdf')
    print(f'{out}: {len(g.fields)} fields, {out.stat().st_size} bytes')
