# Chrome / PDFium behavior: observations and evidence

These were observed while building interactive PDFs in Chrome on Windows, November 2026. Event timings come from
debug builds that logged every action into a visible text field. "Untested" marks claims that were never checked.

| # | Observation | Evidence | Consequence |
|---|---|---|---|
| 1 | The first one or two clicks after opening a PDF produce no events at all. | The debug log stayed empty for that click. These did not help: `setFocus()` on open, hovering first, waiting 6 s, a wake-up click (sometimes). | Footer hint for users; tests warm up with clicks on an empty spot. |
| 2 | Mouse up (`/AA /U`) arrives late, or at the field clicked before. | A stray mouse-up dropped a knob that had just been picked up. | Use `/AA /D` or `/A`. Lint `LP010`. |
| 3 | Drag works. While the button is held, exit and enter go to the fields under the pointer. On release, mouse up goes first to the pressed field, then to the field under the pointer. No `/A` fires unless the release is on the pressed field. | Debug log, headless Chrome, 2026-11-22, mouse moves sent with the button held: `z1E z1D z1X z2E … z6E z1U z6U`. A release off every zone sent only `z5U`. Hover after the drop worked. An earlier test said "no drag", but it moved the mouse without the button flag. | Drag and drop with zones that have `/AA /D`, `/E` and `/U`: grab at mouse down, follow on enter, drop on the first mouse up. `Sim.drag()` and `ChromePdf.drag()` model it. |
| 4 | Clicking a button while a text field has focus runs: button `D`, then the field's `K` and `V` (commit), then about 430 ms later the button's `A`. | Debug log timestamps. A 400 ms lock was too short. | Decide at mouse down; `Sim` uses this order. |
| 5 | A field hidden by a script keeps getting the clicks on its spot while it has the focus, if it was visible in the file. A click on empty page clears that. A field that was hidden in the file does not keep clicks. | Headless Chrome, 2026-11-22: Pump hid itself and showed Again on its spot; every click on Again went to the hidden Pump until a click beside it. The swap back (Again was hidden in the file) worked at once. This was also the cause of "New game does nothing". | Buttons that take turns on one spot get one handler that decides by game state. Lint `LP013`; `Sim` models it. |
| 6 | `field.value` returns numeric-looking text as a number (`"0."` → `0`). | An untouched input counted as a guess of 0.00. | Use `valueAsString`. `Sim` coerces the same way. |
| 7 | `field.rect = [...]` works and is fast (100 fields in 4 to 20 ms). | `recttest.py` | Dots and bars can move every round. |
| 8 | A moved field loses its custom `/AP`. Chrome repaints it from `/MK`: a push button with `/BG` becomes a filled rect, a check box with `/CA (l)` and `/ZaDb` becomes a circle. | Custom-AP dots went blank after a move. | Use `color_bar` and `dot` only. `Sim` warns. |
| 9 | A field moved while visible can leave a ghost at the old spot. | Visible leftovers. | Hide, set rect, show. `Sim` warns. |
| 10 | Chrome draws the regenerated circle at about 0.45 of the field size. | Dots shrank after the first move. | `DOT_SCALE = 0.45` |
| 11 | With `/NeedAppearances true`, Chrome draws its own look (square knob, lost button look). | Before and after comparison. | `false` plus own `/AP`. Lint `LP002`. |
| 12 | Overlapping visible fields: the **first** field in annotation order gets the click, although the last one is drawn on top. | Headless Chrome, 2026-11-22: two stacked buttons, only the first one's action ran. It also explains why a page-wide field placed first ate every click, and why a knob placed before the zones got the clicks. | Do not stack clickable fields; if you must, the first one decides. Lint `LP012`; `Sim` models it. Hover (`/E`) also does not reach a field under a visible one. |
| 13 | Toggling about 100 small segments per animation frame is slow (about 2 s for a large jump). | F1 slider v1 | One full pre-drawn bar per value; switch two fields per frame. |
| 14 | Thin lines can remain at the edges of hidden neighbors on repaint. | Visible hairlines. | Draw inside the BBox with about 2 pt inset. |
| 15 | `app.setInterval(code, 16)` works; the frame rate follows Chrome's repaint. | F1 slider easing | Eased timer, cleared when settled. |
| 16 | A newly opened PDF sometimes renders blank. | Seen in the browser tests. | Reload (`ChromePdf` retries once). |
| 17 | `global.setPersistent` is not expected to survive a reload in Chrome. | **Untested.** | Score in a form field plus Ctrl+S. |
| 18 | The headless Chrome viewer accepts DevTools mouse and keyboard input, and the page's JavaScript runs. Its accessibility tree does not expose field values. | `livepdf.chrome` spike, 2026-11-22 | Pixel checks in `ChromePdf`. |
| 19 | After a click (press and release) on a knob that had `/A`, `/AA /D` and `/AA /E`, Chrome sent the following enter events and the next mouse-up to that knob, wherever the pointer went. The zones under the pointer got no enter events. | Debug log, headless Chrome, 2026-11-22: `E50` for every move from 50 to 57, then `D57 U50 U57` on the drop click. | Knobs only display; zones take `/D`, `/E` and `/U` but no `/A`. Lint `LP014`. |
| 20 | `field.textColor = [...]` from JavaScript did not change the drawn text colour (set before or after the value). | Memory example: symbols stayed black. | One prepared field per colour, shown or hidden. |
| 21 | `field.rect` reads back in Acrobat's order `[left, top, right, bottom]` in Chrome and Edge. Edge does not draw a field set bottom-first; Chrome draws both orders. | Debug text in the Pump bar, Chrome 157 and Edge 158 (visible window), 2026-11-22: set `[25,135,99,169]`, read `[25,169,99,135]`. | Always set `[left, top, right, bottom]`. `Sim` warns about bottom-first rects. |
| 22 | Edge does not draw a field moved to fractional coordinates. | Pump bar with width `level * 3.7`: hidden in Edge, drawn after `Math.round`. | Round every coordinate. `Sim` warns. |
| 23 | After a drag, Edge sends mouse up only to the field under the pointer (Chrome: the pressed field first, then that one). | Debug log, Edge 158: `E D E2 U2`. | Handle the drop in the `/U` of every zone. |
| 24 | In a visible window on a scaled screen, screenshots are in device px but DevTools mouse events take CSS px. | 1.5x display: clicks landed 1.5x too far until `ChromePdf` divided by `devicePixelRatio`. | Fixed in `ChromePdf`; set `LIVEPDF_HEADFUL=1` for visible windows. |
| 25 | Firefox (pdf.js) gives a click to the field drawn on top, does not apply `rect` changes, does not show fields hidden in the file, and sends no enter events. | Playwright Firefox 157, every example played. | Firefox is not supported; see `docs/browser-support.md`. |

Other PDF tools:

- **MuPDF/PyMuPDF** does not run the JavaScript. It skips hidden widgets and shows only the initial state, so use it
  for static previews only. `livepdf.render` draws a simulated state on top of it.
- **PDFium's own test runner** (`pdfium_test --send-events`) can replay events against a V8-enabled PDFium build.
  It is the most exact engine, but V8-enabled builds are not available prebuilt, so `livepdf` drives an
  installed Chrome instead.
- **PowerPoint** cannot carry any of this: the PDF export writes no JavaScript, ActiveX sliders are blocked in
  Microsoft 365, and VBA needs macro trust settings changed.
