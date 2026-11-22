"""livepdf command line: inspect, lint and play interactive PDFs without a browser window.

    livepdf info game.pdf
    livepdf lint game.pdf
    livepdf sim game.pdf "fill guess 0.5" "click btnCheck" "get resRate" "eval hearts" "shot out.png"
    livepdf chrome game.pdf "fill guess 0.5" "click btnCheck" "wait 500" "ink resTrue" "crop resTrue out.png"

Each step prints one line, so a whole play-through costs a few lines of text.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys

from .inspect import load
from .lint import lint

SIM_STEPS = 'click NAME|X,Y · fill NAME TEXT [Enter|Tab] · type TEXT · key KEY · move X Y · wait MS · get NAME · ' \
            'eval JS · run JS · visible [PREFIX] · trace · shot PNG'
CHROME_STEPS = 'click NAME|X,Y · fill NAME TEXT [Enter|Tab] · type TEXT · key KEY · wait MS · color NAME · ' \
               'ink NAME · shot PNG · crop NAME PNG'


def _target(s: str):
    if ',' in s:
        x, y = s.split(',')
        return float(x), float(y)
    return s


def cmd_info(a) -> int:
    doc = load(a.pdf)
    print(f'{doc.path.name}: {doc.width:g} x {doc.height:g} pt, {len(doc.fields)} fields, '
          f'{len(doc.scripts)} document scripts ({sum(len(s) for _, s in doc.scripts)} chars), '
          f'NeedAppearances={doc.need_appearances}')
    for f in doc.fields:
        r = ' '.join(f'{v:.0f}' for v in f.rect)
        acts = ','.join(f.actions) or '-'
        val = f' = {f.value!r}' if f.value not in ('', 'Off', 'Yes') else ''
        print(f'  {f.name:14} {f.type:9} [{r}] {"hidden " if f.hidden else ""}{"ro " if f.readonly else ""}'
              f'actions:{acts}{val}')
    return 0


def cmd_lint(a) -> int:
    findings = lint(load(a.pdf), syntax=not a.no_syntax)
    for f in findings:
        print(f)
    errors = sum(f.level == 'error' for f in findings)
    print(f'{len(findings)} findings, {errors} errors')
    return 1 if errors else 0


def cmd_sim(a) -> int:
    from .sim import Sim, SimError
    s = Sim(a.pdf, seed=a.seed, strict=False, lost_clicks=a.lost_clicks)
    rc = 0
    try:
        for step in a.steps:
            op, *args = shlex.split(step)
            n_err, n_warn = len(s.errors), len(s.warnings)
            try:
                out = _sim_step(s, op, args)
            except SimError as e:
                out, rc = f'ERROR {e}', 1
            print(f'{step} -> {out}' if out is not None else step)
            for e in s.errors[n_err:]:
                print(f'  JS ERROR {e["where"]}: {e["message"]}')
                rc = 1
            for w in s.warnings[n_warn:]:
                print(f'  warning: {w}')
        for line in s.log:
            print(f'  log: {line}')
    finally:
        s.close()
    return rc


def _sim_step(s, op, args):
    if op == 'click':
        return f'hit {s.click(_target(args[0]))}'
    if op == 'fill':
        s.fill(args[0], args[1], args[2] if len(args) > 2 else None)
        return None
    if op == 'type':
        s.type(' '.join(args)); return None
    if op == 'key':
        s.key(args[0]); return None
    if op == 'move':
        return f'over {s.move(float(args[0]), float(args[1]))}'
    if op == 'wait':
        s.advance(float(args[0])); return None
    if op == 'get':
        f = s.get(args[0])
        return f'{f.value!r} {"visible" if f.visible else "hidden"} rect={[round(v, 1) for v in f.rect]}'
    if op == 'eval':
        return json.dumps(s.eval(' '.join(args)))
    if op == 'run':
        s.run(' '.join(args)); return None
    if op == 'visible':
        return ' '.join(s.visible_fields(args[0] if args else ''))
    if op == 'trace':
        return ' '.join(s.trace())
    if op == 'shot':
        return str(s.snapshot(args[0]))
    raise SystemExit(f'unknown sim step {op!r}; steps: {SIM_STEPS}')


def cmd_chrome(a) -> int:
    from .chrome import ChromePdf
    with ChromePdf(a.pdf, headful=a.headful) as c:
        for step in a.steps:
            op, *args = shlex.split(step)
            if op == 'click':
                c.click(_target(args[0])); out = None
            elif op == 'fill':
                c.fill(args[0], args[1], args[2] if len(args) > 2 else None); out = None
            elif op == 'type':
                c.type(' '.join(args)); out = None
            elif op == 'key':
                c.key(args[0]); out = None
            elif op == 'wait':
                c.wait(float(args[0])); out = None
            elif op == 'color':
                out = c.color(args[0])
            elif op == 'ink':
                out = f'{c.ink(args[0]):.3f}'
            elif op == 'shot':
                out = str(c.screenshot(args[0]))
            elif op == 'crop':
                out = str(c.crop(args[0], args[1]))
            else:
                raise SystemExit(f'unknown chrome step {op!r}; steps: {CHROME_STEPS}')
            print(f'{step} -> {out}' if out is not None else step)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog='livepdf', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('info', help='list fields, actions and scripts')
    s.add_argument('pdf')
    s.set_defaults(fn=cmd_info)
    s = sub.add_parser('lint', help='static checks (exit 1 on errors)')
    s.add_argument('pdf')
    s.add_argument('--no-syntax', action='store_true', help='skip the JavaScript syntax check (needs node)')
    s.set_defaults(fn=cmd_lint)
    s = sub.add_parser('sim', help=f'play in the JavaScript simulator. Steps: {SIM_STEPS}')
    s.add_argument('pdf')
    s.add_argument('steps', nargs='*')
    s.add_argument('--seed', type=int, default=1)
    s.add_argument('--lost-clicks', type=int, default=0, help='emulate Chrome ignoring the first N clicks')
    s.set_defaults(fn=cmd_sim)
    s = sub.add_parser('chrome', help=f'play in headless Chrome. Steps: {CHROME_STEPS}')
    s.add_argument('pdf')
    s.add_argument('steps', nargs='*')
    s.add_argument('--headful', action='store_true', help='show the browser window')
    s.set_defaults(fn=cmd_chrome)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == '__main__':
    sys.exit(main())
