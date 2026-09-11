/* Native form submissions keep CSRF, validation and no-script behaviour intact. */
(() => {
    const confirmation = document.getElementById('action-confirm');
    const waiting = document.getElementById('action-wait');
    const guarded = Array.from(document.querySelectorAll('form[data-dirty-guard]'));
    const values = form => JSON.stringify(Array.from(new FormData(form)).filter(([key]) => key !== 'csrf_token'));
    const originals = new Map(guarded.map(form => [form, values(form)]));
    let leaving = false;
    let busy = false;
    const disabled = new Map();
    const dirty = () => guarded.some(form => form.dataset.dirtyGuard === 'changed'
        || values(form) !== originals.get(form));

    function beforeUnload(event) {
        if (!leaving && dirty()) {
            event.preventDefault();
            event.returnValue = '';
        }
    }
    function syncBeforeUnload() {
        // Even an idle listener prevents Firefox from caching the page for Back.
        if (!leaving && dirty()) window.addEventListener('beforeunload', beforeUnload);
        else window.removeEventListener('beforeunload', beforeUnload);
    }
    guarded.forEach(form => {
        form.addEventListener('input', syncBeforeUnload);
        form.addEventListener('change', syncBeforeUnload);
        // Reset's default action restores values after the event dispatch.
        form.addEventListener('reset', () => setTimeout(syncBeforeUnload, 0));
    });
    syncBeforeUnload();

    function ask(prompt) {
        if (typeof confirmation.showModal !== 'function') {
            return Promise.resolve(window.confirm(`${prompt.title}\n\n${prompt.message}`));
        }
        if (confirmation.open) return Promise.resolve(false);
        const previousFocus = document.activeElement;
        document.getElementById('action-confirm-title').textContent = prompt.title;
        document.getElementById('action-confirm-message').textContent = prompt.message;
        document.getElementById('action-cancel').textContent = prompt.cancel;
        document.getElementById('action-accept').textContent = prompt.confirm;
        confirmation.returnValue = '';
        return new Promise(resolve => {
            confirmation.addEventListener('close', () => {
                previousFocus?.focus();
                resolve(confirmation.returnValue === 'confirm');
            }, {once: true});
            confirmation.showModal();
        });
    }
    document.getElementById('action-cancel').addEventListener('click', () => confirmation.close('cancel'));
    document.getElementById('action-accept').addEventListener('click', () => confirmation.close('confirm'));

    document.addEventListener('click', async event => {
        const link = event.target.closest('a[href]');
        if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey
            || event.shiftKey || event.altKey || link.hasAttribute('download')
            || (link.target && link.target !== '_self') || !dirty()) return;
        const destination = new URL(link.href);
        if (destination.pathname === location.pathname && destination.search === location.search
            && destination.origin === location.origin && destination.hash) return;
        event.preventDefault();
        if (await ask({title: 'Discard unsaved changes?',
            message: 'Your edits have not been saved. Leaving this page will discard them.',
            cancel: 'Keep editing', confirm: 'Discard changes'})) {
            leaving = true;
            syncBeforeUnload();
            location.assign(link.href);
        }
    });

    document.addEventListener('submit', async event => {
        if (event.defaultPrevented) return;
        const form = event.target;
        if (busy) {
            event.preventDefault();
            return;
        }
        if (form.dataset.confirm && form.elements.confirmed.value !== 'yes') {
            event.preventDefault();
            if (await ask(JSON.parse(form.dataset.confirm))) {
                form.elements.confirmed.value = 'yes';
                form.requestSubmit(event.submitter);
            }
            return;
        }
        leaving = true;
        // A successful Save must not look dirty if this page returns from history.
        if (originals.has(form)) {
            originals.set(form, values(form));
            form.dataset.dirtyGuard = '';
        }
        syncBeforeUnload();
        if (form.dataset.pending) {
            busy = true;
            document.getElementById('action-wait-title').textContent = form.dataset.pending;
            if (typeof waiting.showModal === 'function') waiting.showModal();
            // These action forms have no named submit button; disabling it cannot
            // remove an action value from the POST body.
            form.querySelectorAll('button').forEach(button => {
                disabled.set(button, button.disabled);
                button.disabled = true;
            });
            form.setAttribute('aria-busy', 'true');
        }
    });
    waiting.addEventListener('cancel', event => event.preventDefault());
    window.addEventListener('pageshow', () => {
        leaving = false;
        busy = false;
        if (waiting.open) waiting.close();
        disabled.forEach((wasDisabled, button) => { button.disabled = wasDisabled; });
        disabled.clear();
        document.querySelectorAll('form[aria-busy]').forEach(form => form.removeAttribute('aria-busy'));
        document.querySelectorAll('form[data-confirm]').forEach(form => { form.elements.confirmed.value = ''; });
        syncBeforeUnload();
    });
})();
