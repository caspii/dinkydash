# The board and the settings UI

Guidance for `web/`. The root `CLAUDE.md` holds the rules that apply to every change; this
file holds the ones that only bite here. Sizing conventions are in the root under
**Conventions** — this is the reasoning behind them and the traps in measuring them.

## Adding to the settings UI

**Adding a field to a settings section.** Add a tuple to the section's `fields` list in
`web/routes/settings.py` — `(name, label, kind, required, help)`. The list template and the edit
form both render from it, and `parse_field` reads it back. `kind` is one of `text`, `url`, `date`,
`monthday`, `textarea`, `checkbox`, `emoji`, `color`, `people`, `emails`. A new `kind` needs a
branch in `parse_field` and a branch in `web/templates/settings/edit.html`; nothing else.

**Adding a whole settings section.** Add an entry to `SECTIONS` and a row to
`web/templates/settings/home.html`. The list, edit, delete and reorder routes are generic and need
no changes.

**A route gets its store from `web.family.current_store()`, never from `app.config`.** In single
mode that is the one `FileStore` the process was built with. In cloud mode it is a `PostgresStore`
built for this request from the family on the session, cached on `g`, over the process-wide pool.
A route that reads `app.config["STORE"]` directly works in single mode and serves `None` in cloud
mode, which is the failure that looks like a bug in something else.

**Poking at cloud mode locally: the session cookie is `Secure`, and every client disagrees about
what that means over `http://localhost`.** Cloud mode is https-only, so the cookie is marked
`Secure` and a laptop serving plain http is the odd case. Four different answers:

| Client | Sends a `Secure` cookie to `http://localhost`? |
|---|---|
| Chrome (89+), Firefox (75+) | Yes — loopback is treated as a secure context |
| **Safari** | **No.** There is no loopback exception, so the preview cannot sign in at all |
| `curl` | Sometimes, depending on version |
| `requests` | Never |

The failure looks identical in all the failing cases and looks nothing like a cookie problem: GETs
redirect to `/login` and POSTs come back 400 from the CSRF check, because there is no session to
hold a token. **Use Chrome or Firefox for the Conductor preview**, and drive `app.test_client()` in
process for anything scripted — it has no cookie policy and exercises the same code. An hour went
into the `requests` half of that.

**A route that touches a store needs `session.guard`**, and the board blueprint's `before_request`
is where that is decided. `board.healthz` is the one exemption and it is load-bearing: App
Platform's health check arrives with no cookie, and a 302 there fails it three times and rolls the
release back. It is also the only route that reads nothing, so it needs no family.

**`web/routes/screen.py` is the other exemption, and it is a separate blueprint for that reason.**
`/s/<token>` has no session by design — a wall panel cannot sign in — so it is not behind `guard()`
and never should be. What replaces the session is the token, resolved by `family.store_for_token`;
what replaces the guard is that the two routes there are GETs that reach a board and nothing else.
Registered only in cloud mode, like `auth`. **In cloud mode `/` is a redirect**, so anything that
used to link to `url_for('board.index')` for a board — the "View board" button, `/preview`'s
iframes — uses `web.urls.board_path()`. Build absolute credential URLs with
`web.urls.absolute_url(path)`: it uses HTTPS and the configured `DINKYDASH_APP_HOST`, with the
request host as a development fallback. The login-link CLI shares the origin policy and accepts
an explicit local `--base-url`. QR codes are generated only on `/settings/screen`.

**Every form that writes needs one hidden field.** `<input type="hidden" name="csrf_token"
value="{{ csrf_token() }}">`, right inside the `<form>`. `csrf_token()` is a Jinja global set up by
`web/session.py`, so no route has to remember to pass anything — but a form without the field is a
400, in both modes, and `tests/test_auth.py` walks the templates and fails on one. There is
deliberately no switch to turn the check off; the test client in `tests/conftest.py` fills the field
in the way a browser does.

**The settings home has a first-run card**, shown by `settings.looks_untouched`: no calendar and the
default family name. A hosted family is created with an invented household in it so the board has
something to show (DIN-41), and this is what stops that reading as a bug. **The signal is the config,
not the mode** — a freshly cloned Pi is in the same state and wants the same two prompts — so there
is no `cloud` branch in it, and it leaves on its own the moment either half is answered. Nothing to
dismiss and nothing remembered.

**Two chromes, one base.** `settings/base.html` is the phone-shaped shell for everything a person
signs into — the settings pages and, in cloud mode, `auth/login.html` and `auth/sent.html`. The
manifest link in its `<head>` is a `{% block manifest %}` so the login page can drop it: the
manifest route is behind the login, and asking for it from outside would only ever be a redirect.

**`cloud` is the template global for the mode**, not Flask's `config`. The settings pages pass the
*family's* config dict under that name and shadow the app's, which is why `create_app` sets a
separate `cloud` boolean — the Sign out button on the settings home is the first thing to use it.

## The board's layout

**Changing the board layout.** Everything is sized in `rem` off one root value, so check all three
sizes at `/preview` rather than just the one you are looking at.

That root value is now *measured*, not guessed. A short script at the foot of `board.html` binary-
searches the largest `html { font-size }` whose content still fits the viewport, capped at
`min(26px, vh/24)`. The CSS `clamp()` stays as the no-JS fallback. Because `body` is
`height:100vh;overflow:hidden`, nothing ever reports an overflow — so the script lets the page lay
out freely for one measurement (`height:auto`) and puts it straight back.

