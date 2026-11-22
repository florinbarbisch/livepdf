---
name: live-pdf
description: Build and test interactive PDFs (games, sliders, quizzes, live charts) that run in Chrome's built-in PDF viewer, using form fields plus document JavaScript. Use when someone wants something clickable or animated inside a PDF, or a PDF game, quiz or teaching demo, or when a PDF with JavaScript misbehaves in Chrome. Covers the livepdf Python library (builder, linter, headless simulator, real-Chrome pixel tests) and the Chrome/PDFium quirks that decide what works.
---

# Interactive PDFs

A PDF can carry JavaScript and form fields. Chrome's viewer (PDFium) runs that script, so a single `.pdf` file can be a
small game. The page itself never changes; the only things a script can change are fields:

- show or hide them
- set their text
- move them with `field.rect`

So all graphics are fields prepared in advance, and the script toggles and moves them.

**Verified:** Chrome on Windows (PDFium).

**Unverified:** expect these viewers to show a static page or behave differently, and tell the user so:

- Acrobat
- Edge
- Firefox (pdf.js)
- mobile viewers
- mail and Teams previews

## Tooling: livepdf

```bash
pip install -e path/to/livepdf[chrome]   # not on PyPI yet; Node 18+ for sim, Node 22+ and Chrome for chrome
livepdf info game.pdf                    # fields, flags, actions
livepdf lint game.pdf                    # static checks + JS syntax; exit 1 on errors
livepdf sim game.pdf "fill guess 0.5" "click btnCheck" "get resRate" "eval hearts" "trace"
livepdf chrome game.pdf "click btnPump" "wait 300" "ink status" "crop status out/status.png"
```

Python API: `LivePdf` (builder), `Sim` (headless JS simulator), `ChromePdf` (real Chrome), `lint(load(pdf))`.
See [references/livepdf-api.md](references/livepdf-api.md).

## Workflow (cheap first, browser last)

1. **Design the state machine first.** Write down the states (for example input → result → next round → game over),
   which fields are visible in each state, and which click moves between states.
2. **Build with `LivePdf`.** Keep the JavaScript in its own `.js` file. Pass layout constants as
   `var CFG = {json};` prepended to the script; never `%`-format JavaScript (`%` in JS breaks it).
   Draw the start state statically, so the page looks right before any script runs.
3. **`livepdf lint`** after every build. It catches:
   - unknown field names (also through `fld("x")`-style helpers)
   - functions called from actions but never defined
   - JS syntax errors
   - covered buttons
   - mouse-up-only actions
   - APIs Chrome lacks
4. **Simulator tests (pytest + `Sim`)** for all game logic: rules, scoring, state changes, button swaps, timers.
   - Results come back as text and run in milliseconds.
   - The simulator uses Chrome's event order and a virtual clock (`advance(ms)`), and Chrome's value coercion.
   - It reports warnings for moves Chrome would render wrong.
   - Write a regression test for every bug before fixing it.
5. **One `ChromePdf` smoke test** proves that PDFium really runs the script and shows the change.
   - Assert on pixels: `color`, `pixel`, `ink` by field name.
   - Save `crop()` images, and look at them only when an assert fails.
6. **For the human:** one final full screenshot or crop. Driving the real browser with screenshots
   (Claude in Chrome) is a last resort for things only a person can judge (looks, feel).

## Rules that decide whether it works in Chrome

**Fields and appearance**

- `/NeedAppearances false`, with your own `/AP` streams. With `true`, Chrome draws its own look and round knobs come
  out square. `LivePdf` does this for you.
- **Moving a field discards its custom `/AP`.** Chrome repaints moved fields from `/MK` only. So:
  - use a push button with `/MK /BG` for bars and bands (`color_bar`)
  - use a check box with the ZapfDingbats circle `/MK /CA (l)` for dots (`dot`, which needs `/ZaDb` in `/DR`)
  - only ever show or hide anything else
- **Hide, then set rect, then show**, or Chrome leaves a ghost at the old spot.
- Chrome draws the regenerated circle at about 0.45 of the field size. Draw static start dots at the same size, or
  they shrink after the first move (`DOT_SCALE`).
- **Show or hide, never redraw.** For a slider, prepare one complete bar per value (101 bars) and switch one on.
  Toggling 100 small segments per frame is visibly slow.
- Inset appearance streams by about 2 pt inside the BBox. This avoids hairlines on repaint.

**Input**

- **The first one or two clicks after opening are lost.** No reliable fix was found. Tell the user in the page
  footer. Tests warm up with clicks on an empty spot.
- **Mouse down (`/AA /D`) and activate (`/A`) are reliable.** Mouse up (`/AA /U`) arrives late, or at the field
  clicked before. Do not build on it.
- **Viewers.** Target desktop Chrome (PDFium) and Edge (Adobe engine); both pass all examples. Firefox (pdf.js)
  runs the logic but does not show or move fields; Safari is untested (see `docs/browser-support.md`). For Edge,
  set `rect` as `[left, top, right, bottom]` in whole points. Edge gives a click to the field drawn on top,
  Chrome to the first: `LivePdf.zone()` writes each zone at both ends of the field order (lint `LP015`).
