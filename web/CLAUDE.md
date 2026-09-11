# The dashboard and the settings UI

Guidance for `web/`. The root `CLAUDE.md` holds the rules that apply to every change; this
file holds the ones that only bite here. Sizing conventions are in the root under
**Conventions** — this is the reasoning behind them and the traps in measuring them.

## Adding to the settings UI

**Adding a field to a settings section.** Add a tuple to the section's `fields` list in
`web/routes/settings.py` — `(name, label, kind, required, help)`. The list template and the edit
form both render from it, and `parse_field` reads it back. `kind` is one of `text`, `url`, `date`,
`monthday`, `textarea`, `checkbox`, `emoji`, `color`, `people`, `emails`. A new `kind` needs a
branch in `parse_field` and a branch in `web/templates/settings/edit.html`; nothing else.

**Validation errors belong to fields.** `validate` maps field names to messages. The editor links
an error summary to each control or fieldset, focuses the summary, and connects inline errors
with `aria-describedby` and `aria-invalid`. Grouped controls use legends; date parts and colour
choices also have individual names. Annual dates validate through `context.parse_monthday`,
which accepts 29 February but rejects impossible combinations. Invalid stored dates remain
editable in settings and are omitted from countdowns until repaired.

**A chore owns its participant order.** Render saved choices before unselected people and submit
them in that order. Reordering People or chores must not change it. The rotation picker moves
checked inputs in the DOM; without JavaScript, its update/move buttons redisplay the submitted
draft. Only Save persists it. Keep an initial hidden Save button so Enter still saves.

**`date` means a date of birth, and it is bounded.** The input carries `min` and `max` of
1900-01-01 and today, and `validate` refuses anything outside them, naming the year it received.
Both halves are needed: a phone's year wheel scrolls down to the year 1, and a mistyped year
used to be saved silently and show up on the People page as somebody 2,009 years old. A `date`
field that is not a birthday needs a kind of its own rather than a looser bound on this one.

**Adding a whole settings section.** Add an entry to `SECTIONS` and a row to
`web/templates/settings/home.html`. The list, edit, delete and reorder routes are generic and need
no changes.

**Every control has a hover, a press and a keyboard state, and a new one needs all three.** They
live at the foot of the shared sheet in `settings/base.html`. Hover rules sit behind
`@media (hover: hover)` — on a phone a hover is a tap that never ends, left glowing on the row
you just came back from — while `:active` and `:focus-visible` apply everywhere. The cue is one
the mockups set with `a:hover`: filled things darken, bare things get `--warm` or `--tint` behind
them, links underline, and nothing changes size. **An inline `style` on a button beats every one
of those rules**, which is why "Not now" and "Delete my account" became `.btn.quiet` and
`.btn.danger.fill` rather than keeping theirs; a new look for a button is a variant, not an
attribute. Two more things a pointer expects: `.btn:disabled` looks disabled and refuses the
cursor, and on a list page the link stretches over the whole row (`a.row-main::after`), so the
avatar and the pill open the item the way the home page's rows already did; anything that must
stay its own target inside a row sits above it the way `.move` does.

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

**A route that touches a store needs `session.guard`**, and the dashboard blueprint's `before_request`
is where that is decided. `board.healthz` is the one exemption and it is load-bearing: App
Platform's health check arrives with no cookie, and a 302 there fails it three times and rolls the
release back. It is also the only route that reads nothing, so it needs no family.

**`web/routes/screen.py` is the other exemption, and it is a separate blueprint for that reason.**
`/s/<token>` has no session by design — a wall panel cannot sign in — so it is not behind `guard()`
and never should be. What replaces the session is the token, resolved by `family.store_for_token`;
what replaces the guard is that the two routes there are GETs that reach a dashboard and nothing else.
Registered only in cloud mode, like `auth`. **In cloud mode `/` is a redirect**, so anything that
used to link to `url_for('board.index')` for a dashboard — the "View dashboard" button, `/preview`'s
iframes — uses `web.urls.board_path()`. Build absolute credential URLs with
`web.urls.absolute_url(path)`: it uses HTTPS and the configured `DINKYDASH_APP_HOST`, with the
request host as a development fallback. The login-link CLI shares the origin policy and accepts
an explicit local `--base-url`. QR codes are drawn by `settings/_screen_link.html`, included by
`/settings/screen` and by the last step of the set-up checklist, and nowhere else.

