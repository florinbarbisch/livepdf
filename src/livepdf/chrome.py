"""Smoke-test an interactive PDF in the real Chrome PDF viewer (PDFium), headless, with pixel checks instead of screenshots.

    with ChromePdf('game.pdf') as c:
        c.fill('guess', '0.5')
        c.click('btnCheck')
        c.wait(500)
        assert c.color('btnNext') == pytest.approx(YELLOW_255, abs=30)   # mean colour of the field's area
        c.crop('resRate', 'out/rate.png')                                 # look at it only if a check fails

Input goes through the DevTools protocol to Chrome's own viewer, so PDFium runs the JavaScript exactly as for a
user. Chrome does not expose field values, so checks are on pixels: ``color``, ``pixel``, ``changed`` and
``crop`` (all by field name or PDF rect). Coordinates are calibrated from a screenshot after opening.

Needs Chrome (or Chromium/Edge: set ``LIVEPDF_CHROME``), Node 22+ and PyMuPDF.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .inspect import GameDoc, load
from .sim import node_exe

DRIVER = Path(__file__).with_name('js') / 'chrome.mjs'
SCALE = 4 / 3          # zoom 100 % at 96 dpi: 1 pt = 4/3 px


def find_chrome() -> str:
    env = os.environ.get('LIVEPDF_CHROME')
    if env:
        return env
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ]
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        if (p := shutil.which(name)):
            candidates.append(p)
    for c in candidates:
        if c and Path(c).exists():
            return c
    raise RuntimeError('Chrome not found; set LIVEPDF_CHROME to the browser executable')


Rect = tuple[float, float, float, float]


class ChromePdf:
    def __init__(self, pdf: str | Path, *, headful: bool = False, warmup_clicks: int = 2, open_wait_ms: int = 2500,
                 hold_ms: int = 80, pace_ms: int = 350, workdir: str | Path | None = None):
        """Open ``pdf`` in a fresh headless Chrome.

        ``warmup_clicks``: Chrome ignores the first one or two clicks after a PDF opens, so this many clicks go to
        an empty spot of the page first. ``pace_ms``: pause after every click/fill (lets PDFium repaint, and keeps
        double-click guards in the game from firing).
        """
        self.doc: GameDoc = load(pdf)
        self.pdf = Path(pdf).resolve()
        self.hold_ms, self.pace_ms = hold_ms, pace_ms
        self.dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix='livepdf-'))
        self.dir.mkdir(parents=True, exist_ok=True)
        self._n = 0
        self._last: Path | None = None
        w, h = int(self.doc.width * SCALE) + 80, int(self.doc.height * SCALE) + 80
        launch = {'chrome': find_chrome(), 'width': w, 'height': h, 'headful': headful}
        self._p = subprocess.Popen([node_exe(), str(DRIVER), json.dumps(launch)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1)
        self._read()                               # 'ready'
        url = self.pdf.as_uri() + '#toolbar=0&navpanes=0&zoom=100'
        self._call('open', url=url, waitMs=open_wait_ms)
        if not self._calibrate():                  # Chrome sometimes shows a blank page on first open
            self._call('open', url=self.pdf.as_uri() + '?reload=1#toolbar=0&navpanes=0&zoom=100', waitMs=open_wait_ms)
            if not self._calibrate():
                raise RuntimeError(f'Chrome did not render the PDF; see {self._last}')
        for _ in range(warmup_clicks):
            x, y = self._blank_point()
            self._call('click', **self._px(x, y), holdMs=hold_ms)
            self._call('wait', ms=250)

    # ---------- plumbing ----------
    def _read(self):
        line = self._p.stdout.readline()
        if not line:
            raise RuntimeError(f'Chrome driver exited: {self._p.stderr.read()}')
        r = json.loads(line)
        if not r['ok']:
            raise RuntimeError(r['error'])
        return r['result']

    def _call(self, cmd: str, **kw):
        self._p.stdin.write(json.dumps({'cmd': cmd, **kw}) + '\n')
        self._p.stdin.flush()
        return self._read()

    def close(self) -> None:
        if self._p.poll() is None:
            self._p.stdin.close()
            try:
                self._p.wait(10)
            except subprocess.TimeoutExpired:
                self._p.kill()

    def __enter__(self) -> 'ChromePdf':
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- coordinates ----------
    def _calibrate(self) -> bool:
        """Find the page in a screenshot: its left/top edge in px and the scale (px per pt)."""
        import pymupdf
        pix = pymupdf.Pixmap(str(self.screenshot()))
        W, H = pix.width, pix.height
        bg = pix.pixel(1, H - 2)
        far = lambda p: sum(abs(a - b) for a, b in zip(p[:3], bg[:3])) > 40
        mid_y, mid_x = H // 2, W // 2
        xs = [x for x in range(W) if far(pix.pixel(x, mid_y))]
        ys = [y for y in range(H) if far(pix.pixel(mid_x, y))]
        if len(xs) < W * 0.3 or not ys:
            return False
        self.x0, self.y0 = xs[0], ys[0]
        self.scale = (xs[-1] - xs[0] + 1) / self.doc.width
        return True

    def _px(self, x: float, y: float) -> dict:
        """PDF point (bottom-left origin) to screen px."""
        return {'x': self.x0 + x * self.scale, 'y': self.y0 + (self.doc.height - y) * self.scale}

    def _rect(self, target: str | Rect) -> Rect:
        return tuple(self.doc.field(target).rect) if isinstance(target, str) else target

    def _blank_point(self) -> tuple[float, float]:
        rects = [f.rect for f in self.doc.fields]
        W, H = self.doc.width, self.doc.height
        for fy in (0.02, 0.98, 0.5):
            for fx in (0.02, 0.98, 0.5, 0.25, 0.75):
                x, y = W * fx, H * fy
                if not any(r[0] - 2 <= x <= r[2] + 2 and r[1] - 2 <= y <= r[3] + 2 for r in rects):
                    return x, y
        return 2, 2

    # ---------- input ----------
    def click(self, target: str | tuple[float, float], hold_ms: int | None = None) -> None:
        """Click a field (at its centre) or a PDF point. Chrome decides which field really gets it."""
        if isinstance(target, str):
            r = self._rect(target)
            x, y = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        else:
            x, y = target
        self._call('click', **self._px(x, y), holdMs=self.hold_ms if hold_ms is None else hold_ms)
        self._pos = (x, y)
        self.wait(self.pace_ms)

    def move(self, target: str | tuple[float, float], steps: int = 1) -> None:
        """Move the mouse to a field's centre or a PDF point without clicking (fires enter/exit actions).
        ``steps`` > 1 moves in a straight line from the last position, like a hand would."""
        if isinstance(target, str):
            r = self._rect(target)
            x, y = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        else:
            x, y = target
        x0, y0 = getattr(self, '_pos', (x, y))
        for i in range(1, steps + 1):
            px = self._px(x0 + (x - x0) * i / steps, y0 + (y - y0) * i / steps)
            self._call('mouse', type='mouseMoved', **px)
            self._call('wait', ms=16)
        self._pos = (x, y)

    def drag(self, start: str | tuple[float, float], end: str | tuple[float, float], steps: int = 10,
             step_ms: int = 16) -> None:
        """Press the left button at ``start``, move to ``end`` with the button held, release there."""
        a, b = (self._centre(t) for t in (start, end))
        self._call('mouse', type='mouseMoved', **self._px(*a))
        self._call('wait', ms=40)
        self._call('mouse', type='mousePressed', **self._px(*a))
        for i in range(1, steps + 1):
            self._call('wait', ms=step_ms)
            px = self._px(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
            self._call('mouse', type='mouseMoved', button='left', buttons=1, **px)
        self._call('wait', ms=step_ms)
        self._call('mouse', type='mouseReleased', button='left', buttons=0, **self._px(*b))
        self._pos = b
        self.wait(self.pace_ms)

    def _centre(self, target: str | tuple[float, float]) -> tuple[float, float]:
        if isinstance(target, str):
            r = self._rect(target)
            return (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        return target

    def fill(self, field: str, text: str, commit: str | None = None) -> None:
        """Click a text field, select all, type. ``commit='Enter'`` commits right away."""
        self.click(field)
        self._call('key', key='SelectAll')
        self._call('text', text=text)
        if commit:
            self.key(commit)
        self.wait(self.pace_ms)

    def type(self, text: str) -> None:
        self._call('text', text=text)

    def key(self, key: str) -> None:
        """Enter, Tab, Escape, Backspace, End, Home, SelectAll."""
        self._call('key', key=key)

    def wait(self, ms: float) -> None:
        if ms > 0:
            self._call('wait', ms=ms)

    # ---------- output ----------
    def screenshot(self, path: str | Path | None = None) -> Path:
        if path is None:
            self._n += 1
            path = self.dir / f'shot{self._n:03d}.png'
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._call('shot', path=str(path))
        self._last = path
        return path

    def _pixmap(self, fresh: bool = True):
        import pymupdf
        return pymupdf.Pixmap(str(self.screenshot() if fresh or self._last is None else self._last))

    def _box(self, target: str | Rect, inset: float = 0) -> tuple[int, int, int, int]:
        x0, y0, x1, y1 = self._rect(target)
        a, b = self._px(x0 + inset, y1 - inset), self._px(x1 - inset, y0 + inset)
        return int(a['x']), int(a['y']), int(b['x']), int(b['y'])

    def color(self, target: str | Rect, inset: float = 2, fresh: bool = True) -> tuple[float, float, float]:
        """Mean RGB (0-255) over a field's area (or a PDF rect), from a new screenshot unless ``fresh=False``."""
        pix = self._pixmap(fresh)
        x0, y0, x1, y1 = self._box(target, inset)
        step = max(1, (x1 - x0) // 40)
        acc, n = [0.0, 0.0, 0.0], 0
        for y in range(max(0, y0), min(pix.height, y1 + 1), step):
            for x in range(max(0, x0), min(pix.width, x1 + 1), step):
                p = pix.pixel(x, y)
                acc[0] += p[0]; acc[1] += p[1]; acc[2] += p[2]; n += 1
        return tuple(round(a / max(n, 1), 1) for a in acc)

    def pixel(self, x: float, y: float, fresh: bool = True) -> tuple[int, int, int]:
        p = self._px(x, y)
        return self._pixmap(fresh).pixel(int(p['x']), int(p['y']))[:3]

    def ink(self, target: str | Rect, fresh: bool = True, threshold: int = 100) -> float:
        """Share (0..1) of dark pixels in the area: tells text or dots from empty background."""
        pix = self._pixmap(fresh)
        x0, y0, x1, y1 = self._box(target)
        dark = tot = 0
        for y in range(max(0, y0), min(pix.height, y1 + 1)):
            for x in range(max(0, x0), min(pix.width, x1 + 1)):
                p = pix.pixel(x, y)
                tot += 1
                dark += (p[0] + p[1] + p[2]) / 3 < threshold
        return dark / max(tot, 1)

    def crop(self, target: str | Rect, path: str | Path, pad: float = 6, fresh: bool = True) -> Path:
        """Save the area of a field (or PDF rect) plus ``pad`` pt as PNG: small images keep reviews cheap."""
        import pymupdf
        pix = self._pixmap(fresh)
        x0, y0, x1, y1 = self._rect(target)
        a, b = self._px(x0 - pad, y1 + pad), self._px(x1 + pad, y0 - pad)
        clip = pymupdf.IRect(max(0, int(a['x'])), max(0, int(a['y'])), min(pix.width, int(b['x'])), min(pix.height, int(b['y'])))
        out = pymupdf.Pixmap(pix.colorspace, clip, pix.alpha)
        out.copy(pix, clip)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        out.save(str(path))
        return path
