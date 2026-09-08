"""Run the configured preview command with invented environment values."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILE_URL = 'postgresql:///invented_file_database'
SCRATCH_URL = 'postgresql:///invented_scratch_database'


@pytest.mark.parametrize('exported,file_value,expected', [
    (SCRATCH_URL, FILE_URL, SCRATCH_URL),
    (None, FILE_URL, FILE_URL),
    (SCRATCH_URL, None, SCRATCH_URL),
    (None, None, None),
    ('', FILE_URL, None),
])
def test_preview_preserves_explicit_environment_and_never_prints_the_database(
        tmp_path, exported, file_value, expected):
    if file_value is not None:
        (tmp_path / '.env').write_text(f'DATABASE_URL="{file_value}"\nDINKYDASH_MODE=single\n')
    executables = tmp_path / 'venv/bin'
    executables.mkdir(parents=True)
    python = executables / 'python'
    python.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
    python.chmod(0o755)
    flask = executables / 'flask'
    flask.write_text(f'#!{sys.executable}\n' + '''import json, os, pathlib, sys
pathlib.Path('captured.json').write_text(json.dumps({
    'database': os.environ['DATABASE_URL'], 'mode': os.environ['DINKYDASH_MODE'],
    'app': os.environ['FLASK_APP'], 'args': sys.argv[1:]}))
''')
    flask.chmod(0o755)
    env = {key: value for key, value in os.environ.items()
           if key not in {'DATABASE_URL', 'DATABASE_URL_DIRECT', 'DINKYDASH_MODE'}}
    env['CONDUCTOR_PORT'] = '5123'
    if exported is not None:
        env['DATABASE_URL'] = exported
    settings = tomllib.loads((ROOT / '.conductor/settings.toml').read_text())
    command = settings['scripts']['run']['dashboard']['command']
    result = subprocess.run(['sh', '-c', command], cwd=tmp_path, env=env,
                            text=True, capture_output=True, timeout=10)
    assert FILE_URL not in result.stdout + result.stderr
    assert SCRATCH_URL not in result.stdout + result.stderr
    if expected is None:
        assert result.returncode != 0
        assert 'Cloud mode needs DATABASE_URL' in result.stderr
        assert not (tmp_path / 'captured.json').exists()
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads((tmp_path / 'captured.json').read_text()) == {
            'database': expected, 'mode': 'cloud', 'app': 'app.py',
            'args': ['run', '--port', '5123', '--debug']}