**`web/routes/admin.py` is the third blueprint only cloud mode registers, and its gate is a list.**
`/admin` (DIN-37) shows signups and activations by week and the newest accounts to the operator and
to nobody else: `guard()` first, so a signed-out visitor is sent to `/login` like everywhere else,
then `family.is_admin()`, which compares the signed-in account's address with
`DINKYDASH_ADMIN_EMAILS` and answers a miss with a 404 — never a 403, and an unset list is nobody.
Everything on it comes from `dinkydash/growth.py`: counts that read no family row, and a roster
that reads the address and bookkeeping columns and never the config — `tests/test_admin.py` puts a
named child and a labelled calendar on a family and asserts neither reaches the page. The chart is
inline SVG drawn from numbers the route works out (`admin.chart`), because arithmetic in a
template is arithmetic nobody tests. Its
two series colours are the shell's own `--accent` and `--purple`, checked as a pair on the card's
white with the dataviz palette validator (CVD ΔE 24.7, both above 3:1); a third series means
running it again, not picking a colour. `tests/test_admin.py` covers the gate, the bounds on
`?weeks=` and the drawing.

**The app bar holds the way back and the title, and never a Save.** A page that saves ends its
form with a full-width `.btn` Save, where the fields are, and the bar's left-hand button is
`icons.back_to(href, label)` — the chevron plus the *name of the page it goes to* ("Settings",
or the section title on an edit form), drawn as a bordered pill so the tap target is visible.
A header Save was tried and taken out: it sat in the shared chrome rather than with the form
it saved, and the bare chevron beside it was too small to read as a button. The calendar
form carries one unseen submit button ahead of "Test calendar link", because Enter presses
a form's first submit button and Enter should save there as it does everywhere else.

**Every form that writes needs one hidden field.** `<input type="hidden" name="csrf_token"
value="{{ csrf_token() }}">`, right inside the `<form>`. `csrf_token()` is a Jinja global set up by
`web/session.py`, so no route has to remember to pass anything — but a form without the field is a
400, in both modes, and `tests/test_auth.py` walks the templates and fails on one. There is
deliberately no switch to turn the check off; the test client in `tests/conftest.py` fills the field
in the way a browser does.

**The settings home has two personalities**, decided by `web/setup.py`. Until the family is set up
and its first dashboard written, the top of the page is a checklist — who lives here, time zone, a
calendar, the screen — and the daily controls (Refresh calendars, View dashboard, Rewrite now) are not
offered at all; after that it is the day's status card. A hosted family is created with an invented
household in it so the dashboard has something to show (DIN-41), each person and pet marked
`invented: true`, and step one names what is still marked. Saving the item from the edit form
clears the mark; renaming a person follows into the chores that name them, and removing one drops
them from those rotations. **The signal is the config, not the mode** — a freshly cloned Pi running
the untouched example file is in the same state — so there is no `cloud` branch in it, and it
leaves on its own. Nothing to dismiss and nothing remembered. The engine asks the same question
(`config.is_set_up`) before writing a brief, so the page and the tick cannot disagree. The time
zone step reads the phone's own zone with `Intl.DateTimeFormat` and offers it as one tap to
`POST /settings/timezone`, which refuses any name `zoneinfo` does not know.

**Two chromes, one base.** `settings/base.html` is the phone-shaped shell for everything a person
signs into — the settings pages and, in cloud mode, `auth/login.html` and `auth/sent.html`. The
manifest link in its `<head>` is a `{% block manifest %}` so the login page can drop it: the
manifest route is behind the login, and asking for it from outside would only ever be a redirect.

**`cloud` is the template global for the mode**, not Flask's `config`. The settings pages pass the
*family's* config dict under that name and shadow the app's, which is why `create_app` sets a
separate `cloud` boolean — the Sign out button on the settings home is the first thing to use it.

