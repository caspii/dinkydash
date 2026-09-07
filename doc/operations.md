# Operations log

State of the running system, and what has been done to it. This is a **log, not guidance** —
it records what was true on a date, and it is not loaded into any agent's context. The
standing rules live in `CLAUDE.md`. If something here hardens into a rule, move it there.

## Secrets and `.env`

**`.env` should hold `ANTHROPIC_API_KEY` and nothing else.** `FLASK_ENV`, `SECRET_KEY`,
`DATABASE_URL`, `UPLOAD_FOLDER` and `MAX_CONTENT_LENGTH` are leftovers from an abandoned plan and
none of them is read by any code — a grep over the repo returns only `web/__init__.py`, and that
reads `DINKYDASH_SECRET_KEY`, a different name. **They are all still there**, as of 7 September 2026:
in the main checkout, on the Pi, and in every new worktree. `.env` is not in git, so stripping it in
a worktree dies with that worktree, and the next workspace is seeded from the main checkout again —
which is why an earlier note in `CLAUDE.md` claiming they had been stripped did not stay true. Every copy has
to be edited where it lives, including the Pi's, whose `.env` `deploy_to_pi.sh` does not overwrite.
Do not put `SECRET_KEY` back: nothing calls `from_prefixed_env`, so Flask never sees it, and the
session key comes from `DINKYDASH_SECRET_KEY` or the hardcoded fallback whatever `.env` says.

**The Anthropic key was rotated on 7 September 2026** (DIN-20), after living on a Pi and having
been rsynced. The old key now reads 401 from the API; the new one is in `.env` in the main checkout
and on the Pi, written in place. CI could not have done it, and a future rotation is the same manual
job: revoke in the Anthropic console, then edit each copy where it lives. `deploy_to_pi.sh` excludes
`.env`, so pushing one copy over the other is not an option and is not meant to be.

## GitHub's own secret scanning

**Do not rely on it yet.** Minutes after it was enabled, a correctly shaped fake
`sk-ant-api03-` key and a correctly shaped fake AWS key pair were both pushed to a scratch
branch without being blocked, and neither raised an alert — so the settings report enabled
while nothing observably enforces. GitHub rescans a repo from scratch when the feature is
turned on, so this may simply have been the backfill; re-test on a scratch branch before
treating a rejected push as the safety net. **gitleaks is the layer that was actually
observed to work**: it failed the build on that same fake key, and `--redact` kept the value
out of the CI log.

## Raspberry Pi deployment

`deploy_to_pi.sh` rsyncs the code to the Pi — protecting the Pi's own `config.yaml`, generated data
and `.env`, and with `--delete` clearing anything dropped from the repo — creates the virtualenv if
it is missing, installs dependencies, and restarts the `dinkydash.service` systemd unit when it is
installed. Host, user and target directory are overridable with the `PI_HOST`, `PI_USER` and
`PI_DIR` environment variables; `--dry-run` shows what a deploy would change without touching the Pi.

Generation runs via cron:
```
*/5 * * * * cd /home/pi/dinkydash && venv/bin/python generate.py --tick >> generate.log 2>&1
```
Each tick does only what `config.yaml` says is owed, and logs nothing when that is nothing — "not
due" is at DEBUG precisely because it is the answer to roughly 260 of the day's 288 ticks. A tick
that overruns its slot makes the next one skip rather than double up, so the interval is a floor and
never a guarantee. The old
`0 6 * * * generate.py` line still works and does both halves at once; use one or the other, not
both. A failed run leaves the previous board in place rather than blanking the screen, the board
labels itself stale, and the next tick tries again.
