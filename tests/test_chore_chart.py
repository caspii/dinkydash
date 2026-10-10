"""The weekly rotation on the chore chart generator.

The marketing site has no JS test runner. The arithmetic lives in
`website/templates/chore-chart.js`, which the page includes, and this
loads that same file in Node when Node is installed. Without Node the
test is skipped; the rule is also written at the top of the file.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "website" / "templates" / "chore-chart.js"

NODE = r"""
const assert = require('assert');
const c = require('./website/templates/chore-chart.js');

const monEpoch = new Date(2024, 0, 1);
const sunEpoch = new Date(2023, 11, 31);
assert.strictEqual(c.weekIndex(monEpoch, 'mon'), 0);
assert.strictEqual(c.weekStart(monEpoch, 'mon').getDate(), 1);
assert.strictEqual(c.weekIndex(sunEpoch, 'sun'), 0);
assert.strictEqual(c.weekIndex(new Date(2024, 0, 7), 'mon'), 0);
assert.strictEqual(c.weekIndex(new Date(2024, 0, 8), 'mon'), 1);
assert.strictEqual(c.weekIndex(new Date(2024, 0, 7), 'sun'), 1);
assert.strictEqual(c.weekIndex(new Date(2026, 9, 5), 'mon'), c.weekIndex(new Date(2026, 9, 10), 'mon'));
assert.strictEqual(c.weekIndex(new Date(2026, 9, 5), 'mon') + 1, c.weekIndex(new Date(2026, 9, 12), 'mon'));
assert.strictEqual(c.weekIndex(new Date(2026, 9, 4), 'sun'), c.weekIndex(new Date(2026, 9, 10), 'sun'));
assert.strictEqual(c.weekIndex(new Date(2026, 9, 4), 'sun') + 1, c.weekIndex(new Date(2026, 9, 11), 'sun'));

assert.deepStrictEqual([0, 1, 2].map((i) => c.assigneeIndex(3, i, 0)), [0, 1, 2]);
assert.deepStrictEqual([0, 1, 2].map((i) => c.assigneeIndex(3, i, 1)), [1, 2, 0]);
assert.strictEqual(c.assigneeIndex(3, 0, -1), 2);
assert.strictEqual(c.assigneeIndex(0, 0, 4), -1);
assert.strictEqual(c.assigneeIndex(1, 3, 9), 0);

assert.strictEqual(c.weekLabel(new Date(2026, 9, 5)), '5\u201311 October');
assert.strictEqual(c.weekLabel(new Date(2026, 8, 28)), '28 September \u2013 4 October');
assert.strictEqual(c.weekLabel(new Date(2026, 11, 28)), '28 December 2026 \u2013 3 January 2027');
assert.deepStrictEqual(c.dayOrder('sun'), [6, 0, 1, 2, 3, 4, 5]);

const state = {
  kids: ['Pip', 'Moss', 'Rue'],
  chores: [{id: 1, title: 'Set the table', mask: 127, who: 0},
           {id: 2, title: 'Bins', mask: 1, who: 1}],
  start: 'mon',
  rotate: true,
  week: '2026-10-05',
  ticks: {'1.1': true}
};
const again = c.decodeState(c.encodeState(state));
assert.deepStrictEqual(again.kids, state.kids);
assert.deepStrictEqual(again.chores, state.chores);
assert.strictEqual(again.rotate, true);
assert.strictEqual(again.ticks['1.1'], true);
assert.deepStrictEqual(c.decodeState('#'), c.blankState());
assert.strictEqual(c.decodeState('#k=' + encodeURIComponent('<script>') + '&c=nope').kids[0], '<script>');
assert.strictEqual(c.rotationSentence(['Pip', 'Moss']),
  "Next week Pip's chores go to Moss, and Moss's to Pip.");
assert.strictEqual(c.encodeState(c.blankState()), '');
"""

RENAME = r"""
const assert = require('assert');
const c = require('./website/templates/chore-chart.js');

const state = {
  kids: ['Pip', 'Moss', 'Rue'],
  chores: [{id: 1, title: 'Set the table', mask: 127, who: 0},
           {id: 2, title: 'Bins', mask: 1, who: 2}],
  start: 'mon',
  rotate: true,
  week: '2026-10-05',
  ticks: {'1.1': true, '1.2': true, '2.1': true}
};

assert.strictEqual(c.renameKid(state, 0, '  Pippa  '), true);
assert.strictEqual(c.renameChore(state, 1, 'Lay the table'), true);
assert.strictEqual(state.kids[0], 'Pippa');
assert.deepStrictEqual(state.kids.slice(1), ['Moss', 'Rue']);
assert.strictEqual(state.chores[0].id, 1);
assert.strictEqual(state.chores[0].title, 'Lay the table');
assert.strictEqual(state.chores[0].mask, 127);
assert.strictEqual(state.chores[0].who, 0);
assert.strictEqual(state.chores[1].title, 'Bins');
assert.strictEqual(state.chores[1].mask, 1);
assert.strictEqual(state.chores[1].who, 2);
assert.strictEqual(state.rotate, true);
assert.strictEqual(state.start, 'mon');
assert.strictEqual(state.week, '2026-10-05');
assert.deepStrictEqual(state.ticks, {'1.1': true, '1.2': true, '2.1': true});

const again = c.decodeState(c.encodeState(state));
assert.strictEqual(again.kids[0], 'Pippa');
assert.strictEqual(again.chores[0].title, 'Lay the table');
assert.strictEqual(again.chores[0].mask, 127);
assert.strictEqual(again.chores[1].mask, 1);
assert.strictEqual(again.rotate, true);
assert.deepStrictEqual(again.ticks, state.ticks);

assert.strictEqual(c.renameKid(state, 0, '   '), false);
assert.strictEqual(state.kids[0], 'Pippa');
assert.strictEqual(c.renameKid(state, 9, 'Ned'), false);
assert.strictEqual(c.renameChore(state, 1, ''), false);
assert.strictEqual(c.renameChore(state, 99, 'Sweep'), false);
assert.strictEqual(state.chores[0].title, 'Lay the table');
assert.deepStrictEqual(state.ticks, {'1.1': true, '1.2': true, '2.1': true});

var longKid = '';
for (var i = 0; i < 30; i++) { longKid += 'A'; }
assert.strictEqual(c.renameKid(state, 1, longKid), true);
assert.strictEqual(state.kids[1].length, c.MAX_NAME);
var longChore = '';
for (var j = 0; j < 50; j++) { longChore += 'B'; }
assert.strictEqual(c.renameChore(state, 2, longChore), true);
assert.strictEqual(state.chores[1].title.length, c.MAX_TITLE);
assert.strictEqual(c.renameChore(state, 2, 'Wash|up'), true);
assert.strictEqual(state.chores[1].title, 'Wash up');
assert.strictEqual(state.chores[1].mask, 1);
assert.deepStrictEqual(c.decodeState(c.encodeState(state)).ticks, {'1.1': true, '1.2': true, '2.1': true});
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_rotation_week_and_link_round_trip():
    subprocess.run(["node", "-e", NODE], cwd=ROOT, check=True)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_renaming_keeps_ticks_days_and_rotation():
    subprocess.run(["node", "-e", RENAME], cwd=ROOT, check=True)
