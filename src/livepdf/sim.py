"""Run an interactive PDF's JavaScript headless and drive it like a user, with plain-text results.

    with Sim('game.pdf', seed=1) as s:
        s.fill('guess', '0.5')
        s.click('btnCheck')
        assert s.value('resRate') == 'Very good'
        assert s.eval('hearts') == 3

The JavaScript runs in Node (``node`` must be on PATH, version 18 or later) against a mock of the Acrobat API
subset that Chrome's PDF viewer implements. Clicks follow Chrome's order: mouse move (enter/exit), mouse down (``/AA /D``), then
the previously focused text field commits (keystroke, validate, format) and blurs, the clicked field gets the
focus, ``hold_ms`` of virtual time passes, mouse up, activate (``/A``). Hit testing follows Chrome: on overlapping fields the first in
annotation order wins, and a field hidden by a script keeps the clicks on its spot while it has the focus.
``order='acrobat'`` commits and focuses before mouse down and hits the topmost visible field instead (an
assumption; Acrobat is untested). ``Date`` and timers use a virtual clock that only moves on ``advance()`` and during a
click; ``Math.random`` is seeded. Before every click
and fill, ``pace_ms`` (default 400) of virtual time passes, like a person between clicks; set it to 0 to test
double-click guards.

What it does not model: rendering (see :mod:`livepdf.render` and :mod:`livepdf.chrome`), Chrome losing the
first click after opening (``lost_clicks=1`` emulates it), late or misrouted mouse-up events, caret position.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .inspect import GameDoc, load

RUNTIME = Path(__file__).with_name('js') / 'runtime.mjs'


class SimError(AssertionError):
    """A script threw, or the simulator rejected a command."""


@dataclass
class FieldState:
    name: str
    type: str
    value: str
    display: int
    visible: bool
    rect: list[float]
    moves: int
    props: dict


def node_exe() -> str:
    exe = shutil.which('node')
    if not exe:
        raise RuntimeError('livepdf.sim needs Node.js (node) on PATH')
    return exe


class Sim:
    def __init__(self, pdf: str | Path | GameDoc, *, seed: int = 1, lost_clicks: int = 0, numeric_values: bool = True,
                 strict: bool = True, start_time: int | None = None, hold_ms: int = 80, pace_ms: int = 400,
                 order: str = 'chrome'):
        """``strict``: raise :class:`SimError` as soon as a script throws (otherwise collect them in ``errors``)."""
        self.doc = pdf if isinstance(pdf, GameDoc) else load(pdf)
        self.strict, self.hold_ms, self.pace_ms = strict, hold_ms, pace_ms
        self.errors: list[dict] = []
        self.warnings: list[str] = []
        self.log: list[str] = []
        self._p = subprocess.Popen([node_exe(), str(RUNTIME)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1)
        if order not in ('chrome', 'acrobat'):
            raise ValueError("order must be 'chrome' or 'acrobat'")
        opts = {'seed': seed, 'lostClicks': lost_clicks, 'numericValues': numeric_values, 'order': order}
        if start_time is not None:
            opts['startTime'] = start_time
        self._call('load', spec={**self.doc.to_json(), 'options': opts})

    # ---------- plumbing ----------
    def _call(self, cmd: str, **kw):
        if self._p.poll() is not None:
            raise SimError(f'simulator exited: {self._p.stderr.read()}')
        self._p.stdin.write(json.dumps({'cmd': cmd, **kw}) + '\n')
        self._p.stdin.flush()
        line = self._p.stdout.readline()
        if not line:
            raise SimError(f'simulator exited: {self._p.stderr.read()}')
        r = json.loads(line)
        self.log += r.get('log', [])
        self.warnings += r.get('warnings', [])
        self.errors += r.get('errors', [])
        if not r['ok']:
            raise SimError(r['error'])
        if self.strict and r.get('errors'):
            e = r['errors'][0]
            raise SimError(f"JavaScript error in {e['where']}: {e['message']}")
        return r['result']

    def _pause(self) -> None:
        if self.pace_ms:
            self._call('advance', ms=self.pace_ms)

    def close(self) -> None:
        if self._p.poll() is None:
            self._p.stdin.close()
            self._p.wait(5)

    def __enter__(self) -> 'Sim':
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------- input ----------
    def click(self, target: str | tuple[float, float], hold_ms: int | None = None) -> str | None:
        """Click a field by name (at its centre) or at PDF point ``(x, y)``. Returns the field that was hit.

        Clicking a field that is hidden or covered hits whatever is really there, as in Chrome, and adds a warning.
        """
        t = list(target) if isinstance(target, tuple) else target
        self._pause()
        return self._call('click', target=t, holdMs=self.hold_ms if hold_ms is None else hold_ms)['hit']

    def drag(self, start: str | tuple[float, float], end: str | tuple[float, float], steps: int = 10,
             step_ms: int = 16) -> tuple[str | None, str | None]:
        """Press at ``start`` (field name or PDF point), move to ``end`` with the button held, release there.
        Returns (pressed field, field under the pointer at release). Events follow Chrome's drag order."""
        t = [list(x) if isinstance(x, tuple) else x for x in (start, end)]
        self._pause()
        r = self._call('drag', start=t[0], end=t[1], steps=steps, stepMs=step_ms)
        return r['hit'], r.get('end')

    def move(self, x: float, y: float) -> str | None:
        """Move the mouse (fires exit/enter actions). Returns the field under the pointer."""
        return self._call('move', x=x, y=y)['hit']

    def type(self, text: str) -> None:
        """Type into the focused text field (keystroke actions run per character; not committed yet)."""
        self._call('type', text=text)

    def key(self, key: str) -> None:
        """``Enter`` (commit), ``Tab`` (commit and blur), ``Escape``, ``Backspace``, ``SelectAll``."""
        self._call('key', key=key)

    def fill(self, field: str, text: str, commit: str | None = None) -> None:
        """Click a text field, select all, type ``text``. ``commit='Enter'`` or ``'Tab'`` commits right away;
        otherwise the value is committed by the next click elsewhere (as in Chrome)."""
        self._pause()
        self._call('fill', target=field, text=text, holdMs=self.hold_ms)
        if commit:
            self.key(commit)

    def focus(self, field: str) -> None:
        self._call('focus', target=field)

    def blur(self) -> None:
        self._call('blur')

    def advance(self, ms: float) -> None:
        """Let ``ms`` of virtual time pass; due ``app.setInterval`` / ``app.setTimeOut`` callbacks run in order."""
        self._call('advance', ms=ms)

    # ---------- inspection ----------
    def get(self, name: str) -> FieldState:
        return FieldState(**self._call('get', name=name))

    def value(self, name: str):
        return self.get(name).value

    def visible(self, name: str) -> bool:
        return self.get(name).visible

    def state(self) -> dict[str, FieldState]:
        return {k: FieldState(**v) for k, v in self._call('state').items()}

    def eval(self, js: str):
        """Evaluate an expression in the document scope (game globals are visible), JSON round-tripped."""
        return self._call('eval', js=js)

    def run(self, js: str) -> None:
        """Run statements in the document scope, e.g. to set up a game state for a test."""
        self._call('run', js=js)

    def hit(self, x: float, y: float) -> str | None:
        """Name of the field a click at PDF point (x, y) would reach."""
        return self._call('hit', x=x, y=y)

    def timers(self) -> list[dict]:
        return self._call('timers')

    def trace(self) -> list[str]:
        """Actions that ran since the last call, as ``field:trigger`` (e.g. ``guess:V``, ``btnCheck:A``)."""
        return self._call('trace')

    def visible_fields(self, prefix: str = '') -> list[str]:
        return [n for n, f in self.state().items() if f.visible and n.startswith(prefix)]

    def snapshot(self, out_png: str | Path, dpi: int = 96) -> Path:
        """Render the current state to PNG (approximate; see :mod:`livepdf.render`)."""
        from .render import render_state
        return render_state(self.doc.path, self.state(), out_png, dpi=dpi)


def syntax_errors(doc: GameDoc) -> list[dict]:
    """JavaScript syntax errors in document scripts and field actions (``where``, ``message``)."""
    p = subprocess.run([node_exe(), str(RUNTIME)], input=json.dumps({'cmd': 'syntax', 'spec': doc.to_json()}) + '\n',
                       capture_output=True, text=True, encoding='utf-8', timeout=60)
    return json.loads(p.stdout.splitlines()[0])['result']
