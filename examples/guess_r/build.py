"""Guess r: a "guess the correlation" game that runs inside a PDF viewer. The largest livepdf example: live
random data in 100 moving dot fields, a residual chart with a moving quartile band, hearts, coins, streaks, and
three buttons taking turns on one spot. Standalone repo with its own tests: guess-r-pdf.

    python examples/guess_r/build.py out/guess-r.pdf

Every round the script draws 100 new random points with a random target correlation (0 to 1) and moves 100 dot
fields to them. The page is drawn here; the game logic lives in game.js and gets its layout constants as a
CFG object prepended to it (no %-formatting of JavaScript, so a literal % in the script is safe).
"""
import json
import math
import random
import sys
from pathlib import Path

from livepdf import LivePdf
from livepdf.build import DOT_SCALE, GREY, INK, YELLOW, circle_path, rgb

W, H = 960, 540
N = 100
PX, PTOP, PS = 50, 40, 450                 # scatter plot box (top-based)
RX = 560                                   # right column
CX, CTOP, CW, CH = RX, 368, 360, 96        # residual chart box (top-based)
CMAX, NHIST = 0.5, 30                      # residuals -0.5..+0.5, last 30 rounds
RED, DARKYEL, MUTED = (0.85, 0.15, 0.2), (0.6, 0.45, 0), (0.35, 0.35, 0.35)
DOT = 14                                   # dot field size; the visible dot is DOT_SCALE * DOT across
M = 22                                     # margin inside the plot box
HX, HTOP, HW = RX + 118, 46, 20            # hearts row

g = LivePdf(W, H)

# ---------- static page ----------
g.rect(PX, PTOP, PS, PS, fill=(0.97, 0.97, 0.97), stroke=GREY)
g.text(RX, 44, 26, 'Guess r', bold=True)
for i, s in enumerate(('How strongly are the two values related?', 'Type the correlation r between 0 and 1.',
                       '0 = no relationship, 1 = a perfect straight line.')):
    g.text(RX, 80 + 18 * i, 13, s, color=MUTED)
g.text(RX, 152, 12, 'YOUR GUESS', bold=True, color=DARKYEL)
g.text(RX, 236, 12, 'RESULT', bold=True, color=DARKYEL)
g.text(RX, 330, 12, 'YOUR RESIDUALS', bold=True, color=DARKYEL)
g.rect(CX, CTOP, CW, CH, stroke=GREY)


def cy(v):  # residual value -> top-based y
    return CTOP + CH * (0.5 - v / (2 * CMAX))


for v in (0.25, -0.25):
    g.line(CX, cy(v), CX + CW, cy(v), (0.88, 0.88, 0.88), 0.5)
g.line(CX, cy(0), CX + CW, cy(0), GREY, 0.75)
for v, s in ((0.5, '+0.5'), (0.25, '+0.25'), (0, '0'), (-0.25, '-0.25'), (-0.5, '-0.5')):
    g.text(CX + CW + 5, cy(v) - 4, 8, s, color=GREY)
g.text(CX + 6, CTOP + 4, 8, 'guessed too high', color=GREY)
g.text(CX + 6, CTOP + CH - 12, 8, 'guessed too low', color=GREY)
g.text(CX, CTOP + CH + 5, 8, f'residual = guess - true r, last {NHIST} rounds; grey band = middle 50 % (Q1 to Q3), '
                             'black bar = bias', color=GREY)
g.text(RX, 488, 8, 'Hearts: off by more than 0.10 costs one, within 0.02 earns one (max 5). Coins: 5 / 3 / 1 for an '
                   'error within', color=(0.4, 0.4, 0.4))
g.text(RX, 498, 8, '0.02 / 0.05 / 0.10. Streak = rounds in a row within 0.05; each streak round adds bonus coins.',
       color=(0.4, 0.4, 0.4))
g.text(RX, 512, 8, 'Works in Chrome (and Acrobat). In Chrome the first click after opening only activates the page.',
       color=(0.55, 0.55, 0.55))


def heart(x0, y0):
    p = [(8, 1.5), (3, 5), (0, 7.5), (0, 10), (0, 12.5), (2, 14), (4, 14), (6, 14), (7.3, 12.8), (8, 11.5),
         (8.7, 12.8), (10, 14), (12, 14), (14, 14), (16, 12.5), (16, 10), (16, 7.5), (13, 5), (8, 1.5)]
    q = [(x0 + a, y0 + b) for a, b in p]
    d = f'{q[0][0]:.2f} {q[0][1]:.2f} m '
    for i in range(1, len(q), 3):
        d += ' '.join(f'{u:.2f} {v:.2f}' for u, v in q[i:i + 3]) + ' c '
    return d + 'h'