- **Drag and drop works.** While the button is held, enter and exit go to the fields under the pointer. On
  release, mouse up goes to the pressed field first, then to the one under the pointer. Grab at mouse down, follow
  on enter, drop on the first mouse up.
- **Events can follow the clicked field.** After a click on a field that has enter and activate actions, Chrome
  kept sending enter and mouse-up events to that field while the pointer moved elsewhere. Keep `/E` on fields
  that are never clicked for their own action, or that act at mouse down only.
- **Script-set colours may not show.** `textColor` set from JavaScript did not change the drawn text in Chrome.
  Prepare one field per colour and show the right one.
- **Overlapping fields: the first one in annotation order gets the click**, although the last one is drawn on top.
  A page-wide field placed first swallows every click. Hover (`/E`) does not reach a field under a visible one.
  Avoid stacked clickable fields and big catch-all fields.
- **Clicking a button while a text field has focus:** Chrome first runs the button's mouse down. Then the text
  field commits (keystroke, then validate `/AA /V`). Only about 430 ms later does the button's `/A` run. If the
  validate action already changes the game state, the button sees the new state. **Decide what a click means at
  mouse down** (see the pattern below).
- **Buttons that take turns on one spot** (Pump → Again, Check → Next → New game): a button that a script hides
  keeps getting the clicks on its spot while it has the focus, until the user clicks elsewhere. (This applies only
  if it was visible in the file.) So Again seems dead after the win. Give all of them one handler that decides by
  game state. Ignore a second `main()` within 300 ms (repeated release), and ignore clicks just after a state
  change if fast clicking could skip a screen.
- `field.value` turns numeric-looking text into a number, so `"0."` becomes `0`. Read input with `valueAsString`.
- Typing: the caret often lands at the start of the field. Tests select all before typing.

**Other**

- `app.setInterval("tick()", 16)` works for animation. A target value plus an eased timer feels smooth. Stop the
  timer once everything has settled.
- Persistence: do not rely on `global.setPersistent` in Chrome (untested; expect nothing to survive a reload).
  Keep a high score in a form field; the user saves the PDF with Ctrl+S.
- Chrome can render a newly opened PDF blank. Reloading fixes it (`ChromePdf` retries once).

## Patterns

One handler for buttons that share a spot, decided at mouse down:

```js
var lastMain = 0, pressState = -1, pressAt = 0;
function stateNow() { return over ? 2 : done ? 1 : 0; }
function press() { pressState = stateNow(); pressAt = new Date().getTime(); }     // every button: /AA /D
function main() {                                                                   // every button: /A
  var now = new Date().getTime();
  var st = (pressState >= 0 && now - pressAt < 3000) ? pressState : stateNow();
  pressState = -1;
  if (now - lastMain < 300) return;   // repeated release
  lastMain = now;
  if (st == 2) newGame(); else if (st == 1) nextPlot(); else check(fld("guess").valueAsString);
}
```

Move a marker safely:

```js
function fld(n) { return this.getField(n); }
function place(n, x, y, s) { var f = fld(n); f.display = display.hidden; x = Math.round(x); y = Math.round(y); f.rect = [x, y + s, x + s, y]; f.display = display.visible; }   // rect: [left, top, right, bottom], whole points
```

Drag and drop (examples/f1_slider, examples/histogram). Use one invisible zone per value with `/AA /D`, `/E`
and `/U`, no `/A`, placed first. The knobs only display the value and take no events. A press on the track grabs
the knob there:

```js
function zDown(k, v) { drag = k; setVal(k, v); }      // mouse down: grab
function zEnter(k, v) { if (drag == k) setVal(k, v); } // button held: follow the pointer
function zUp() { drag = null; }                        // first mouse up (to the pressed zone): drop
```

Test it with `Sim.drag(start, end)` and `ChromePdf.drag(start, end)`. Do not give the knobs their own actions:
a knob with `/A` and `/E` kept getting the enter and mouse-up events after a click, and the value jumped back
(lint `LP014`).

Tolerant number input: accept `0,7` (`replace(",", ".")`), strip spaces, treat `""` and the prefill `"0."` as empty,
and show errors in a red text field rather than with `app.alert`.

## Debugging

- First, write a failing `Sim` test. `s.trace()` lists the actions that ran (`btnCheck:D`, `guess:V`,
  `btnCheck:A`); `s.warnings` flags covered clicks and unsafe moves.
- If only Chrome misbehaves, build a debug variant with a visible log field:
  `function lg(s){ LOG=(LOG+' '+s+'@'+(Date.now()%100000)).slice(-120); fld('dbg').value=LOG; }`
  Call it from every action and read the field with `crop`. Guessing without a log cost many rounds before.
- Write patches as script files that assert the old text exists before replacing it. Inline shell heredocs with
  nested quotes broke more than once.

More detail and evidence: [references/chrome-pdfium-quirks.md](references/chrome-pdfium-quirks.md).
