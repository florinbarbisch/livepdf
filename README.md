# livepdf

Build, lint and test interactive PDFs (games, quizzes, sliders, live charts and other teaching demos) that run in Chrome's built-in PDF viewer.

**Runs in desktop Chrome and Edge** (both tested). In Firefox the script runs but the page does not update
properly; iOS Safari and Android show a still page (details: [docs/browser-support.md](docs/browser-support.md)).

A PDF can carry form fields and JavaScript, and Chrome's viewer (PDFium) runs that script. Building such a file is
the easy part. Testing it usually means clicking through a browser by hand or taking screenshots. livepdf moves
most of that testing out of the browser:

| Layer | What it checks | Speed | Output |
|---|---|---|---|
| `livepdf lint` | field names used in scripts, undefined functions, JS syntax, covered buttons, Chrome-hostile patterns | under 1 s | text |
| `Sim` (Node) | game logic, played in Chrome's event order with a virtual clock | milliseconds per step | text |
| `ChromePdf` | the real Chrome PDF viewer, headless: input through DevTools, pixel checks by field name | about 4 s to open | numbers, plus PNG crops on failure |

`LivePdf` writes the PDF itself, with field types that survive Chrome's quirks (see
[skills/live-pdf/references/chrome-pdfium-quirks.md](skills/live-pdf/references/chrome-pdfium-quirks.md)).

## Install

```bash
pip install "livepdf[chrome] @ git+https://github.com/florinbarbisch/livepdf"   # pypdf is the only hard dependency
pip install -e .[chrome]                                                       # or from a checkout
```

The simulator needs Node 18 or later. The Chrome driver needs Node 22 or later, Google Chrome, and PyMuPDF; set
`LIVEPDF_CHROME` if Chrome is not found.

## Example

```python
from livepdf import LivePdf, Sim

g = LivePdf(420, 260)
g.text(24, 24, 22, 'Pump', bold=True)
g.color_bar('level', 25, 91, 1, 34, (0.2, 0.55, 0.95))      # may be moved by the script
g.text_field('status', 24, 140, 372, 22, 'level 0', size=14)
g.push_button('btnPump', 24, 180, 120, 40, 'Pump', on_click='pump();')
g.script(PUMP_JS)                    # the game logic; see examples/pump.py
g.save('pump.pdf')

with Sim('pump.pdf') as s:
    s.click('btnPump')
    s.advance(500)                       # virtual time: app.setInterval callbacks run
    assert s.value('status') == 'level 5'
    print(s.trace(), s.warnings)
```

Examples (tests in [tests/](tests)):

| Example | Shows |
|---|---|
| [examples/pump.py](examples/pump.py) | the smallest game: a timer, a moving bar, two buttons taking turns on one spot |
| [examples/guess_r/](examples/guess_r) | a full game: 100 moving dots, text input, a residual chart, hearts, coins and streaks. Standalone repo with more tests: [guess-r-pdf](../guess-r-pdf) |
| [examples/f1_slider/](examples/f1_slider) | drag and drop sliders; animated bars with an eased timer |
| [examples/reaction/](examples/reaction) | timing with `app.setTimeOut` and mouse-down events; one pad as start button, target and display |
| [examples/quiz/](examples/quiz) | multiple choice from a JSON file; buttons whose caption changes (zone + bar + text) |
| [examples/memory/](examples/memory) | 16 cards with layered faces, a turn-back timer, a game clock, prepared coloured symbols |
| [examples/histogram/](examples/histogram) | a live chart: drag the knob to choose 2 to 60 bins for five real distributions; Sturges and Freedman-Diaconis marks |

The histogram data are small demo series (CO2, temperature and light in classrooms, a simulated hydrogen feed-in,
one day of solar power), stored in [datasets.json](examples/histogram/datasets.json).

From the shell, each step prints one line:

```text
$ livepdf sim pump.pdf "click btnPump" "wait 500" "get status" "eval level"
click btnPump -> hit btnPump
wait 500
get status -> 'level 5' visible rect=[24, 98, 396, 120]
eval level -> 5
```

```bash
livepdf chrome pump.pdf "click btnPump" "wait 200" "ink status" "crop status out/status.png"
```

## Docs

- [docs/simulator.md](docs/simulator.md): what `Sim` models, and what it does not
- [docs/browser-support.md](docs/browser-support.md): which browsers run these PDFs, and how that was tested
- [skills/live-pdf/references/chrome-pdfium-quirks.md](skills/live-pdf/references/chrome-pdfium-quirks.md): measured
  viewer behaviour

## Claude Code skill

[skills/live-pdf](skills/live-pdf) is an agent skill: a workflow, the rules that decide what works in Chrome, and
proven interaction patterns. To use it, copy or link the folder into `~/.claude/skills/`.

## Development

```bash
uv sync
uv run pytest              # the Chrome test is skipped when Chrome or Node is missing
```

## License

MIT
