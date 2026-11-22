"""Every example builds, lints clean and plays correctly in the simulator."""
import runpy
from pathlib import Path

import pytest

from livepdf import Sim, lint, load

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


@pytest.fixture(scope='module')
def build(tmp_path_factory):
    out = tmp_path_factory.mktemp('examples')
    cache = {}

    def _build(name):
        if name not in cache:
            g = runpy.run_path(str(EXAMPLES / name / 'build.py'))['g']
            cache[name] = g.save(out / f'{name}.pdf')
        return cache[name]
    return _build


@pytest.mark.parametrize('name', ['guess_r', 'f1_slider', 'reaction', 'quiz', 'memory', 'histogram'])
def test_lints_clean(build, name):
    assert [str(f) for f in lint(load(build(name)))] == []


def test_guess_r(build):
    with Sim(build('guess_r'), seed=2) as s:
        r = s.eval('cur')
        s.fill('guess', f'{r:.2f}')
        s.click('btnCheck')
        assert s.value('resRate') == 'Perfect! +1 heart' and s.eval('coins') == 5
        s.click('btnNext')
        assert s.value('resTrue') == '' and s.visible('btnCheck')


def test_f1_drag_and_drop(build):
    with Sim(build('f1_slider')) as s:
        assert s.drag('kR_50', 'zR_57') == ('zR_50', 'zR_57')    # the knob only displays; the zone under it is pressed
        assert s.eval('[drag, val.R]') == [None, 57]
        s.advance(1500)                                          # the bars ease to their targets
        assert s.value('vF') == '73 %' and s.value('vA') == '79 %' and s.visible('bF_73')
        assert s.visible('kR_57') and not s.visible('kR_50')
        s.move(300, 364)                                         # dropped: hovering changes nothing
        assert s.eval('val.R') == 57


def test_f1_release_off_the_track_keeps_the_last_value(build):
    with Sim(build('f1_slider')) as s:
        s.drag('zR_50', (532, 450))                              # ends far above the slider
        assert s.eval('drag') is None and 50 < s.eval('val.R') <= 57


def test_f1_press_on_the_track_jumps_there(build):
    with Sim(build('f1_slider')) as s:
        s.click('zR_80')
        assert s.eval('[drag, val.R]') == [None, 80]


def test_reaction_timing_and_early_click(build):
    with Sim(build('reaction'), pace_ms=0, hold_ms=0) as s:
        s.click('pad')
        assert s.eval('state') == 'wait' and s.visible('padWait')
        s.click('pad')                               # too early
        assert s.value('padText') == 'Too early!' and s.timers() == []
        for i in range(5):
            s.click('pad')
            due = s.timers()[0]['next'] - s.eval('new Date().getTime()')
            assert 1500 <= due <= 4000                   # the random wait
            s.advance(due)
            assert s.visible('padGo')
            s.advance(200 + 10 * i)
            s.click('pad')
        assert s.eval('times') == [200, 210, 220, 230, 240]
        assert s.value('padText') == '220 ms average' and s.value('best') == '220 ms'
        assert s.value('try4') == '5.  240 ms'


def test_quiz_full_round_and_restart(build):
    with Sim(build('quiz')) as s:
        n = s.eval('QUESTIONS.length')
        s.click('nextZ')                             # nothing to go on to before answering
        assert s.eval('cur') == 0
        for i in range(n):
            ok = s.eval(f'QUESTIONS[{i}].ok')
            s.click(f'aZ{(ok + 1) % 4 if i == 0 else ok}')     # first one wrong, the rest right
            s.click(f'aZ{ok}')                       # a second answer is ignored
            s.click('nextZ')
        assert s.value('q1') == f'You got {n - 1} of {n} right.'
        assert not s.visible('a0') and s.value('nextTxt') == 'Play again'
        s.click('nextZ')
        assert s.eval('[cur, score, state]') == [0, 0, 'ask'] and s.visible('a0')


def test_quiz_marks_right_and_wrong(build):
    with Sim(build('quiz')) as s:
        ok = s.eval('QUESTIONS[0].ok')
        wrong = (ok + 1) % 4
        s.click(f'aZ{wrong}')
        assert s.visible(f'aOk{ok}') and s.visible(f'aBad{wrong}')
        assert s.value('fb') == f'Not quite: it is {"ABCD"[ok]}.'


