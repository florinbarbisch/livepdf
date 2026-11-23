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
| Edge, desktop | Adobe engine (since Edge 156) | yes | **all work** | Edge 158, real viewer on a hidden desktop: the `ChromePdf` test suite, plus every other example played |
| Firefox, desktop | pdf.js | yes | **broken display**: clicks and game logic work, but shown or moved fields are not drawn | Firefox 157 (Playwright build), headless, every example played; checked by hand in current Firefox: pump's text and button work, its bar does not move |
| Safari, macOS | PDFKit | **no** | a still page | Safari 17 on macOS Sonoma 14.6.1 (virtual machine): the probe stayed at "NO JS", clicks on Pump did nothing |
| Preview, macOS (the Mac's PDF app) | PDFKit | **no** | a still page | same machine, pump opened with "Open with Preview": clicks did nothing |
| Safari, iOS (and every iOS browser) | PDFKit | **no** | a still page | iOS Simulator (iPhone 17 Pro) on a GitHub-hosted Mac: the probe stayed at "NO JS" |
| Chrome on Android | hands the PDF to the Drive PDF viewer | **no** | a still page | Android 16 emulator (Chrome 133) on this PC: probe stayed at "NO JS", taps did nothing |
| Samsung Internet | not tested | | | needs a Play Store sign-in in the emulator |

Chromium-based desktop browsers that use PDFium (Opera, Brave, Vivaldi) should behave like Chrome, but they were
not tested. Adobe Acrobat Reader runs the full Acrobat JavaScript API, but it was not installed here.

Chrome's share is mostly Android phones. Treat the examples as **desktop Chrome and Edge** content and say so on
the page: "Open in Chrome or Edge on a computer."

## Edge (Adobe engine)

Headless Edge renders like Chrome (it looked like PDFium), so only a real window tests the Edge viewer. With
`LIVEPDF_HEADFUL=1`, `ChromePdf` starts the browser on a separate, invisible Windows desktop: the window never
appears on screen and never takes the keyboard focus (`LIVEPDF_VISIBLE=1` shows it instead).

What worked in Edge 158: the document script on open, timers, clicks (10 of 10, no lost first clicks), show and
hide, moving fields, drag and drop, typed input. All seven examples play correctly.

What Edge does differently from Chrome:

- **Clicks go to the field drawn on top** (the last in the field order), even one without actions, such as a
  label or a knob. Chrome gives them to the first one. `LivePdf.zone()` therefore writes every zone twice: first
  in the field order (for Chrome) and as `<name>~top` after every other field (for Edge), with the same
  actions. Lint `LP015` flags clickable fields that something later covers.
- **`rect` order.** A field moved with `rect = [left, bottom, right, top]` is not drawn. Use Acrobat's documented
  order `[left, top, right, bottom]`. Chrome accepts both, and both read the value back in Acrobat's order.
- **Whole points.** A field moved to fractional coordinates is not drawn. Round them with `Math.round()`.
- **Mouse up after a drag** goes only to the field under the pointer. Chrome sends it to the pressed field first.
  Handle the drop in the mouse-up action of every zone, as the F1 slider and the histogram do.

The simulator warns about the two `rect` rules, and the examples follow all four.

## Firefox (pdf.js)

What works: the document script, timers, clicks (like Edge, pdf.js picks the field drawn on top, so the zones'
top copies get them), and the game logic: the quiz scores, the reaction test times, the memory counts moves.
Typed text shows up, but Guess r read the typed guess as 0.00.

What breaks the display:

- **No `rect` changes:** fields do not move or resize.
- **Fields hidden in the file stay hidden** when a script shows them.
- **No enter or exit events**, so no hover and no drag.
- Invisible push buttons are drawn as pale highlight boxes.

- Text fields drawn over a colour bar disappeared (the histogram's dataset labels).

A PDF built for Firefox would need no moving fields, and pre-drawn states shown by changing values instead of
`display`. That is not what livepdf builds today.

## Safari and mobile

Playwright's WebKit build is not Safari and has no PDF viewer, so Safari was tested in macOS itself.

- **iOS Safari** (iOS Simulator): the probe PDF, whose open script replaces "NO JS", still showed "NO JS". The
  page is drawn, the script does not run.
- **macOS Safari** (Safari 17, macOS Sonoma 14.6.1 in a virtual machine, driven over VNC): the PDFs are drawn,
  but the probe stayed at "NO JS" and pump stayed at "level 0" after five clicks. Preview behaves the same.
  PDFKit also ignores the hidden flag: pump shows its Again button, which the file hides, on top of Pump.
  A first try on a GitHub-hosted Mac (macOS 26.7) drew every PDF blank, so it could not answer this.
- **Chrome on Android** (Android 16 emulator with Google Play, Chrome 133, on Windows; `adb` taps and
  screenshots): Chrome downloads the PDF and opens it in the Drive PDF viewer. The probe stayed at "NO JS" and
  taps did nothing. Newer Chrome versions have a built-in viewer; updating Chrome needs a Play Store sign-in.

Where the script does not run, the reader sees the page as built, with hidden fields shown (Safari, Preview).
Guess r looked complete; the quiz showed empty answer rows, because its script fills in the question. Drawing
the start state at build time helps there.

## How to rerun

```bash
uv run pytest -m chrome                                                          # Chrome, headless
LIVEPDF_CHROME="C:/Program Files (x86)/Microsoft/EdgeCore/<version>/msedge.exe" LIVEPDF_HEADFUL=1 uv run pytest -m chrome   # Edge, hidden desktop
```

Sources: [Statcounter browser market share](https://gs.statcounter.com/browser-market-share),
[Microsoft: PDF reader in Microsoft Edge](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-pdf).
