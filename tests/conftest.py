import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _example(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'examples' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='session')
def pump_pdf(tmp_path_factory) -> Path:
    return _example('pump').g.save(tmp_path_factory.mktemp('pdf') / 'pump.pdf')


def pytest_collection_modifyitems(config, items):
    from livepdf.chrome import find_chrome
    try:
        find_chrome()
        ok = shutil.which('node') is not None
    except RuntimeError:
        ok = False
    for item in items:
        if 'chrome' in item.keywords and not ok:
            item.add_marker(pytest.mark.skip(reason='needs Chrome and node'))
