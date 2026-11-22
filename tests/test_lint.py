from livepdf import LivePdf, lint, load


def codes(pdf):
    return sorted({f.code for f in lint(load(pdf))})


def test_example_is_clean(pump_pdf):
    assert codes(pump_pdf) == []


def test_finds_typical_mistakes(tmp_path):
    g = LivePdf(300, 200)
    g.push_button('btn', 10, 10, 80, 30, 'Go', on_click='go(); missing();')
    g.push_button('btn2', 20, 10, 80, 30, 'Two', on_click='go();')                 # covers most of btn
    g.text_field('out', 10, 60, 200, 20, '', U='go();')
    g.script('function fld(n) { return this.getField(n); }\n'
             'function go() { fld("nope").value = 1; getField("d" + 1); global.setPersistent("x", true);'
             ' var s = "50 %"; if ( }')
    found = codes(g.save(tmp_path / 'bad.pdf'))
    assert {'LP003', 'LP004', 'LP005', 'LP007', 'LP010', 'LP012'} <= set(found)


def test_swap_pair_with_separate_handlers(tmp_path):
    g = LivePdf(300, 100)
    g.push_button('a', 10, 10, 80, 30, 'A', on_click='goA();')
    g.push_button('b', 10, 10, 80, 30, 'B', hidden=True, on_click='goB();')
    g.script('function goA() {} function goB() {}')
    assert codes(g.save(tmp_path / 'swap.pdf')) == ['LP013']