for i in range(5):                          # empty heart outlines; filled hearts are fields on top
    g.raw(f'{rgb((0.75, 0.75, 0.75), "RG")} 1 w ' + heart(HX + i * HW, g.y(HTOP) - 15) + ' S')
coin_x, coin_y = HX + 5 * HW + 14, g.y(HTOP) - 8
g.raw(f'{rgb(YELLOW, "rg")} {rgb(DARKYEL, "RG")} 1.2 w {circle_path(coin_x, coin_y, 7)} b')

# ---------- start plot, drawn as field positions so the page looks right before any script runs ----------
rng = random.Random(7)


def sample(target):
    while True:
        xs = [rng.gauss(0, 1) for _ in range(N)]
        ys = [target * a + math.sqrt(1 - target ** 2) * rng.gauss(0, 1) for a in xs]
        mx, my = sum(xs) / N, sum(ys) / N
        r = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / math.sqrt(
            sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
        if r >= 0:
            return xs, ys, round(r, 2)


xs, ys, r0 = sample(0.7)
lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)

# ---------- fields (order matters: later fields are drawn on top, but Chrome gives a click on overlapping
# fields to the first one) ----------
for i, (a, b) in enumerate(zip(xs, ys)):
    g.dot(f'd{i}', PX + M + (a - lo_x) / (hi_x - lo_x) * (PS - 2 * M),
          PTOP + PS - M - (b - lo_y) / (hi_y - lo_y) * (PS - 2 * M), DOT, INK)
g.color_bar('band', CX, CTOP + CH - 2, CW, 2, (0.86, 0.86, 0.86), hidden=True)     # Q1..Q3, under the dots
for i in range(NHIST):
    g.dot(f'h{i}', CX + 7, CTOP + CH - 7, DOT, DARKYEL, hidden=True)
g.color_bar('meanbar', CX, CTOP + CH - 1.6, CW, 1.6, INK, hidden=True)
g.text_field('guess', RX, 170, 160, 44, '0.', size=26, bold=True, align=1, readonly=False, max_len=5,
             bg=(1, 1, 1), border=INK, border_width=1.5, V='check(event.value);')
# Check, New game and Next plot share one spot and one handler: what a click means is decided at mouse down.
# Chrome keeps giving clicks on that spot to Check after it is hidden (it still has the focus), so the handler,
# not the button, decides.
for name, label, hidden in (('btnCheck', 'Check', False), ('btnNew', 'New game', True)):
    g.push_button(name, RX + 176, 172, 130, 40, label, hidden=hidden, on_click='main();', D='press();')
ap_heart = g.form_xobject(f'{rgb(RED, "rg")} {heart(0, 0)} f', (0, 0, 16, 15))
for i in range(5):
    g.push_button(f'hf{i}', HX + i * HW, HTOP, 16, 15, appearance=ap_heart, readonly=True, hidden=i >= 3)
g.text_field('coins', coin_x + 11, HTOP - 2, 52, 20, '0', size=15, bold=True)
g.text_field('streak', RX + 300, HTOP - 1, 80, 18, 'streak 0', size=10, bold=True, color=DARKYEL, align=2)
g.push_button('btnNext', RX + 176, 172, 130, 40, 'Next plot', hidden=True, on_click='main();', D='press();')
g.text_field('warn', RX, 218, 380, 14, '', size=11, color=(0.75, 0.1, 0.1))
g.text_field('resTrue', RX, 252, 200, 40, '', size=32, bold=True)
g.text_field('resRate', RX + 210, 262, 170, 24, '', size=20, bold=True, color=DARKYEL)
g.text_field('resLine', RX, 296, 380, 20, '', size=14, color=(0.3, 0.3, 0.3))
g.text_field('stats', RX + 120, 331, 260, 13, 'no rounds yet', size=10, bold=True, align=2)

CFG = {'N': N, 'PX': PX, 'PB': g.y(PTOP + PS), 'PS': PS, 'M': M, 'DOT': DOT, 'CX': CX, 'CB': g.y(CTOP) - CH,
       'CW': CW, 'CH': CH, 'CMAX': CMAX, 'NHIST': NHIST, 'r0': r0}
game_js = (Path(__file__).parent / 'game.js').read_text(encoding='utf-8')
g.script(f'var CFG = {json.dumps(CFG)};\n' + game_js, name='game')

if __name__ == '__main__':
    out = g.save(sys.argv[1] if len(sys.argv) > 1 else 'guess-r.pdf')
    print(f'{out}: start r {r0}, {len(g.fields)} fields, {out.stat().st_size} bytes')