def test_memory_solve_and_best(build):
    with Sim(build('memory'), seed=5) as s:
        deck = s.eval('deck')
        first = deck.index(0)
        other = next(i for i, p in enumerate(deck) if p != 0)
        s.click(f'c{first}')
        s.click(f'c{other}')                         # a miss
        assert s.visible(f'sym{other}_{deck[other]}') and not s.visible(f'sym{other}_{(deck[other] + 1) % 8}')
        s.advance(1000)
        assert s.visible(f'back{first}') and s.visible(f'back{other}')
        for p in range(8):
            a, b = [i for i, q in enumerate(deck) if q == p]
            s.click(f'c{a}')
            s.click(f'c{b}')
            assert s.visible(f'done{a}') and s.visible(f'done{b}')
        assert s.eval('[moves, pairs]') == [9, 8]
        assert s.value('msg') == 'New best! 9 moves.' and s.value('best').startswith('9 moves')
        assert s.timers() == []                      # the clock stopped
        s.click('newZ')
        assert s.eval('[moves, pairs]') == [0, 0] and all(s.visible(f'back{i}') for i in range(16))


def test_memory_next_click_turns_a_miss_back(build):
    with Sim(build('memory'), seed=5) as s:
        deck = s.eval('deck')
        a = 0
        b = next(i for i in range(1, 16) if deck[i] != deck[0])
        c = next(i for i in range(1, 16) if i != b and deck[i] not in (deck[0], deck[b]))
        s.click(f'c{a}')
        s.click(f'c{b}')
        s.click(f'c{c}')                             # no waiting for the timer
        assert s.visible(f'back{a}') and s.visible(f'back{b}') and s.visible(f'face{c}')
        assert s.eval('open') == [c]


def _counts_from_bars(s, k):
    ymax, ch = int(s.value('ymax')), s.eval('CFG.CH')
    total = 0
    for i in range(k):
        f = s.get(f'bar{i}')
        if f.visible:
            total += round((f.rect[3] - f.rect[1]) / ch * ymax)
    return total


@pytest.mark.parametrize('ds', range(5))
def test_histogram_bars_add_up(build, ds):
    with Sim(build('histogram')) as s:
        s.click(f'dsZ{ds}')
        n = s.eval(f'DATA[{ds}].values.length')
        for k in (2, 7, 23, 60):
            s.drag('knob', f'z{k}')
            assert s.eval('bins') == k
            assert _counts_from_bars(s, k) == n
            assert not any(s.visible(f'bar{i}') for i in range(k, 60))
            knob = s.get('knob').rect
            assert (knob[0] + knob[2]) / 2 == pytest.approx(s.eval(f'kx({k})'))


def test_histogram_click_on_track_and_hover_after_drop(build):
    with Sim(build('histogram')) as s:
        s.click('z30')
        assert s.eval('bins') == 30
        r = s.get('z45').rect
        s.move((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
        assert s.eval('bins') == 30


def test_histogram_rules_and_buttons(build):
    with Sim(build('histogram')) as s:
        assert s.value('lS') == 'Sturges: 11 bins'           # n = 736: ceil(log2 736) + 1
        s.click('fdZ')
        assert s.eval('bins') == s.eval('fdK')
        s.click('plusZ')
        s.click('plusZ')
        assert s.eval('bins') == min(60, s.eval('fdK') + 2)
        for _ in range(70):
            s.click('minusZ')
        assert s.eval('bins') == 2                            # clamped
        s.click('dsZ3')                                       # hydrogen: tiny IQR, FD wants more than 60
        assert s.value('lF') == 'Freedman-Diaconis: 60 bins (or more)'


def test_histogram_static_start_matches_script(build):
    """The page drawn by Python (seen before or without JavaScript) equals what the script draws on open."""
    pdf = build('histogram')
    doc = load(pdf)
    with Sim(pdf) as s:
        for i in range(60):
            f, st = doc.field(f'bar{i}'), s.get(f'bar{i}')
            assert (not f.hidden) == st.visible
            if st.visible:
                assert f.rect == pytest.approx(st.rect, abs=0.01)
