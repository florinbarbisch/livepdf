# What the simulator models

`Sim` runs the PDF's JavaScript in Node and plays it in Chrome's event order.

- The Acrobat JavaScript API subset that games use:
  - `getField`, `display`, `color`
  - `app.setInterval` and `app.setTimeOut`
  - `app.alert`, `util.printf`, `console.println`, `event`
  - field `value`, `valueAsString`, `display`, `rect`, `setFocus`, check boxes
- Unknown field properties produce a warning.
- Chrome's click sequence:
  1. mouse move (enter, exit)
  2. mouse down
  3. commit and blur of the text field that had the focus (keystroke, validate, format)
  4. focus
  5. mouse up
  6. activate (`/A`)

  `order='acrobat'` commits before mouse down instead.
- Chrome's hit testing, measured in headless Chrome:
  - On overlapping fields, the first one in annotation order gets the click.
  - A field hidden by a script keeps the clicks on its spot while it has the focus.

  A warning names the field that really got the click.
- Chrome's drag: while the button is held, exit and enter go to the fields under the pointer; on release, mouse
  up goes to the pressed field first, then to the field under the pointer (`Sim.drag()`).
- PDFium's value coercion: `"0."` reads as the number `0`.
- Warnings for field moves that a viewer would render wrong: a custom appearance without `/MK`, a move while
  visible, a `rect` set bottom-first, or a `rect` with fractional points (Edge draws neither of the last two).
- `Date` and timers run on a virtual clock, and `Math.random` is seeded.

It does not model rendering (`Sim.snapshot()` draws an approximation with PyMuPDF), the caret position, or
Chrome's lost first clicks (`lost_clicks=1` emulates those). Other viewers' rules (see
[browser-support.md](browser-support.md)) show up only in a real browser.
