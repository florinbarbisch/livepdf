import pytest

from livepdf import LivePdf, Sim, SimError


def test_pump_click_and_leak(pump_pdf):
    with Sim(pump_pdf, pace_ms=0) as s:
        assert s.click('btnPump') == 'btnPump'
        assert s.eval('level') == 10                 # the 80 ms click hold is shorter than one 100 ms leak tick
        s.advance(500)
        assert s.eval('level') == 5
        assert s.value('status') == 'level 5'
        assert s.get('level').rect[2] == round(25 + 5 * 3.7)            # whole points (Edge)


def test_pump_win_swaps_buttons(pump_pdf):
    with Sim(pump_pdf, pace_ms=0, hold_ms=0) as s:          # no virtual time passes, so nothing leaks
        for _ in range(10):
            s.click('btnPump')
        assert s.value('status') == 'Full! You won.'
        assert not s.visible('btnPump') and s.visible('btnAgain')
        s.click('btnAgain')                           # too soon after the win: ignored, fast pumping is safe
        assert s.eval('won')


def test_again_works_on_the_first_click(pump_pdf):
    """Regression: Chrome gave the click on Again to the hidden, still focused Pump, so Again only worked after
    a click elsewhere. Both buttons now share one handler."""
    with Sim(pump_pdf, pace_ms=0, hold_ms=0) as s:
        for _ in range(10):
            s.click('btnPump')
        s.advance(700)
        assert s.click('btnAgain') == 'btnPump'       # what Chrome does
        assert s.eval('level') == 0 and not s.eval('won') and s.visible('btnPump')


def test_moves_follow_hide_move_show(pump_pdf):
    with Sim(pump_pdf) as s:
        s.click('btnPump')
        assert not [w for w in s.warnings if 'moved' in w]


def _game(js, **fields):
    g = LivePdf(300, 200)
    g.text_field('inp', 10, 10, 100, 30, '0.', readonly=False, V='validated = event.value;')
    g.text_field('out', 10, 50, 200, 20, '')
    g.push_button('btn', 150, 10, 80, 30, 'Go', on_click='go();', D='down();')
    g.script(js)
    return g


def test_chrome_order_mouse_down_before_commit(tmp_path):
    pdf = _game('var log = [], validated = null;'
                'function down() { log.push("down:" + validated); } function go() { log.push("go:" + validated); }'
                ).save(tmp_path / 'g.pdf')
    with Sim(pdf) as s:
        s.fill('inp', '0.4')
        s.click('btn')
        assert s.eval('log') == ['down:null', 'go:0.4']
        assert s.trace()[-3:] == ['btn:D', 'inp:V', 'btn:A']
    with Sim(pdf, order='acrobat') as s:
        s.fill('inp', '0.4')
        s.click('btn')
        assert s.eval('log') == ['down:0.4', 'go:0.4']


def test_value_coercion_like_pdfium(tmp_path):
    pdf = _game('function down() {} function go() {}').save(tmp_path / 'g.pdf')
    with Sim(pdf) as s:
        assert s.eval('getField("inp").value') == 0               # "0." comes back as the number 0
        assert s.eval('getField("inp").valueAsString') == '0.'


def test_script_errors_raise(tmp_path):
    pdf = _game('function down() {} function go() { undefinedThing(); }').save(tmp_path / 'g.pdf')
    with Sim(pdf) as s:
        with pytest.raises(SimError, match='undefinedThing'):
            s.click('btn')


def test_overlap_goes_to_first_field(tmp_path):
    """Measured in Chrome: on overlapping fields the first one in annotation order gets the click."""
    g = LivePdf(200, 100)
    g.push_button('under', 10, 10, 80, 30, 'A', on_click='hits.push("under");')
    g.zone('over', 10, 10, 80, 30, on_click='hits.push("over");')       # drawn on top, but second
    g.script('var hits = [];')
    with Sim(g.save(tmp_path / 'g.pdf')) as s:
        assert s.click('over') == 'under'
        assert s.eval('hits') == ['under']
        assert any('first in the annotation order' in w for w in s.warnings)


def _swap_pair(tmp_path, one_handler):
    """Button a hides itself and shows b on the same spot (and back), like Pump / Again."""
    g = LivePdf(300, 100)
    a = 'main();' if one_handler else 'goA();'
    b = 'main();' if one_handler else 'goB();'
    g.push_button('a', 10, 10, 80, 30, 'A', on_click=a)
    g.push_button('b', 10, 10, 80, 30, 'B', hidden=True, on_click=b)
    g.script('var hits = [], showing = "a";'
             'function show(n) { getField(n == "a" ? "b" : "a").display = display.hidden; getField(n).display = display.visible; showing = n; }'
             'function goA() { hits.push("a"); show("b"); } function goB() { hits.push("b"); show("a"); }'
             'function main() { if (showing == "a") goA(); else goB(); }')
    return g.save(tmp_path / 'swap.pdf')


def test_hidden_field_keeps_clicks_while_focused(tmp_path):
    """Measured in Chrome: a field that hides itself keeps the clicks on its spot until a click elsewhere."""
    with Sim(_swap_pair(tmp_path, one_handler=False)) as s:
        s.click('a')
        assert s.click('b') == 'a'                     # b is visible, but the hidden, focused a gets it
        assert s.eval('hits') == ['a', 'a']
        s.click((250, 50))                             # empty page: a loses the focus
        assert s.click('b') == 'b'
        assert s.click('a') == 'a'                     # b was hidden in the file: it does not keep clicks


def test_one_handler_survives_the_swap(tmp_path):
    with Sim(_swap_pair(tmp_path, one_handler=True)) as s:
        for _ in range(4):
            s.click('a')
        assert s.eval('hits') == ['a', 'b', 'a', 'b']


def test_lost_clicks(pump_pdf):
    with Sim(pump_pdf, lost_clicks=1) as s:
        assert s.click('btnPump') is None
        assert s.click('btnPump') == 'btnPump'
