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

## Managed Postgres, created 8 September 2026

`dinkydash` — PostgreSQL 17.11, `db-s-1vcpu-1gb`, single node, **fra1**, $15.15/month. Cluster id
`a65a8bae-ea6e-4d0b-a162-b6821e1ddc1a`. Same size `qrpage-db` already runs.

What is on it:

| | |
|---|---|
| Databases | `dinkydash` (the app), `dinkydash_test` (the contract suite), `defaultdb` (unused) |
| Users | `doadmin` (primary), `dinkydash_app` (normal — what the app connects as) |
| Pool | `dinkydash-pool`, **transaction mode**, size 15, on port 25061 |

`migrations/001_initial_schema.sql` is applied: `families`, `users`, `login_tokens`, `agendas`,
`generations`, `content_history`, `calendar_health`, `schema_migrations`. The whole suite was run
against it with `DINKYDASH_TEST_DATABASE_URL` pointed at `dinkydash_test` — **490 passed, nothing
skipped**, which is the first time the store contract has run against real managed Postgres rather
than a CI service container.

**Two passwords were rotated the same hour, because `doctl` printed them.** `doctl databases create`
puts the full `doadmin` URI in its output, and `doctl databases pool create` does the same for the
pool's user — both landed in a terminal and an agent transcript. Both were reset through
`POST /v2/databases/{id}/users/{user}/reset_auth` within minutes and the printed ones are dead.
**Filter `doctl` database output.** The credential is in the success message, not in an error.

**Postgres 15 changed who may write to `public`.** The app user could not create tables until
`ALTER SCHEMA public OWNER TO dinkydash_app` was run as `doadmin` against each database. A fresh
cluster will need it again; the migration runner does not do it and should not.

**CI's Postgres was pinned to 16 and is now 17**, to match. `.github/workflows/test.yml` said
`postgres:16` with a comment claiming it tracked the managed cluster — written before the cluster
existed. Until 8 September 2026 CI was therefore proving migrations against a major the app does
not run. Postgres 15 changed who may write to `public`; a difference of that size is exactly what
the service container is there to catch. **When the cluster is upgraded, move that pin with it** —
`doctl databases get <id> --format VersionSlug` is the check.

**The cluster has no trusted sources, and that is a decision rather than an oversight.** It is
reachable from any address holding the password. Restricting it to the App Platform app was
proposed on 8 September 2026 and **declined by the owner: external tools need to reach the
database.** The concern was raised, repeated, and overruled, which is the owner's call to make.
Two things follow. Trusted sources accept a list, so a future middle ground is an allowlist rather
than all-or-nothing. And the password is now the only thing between the internet and other
families' calendars, which raises what a leak of `DATABASE_URL` costs — see the note above about
`doctl` printing them.

**App Platform's database binding (`${db.DATABASE_URL}`) is deliberately not used** for the same
reason. Attaching a cluster to an app adds that app to the cluster's trusted sources, which would
turn the open firewall into a restricted one as a side effect of a config change nobody read that
way. The connection strings are plain `SECRET` env vars instead.

## The deploy, 8 September 2026

`dinkydash-site` now serves both hostnames from one container, `wsgi.py` routing on the `Host`
header. `dinkydash.co` is the marketing site; `app.dinkydash.co` is the board, reading from
Postgres in cloud mode. Both verified live over TLS, and the `PRE_DEPLOY` migration job reported
`Schema is up to date`.

One family exists, seeded from `config.example.yaml` — invented people, no calendar URL — and
`DINKYDASH_FAMILY_ID` points at it. Nothing outside `tests/conftest.py` creates a family, so that
was done by hand and will be until the signup flow exists.

**Omitting the value of a `type: SECRET` env var does NOT work, and the way it fails is the
problem.** The earlier note here said it did, on the strength of a canary test: a throwaway
variable was set to a value, the spec re-applied without one, and `doctl apps spec get` still
showed `EV[...]`. That test was wrong — it checked the *display*, not the *runtime*. Applying a
spec with `type: SECRET` and no `value:` leaves the spec looking correct and hands the container an
**empty** variable. Two deploys died on `DATABASE_URL_DIRECT is not set` before this was understood,
and at no point did the spec look wrong.

So `.do/app.yaml` is the shape of the app, not something to apply directly. The values are merged
in from `.env` at apply time, through a temp file outside the working tree, and the file's own
header carries the snippet. **Never commit an `EV[...]` blob** either — encrypted or not, it is a
production credential in a world-readable repo.

**`deploy_on_push` does not apply the committed spec.** It rebuilds the components that already
exist from the new code. Adding a *component* — the `worker`, when it first landed — needs an
explicit `doctl apps update`. Merging a PR that adds both the code and the spec entry gets you the
code and not the component, which is a quiet way to think something shipped when it did not.

**The `worker` component and the `worker/` package have to land together.** Applying the spec from
a checkout without the package gives a component whose `run_command` cannot import, and a failed
deploy. The worker was held out of the first apply for exactly that reason, because the app deploys
from `main` and the code was still on a branch.

**The worker has been running since 8 September 2026, 10:58 UTC.** Its first pass refreshed the
seeded family's (empty) calendars, called Claude, and wrote a board — `Tuesday with no plans means
extra time together`, visible on app.dinkydash.co within seconds. A pass every 300 seconds after
that. There is no dead-man's switch yet (PLAN.md Phase 6), so a worker that stops looks exactly
like a quiet day: `doctl apps logs <id> worker --type run --follow` is the only check there is.


## Magic links, 8 September 2026 (DIN-38)

`/login`, `/login/link` and `/logout` exist in cloud mode. **Nothing creates a user yet** — sign-up
is a later issue — so the one family seeded from `config.example.yaml` needs a row inserted by hand
before anybody can sign in:

```sql
INSERT INTO users (family_id, email) VALUES ('<DINKYDASH_FAMILY_ID>', 'you@example.com');
```

One outstanding action, and it is a security one. **`.do/app.yaml` now sets a gunicorn
`--access-logformat`** built from `%(U)s`, so the sign-in link's `?t=` is not written to the
platform's log. `deploy_on_push` rebuilds components from new code and does **not** apply a changed
spec, so **until somebody runs `doctl apps update` the running service is still on gunicorn's
default `%(r)s`**, which is the whole request line. Applying it is the same merge-values-from-`.env`
dance as every other change to this file — see the header of the spec.

Meanwhile the code covers the gap: `web.routes.auth.NoTokens` is attached to both the `werkzeug` and
`gunicorn.access` loggers and replaces `?t=<token>` with `?t=[redacted]` in the message. That was
written after watching real tokens scroll past a local terminal, not from theory. DigitalOcean's own
edge logs are outside all of this and always will be; single use and fifteen minutes are what covers
them.

`SENDGRID_API_KEY` is already in the app's environment (DIN-36) and is the send-only key. The
per-address rate limit is three live links; the per-caller-address one is twenty an hour **per
process**, and the service runs `--workers 2`, so the real ceiling is forty and a redeploy resets
it. That is a bound on abuse, not a quota.


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
