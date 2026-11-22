"""F1 slider: drag precision and recall and watch F1 against the plain average.

Drag and drop: 101 invisible zones per slider take mouse down (grab), mouse enter (follow the pointer while the
button is held) and mouse up (drop). The knobs only display the value and take no events: a knob with its own
actions on top of the zones would take the mouse down and the events after it. Bars are 101 complete
pre-drawn bars per value, of which one is visible, and a timer eases between them.

    python examples/f1_slider/build.py out/f1_slider.pdf
"""
import json
import sys
from pathlib import Path

from livepdf import LivePdf
from livepdf.build import INK, YELLOW, rgb

W, H = 960, 540
TL, FULL = 190, 600              # slider and bar track: left edge and length
STEP = FULL / 100
GREY, MID, LIGHT, MUTED = (0.75, 0.75, 0.75), (0.60, 0.60, 0.60), (0.93, 0.93, 0.93), (0.35, 0.35, 0.35)
P0, R0 = 100, 50

g = LivePdf(W, H)
g.text(40, 24, 26, 'Try it: how F1 reacts to precision and recall', bold=True)
g.text(40, 66, 13, 'Drag a yellow knob. F1 is high only when both are high; '
                   'the plain average is shown for comparison.', color=MUTED)
sliders = [('Precision', 'P', 126), ('Recall', 'R', 176)]
for label, k, cy in sliders:
    g.text(40, cy - 9, 16, label, bold=True)
    g.rect(TL, cy - 2, FULL, 4, fill=GREY)
    for v in (0, 50, 100):
        s = f'{v} %'
        g.text(TL + STEP * v - len(s) * 2.4, cy + 12, 9, s, color=(0.5, 0.5, 0.5))
bars = [('Precision', 'P', GREY), ('Recall', 'R', GREY), ('Plain average', 'A', MID), ('F1', 'F', INK)]
for j, (label, k, col) in enumerate(bars):
    top = 230 + j * 58
    g.text(40, top + 12, 16, label, bold=(k == 'F'))
    g.rect(TL, top, FULL, 40, fill=LIGHT)
g.text(40, 506, 10, 'In Chrome the first click after opening only activates the page. Needs a viewer that runs PDF '
                    'JavaScript (tested: Chrome, Edge); others show a still image.', color=(0.5, 0.5, 0.5))

# one segment appearance per bar colour, inset 2 pt inside a 44 pt box (avoids repaint hairlines); the viewer
# stretches it to the field width, so bar i is simply a field STEP * i wide
ap_bar = {k: g.form_xobject(f'{rgb(col, "rg")} 0 2 {STEP:.2f} 40 re f', (0, 0, round(STEP, 2), 44)) for _, k, col in bars}
k9 = 0.5523 * 9
ap_knob = g.form_xobject(f'{rgb(YELLOW, "rg")} {rgb(INK, "RG")} 1.5 w 17.25 9 m 18 {9 + k9:.2f} {9 + k9:.2f} 18 9 18 c '
                         f'{9 - k9:.2f} 18 0 {9 + k9:.2f} 0 9 c 0 {9 - k9:.2f} {9 - k9:.2f} 0 9 0 c '
                         f'{9 + k9:.2f} 0 18 {9 - k9:.2f} 18 9 c b', (-2, -2, 20, 20))

start = {'P': P0, 'R': R0, 'A': round((P0 + R0) / 2), 'F': round(2 * P0 * R0 / (P0 + R0))}
for j, (_, k, _) in enumerate(bars):          # one complete bar per value; only the current one is visible
    for i in range(1, 101):
        g.push_button(f'b{k}_{i}', TL, 230 + j * 58 - 2, STEP * i, 44, appearance=ap_bar[k], readonly=True,
                      hidden=i != start[k])


# Zones first: Chrome gives a click on overlapping fields to the first one in the field order.
for _, k, cy in sliders:                      # 1 %-wide zones that report the mouse position along the track
    for v in range(101):
        g.zone(f'z{k}_{v}', TL + STEP * v - STEP / 2, cy - 22, STEP, 44, D=f'zDown("{k}",{v});', E=f'zEnter("{k}",{v});',
               U='zUp();')
for _, k, cy in sliders:                      # knobs only show the value; they take no events
    for v in range(101):
        g.push_button(f'k{k}_{v}', TL + STEP * v - 11, cy - 11, 22, 22, appearance=ap_knob, readonly=True,
                      hidden=v != start[k])
for j, (_, k, _) in enumerate(bars):
    g.text_field(f'v{k}', 800, 230 + j * 58 + 4, 120, 32, f'{start[k]} %', size=20, bold=(k == 'F'),
                 color=INK if k == 'F' else MUTED)
g.text_field('msg', 40, 464, 880, 24, '', size=15, bold=True)

CFG = {'P0': P0, 'R0': R0, 'start': start}
g.script(f'var CFG = {json.dumps(CFG)};\n' + (Path(__file__).parent / 'f1.js').read_text(encoding='utf-8'), name='f1')

if __name__ == '__main__':
    out = g.save(sys.argv[1] if len(sys.argv) > 1 else 'f1_slider.pdf')
    print(f'{out}: {len(g.fields)} fields, {out.stat().st_size} bytes')
