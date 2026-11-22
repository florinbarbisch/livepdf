# livepdf API reference

## Build: `livepdf.LivePdf(width=960, height=540)`

The builder takes top-based coordinates: y counts down from the top edge. In JavaScript, `field.rect` uses PDF
coordinates (y up from the bottom). `g.y(top)` converts between the two.

| Call | Makes |
|---|---|
| `text(x, top, size, s, bold=False, color=INK)` | static text |
| `line(x1, t1, x2, t2, color, width)` / `rect(x, top, w, h, fill=, stroke=)` / `circle(cx, ctop, r)` / `raw(ops)` | static drawing |
| `text_field(name, x, top, w, h, value, size=, bold=, color=, align=0/1/2, readonly=True, max_len=, bg=, border=, hidden=, on_click=, V=..., K=..., ...)` | output label (read-only) or input |
| `push_button(name, x, top, w, h, label, fill=YELLOW, appearance=None, hidden=, readonly=, on_click=, D=..., ...)` | clickable button with its own look; do not move it |
| `zone(name, x, top, w, h, on_click=, D=, E=, ..., top_copy=True)` | invisible clickable area; also written as `<name>~top` after all fields (Edge clicks the top field, Chrome the first) |
| `color_bar(name, x, top, w, h, color, hidden=)` | filled rectangle that may move |
| `dot(name, cx, ctop, size=14, color=, hidden=)` | round marker that may move |
| `form_xobject(content, bbox, fonts=False)` | appearance stream (identical ones are shared) |
| `script(js, name=)` | document-level JavaScript, run on open |
| `save(path)` / `to_bytes()` | write the file |

Triggers: `on_click` becomes `/A`. Keywords `E X D U Fo Bl K F V C` become `/AA` entries. The annotation order is the
call order: later fields are drawn on top, but Chrome gives a click on overlapping fields to the first one.

## Inspect and lint

- `load(pdf) -> GameDoc`: `.fields` (name, type, rect, value, flags, hidden, actions …), `.scripts`, `.need_appearances`
- `lint(doc) -> [Finding]` with codes:

| Code | Check |
|---|---|
| LP000 | PDF syntax problem (unescaped bracket, broken object) |
| LP001 | no JS |
| LP002 | NeedAppearances |
| LP003 | syntax |
| LP004 | unknown field |
| LP005 | API missing in Chrome |
| LP006 | Python format leftovers |
| LP007 | undefined function in an action |
| LP008 | invisible button |
| LP009 | font missing in /DR |
| LP010 | mouse-up only |
| LP011 | hover only |
| LP012 | overlapping clickable fields (the first one gets the click) |
| LP013 | buttons taking turns on one spot with different actions |
| LP014 | enter plus activate on one field (events follow the clicked field) |
| LP015 | a clickable field covered by a later field: Edge gives the click to the cover |

## Simulate: `Sim(pdf, seed=1, lost_clicks=0, order='chrome', pace_ms=400, hold_ms=80, strict=True)`

- **Input:** `click(name | (x, y)) -> hit field`, `fill(name, text, commit=None|'Enter'|'Tab')`, `type(text)`,
  `key('Enter'|'Tab'|'Escape'|'Backspace'|'SelectAll')`, `move(x, y)`, `drag(start, end, steps=10) -> (pressed, released on)`,
  `focus(name)`, `blur()`
- **Time:** `advance(ms)` runs due `app.setInterval` and `app.setTimeOut` callbacks. Before every click and fill,
  `pace_ms` passes; the mouse button is held for `hold_ms`.
- **Read:** `get(name) -> FieldState(value, display, visible, rect, moves)`, `value(name)`, `visible(name)`,
  `visible_fields(prefix)`, `state()`, `eval(js)` (game globals), `run(js)`, `hit(x, y)`, `timers()`,
  `trace()` (actions run since the last call)
- **Diagnostics:** `errors` (JS exceptions; `strict` raises `SimError`), `warnings` (covered clicks, unsafe moves,
  unknown properties, Chrome-missing APIs), `log` (`console.println`, `app.alert`)
- `snapshot(png)`: approximate render of the current state (needs PyMuPDF)
- **Mocked API:**
  - `getField`, `display.*`, `color.*`
  - `app.alert`, `app.setInterval`, `app.clearInterval`, `app.setTimeOut`, `app.clearTimeOut`, `app.beep`
  - `util.printf`, `console.println`, `event`
  - Field properties: `value`, `valueAsString`, `display`, `hidden`, `rect`, `readonly`, `setFocus`,
    `isBoxChecked`, `checkThisBox`, colors as plain properties
  - `Date` and `Math.random` are deterministic.

## Real Chrome or Edge: `ChromePdf(pdf, headful=None, warmup_clicks=2, pace_ms=350, workdir=None)`

- `LIVEPDF_CHROME`: the browser (Chrome or `msedge.exe`). `LIVEPDF_HEADFUL=1`: a real window, started on a hidden
  Windows desktop so it never takes the focus (needed for Edge's real PDF engine). `LIVEPDF_VISIBLE=1`: show it.

- **Input:** `click(name | (x, y))`, `drag(start, end, steps=10)`, `fill(name, text, commit=)`, `type(text)`, `key(k)`, `wait(ms)`
- **Pixels:**
  - `color(name | rect)`: mean RGB, 0 to 255
  - `pixel(x, y)`
  - `ink(name, threshold=100)`: share of dark pixels, for "is there text or a dot"
  - `crop(name | rect, png, pad=6)`
  - `screenshot(png)`
- Every read takes a new screenshot unless you pass `fresh=False`.
- Each test takes about 4 s to open and about 0.5 s per click.