Hosted refreshes and feed checks take the same account-access check as generation. Hiding a
button is not enforcement. `current_access()` supplies the settings status; the token route
resolves access for its own family and passes it to `render_board`. Lapsed dashboards hold the last
brief's date for 30 days, then show only the ended message, with the same no-store headers and
reload timer. Export, deletion and settings remain accessible. Exports include both all retained
`generations` and the separate recent `content_history`; the latter alone omits older briefs.

## The dashboard's layout

**Changing the dashboard layout.** Everything is sized in `rem` off one root value, so check all three
sizes at `/preview` rather than just the one you are looking at.

That root value is now *measured*, not guessed. A short script at the foot of `board.html` binary-
searches the largest `html { font-size }` whose content still fits the viewport, capped at
`min(26px, vh/24)`. The CSS `clamp()` stays as the no-JS fallback. Because `body` is
`height:100vh;overflow:hidden`, nothing ever reports an overflow — so the script lets the page lay
out freely for one measurement (`height:auto`) and puts it straight back.

**Nunito is served from `web/static/fonts/`, not from Google**, as one variable font per subset
(`nunito-latin.woff2`, `nunito-latin-ext.woff2`, covering weights 200-1000 so every weight the dashboard
asks for comes out of one download). `web/templates/_fonts.html` holds the `@font-face` rules and the
reasoning, inline in every page's head with a preload of the Latin file — a stylesheet cost each page
one more round trip before the font could start; `website/static/` has its own copy plus the italic
pair the marketing site uses. Editing
either means editing both — they are separate deployables on purpose, and `website/` never runs on
the dashboard. The files are byte-for-byte what Google was serving, so the metrics did not change; what
changed is that a screen at `/s/<token>` no longer tells Google that URL, and a Pi with no internet
renders the same dashboard rather than falling back to a system font.

It re-fits on `document.fonts.ready` as well as on resize, and that is not optional. Nunito arrives
after the first paint and sets taller lines than the system fallback, so a size measured before it
lands can overflow once it swaps in — measured at 557px of content in a 480px panel. The dashboard only
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

