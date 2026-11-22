import pytest

from livepdf.chrome import ChromePdf

pytestmark = pytest.mark.chrome


def test_pump_in_real_chrome(pump_pdf, tmp_path):
    with ChromePdf(pump_pdf, workdir=tmp_path) as c:
        assert c.pixel(40, 152)[2] > 240 and c.pixel(40, 152)[0] > 240     # inside the empty tank: white
        for _ in range(3):
            c.click('btnPump', hold_ms=40)
        r, g, b = c.pixel(40, 152)                                          # near the left end: the bar is there
        assert r < 120 and b > 180, (r, g, b)                               # blue: PDFium ran the script
        assert c.ink('status', fresh=False) > 0.005                        # status text is drawn


def test_again_works_on_the_first_click_in_chrome(pump_pdf, tmp_path):
    with ChromePdf(pump_pdf, workdir=tmp_path, pace_ms=60) as c:
        for _ in range(30):
            c.click('btnPump', hold_ms=30)
            if c.pixel(380, 152)[0] < 120:                 # the bar reached the right end: won
                break
        assert c.pixel(380, 152, fresh=False)[0] < 120, c.crop('level', tmp_path / 'not_won.png', fresh=False)
        c.wait(700)
        c.click('btnAgain')
        c.wait(400)                                        # let Chrome repaint
        assert c.pixel(380, 152)[0] > 240, c.crop('level', tmp_path / 'not_reset.png', fresh=False)


def _example(name, tmp_path):
    import runpy
    from pathlib import Path
    g = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'examples' / name / 'build.py'))['g']
    return g.save(tmp_path / f'{name}.pdf')


def test_f1_drag_and_drop_in_chrome(tmp_path):
    """Press on the knob, move with the button held, release: the knob follows and stays where it was dropped."""
    with ChromePdf(_example('f1_slider', tmp_path), workdir=tmp_path) as c:
        assert c.pixel(520, 232)[0] > 225                       # recall bar ends at 50 %: x = 55 % is empty
        c.drag('kR_50', (532, 364), steps=12)
        c.move((300, 300), steps=4)                             # dropped: moving away changes nothing
        c.wait(1200)
        assert c.pixel(520, 232)[0] < 205, c.crop((180, 220, 800, 260), tmp_path / 'recall.png')
        assert c.pixel(560, 232)[0] > 225                       # and it stopped at 57 %


def test_histogram_drag_in_chrome(tmp_path):
    pdf = _example('histogram', tmp_path)
    from livepdf import load
    doc = load(pdf)
    knob = doc.field('knob').rect
    with ChromePdf(pdf, workdir=tmp_path) as c:
        c.drag('knob', 'z40', steps=15)
        c.move((480, 520), steps=4)
        c.wait(500)
        x = (doc.field('z40').rect[0] + doc.field('z40').rect[2]) / 2
        y = (knob[1] + knob[3]) / 2
        assert c.pixel(x, y)[0] < 80, c.crop((60, 80, 660, 140), tmp_path / 'track.png')   # the black knob is at 40
        assert c.pixel((knob[0] + knob[2]) / 2, y)[0] > 120                                   # and no longer at 11
