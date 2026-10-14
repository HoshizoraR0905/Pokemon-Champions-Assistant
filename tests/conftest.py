"""Explicit local recording integration prerequisites; portable unit tests need none."""
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config):
    config.addinivalue_line('markers', 'local_artifacts(*paths): optional local recording/cache integration prerequisites')


def pytest_runtest_setup(item):
    for marker in item.iter_markers('local_artifacts'):
        missing = [path for path in marker.args if not (ROOT / path).exists()]
        if missing:
            pytest.skip('Optional local recording integration: missing ' + ', '.join(missing))
