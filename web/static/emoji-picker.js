/* The emoji picker. The quick picks are plain radios in the form; this is the way to the
   rest of them: a dialog filled from emoji.json the first time it opens, with a search box
   that also takes an emoji typed on the phone's own keyboard. A choice lands in the form's
   own radio (or ticks the quick pick it matches), so the form still submits one radio group
   and works as it always did when none of this runs. */
(() => {
    const picker = document.querySelector('[data-emoji-picker]');
    const dialog = document.getElementById('emoji-dialog');
    if (!picker || !dialog || typeof dialog.showModal !== 'function') return;

    const more = picker.querySelector('.more');
    const own = picker.querySelector('input[data-own]');
    const ownLabel = picker.querySelector(`label[for="${own.id}"]`);
    const chosen = picker.querySelector('[data-chosen]');
    const search = dialog.querySelector('input');
    const results = dialog.querySelector('.emoji-results');
    const typed = dialog.querySelector('.emoji-typed');
    const typedButton = typed.querySelector('button');
    const note = dialog.querySelector('.emoji-note');
    const count = dialog.querySelector('.emoji-count');

    // A variation selector is a rendering hint, not a different emoji: "🍽" and "🍽️" are one.
    const plain = text => text.replace(/\uFE0F/g, '');
    // Lower-case words with the punctuation gone, so "T-Rex" and "st patrick's day" search as
    // typed. Matched at word starts: "cat" finds "cat face" and "black cat", not "vacation".
    const normalise = text => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
    // The shape of one emoji, and the same grammar the server checks (web/emoji.py), so nothing
    // is offered here that Save would refuse: a pictograph with an optional variation selector
    // and skin tone or tag flag, or a keycap, or a two-letter flag — joined to more of the same
    // with zero-width joiners, ten code points at most. "🐶🐱" is two, and is not offered.
    const ELEMENT = '(?:\\p{Extended_Pictographic}\\uFE0F?(?:[\\u{1F3FB}-\\u{1F3FF}]|[\\u{E0020}-\\u{E007E}]+\\u{E007F})?'
        + '|[0-9#*]\\uFE0F?\\u20E3|\\p{Regional_Indicator}{2})';
    const ONE_EMOJI = new RegExp(`^${ELEMENT}(?:\\u200D${ELEMENT})*$`, 'u');
    const looksLikeEmoji = text => [...text].length <= 10 && ONE_EMOJI.test(text);

    let state = 'idle';

    const say = text => {
        note.textContent = text;
        note.hidden = !text;
    };

    function load() {
        if (state !== 'idle') return;
        state = 'loading';
        say('Loading the emoji list…');
        fetch(more.dataset.src)
            .then(response => {
                if (!response.ok) throw new Error(String(response.status));
                return response.json();
            })
            .then(data => {
                build(data.groups);
                state = 'ready';
                filter();
            })
            .catch(() => {
                state = 'idle';
                say('The emoji list could not be loaded. Close this and try again.');
            });
    }

    function build(groups) {
        for (const group of groups) {
            const section = document.createElement('section');
            section.className = 'emoji-group';
            const heading = document.createElement('h3');
            heading.className = 'label';
            heading.textContent = group.name;
            const grid = document.createElement('div');
            grid.className = 'emoji-grid';
            for (const [emoji, name, keywords] of group.emoji) {
                const button = document.createElement('button');
                button.type = 'button';
                button.textContent = emoji;
                button.title = name;
                button.setAttribute('aria-label', name);
                button.dataset.emoji = emoji;
                button.dataset.search = ` ${normalise(keywords ? `${name} ${keywords}` : name)}`;
                grid.append(button);
            }
            section.append(heading, grid);
            results.append(section);
        }
    }

    function filter() {
        const query = search.value.trim();
        const needle = normalise(query);
        let shown = 0;
        for (const section of results.querySelectorAll('.emoji-group:not(.emoji-typed)')) {
            let visible = 0;
            for (const button of section.querySelectorAll('button')) {
                // No query shows everything; a query with no words in it (an emoji) shows nothing
                // from the list, so what was typed stands alone.
                const hit = needle ? button.dataset.search.includes(` ${needle}`) : !query;
                button.hidden = !hit;
                if (hit) visible += 1;
            }
            section.hidden = visible === 0;
            shown += visible;
        }
        // Whatever was typed is offered as it is when it looks like an emoji — the keyboard's
        // own picker knows every emoji there is, including the ones this list leaves out.
        const useTyped = Boolean(query) && looksLikeEmoji(query);
        typed.hidden = !useTyped;
        if (useTyped) {
            typedButton.textContent = query;
            typedButton.dataset.emoji = query;
            shown += 1;
        }
        if (state === 'ready') {
            say(shown ? '' : `Nothing matches “${query}”. Try another word, or type an emoji from your keyboard.`);
        }
        count.textContent = needle || useTyped ? `${shown} emoji ${shown === 1 ? 'matches' : 'match'}` : '';
    }

    function choose(emoji, name) {
        const radios = Array.from(picker.querySelectorAll('input[type=radio]'));
        let target = radios.find(radio => radio !== own && radio.value && plain(radio.value) === plain(emoji));
        if (!target) {
            own.value = emoji;
            ownLabel.textContent = emoji;
            own.hidden = false;
            ownLabel.hidden = false;
            target = own;
        }
        target.checked = true;
        dialog.close();
        target.focus();
        chosen.textContent = `${name} chosen.`;
        // Ticking a radio from a script fires no event, and the unsaved-changes guard listens for one.
        picker.dispatchEvent(new Event('change', {bubbles: true}));
    }

    more.hidden = false;
    more.addEventListener('click', () => {
        search.value = '';
        dialog.showModal();
        if (state === 'ready') filter();
        else load();
        search.focus();
    });
    search.addEventListener('input', filter);
    search.addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        const first = results.querySelector('.emoji-group:not([hidden]) button:not([hidden])');
        if (first) first.click();
    });
    results.addEventListener('click', event => {
        const button = event.target.closest('button[data-emoji]');
        if (button && button.dataset.emoji) {
            choose(button.dataset.emoji, button.getAttribute('aria-label') || button.dataset.emoji);
        }
    });
    dialog.querySelector('[data-close]').addEventListener('click', () => dialog.close());
})();
