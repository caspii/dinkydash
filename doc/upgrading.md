# Upgrading from an earlier version

Nothing to do to your config — it is migrated on load. But be aware:

- **New dependency.** `pip install -r requirements.txt` — `ruamel.yaml` is needed for the settings
  UI to write the config without destroying your comments.
- **`calendar_url` becomes `calendars`.** A single URL is migrated into a one-entry list. The
  settings UI will write the new shape back the first time you save.
- **`calendar_filter_emails` becomes `shared_with` on that calendar.** The old key was one filter
  for the one `calendar_url`, so it moves onto the entry that URL is migrated into. It also works
  differently now: any one listed address is enough rather than all of them, and the organiser of
  an event counts as well as its guests — the old rule required every address as an `ATTENDEE`,
  which most personal calendar entries do not have, so it silently returned zero events. If your
  config already has a `calendars:` list, there is no way to tell which feed the old key meant, and
  it is dropped with a warning in the log; set **Only show events shared with** on the right
  calendar in the settings UI instead.
- **Photos are no longer used.** The board shows an agenda rather than person cards, so the `image:`
  fields do nothing, and the root `static/` folder that held the JPEGs is gone. `avatar_emoji` and
  `avatar_color` replace them, and are used in the settings UI. Old keys are harmless if left in
  place, but the photos themselves can be deleted.
- **Dates read as `25 December`,** not `December 25`.
- **The model default is now `claude-haiku-4-5`.** If your config pins
  `claude-sonnet-4-5-20250929`, it will keep using it — that model is dated, and newer models run
  adaptive thinking by default, which competes with `max_tokens` and can truncate the response.
  Either move to `claude-haiku-4-5` or `claude-sonnet-5`.
