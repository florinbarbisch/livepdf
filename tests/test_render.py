import pytest

pymupdf = pytest.importorskip('pymupdf')
from livepdf import Sim  # noqa: E402


def test_snapshot_shows_level_bar(pump_pdf, tmp_path):
    with Sim(pump_pdf, pace_ms=0) as s:
        for _ in range(5):
            s.click('btnPump')
        png = s.snapshot(tmp_path / 'pump.png')
    pix = pymupdf.Pixmap(str(png))
    scale = pix.width / 420
    inside = pix.pixel(int(60 * scale), int(108 * scale))    # inside the blue bar (level 50 -> 185 pt wide)
    outside = pix.pixel(int(380 * scale), int(108 * scale))
    assert inside[2] > 200 and inside[0] < 100
    assert outside[:3] == (255, 255, 255)
