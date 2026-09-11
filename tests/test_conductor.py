"""Conductor delegates to the same validated launcher used in a terminal."""

import os
from pathlib import Path
import tomllib

import pytest

import dev

ROOT = Path(__file__).resolve().parents[1]
FILE_URL = 'postgresql:///invented_file_database'
SCRATCH_URL = 'postgresql:///invented_scratch_database'


def test_one_default_run_starts_both_apps():
    settings = tomllib.loads((ROOT / '.conductor/settings.toml').read_text())
    runs = settings['scripts']['run']
    assert runs['dev']['command'] == 'venv/bin/python dev.py'
    assert runs['dev']['default'] is True
    assert 'dashboard' not in runs and 'website' not in runs


@pytest.mark.parametrize('exported,file_value,expected', [
    (SCRATCH_URL, FILE_URL, SCRATCH_URL),
    (None, FILE_URL, FILE_URL),
    (SCRATCH_URL, None, SCRATCH_URL),
    (None, None, None),
    ('', FILE_URL, None),
])
def test_preview_preserves_explicit_environment_and_never_prints_the_database(
        tmp_path, monkeypatch, capsys, exported, file_value, expected):
    if file_value is not None:
        (tmp_path / '.env').write_text(f'DATABASE_URL="{file_value}"\nDINKYDASH_MODE=single\n')
    for key in ('DATABASE_URL', 'DINKYDASH_MODE', 'DINKYDASH_APP_URL', 'DINKYDASH_APP_HOST'):
        # Record absent keys too, so configure's environment changes are undone.
        monkeypatch.setenv(key, '')
        monkeypatch.delenv(key)
    monkeypatch.setenv('DINKYDASH_SECRET_KEY', 'development-test-key')
    monkeypatch.setenv('CONDUCTOR_PORT', '5123')
    if exported is not None:
        monkeypatch.setenv('DATABASE_URL', exported)
    monkeypatch.setattr(dev, 'ROOT', tmp_path)
    captured = {}

    def validate():
        captured['database'] = os.environ['DATABASE_URL']

    def supervise(ports):
        captured.update(mode=os.environ['DINKYDASH_MODE'], ports=ports)
        return 0

    monkeypatch.setattr(dev, 'validate_database', validate)
    monkeypatch.setattr(dev, 'supervise', supervise)
    result = dev.main()
    output = capsys.readouterr()
    assert FILE_URL not in output.out + output.err
    assert SCRATCH_URL not in output.out + output.err
    if expected is None:
        assert result != 0
        assert 'DATABASE_URL is required' in output.err
        assert not captured
    else:
        assert result == 0, output.err
        assert captured == {
            'database': expected, 'mode': 'cloud',
            'ports': {'Dashboard': 5123, 'Website': 5124},
        }
