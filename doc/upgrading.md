# Upgrading from an earlier version

Nothing to do to your config — it is migrated on load. But be aware:

- **New dependency.** `pip install -r requirements.txt` — `ruamel.yaml` is needed for the settings
  UI to write the config without destroying your comments.
- **`calendar_url` becomes `calendars`.** A single URL is migrated into a one-entry list. The
  settings UI will write the new shape back the first time you save.
- **`calendar_filter_emails` is gone.** It required every listed address to appear as an `ATTENDEE`
  on an event, which most personal calendar entries do not have — so it silently returned zero
  events. Add one feed per person instead. It is ignored with a warning in the log.
- **Photos are no longer used.** The board shows an agenda rather than person cards, so the `image:`
  fields do nothing, and the root `static/` folder that held the JPEGs is gone. `avatar_emoji` and
  `avatar_color` replace them, and are used in the settings UI. Old keys are harmless if left in
  place, but the photos themselves can be deleted.
- **Dates read as `25 December`,** not `December 25`.
- **The model default is now `claude-haiku-4-5`.** If your config pins
  `claude-sonnet-4-5-20250929`, it will keep using it — that model is dated, and newer models run
  adaptive thinking by default, which competes with `max_tokens` and can truncate the response.
  Either move to `claude-haiku-4-5` or `claude-sonnet-5`.
