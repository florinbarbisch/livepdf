# Browser support

A livepdf PDF needs a viewer that runs PDF JavaScript (AcroForm actions and document scripts). Most browsers
show the page without running the script. Measured on Windows 11, 2026-11-22.

## Which browsers were tested

The five most used browsers, by Statcounter's worldwide share for September 2026 (all platforms), cover 95.8 %
of users: Chrome 66.4 %, Safari 18.3 %, Edge 6.0 %, Firefox 2.8 %, Samsung Internet 2.3 %. They use four PDF
engines:

| Browser | PDF engine | Runs the script | livepdf examples | How it was tested |
|---|---|---|---|---|
| Chrome, desktop | PDFium | yes | **all work** | Chrome 157, headless and in a visible window: the `ChromePdf` test suite |
| Edge, desktop | Adobe engine (since Edge 156) | yes | **probably work, not fully verified** | Edge 158, visible window: feature probes passed. The example suite was not finished (the screen locked) |
| Firefox, desktop | pdf.js | partly | **broken** | Firefox 157 (Playwright build), headless, every example played |
| Safari (macOS, iOS), and every browser on iOS | PDFKit | not expected | not supported: a still page | not tested (no Apple device here) |
| Chrome on Android, Samsung Internet | the system's PDF viewer, or a download | not expected | not supported | not tested |

Chromium-based desktop browsers that use PDFium (Opera, Brave, Vivaldi) should behave like Chrome, but they were
not tested. Adobe Acrobat Reader runs the full Acrobat JavaScript API, but it was not installed here.

Chrome's share is mostly Android phones. Treat the examples as **desktop Chrome and Edge** content and say so on
the page: "Open in Chrome or Edge on a computer."

## Edge (Adobe engine)

Headless Edge renders like Chrome (it looked like PDFium), so only a visible window tests the real Edge viewer:
`LIVEPDF_CHROME=<path to msedge.exe> LIVEPDF_HEADFUL=1 pytest -m chrome`. A visible window paints only while
the desktop is unlocked.

What worked in Edge 158:

- the document script on open, `app.setInterval`, button clicks (10 of 10, no lost first clicks)
- show and hide (`display`), and moving fields with `rect`
- a drag: enter events go to the fields under the pointer while the button is held

What Edge does differently from Chrome:

- **`rect` order.** A field moved with `rect = [left, bottom, right, top]` is not drawn. Use Acrobat's documented
  order `[left, top, right, bottom]`. Chrome accepts both, and both read the value back in Acrobat's order.
- **Whole points.** A field moved to fractional coordinates is not drawn. Round them with `Math.round()`.
- **Mouse up after a drag** goes only to the field under the pointer. Chrome sends it to the pressed field first.
  Handle the drop in the mouse-up action of every zone, as the F1 slider and the histogram do.

The simulator warns about the first two, and the examples follow all three.

## Firefox (pdf.js)

What works: the document script, timers, button clicks, changing field values. Typed text shows up, but Guess r
read the typed guess as 0.00.

What breaks the examples:

- **Clicks go to the field drawn on top** (the last one in the annotation order). Chrome gives them to the first
  one. The examples put click zones first and labels on top of them, so in Firefox the labels take the clicks.
- **No `rect` changes:** fields do not move or resize.
- **Fields hidden in the file stay hidden** when a script shows them.
- **No enter or exit events**, so no hover and no drag.
- Invisible push buttons are drawn as pale highlight boxes.

A PDF built for Firefox would need click zones with nothing on top, no moving fields, and pre-drawn states
shown by changing values instead of `display`. That is not what livepdf builds today.

## How to rerun

```bash
uv run pytest -m chrome                                                          # Chrome, headless
LIVEPDF_CHROME="C:/Program Files (x86)/Microsoft/EdgeCore/<version>/msedge.exe" LIVEPDF_HEADFUL=1 uv run pytest -m chrome   # Edge
```

Sources: [Statcounter browser market share](https://gs.statcounter.com/browser-market-share),
[Microsoft: PDF reader in Microsoft Edge](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-pdf).
