# Design mockups

Visual mockups for the hosted MVP — the settings UI and the dashboard.
These are **design artefacts, not application code**. Nothing here is imported or
served by `app.py`; they exist so the layout and copy decisions can be reviewed
before the templates get written.

| Directory | What it covers |
|---|---|
| [`settings-ui/`](settings-ui/) | The logged-in family settings UI, mobile (390×844) |
| [`board-ui/`](board-ui/) | The dashboard itself, across TV / iPad / Pi, light and dark |

## Format

Each `*.dc.html` file is one artboard — a self-contained HTML page laid out at a
fixed pixel size, styled with inline styles lifted from `website/templates/`
(Nunito, `#fffaf5` ground, `#e85d24` accent, `#f0e6da` borders). `canvas.json`
positions them on a shared canvas and carries the annotations explaining each
design decision.

The `<script src="./support.js">` line and the `<x-dc>` / `<helmet>` wrappers are
required by the canvas editor these were authored in. Opening a `.dc.html`
directly in a browser renders it close enough to read, with two caveats: the
`{{qr}}` placeholder in `settings-ui/Screen.dc.html` stays empty, and headless
screenshots of a fixed-height artboard tend to drop the bottom ~70px — measure
`scrollHeight` against the frame rather than trusting a screenshot.

## Decisions recorded here

**Settings** — a hub whose rows carry live state, so a broken calendar feed
surfaces before you tap in. Chore rotation is an explicit ordered list plus a
next-week preview, making the day-of-year modulo visible. Adding a calendar
validates on paste and answers with a real event count.

**Dashboard** — no person cards; the agenda is the dashboard, at a size that reads across
a room. One prose box carries whatever the generator wrote that day rather than
three fixed slots. Wide-and-short screens (TV, Pi) get two columns, tall ones
(iPad) one — a real breakpoint, not the `vmin` scaling the current template uses.

**Stale state** — the payload has two halves. Ages, countdowns, chore rotation and
the agenda are computed and stay correct when generation fails; only the prose is
stale, so only the prose is marked and the AI headline gives way to a computed one.

**Colour scheme** — Light and Dark, chosen on the Screen link screen because the
colour belongs to the screen on the wall, not to the person editing. Dark is a
full palette swap: `#17120f` ground, accent lifted to `#ff7a45`, chore-pill tints
raised to stay visible.

## Known gaps

- Drag-to-reorder is not drawn; the "Reorder" affordance is a placeholder.
- The artboards put Cancel and Save in the app bar. The built UI does not (September 2026):
  the bar holds a labelled back button and the title, and Save ends the form.
- Post-trial lapse behaviour is not drawn. The built UI keeps the last dashboard on the wall for
  30 days after access ends, then shows only an ended-access message (DIN-52).
- The QR code is an illustrative pattern, not a scannable code.
- An Auto colour mode (dark after sunset, using the family timezone) is proposed
  in the annotations but not designed.
