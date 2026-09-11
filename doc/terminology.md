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
| Dashboard | The complete household display | “Dashboard”, “View dashboard”, “Set up your dashboard”, “Show on the dashboard”, “Dashboard colours”, “Name on the dashboard”. |
| Screen | A device displaying the dashboard | “The screen” in hosted settings; “Preview the screens” opens the device previews. Use dashboard when referring to the shared content. |
| Screen link | The address opened on a display device | “Screen link & QR code”, “Copy link”, “Change the link”, followed by “Keep current link” / “Replace screen link”. In hosted mode anyone with the link can view the dashboard; replacing it invalidates the previous link on every screen. |
| QR code | A scannable representation of the screen link | Available in hosted mode. It is another way to open the same dashboard, not a pairing code. |
| Settings | The area for configuring the household and dashboard | The home page for a signed-in hosted user, or `/settings` when self-hosting. |
| Family / household | The people sharing a dashboard and its settings | The current system stores one household per account. “Name on the dashboard” controls its displayed name. Do not imply that each person has a separate login. |
| Person / People | A household member | “People”, “Add a person”, “New person”, “Remove this person”. Birth date supplies the age and birthday countdown; names can participate in chores. |
| Pet / Pets | A household animal | “Pets”, “Add a pet”, “New pet”, “Kind of animal”. A pet can be mentioned in the generated daily note. |
| Chore / Chores | A household task assigned on a daily rotation | “Chores”, “Add a chore”, “New chore”, “Chore”, “Remove this chore”. There is no completion checkbox. |
| Rotation order | The sequence of people who take a chore | “Whose turn, in order” shows the saved sequence. Checkboxes select people; arrows move them earlier or later. Newly selected people join at the end, and Save keeps the changes. This is separate from reordering People or the chore list. |
| Whose turn | The current chore assignments | The dashboard section heading. Turns change daily; this is not task completion or an on-demand swap feature. |
| Calendar / Calendars | A connected source of events | “Calendars”, “Calendar name”, “Add a calendar”, “Save calendar”. Multiple enabled calendars merge into the agenda. The name is for recognising the source in settings. |
| Calendar link | The calendar provider's iCal/ICS subscription address | Field label: “Calendar link (iCal / ICS)”. HTTPS and `webcal://` are accepted; a provider's ordinary webpage or sharing page is not necessarily a calendar feed. |
| Guest filter | The optional restriction to events shared with selected email addresses | Visible label: “Only show events shared with”. Matching guests or organisers allow an event through. An empty field allows all events from that calendar. |
| On / Paused | Whether a calendar contributes events | List status labels. The edit checkbox is “Show on the dashboard”. Pausing keeps the calendar entry and clears its stored events. |
| Agenda | The combined event list | The dashboard labels it “Today” and, when there is room, “Tomorrow”. It is assembled from calendars; it is not AI-generated. |
| Headline | The large heading on the dashboard | Normally generated with the daily note. A stale dashboard can use a computed headline instead. |
| Daily note | The short generated text accompanying the agenda | Interests, pets and the agenda inform it. A note is one part of the daily message; descriptive prose may call it a line, but this is not a separate feature. |
| Special date / Special dates | A named annual occasion | “Special dates”, “Add a date”, “What is it”, with “Day” and “Month” under “Date”. Lists use named months, such as “1 July”. Invalid stored dates are flagged for repair and omitted from countdowns; 29 February is allowed. |
| Countdown | Days remaining until a birthday or special date | Appears under “Coming up”. Birthday countdowns come from People and need no duplicate special-date entry. |
| Refresh calendars | Fetch the latest events from enabled calendars | Updates the agenda; it does not rewrite the daily note. “Fetch the calendars” sets this interval under “How often it updates”. |
| Daily message | The generated headline and daily note together | “Rewrite daily message” fetches calendars, then generates fresh text. Before the first generation the action is “Write first daily message”. “Write the daily message at” sets the schedule. Pending feedback says “Writing your daily message…”. |
| Time zone | The household's clock for dates, events and daily generation | “Time zone” under “Family & system”, with a suggested local zone during setup. |
| Colours | The dashboard's light or dark appearance | “Dashboard colours”, choices “Light” and “Dark”. Self-hosted navigation calls the page “Colours”; hosted navigation calls it “The screen” because it also holds the screen link. Changes apply immediately. |
| Your data | The hosted account's export and deletion page | “Download my data” exports JSON. “Delete my account” removes the household and its saved data after email-address confirmation. |
| Sign-in link | The email link used to sign in or start a hosted dashboard | “Email me a link”, “Sign in or start a dashboard”. It works once and expires after fifteen minutes; it is distinct from the persistent screen link. |
| Trial | The initial hosted trial period | Fourteen days. Do not describe payment or renewal flows as available unless implemented. |

## Copy conventions

Use **chore** for the household task and **calendar** for a connected event source in settings.
**Daily message** names the headline-plus-note generation; **daily note** names its short prose
part. Keep **brief** for implementation details. Use **Refresh calendars** for fetching events,
which does not generate a new daily message. “Feed” is appropriate when explaining iCal/ICS,
not as a competing settings label for a connected calendar.

“Your dashboard” groups settings shared by every screen. A **screen** is the physical device,
not a separate copy of the household settings. Removal confirmations name the item, and explain
any effects on chore rotations or stored calendar events. **Keep editing** / **Discard changes**
applies to leaving an unsaved form; **Keep current link** / **Replace screen link** applies to
revoking the shared screen address.

## Implementation names and compatibility

Existing source files, Python names, Flask endpoint names, CSS classes, screenshot URLs and the
JSON export key `board` retain their technical spelling. Examples include `dinkydash/board.py`,
`web/templates/board.html`, `board.index`, `sample_board.py` and existing image paths. They are
implementation or compatibility identifiers, not approved product wording. A terminology edit
must not silently change a saved export format, a working link or an import.

When adding or changing a concept, update its entry here in the same change. Check the actual
labels in `web/routes/settings.py`, `web/setup.py` and `web/templates/`, then check sign-in
emails, website text, metadata, image captions and screenshots for the same wording.
