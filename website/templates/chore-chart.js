/* Weekly chore-chart arithmetic for /chore-chart-generator/.
   The page includes this file. There is no separate JS test runner;
   tests/test_chore_chart.py loads the same file in Node when Node is
   installed, so the page and the tests cannot drift.

   Whose turn a chore is
   ---------------------
   Kids stay in the order they were added. Week 0 is the week of Monday
   1 January 2024. A chart that starts on Sunday counts from Sunday
   31 December 2023, so the names move on Sunday morning instead.

   assignee = kids[mod(weekIndex + choreIndex, kids.length)]

   The chore's place in the list spreads chores across children in the
   same week. Next week every chore moves one child along. With the
   rotation switch off, a chore keeps the child it was given.

   Worked example, Monday weeks, kids Pip, Moss, Rue:
     week 0 (1 January 2024): chores 0, 1, 2 -> Pip, Moss, Rue
     week 1 (8 January 2024): chores 0, 1, 2 -> Moss, Rue, Pip

   JavaScript's remainder keeps the sign of the dividend, so a week
   before the epoch is normalised before it is used as an index.

   Days are a bitmask, Monday in the low bit through Sunday in the high
   bit, so changing the first column does not change which days a chore
   falls on. The link is this state and nothing else: no account, and
   the page does not write it anywhere but the hash.
*/
var DDChoreChart = (function () {
    'use strict';

    var MAX_KIDS = 6;
    var MAX_CHORES = 12;
    var MAX_NAME = 24;
    var MAX_TITLE = 40;
    var WEEK_MS = 7 * 24 * 60 * 60 * 1000;
    var EPOCH_MON = Date.UTC(2024, 0, 1);
    var EPOCH_SUN = Date.UTC(2023, 11, 31);
    var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December'];
    var DAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    var DAY_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                    'Saturday', 'Sunday'];
    /* Index 0 is Monday, matching DAY_SHORT. Bit 0 is Monday. */
    var DAY_BIT = [1, 2, 4, 8, 16, 32, 64];

    function mod(n, m) {
        return ((n % m) + m) % m;
    }

    function weekStart(date, start) {
        var d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        var target = start === 'sun' ? 0 : 1;
        var delta = (d.getDay() - target + 7) % 7;
        d.setDate(d.getDate() - delta);
        return d;
    }

    function weekIndex(date, start) {
        var startDate = weekStart(date, start);
        var epoch = start === 'sun' ? EPOCH_SUN : EPOCH_MON;
        var ms = Date.UTC(startDate.getFullYear(), startDate.getMonth(), startDate.getDate()) - epoch;
        return Math.floor(ms / WEEK_MS);
    }

    function assigneeIndex(kidCount, choreIndex, weekIdx) {
        if (!kidCount) { return -1; }
        return mod(weekIdx + choreIndex, kidCount);
    }

    function weekLabel(startDate) {
        var end = new Date(startDate.getFullYear(), startDate.getMonth(), startDate.getDate() + 6);
        function dm(d) { return d.getDate() + ' ' + MONTHS[d.getMonth()]; }
        if (startDate.getFullYear() !== end.getFullYear()) {
            return dm(startDate) + ' ' + startDate.getFullYear() + ' \u2013 ' +
                dm(end) + ' ' + end.getFullYear();
        }
        if (startDate.getMonth() !== end.getMonth()) {
            return dm(startDate) + ' \u2013 ' + dm(end);
        }
        return startDate.getDate() + '\u2013' + end.getDate() + ' ' + MONTHS[end.getMonth()];
    }

    function iso(date) {
        var m = date.getMonth() + 1;
        var day = date.getDate();
        return date.getFullYear() + '-' +
            (m < 10 ? '0' : '') + m + '-' +
            (day < 10 ? '0' : '') + day;
    }

    function dayOrder(start) {
        return start === 'sun' ? [6, 0, 1, 2, 3, 4, 5] : [0, 1, 2, 3, 4, 5, 6];
    }

    function cleanText(value, max) {
        return String(value || '').replace(/[\u0000-\u001f|]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
    }

    function blankState() {
        return { kids: [], chores: [], start: 'mon', rotate: false, week: '', ticks: {} };
    }

    function parseHash(raw) {
        var out = {};
        var parts = String(raw || '').replace(/^#/, '').split('&');
        for (var i = 0; i < parts.length; i++) {
            if (!parts[i]) { continue; }
            var eq = parts[i].indexOf('=');
            var key, val;
            try {
                key = decodeURIComponent(eq < 0 ? parts[i] : parts[i].slice(0, eq));
                val = decodeURIComponent((eq < 0 ? '' : parts[i].slice(eq + 1)).replace(/\+/g, ' '));
            } catch (e) {
                continue;
            }
            if (!out[key]) { out[key] = []; }
            out[key].push(val);
        }
        return out;
    }

    function buildHash(pairs) {
        var bits = [];
        for (var i = 0; i < pairs.length; i++) {
            bits.push(encodeURIComponent(pairs[i][0]) + '=' + encodeURIComponent(pairs[i][1]));
        }
        return bits.join('&');
    }

    function decodeState(raw) {
        var state = blankState();
        var bag;
        try {
            bag = parseHash(raw);
        } catch (e) {
            return state;
        }
        var kids = bag.k || [];
        var seen = {};
        for (var i = 0; i < kids.length && state.kids.length < MAX_KIDS; i++) {
            var name = cleanText(kids[i], MAX_NAME);
            if (name) { state.kids.push(name); }
        }
        var chores = bag.c || [];
        for (var j = 0; j < chores.length && state.chores.length < MAX_CHORES; j++) {
            var fields = chores[j].split('|');
            if (fields.length !== 4) { continue; }
            var id = parseInt(fields[0], 10);
            var title = cleanText(fields[1], MAX_TITLE);
            var mask = parseInt(fields[2], 10);
            var who = parseInt(fields[3], 10);
            if (!(id > 0) || seen[id] || !title || !(mask >= 1 && mask <= 127)) { continue; }
            if (isNaN(who) || who < -1) { who = -1; }
            if (state.kids.length && who >= state.kids.length) { who = state.kids.length - 1; }
            if (!state.kids.length) { who = -1; }
            seen[id] = true;
            state.chores.push({ id: id, title: title, mask: mask, who: who });
        }
        state.start = (bag.start && bag.start[0] === 'sun') ? 'sun' : 'mon';
        state.rotate = !!(bag.rotate && bag.rotate[0] === '1');
        var week = bag.week && bag.week[0];
        if (week && /^\d{4}-\d{2}-\d{2}$/.test(week)) { state.week = week; }
        var ticks = bag.t || [];
        for (var t = 0; t < ticks.length; t++) {
            var tick = ticks[t];
            var dot = tick.indexOf('.');
            if (dot < 1) { continue; }
            var choreId = parseInt(tick.slice(0, dot), 10);
            var bit = parseInt(tick.slice(dot + 1), 10);
            var chore = null;
            for (var c = 0; c < state.chores.length; c++) {
                if (state.chores[c].id === choreId) { chore = state.chores[c]; }
            }
            if (!chore || !(bit >= 1 && bit <= 64) || (chore.mask & bit) !== bit) { continue; }
            state.ticks[choreId + '.' + bit] = true;
        }
        return state;
    }

    function encodeState(state) {
        if (!state.kids.length && !state.chores.length) { return ''; }
        var pairs = [];
        var kids = state.kids.slice(0, MAX_KIDS);
        var chores = state.chores.slice(0, MAX_CHORES);
        for (var i = 0; i < kids.length; i++) { pairs.push(['k', kids[i]]); }
        for (var j = 0; j < chores.length; j++) {
            var chore = chores[j];
            pairs.push(['c', chore.id + '|' + chore.title + '|' + chore.mask + '|' + chore.who]);
        }
        pairs.push(['start', state.start === 'sun' ? 'sun' : 'mon']);
        pairs.push(['rotate', state.rotate ? '1' : '0']);
        if (state.week) { pairs.push(['week', state.week]); }
        var keys = [];
        for (var key in state.ticks) {
            if (state.ticks.hasOwnProperty(key) && state.ticks[key]) { keys.push(key); }
        }
        keys.sort();
        for (var t = 0; t < keys.length; t++) { pairs.push(['t', keys[t]]); }
        return buildHash(pairs);
    }

    function rotationSentence(kids) {
        if (!kids || kids.length < 2) { return ''; }
        var parts = [];
        for (var i = 0; i < kids.length; i++) {
            var next = kids[(i + 1) % kids.length];
            parts.push(i === 0 ? kids[i] + "'s chores go to " + next : kids[i] + "'s to " + next);
        }
        if (parts.length === 2) { return 'Next week ' + parts[0] + ', and ' + parts[1] + '.'; }
        var last = parts.pop();
        return 'Next week ' + parts.join(', ') + ', and ' + last + '.';
    }

    function nameList(kids) {
        if (!kids.length) { return ''; }
        if (kids.length === 1) { return kids[0]; }
        if (kids.length === 2) { return kids[0] + ' and ' + kids[1]; }
        return kids.slice(0, -1).join(', ') + ' and ' + kids[kids.length - 1];
    }

    return {
        MAX_KIDS: MAX_KIDS,
        MAX_CHORES: MAX_CHORES,
        MAX_NAME: MAX_NAME,
        MAX_TITLE: MAX_TITLE,
        DAY_SHORT: DAY_SHORT,
        DAY_LONG: DAY_LONG,
        DAY_BIT: DAY_BIT,
        mod: mod,
        weekStart: weekStart,
        weekIndex: weekIndex,
        assigneeIndex: assigneeIndex,
        weekLabel: weekLabel,
        iso: iso,
        dayOrder: dayOrder,
        cleanText: cleanText,
        blankState: blankState,
        decodeState: decodeState,
        encodeState: encodeState,
        rotationSentence: rotationSentence,
        nameList: nameList
    };
})();

if (typeof module === 'object' && module.exports) {
    module.exports = DDChoreChart;
}
