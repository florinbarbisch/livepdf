"""Quiz: six multiple-choice questions about reading data, with feedback, an explanation and a score.

Every answer row is an invisible click zone (placed first, so it gets the clicks) under a coloured background bar
and a text field. The single "Next" button works the same way, so its caption can change ("Next question",
"See result", "Play again") without swapping buttons on one spot. Questions live in questions.json.

    python examples/quiz/build.py out/quiz.pdf
"""
import json
import sys
from pathlib import Path

from livepdf import LivePdf
from livepdf.build import GREY, INK, YELLOW

HERE = Path(__file__).parent
QUESTIONS = json.loads((HERE / 'questions.json').read_text(encoding='utf-8'))
W, H = 960, 540
X, AW, AH, ATOP, GAP = 60, 840, 50, 170, 12          # answer rows
MUTED, DARKYEL = (0.35, 0.35, 0.35), (0.6, 0.45, 0)
LETTERS = 'ABCD'

g = LivePdf(W, H)
g.text(X, 28, 14, 'QUIZ: READING DATA', bold=True, color=DARKYEL)
g.text(X, 506, 9, 'In Chrome the first click after opening only activates the page.', color=(0.55, 0.55, 0.55))

# click zones first: Chrome gives a click on overlapping fields to the first one in the field order
for i in range(4):
    g.zone(f'aZ{i}', X, ATOP + i * (AH + GAP), AW, AH, D=f'answer({i});')
g.zone('nextZ', X + AW - 200, 440, 200, 44, D='next();')
for i in range(4):
    top = ATOP + i * (AH + GAP)
    g.color_bar(f'aBg{i}', X, top, AW, AH, (0.94, 0.94, 0.94))
    g.color_bar(f'aOk{i}', X, top, AW, AH, (0.70, 0.90, 0.72), hidden=True)
    g.color_bar(f'aBad{i}', X, top, AW, AH, (0.97, 0.72, 0.70), hidden=True)
    g.text_field(f'aL{i}', X + 14, top + 12, 30, 26, LETTERS[i], size=18, bold=True, color=GREY)
    g.text_field(f'a{i}', X + 50, top + 13, AW - 60, 24, '', size=16)
g.color_bar('nextBg', X + AW - 200, 440, 200, 44, YELLOW, hidden=True)
g.text_field('nextTxt', X + AW - 200, 451, 200, 24, '', size=16, bold=True, align=1)
g.text_field('prog', X + AW - 200, 26, 200, 18, '', size=12, bold=True, align=2, color=MUTED)
g.text_field('score', X + AW - 200, 46, 200, 18, '', size=12, align=2, color=MUTED)
g.text_field('q1', X, 70, AW, 30, '', size=22, bold=True)
g.text_field('q2', X, 104, AW, 30, '', size=22, bold=True)
g.text_field('fb', X, 434, AW - 220, 26, '', size=18, bold=True)
g.text_field('expl', X, 462, AW - 220, 20, '', size=12, color=MUTED)

g.script(f'var QUESTIONS = {json.dumps(QUESTIONS)};\n' + (HERE / 'quiz.js').read_text(encoding='utf-8'), name='quiz')

if __name__ == '__main__':
    out = g.save(sys.argv[1] if len(sys.argv) > 1 else 'quiz.pdf')
    print(f'{out}: {len(QUESTIONS)} questions, {len(g.fields)} fields, {out.stat().st_size} bytes')