**Nunito is served from `web/static/fonts/`, not from Google**, as one variable font per subset
(`nunito-latin.woff2`, `nunito-latin-ext.woff2`, covering weights 200-1000 so every weight the board
asks for comes out of one download). `web/static/fonts.css` holds the `@font-face` rules and the
reasoning; `website/static/` has its own copy plus the italic pair the marketing site uses. Editing
either means editing both — they are separate deployables on purpose, and `website/` never runs on
the board. The files are byte-for-byte what Google was serving, so the metrics did not change; what
changed is that a screen at `/s/<token>` no longer tells Google that URL, and a Pi with no internet
renders the same board rather than falling back to a system font.

It re-fits on `document.fonts.ready` as well as on resize, and that is not optional. Nunito arrives
after the first paint and sets taller lines than the system fallback, so a size measured before it
lands can overflow once it swaps in — measured at 557px of content in a 480px panel. The board only
looks right because it re-measures when the font arrives.

**The agenda's row budget.** `MAX_EVENTS = 5` is the budget for the whole agenda, not today's cap.
Today fills it first; tomorrow tops up whatever is left, capped again at `MAX_TOMORROW = 3` so it
stays a footnote even on an empty day. A five-event day therefore renders exactly as it did before
tomorrow existed. This is what "if there is space" means in code — a fixed row count, decided by a
pure function, rather than a layout measurement.

What those rows cost depends on which column is taller, so measure against a real config rather
than `config.example.yaml`. In two-column mode the side column (chores plus countdowns) usually
sets the page height, and the agenda grows into slack it was already wasting. On a config with
three chores and four birthdays the 800x480 root moves 14.23px -> 14.10px on a three-event day —
under 1% — and 14.23px -> 13.32px on a quiet one. The two-chore example config has a shorter side
column, so there the agenda *is* the constraint and the same change costs 8% and 13%. The stacked
single-column layout (an iPad in portrait) has no side column to hide behind and always pays the
full price, around 13-18%. Everything fits at all three sizes in every case. Raising either
constant spends more type size, so measure at `/preview` before you do.

**The shared waiting screen must work in both modes.** Refer to the settings button, **Write it
now**, rather than a shell command. Keep that label in sync with `settings/home.html` and see
[The first board](../PLAN.md#the-first-board) for scheduling behaviour.

In two-column mode the body is a grid, and **the note sits under the agenda, not across the
bottom**. The agenda is short on a quiet day while chores plus countdowns are not, so a full-width
note left the lower left quarter of an 800x480 panel empty. Under the agenda it balances the two
columns instead: on a five-event day the left column measures 311px against the side column's 312.

## Home screens and manifests

**Saving a page to a home screen.** `/` and `/settings/` each serve their own web app manifest
(`web/manifest.py` holds what they share), so a saved link gets the mark and a name instead of a
URL — the board full screen for a tablet used as the panel, the settings UI standalone on a phone.
They must keep **different `id`s**: share one and the phone treats them as a single app, so saving
the board would replace the settings icon. iOS reads none of the manifest; its icon and label come
from the `apple-touch-icon` link and `apple-mobile-web-app-title` in the page head, which is why
both are set on both pages. The PNGs in `web/static/` are drawn by `website/generate_favicon.py`,
which renders the same mark as the favicon at every size the site and the app need — the outputs
are committed, so Pillow stays out of `requirements.txt` (it is declared in `requirements-dev.txt`).
**Editing `favicon.svg` means re-running that script**, or the `.ico` and the PNGs keep serving the
old mark: `website/static/favicon.ico` sat two weeks behind its own SVG that way. The settings page offers this once and
remembers a "Not now" in `localStorage`; it hides itself when already running from a home screen.
Note that Chrome's own install prompt needs https, so on a home network it never fires and the
written steps are what people see.

## Measuring the board

Everything below is about *checking* a layout change, and every line of it was learned the
hard way.

- **Headless Chrome lies about the viewport.** `--window-size=800,480` renders into 800x393 — 87px
  short — while `--screenshot` still writes an 800x480 PNG, so the bottom fifth looks empty when it
  is simply not there. Add 87 to the height you want (`--window-size=800,567` gives a true 480), and
  confirm it by reading `window.innerHeight` out of the page rather than trusting the flag. Chrome
  also reuses a running instance unless each run gets its own `--user-data-dir`, which silently
  makes every size in a loop return the first one's numbers.
- **Do not trust `--window-size` for layout work at all.** Even with the +87 correction it has been
  seen to ignore the flag and report a 756x469 viewport, which silently puts the board on the wrong
  side of the `3/2` media query. Size the page with an **iframe of exactly the target dimensions**
  instead, the way `/preview` already does, and read the numbers out of `iframe.contentWindow`. That
  is deterministic; the flag is not.
- **The board's `<meta http-equiv="refresh">` stops headless Chrome ever exiting.** `--screenshot`
  and `--dump-dom` both hang until the timeout, though they do write their output first. Strip the
  tag when rendering a copy for measurement, and wrap the call in `timeout` regardless.
- The honest check is `scrot` over SSH on the Pi itself: a real 800x480 panel, a real kiosk browser,
  no capture artifacts. The board reloads itself every 5 minutes on a default config, so a change
  takes one reload to appear — check `refresh_minutes` before concluding it did not work.
