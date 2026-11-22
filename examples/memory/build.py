"""Memory: find the 8 pairs on a 4 x 4 board. Counts moves and time, keeps the best result.

Each card is a permanent click zone (all 16 come first in the field order) under three layers: the back (blue),
the face (white) or the solved face (green), and 8 prepared symbol fields in ZapfDingbats (one per pair). Flipping = showing and
hiding; two cards that do not match turn back after a short app.setTimeOut, or at once with the next click.
"New game" is one more zone under a bar and a caption, always visible, so nothing swaps places.

    python examples/memory/build.py out/memory.pdf
"""
import sys
from pathlib import Path

from livepdf import LivePdf
from livepdf.build import GREY, YELLOW, esc, rgb

W, H = 900, 520
N, SIZE, GAP, X0, TOP0 = 4, 96, 12, 40, 50
MUTED, DARKYEL = (0.35, 0.35, 0.35), (0.6, 0.45, 0)
RX = X0 + N * (SIZE + GAP) + 40
# ZapfDingbats characters (circle, square, star, triangle, diamond, check, phone, envelope) and their colours.
# Chrome ignored textColor set by the script, so each colour lives in its own field.
SYMBOLS = [('l', (0.85, 0.15, 0.20)), ('n', (0.15, 0.40, 0.85)), ('H', (0.90, 0.60, 0.00)), ('s', (0.20, 0.60, 0.30)),
           ('u', (0.55, 0.25, 0.70)), ('4', (0.10, 0.10, 0.10)), ('%', (0.80, 0.30, 0.55)), (')', (0.10, 0.55, 0.60))]


def cell(i):
    return X0 + (i % N) * (SIZE + GAP), TOP0 + (i // N) * (SIZE + GAP)


g = LivePdf(W, H)
g.text(RX, 50, 26, 'Memory', bold=True)
g.text(RX, 88, 12, 'Click two cards. A pair stays open,', color=MUTED)
g.text(RX, 104, 12, 'other cards turn back. Find all 8 pairs.', color=MUTED)
g.text(RX, 150, 12, 'MOVES', bold=True, color=DARKYEL)
g.text(RX + 130, 150, 12, 'TIME', bold=True, color=DARKYEL)
g.text(RX, 236, 12, 'BEST', bold=True, color=DARKYEL)
g.text(40, 496, 9, 'In Chrome the first click after opening only activates the page.', color=(0.55, 0.55, 0.55))
for i in range(N * N):
    x, top = cell(i)
    g.rect(x - 1, top - 1, SIZE + 2, SIZE + 2, stroke=GREY)

for i in range(N * N):                      # click zones first: they get the clicks on the overlapping layers
    g.zone(f'c{i}', *cell(i), SIZE, SIZE, D=f'flip({i});')
g.zone('newZ', RX, 330, 170, 44, D='newGame();')
for i in range(N * N):
    x, top = cell(i)
    g.color_bar(f'back{i}', x, top, SIZE, SIZE, (0.22, 0.45, 0.85))
    g.color_bar(f'face{i}', x, top, SIZE, SIZE, (0.98, 0.98, 0.98), hidden=True)
    g.color_bar(f'done{i}', x, top, SIZE, SIZE, (0.80, 0.93, 0.80), hidden=True)
    for p, (ch, col) in enumerate(SYMBOLS):   # one prepared symbol per pair; the script shows one of them
        g.widget(f'sym{i}_{p}', x, top + 20, SIZE, 56,
                 f'/FT /Tx /Ff 1 /F 6 /V ({esc(ch)}) /DA (/ZaDb 46 Tf {rgb(col, "rg")}) /Q 1')   # ZapfDingbats
g.color_bar('newBg', RX, 330, 170, 44, YELLOW)
g.text_field('newTxt', RX, 341, 170, 24, 'New game', size=16, bold=True, align=1)
g.text_field('moves', RX, 168, 120, 40, '0', size=30, bold=True)
g.text_field('time', RX + 130, 168, 120, 40, '0 s', size=30, bold=True)
g.text_field('best', RX, 254, 260, 30, '-', size=20, bold=True)
g.text_field('msg', RX, 400, 260, 24, '', size=16, bold=True, color=(0.15, 0.55, 0.25))
g.script((Path(__file__).parent / 'memory.js').read_text(encoding='utf-8'), name='memory')

if __name__ == '__main__':
    out = g.save(sys.argv[1] if len(sys.argv) > 1 else 'memory.pdf')
    print(f'{out}: {len(g.fields)} fields, {out.stat().st_size} bytes')
