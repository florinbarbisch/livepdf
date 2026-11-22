"""Smallest useful livepdf example: "Pump". Every click on Pump adds 10 to a tank, which leaks 1 per 100 ms.
Fill it to 100 to win.

    python examples/pump.py out/pump.pdf
"""
import json
import sys

from livepdf import LivePdf
from livepdf.build import GREY

W, H = 420, 260
g = LivePdf(W, H)
g.text(24, 24, 22, 'Pump', bold=True)
g.text(24, 56, 11, 'Click Pump to fill the tank before it leaks empty.', color=(0.35, 0.35, 0.35))
g.rect(24, 90, 372, 36, stroke=GREY)
g.color_bar('level', 25, 91, 1, 34, (0.2, 0.55, 0.95))          # width follows the level; moved by the script
g.text_field('status', 24, 140, 372, 22, 'level 0', size=14, bold=True)
# Pump and Again share one spot. Chrome keeps giving clicks on that spot to Pump after Pump hides itself (it still
# has the focus, and it comes first in the annotation order), so both buttons run the same handler and the game
# state decides what a click means.
for name, label, hidden in (('btnPump', 'Pump', False), ('btnAgain', 'Again', True)):
    g.push_button(name, 24, 180, 120, 40, label, hidden=hidden, on_click='main();')
CFG = {'barBottom': g.y(91 + 34), 'barTop': g.y(91)}
g.script(f'var CFG = {json.dumps(CFG)};\n' + '''
var level = 0, won = false, wonAt = 0, timer = null;
function fld(n) { return this.getField(n); }
function draw() {
  var b = fld("level");
  b.display = display.hidden;
  b.rect = [25, CFG.barBottom, 25 + Math.max(1, level * 3.7), CFG.barTop];
  b.display = display.visible;
  fld("status").value = won ? "Full! You won." : "level " + level;
}
function leak() {
  if (won || level <= 0) return;
  level = Math.max(0, level - 1);
  draw();
}
function main() {                     // the click handler of both buttons
  if (!won) { pump(); return; }
  if (new Date().getTime() - wonAt > 600) again();   // fast pumping must not restart the game right away
}
function pump() {
  level = Math.min(100, level + 10);
  if (level >= 100) {
    won = true; wonAt = new Date().getTime();
    fld("btnPump").display = display.hidden; fld("btnAgain").display = display.visible;
  }
  draw();
}
function again() {
  level = 0; won = false; draw();
  fld("btnAgain").display = display.hidden; fld("btnPump").display = display.visible;
}
timer = app.setInterval("leak()", 100);
''', name='game')

if __name__ == '__main__':
    print(g.save(sys.argv[1] if len(sys.argv) > 1 else 'pump.pdf'))