**The shared waiting screen must work in both modes.** Refer to the settings button, **Write the
first dashboard**, rather than a shell command. Keep that label in sync with `settings/home.html` and
see [The first dashboard](../PLAN.md#the-first-dashboard) for scheduling behaviour. It has two wordings,
chosen by `view.set_up`: "writing your first dashboard" when one is on its way, and "nearly there"
while the family is still setting up and nothing is being written.

In two-column mode the body is a grid, and **the note sits under the agenda, not across the
bottom**. The agenda is short on a quiet day while chores plus countdowns are not, so a full-width
note left the lower left quarter of an 800x480 panel empty. Under the agenda it balances the two
columns instead: on a five-event day the left column measures 311px against the side column's 312.

## Home screens and manifests

**Saving a page to a home screen.** `/` and `/settings/` each serve their own web app manifest
(`web/manifest.py` holds what they share), so a saved link gets the mark and a name instead of a
URL — the dashboard full screen for a tablet used as the panel, the settings UI standalone on a phone.
They must keep **different `id`s**: share one and the phone treats them as a single app, so saving
the dashboard would replace the settings icon. iOS reads none of the manifest; its icon and label come
from the `apple-touch-icon` link and `apple-mobile-web-app-title` in the page head, which is why
both are set on both pages. The PNGs in `web/static/` are drawn by `website/generate_favicon.py`,
which renders the same mark as the favicon at every size the site and the app need — the outputs
are committed, so Pillow stays out of `requirements.txt` (it is declared in `requirements-dev.txt`).
**Editing `favicon.svg` means re-running that script**, or the `.ico` and the PNGs keep serving the
old mark: `website/static/favicon.ico` sat two weeks behind its own SVG that way. The settings page offers this once and
remembers a "Not now" in `localStorage`; it hides itself when already running from a home screen.
Note that Chrome's own install prompt needs https, so on a home network it never fires and the
written steps are what people see.

**"View dashboard" opens the dashboard in its own tab, and so does the "Dashboard" link beside it.** The dashboard
is the wall panel: full screen, no link out, and it reloads itself for years. Opened in the same tab
from a settings page saved to a phone's home screen it was a dead end — a saved web app has no
address bar and, on an iPhone, no Back button, so the way out was to force-quit the app; and in a
Safari tab every self-reload adds a history entry, so Back needed one tap per reload spent looking.
Its own tab is a way back the dashboard never has to draw: a tab to close, an in-app sheet with Done on
iOS, a custom tab with an X on Android. **Do not answer this with a Settings control on the dashboard.**
A tablet set up in the same tab would keep it on the wall, because the reload keeps the URL; and
hosted, a tap on it from a panel with no session lands on `/login`, which has no reload timer, so
the wall stays there. `tests/test_settings.py` asserts the tab and the dashboard's lack of a way back.

**Copy and Share beside the screen link are the browser's own** — `navigator.clipboard` and
`navigator.share`, in `settings/_screen_link.html`. Nothing is fetched and nothing leaves the page
except by the person's hand. Share needs https, so a Pi on plain http gets Copy alone, by way of
the selection; without JavaScript neither button is drawn and the text is still one tap to select.
Hosted, the daily card also carries a **Screen link & QR code** button to `/settings/screen`: the
link is the finish line of the product, and as the ninth row down it was not found.

## Static files, and moving between pages

**Every static URL goes through `static_url()`, never `url_for('static', ...)`**, and
`tests/test_static_assets.py` walks `web/` to make sure. `web/assets.py` puts the file's content
version on the URL — `?v=` and twelve hex digits of its SHA-256 — and answers a request carrying the
current version with a year of `Cache-Control` and `immutable`. A bare URL, or one with the version
from before a deploy, keeps Flask's `no-cache`. That is the whole difference between a tap that
draws at once and one that asks the server about the font first: Flask's default made every
navigation pay for the stylesheet and then the font again, one after the other, after the page.

**A static response carries no session.** `web/session.py` skips `save_session` for the static
endpoint, because Flask re-signs a permanent session on every response and marks the response
`Vary: Cookie` — and a font that varies on a cookie whose value changes with every page is one no
cache can ever match. Put a cookie on a static response and the year silently stops working.

**The settings shell crossfades between pages and renders the next one early.** Both live in
`settings/base.html`, and browsers that do not know them ignore them. `@view-transition
{ navigation: auto }` turns the cut into a 150 ms fade (Chrome 126+, Safari 18.2+). The
`speculationrules` block has Chrome (121+) fetch and render whichever `/settings/` link the pointer
hovers or a finger touches down on, so the tap lands on a page that is already there. **Every page
under `/settings/` is a read on GET, and has to stay one**: a prerender runs the page. The data
export is the one link that is not a page, and it is excluded by name — a new link that downloads,
charges or writes on GET goes in the same `not` clause. Forms are not links and are never
speculated. The dashboard is outside the pattern on purpose: it reloads itself, and `/preview` renders
it three times over.

## Measuring the dashboard

Everything below is about *checking* a layout change, and every line of it was learned the
hard way.

- **Headless Chrome lies about the viewport.** `--window-size=800,480` renders into 800x393 — 87px
  short — while `--screenshot` still writes an 800x480 PNG, so the bottom fifth looks empty when it
  is simply not there. Add 87 to the height you want (`--window-size=800,567` gives a true 480), and
  confirm it by reading `window.innerHeight` out of the page rather than trusting the flag. Chrome
  also reuses a running instance unless each run gets its own `--user-data-dir`, which silently
  makes every size in a loop return the first one's numbers.
- **Do not trust `--window-size` for layout work at all.** Even with the +87 correction it has been
  seen to ignore the flag and report a 756x469 viewport, which silently puts the dashboard on the wrong
  side of the `3/2` media query. Size the page with an **iframe of exactly the target dimensions**
  instead, the way `/preview` already does, and read the numbers out of `iframe.contentWindow`. That
  is deterministic; the flag is not.
- **The dashboard's `<meta http-equiv="refresh">` stops headless Chrome ever exiting.** `--screenshot`
  and `--dump-dom` both hang until the timeout, though they do write their output first. Strip the
  tag when rendering a copy for measurement, and wrap the call in `timeout` regardless.
- The honest check is `scrot` over SSH on the Pi itself: a real 800x480 panel, a real kiosk browser,
  no capture artifacts. The dashboard reloads itself every 5 minutes on a default config, so a change
  takes one reload to appear — check `refresh_minutes` before concluding it did not work.
