# Product terminology

Checked against the application and website on 11 September 2026. This is the reference for
product copy, help pages, emails, accessibility labels, design mockups and marketing images.
Use British English and sentence case, except for the product name **DinkyDash**.

## The dashboard

**Dashboard** is the name of the complete DinkyDash display: the agenda, chore turns,
countdowns, headline and daily note. It replaces the former product term **board**.
Use **dashboard** in prose and **Dashboard** at the start of a heading or button.

A **screen** is the physical TV, tablet, monitor or Raspberry Pi panel showing a dashboard.
Several screens can show the same dashboard; changing its settings affects all of them.
A **calendar** is one source of events, not the whole dashboard.

## Glossary

| Term | Meaning | Current interface and usage |
|---|---|---|
| DinkyDash | The product | Preserve the capital D in both parts. |
| Dashboard | The complete household display | “Dashboard”, “View dashboard”, “Set up your dashboard”, “Write the first dashboard”, “Show on the dashboard”, “Dashboard colours”, “Name on the dashboard”. |
| Screen | A device displaying the dashboard | “The screen” in hosted settings; “Preview the screens” opens the device previews. Use dashboard when referring to the shared content. |
| Screen link | The address opened on a display device | “Screen link & QR code”, “Copy link”, “Change the link”. In hosted mode anyone with the link can view the dashboard; replacing it invalidates the previous link on every screen. |
| QR code | A scannable representation of the screen link | Available in hosted mode. It is another way to open the same dashboard, not a pairing code. |
| Settings | The area for configuring the household and dashboard | The home page for a signed-in hosted user, or `/settings` when self-hosting. |
| Family / household | The people sharing a dashboard and its settings | The current system stores one household per account. “Name on the dashboard” controls its displayed name. Do not imply that each person has a separate login. |
| Person / People | A household member | “People”, “Add a person”, “New person”, “Remove this person”. Birth date supplies the age and birthday countdown; names can participate in chores. |
| Pet / Pets | A household animal | “Pets”, “Add a pet”, “New pet”, “Kind of animal”. A pet can be mentioned in the generated daily note. |
| Chore / Chores | A household task assigned on a daily rotation | The section is “Chores”. Existing add/edit/remove copy still uses “job”; see the outstanding differences below. There is no completion checkbox. |
| Rotation order | The sequence of people who take a chore | The editor currently labels participants “Whose turn, in order”; lists use arrows between names. Do not describe these checkboxes as functioning ordering controls: that editor has an open rotation-order defect. |
| Whose turn | The current chore assignments | The dashboard section heading. Turns change daily; this is not task completion or an on-demand swap feature. |
| Calendar / Calendars | A connected source of events | “Calendars”, “Calendar name”, “Add a calendar”, “Save calendar”. Multiple enabled calendars merge into the agenda. The name is for recognising the source in settings. |
| Calendar link | The calendar provider's iCal/ICS subscription address | Field label: “Calendar link (iCal / ICS)”. HTTPS and `webcal://` are accepted; a provider's ordinary webpage or sharing page is not necessarily a calendar feed. |
| Guest filter | The optional restriction to events shared with selected email addresses | Visible label: “Only show events shared with”. Matching guests or organisers allow an event through. An empty field allows all events from that calendar. |
| On / Paused | Whether a calendar contributes events | List status labels. The edit checkbox is “Show on the dashboard”. Pausing keeps the calendar entry and clears its stored events. |
| Agenda | The combined event list | The dashboard labels it “Today” and, when there is room, “Tomorrow”. It is assembled from calendars; it is not AI-generated. |
| Headline | The large heading on the dashboard | Normally generated with the daily note. A stale dashboard can use a computed headline instead. |
| Daily note | The short generated text accompanying the agenda | Also called the “daily line” or “day's line” in current copy. Interests, pets and the agenda inform it. “Brief” is used internally for the generated headline and note together. |
| Special date / Special dates | A named annual occasion | “Special dates”, “Add a date”, “What is it”, “Date”. Day and month repeat every year; this is not a one-off calendar event. |
| Countdown | Days remaining until a birthday or special date | Appears under “Coming up”. Birthday countdowns come from People and need no duplicate special-date entry. |
| Refresh calendars | Fetch the latest events from enabled calendars | Updates the agenda; it does not rewrite the daily note. “Fetch the calendars” sets this interval under “How often it updates”. |
| Rewrite now | Generate a fresh headline and daily note | Also fetches calendars first. Before the first generation the action is “Write the first dashboard”. “Write the daily line at” sets the daily generation time. |
| Time zone | The household's clock for dates, events and daily generation | “Time zone” under “Family & system”, with a suggested local zone during setup. |
| Colours | The dashboard's light or dark appearance | “Dashboard colours”, choices “Light” and “Dark”. Self-hosted navigation calls the page “Colours”; hosted navigation calls it “The screen” because it also holds the screen link. Changes apply immediately. |
| Your data | The hosted account's export and deletion page | “Download my data” exports JSON. “Delete my account” removes the household and its saved data after email-address confirmation. |
| Sign-in link | The email link used to sign in or start a hosted dashboard | “Email me a link”, “Sign in or start a dashboard”. It works once and expires after fifteen minutes; it is distinct from the persistent screen link. |
| Trial | The initial hosted trial period | Fourteen days. Do not describe payment or renewal flows as available unless implemented. |

## Outstanding wording differences

The dashboard rename is applied throughout current product copy. These other differences remain
in the interface; they are recorded here so this reference does not mistake a recommendation
for a shipped change:

- **Chore / job:** the Chores section still uses “Add a job”, “New job”, “Job” and
  “Remove this job”. Prefer **chore** when that copy is standardised.
- **Calendar / feed:** settings summaries still say “1 feed” or “2 feeds”. Prefer **calendar**
  for the user-facing source; keep feed for implementation details or explaining the file format.
- **Daily note / daily line / brief:** current copy uses all three. “Daily message” for the
  headline-plus-note operation was proposed in the QA review; it has not been adopted as a new
  UI label. Distinguish the generated text from the agenda and from the complete dashboard.
- **This screen:** the settings group heading currently contains shared dashboard controls.
  Do not imply those changes affect only the device used to edit them.

Other observed functional and accessibility defects belong in the QA report, not in this glossary
as promises about supported behaviour.

## Implementation names and compatibility

Existing source files, Python names, Flask endpoint names, CSS classes, screenshot URLs and the
JSON export key `board` retain their technical spelling. Examples include `dinkydash/board.py`,
`web/templates/board.html`, `board.index`, `sample_board.py` and existing image paths. They are
implementation or compatibility identifiers, not approved product wording. A terminology edit
must not silently change a saved export format, a working link or an import.

When adding or changing a concept, update its entry here in the same change. Check the actual
labels in `web/routes/settings.py`, `web/setup.py` and `web/templates/`, then check sign-in
emails, website text, metadata, image captions and screenshots for the same wording.
