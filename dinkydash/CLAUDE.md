# The engine, the storage seam, and the clock

Guidance for `dinkydash/` and `migrations/`. The root `CLAUDE.md` holds the rules that apply
to every change; this file holds the ones that only bite here.

## The storage seam

Seven operations, on one object, and nothing above them knows what is behind it:

```python
load_config()                save_config(config, invalidate_calendars=())
load_payload(config)         save_agenda(config, agenda)
                             save_brief(config, brief)
recent_notes(config, days)   record_note(config, entry, keep)
```

Both implementations exist. `FileStore(config_path)` is `config.yaml` and two JSON files in one
directory. `PostgresStore(pool, family_id)` is the same seven operations against rows, with the
payload composed from `generations` (the brief) and `agendas` (the fetched window) and handed back
as the same dict. The runner takes a store; web routes get theirs from
`web.family.current_store()`. `create_app(store=None, *, pool=None)` accepts a store in single
mode or a pool in cloud mode. Cloud stores are scoped to the authenticated request.

These rules keep the storage contract consistent:

- **`store.py` and `config.py` are the only files under `dinkydash/` that open a file**, and
  `pgstore.py` and `db.py` are the only ones that import psycopg. `grep -rn "open(" dinkydash web`
  is the check, and it should stay that short. A new file read anywhere else is a caller that cloud
  mode will have to fork. `accounts.py` queries Postgres and still imports no driver: it is handed
  a pool and asks it for connections, which is the shape anything cloud-only should copy.
- **`data_file` and `content_history_file` are storage-layer keys.** They stay in `DEFAULTS` and in
  `config.example.yaml` for compatibility, and only `FileStore` reads them. They mean nothing hosted.
- **The store is passed, never constructed, below the entry points.** `generate.py`, `app.py` and
  `sample_board.py` build one; everything else is handed it.
- **The board is read whole and written in halves, and neither half can write the other's keys.**
  `save_agenda` drops anything that is not in `store.AGENDA_KEYS`; `save_brief` drops anything that
  is. Enforced by the store rather than by the caller, because the caller that would get it wrong is
  `write_brief` — it reads the payload, waits seconds on a model call, and writes, so the agenda in
  its hand is stale by then (DIN-28). Each half is **replaced, not merged into**: a key the caller
  stops sending disappears, because that is what whole-row writes do in Postgres, and a stale value
  surviving on a Pi but not in the cloud is exactly the divergence the seam exists to prevent.
  `FileStore` takes a short `flock` **on the config directory** for settings and payload writes — a
  lock file beside the data would have to be kept out of `deploy_to_pi.sh`'s `rsync --delete`, and a
  deploy landing mid-write would otherwise unlink the inode a running tick still held, leaving the
  next writer to lock a fresh file and serialise against nobody. This also covers a `data_file`
  in another directory. Cloud mode stores the two halves in separate rows.
- **Settings saves invalidate affected calendars before another refresh can publish.** Both
  stores compare the fetch's calendar settings with the saved config inside the write lock;
  `save_agenda` returns `False` if they differ. `save_config` clears changed labels and the fetch
  stamp under that same lock, with an optional `invalidate_calendars` for an explicit Save of
  unchanged values. Postgres uses a family-row lock and one transaction; FileStore clears the
  agenda before replacing the config. No network call holds either lock. Item ID backfills and
  unrelated settings preserve the agenda; changing the timezone or fetched window clears it.
- **`tests/test_store_contract.py` runs every one of its assertions against both**, parametrised over
  the two backends with no branching. That parity is most of the value of having named the seam: a
  suite that only ran against files would not notice the day the two drifted. The Postgres half
  skips unless `DINKYDASH_TEST_DATABASE_URL` is set, so a self-hoster with no database still gets a
  green suite — and CI runs the suite twice, once with the variable and once without.

**Every `PostgresStore` query is scoped to `self.family_id`.** There is no unscoped read and no
unscoped write in that file, and there must never be one. That only protects anybody if the id the
store was *built* with is trustworthy, which is `web/family.py`'s job: in cloud mode it comes from
the session and from nowhere else, and one store is built per request. `PostgresStore` is two
attributes round a pool and costs nothing to build; the pool is process-wide and must stay that way.

`load_config` raises **`NoSuchFamily`**, a named `LookupError`, because the web app handles it — a
thirty-day session can outlive the account it names, and that should sign the holder out rather than
500. Catching the bare parent would swallow `KeyError` and `IndexError` too, which is to say every
real bug, and send it to the login page.

Three things are unscoped, all deliberately outside the store rather than weakening it, and each
because there is no family to scope *to* yet:

- **`worker.family_ids`**, whose whole job is to walk every family;
- **`dinkydash/accounts.py`**, which resolves an email address to a user before there is a family.
  A magic link has to find exactly one person without being told which family they belong to, which
  is why `users.email` is globally unique;
- **`dinkydash/screens.py`**, which resolves a screen token to a family. A wall panel has no session
  to scope to and never will — that is what the token is for.

Each of the three hands its result to a `PostgresStore` built for exactly one family, so the rule
that matters is untouched. `web/family.py` is where the last two arrive, and it has both doors in
one file on purpose: if a third is ever added it should be as obvious as those two are.

## Signing somebody in, and signing somebody up

`accounts.py` is the token lifecycle and nothing else: mint, hash, spend, sweep. Four things in it
are load-bearing, and each is asserted in `tests/test_auth.py`:

- **Only the hash is stored.** The plaintext exists for the length of one email. SHA-256 rather
  than a slow KDF, because 32 bytes from `secrets` has nothing to guess and bcrypt would only make
  every login slower.
- **Single use is one statement.** `UPDATE ... WHERE token_hash = %s AND used_at IS NULL AND
  expires_at > now() RETURNING user_id` decides and marks together, so two clicks — or a mail
  scanner arriving a second before the person — cannot both come back with a user. A read-then-write
  would pass every test that ran the two in order.
- **Time comes from Postgres.** `now()` is the transaction clock, one clock for however many web
  instances, and it cannot drift out of step with the row it is compared to.
- **Expired, spent and never-issued are one answer.** `consume_link` returns `None` for all three,
  so there is nothing for a caller to leak by accident.

Login and signup share `_issue_link`: at most `MOST_LIVE_LINKS` unexpired tokens per subject,
including used tokens. A transaction advisory lock serialises issuance for the user id or normalised
signup email. Acquire it before the INSERT so READ COMMITTED sees the previous issuer's commit;
putting the count inside an INSERT alone does not prevent concurrent requests exceeding the limit.
The per-IP limit in `web/ratelimit.py` is in-process.

**Sign-up is the same token and the same `consume_link`** (DIN-41). An address with no account gets
a row carrying the address instead of a `user_id`; spending it creates the family, the parent and a
starter config in the transaction that spent it. Five things about that are deliberate:

- **The family is created on the click, never on the submit.** A `families` row starts a 14-day
  trial and the worker calls Anthropic daily for it, so a POST that created one would be a way to
  spend our money without a card. Verifying first makes an unverified sign-up cost one row and one
  email. The reasoning in full is in [PLAN.md](../PLAN.md#sign-up).
- **One table, not two.** `login_tokens.user_id` is nullable with an `email` beside it and a CHECK
  that exactly one is set. A `signup_tokens` table would have meant a second single-use `UPDATE`,
  and that statement is the thing the whole design rests on — written twice, one copy drifts.
- **A sign-up token is outside every cascade.** It has no `user_id`, so deleting a family does not
  reach it; the sweep does, fifteen minutes later. That is fine in production and it bit the test
  suite, where the scratch database is reused between runs — `tests/conftest.forget_unowned_rows`
  is what stops three abandoned sign-ups silently exhausting `MOST_LIVE_LINKS` on the next run.
- **Two links for one new address must not make two families.** `_start_a_family` looks the address
  up first and the INSERT that follows carries `ON CONFLICT DO NOTHING`; losing that race means
  deleting the family just made, which nothing else can have seen.
- **The screen token is generated and checked in the same statement**, so the UNIQUE index is the
  backstop rather than the error path. A collision at 59 bits is not something anyone will see, but
  an unhandled one would spend somebody's sign-up link and hand them a 500.

## What a call is allowed to cost

`budget.py` is the breaker, and it is injected the way a store is: `write_brief(config, store,
budget=...)`. Single mode passes nothing and gets `NoBudget`, because a self-hoster's key is their
own bill; cloud mode passes `budget.for_family(pool, family_id)`, built in the one place that knows
both the pool and the family — `worker.tick_all` and `web/family.current_budget()`.

Five things in it are load-bearing, and `tests/test_budget.py` asserts each:

- **Calls, not money.** A price table in code goes stale silently and in the wrong direction: it
  under-counts after a price rise, which is exactly when a breaker matters. A call is exact and is
  knowable before it is made.
- **Charged on the attempt, not on success.** A revoked API key fails every call and reports no
  usage. Counting successes would let a five-minute retry loop pay for input tokens for ever.
- **The per-family cap appears in the statement twice, and that is not redundant.** An upsert has
  two paths: `DO UPDATE ... WHERE` covers the update and is evaluated against the locked row, which
  is what makes it exact — and the source `WHERE` covers the *first call of the day*, when there is
  no row to conflict with. Written with only the first, a cap of `0` let every family through once
  daily, so the brake that exists to stop all spending was the one setting that could not.
- **The global cap is approximate and says so**, by at most the number of simultaneous callers.
  Its check reads a daily aggregate before the charge. A trigger atomically adds successful
  charges to `global_model_spend`, which has only a date and count and survives family deletion.
  Keep the trigger: older instances still write `model_spend` during pre-deploy migrations.
- **A refusal is an `OverBudget`, a subclass of `GenerationError`.** That is what lets every caller
  keep the board on the wall with no new branch — "a failure is not handled, it is simply due again"
  already covers it. A second kind of failure would mean a second keep-last-good path.

The **calendar refresh is outside the budget**. A fetch costs HTTP requests to somebody else's
server, not money, and a family who cannot afford a new headline today should still have an
accurate agenda under yesterday's.

The budget also supplies `generation_config(config)` at the shared `write_brief` boundary
(DIN-51). `NoBudget` preserves the self-hoster's settings; `PostgresBudget` returns a copy with
the platform's `DEFAULT_MODEL` and `DEFAULT_MAX_TOKENS`. Do not read the mode from the environment
inside the engine or trust saved family model overrides. Both hosted entry points must continue
to pass the same budget; API-stub tests cover worker ticks and manual rewrites.

## Cloud mode: schema, migrations, connections

`migrations/*.sql` is plain SQL applied in filename order by `migrate.py`, which records each one in
`schema_migrations`. No ORM and no Alembic — seven tables and one jsonb document do not need one.
App Platform runs it as a **pre-deploy job**, so a failed migration fails the deploy rather than
half-updating a live app.

Three things about that runner are load-bearing:

- **The connection must be autocommit.** Without it psycopg opens an implicit transaction on the
  first statement, and `conn.transaction()` entered inside one is a *savepoint*, not a `BEGIN`.
  Every migration then appears to apply, releases its savepoint, and is discarded when the
  connection closes — no error, no tables, an empty `schema_migrations`. This was written wrong once
  and caught by running it.
- **A migration containing `-- no-transaction` is applied statement by statement, outside a
  transaction**, because `CREATE INDEX CONCURRENTLY` refuses to run inside one. Those cannot be
  all-or-nothing, so they have to be safe to re-run — every index in them is `IF NOT EXISTS`.
- **Migrations connect with `DATABASE_URL_DIRECT`, not `DATABASE_URL`.** The first is the cluster,
  the second is DigitalOcean's transaction-mode pool, which is the wrong end for schema work and for
  `pg_dump`.

Connections go through `dinkydash/db.py`. `pool()` is a small bounded `psycopg_pool` — its size is a
latency knob, not a safety one, because DigitalOcean's own pool is what stops the cluster's 22
connections running out. **`prepare_threshold` is set to `None` on every connection**, everywhere,
including local development and CI: psycopg 3 prepares a statement server-side once it repeats, and
under transaction-mode pooling the next execution can land on a different backend connection. The
full reasoning, and why KeepTheScore's clean record on psycopg2 does not transfer, is in PLAN.md
under [Connection pooling](../PLAN.md#connection-pooling).

**`psycopg` is in `requirements-cloud.txt`, not `requirements.txt`.** A Pi has no database and
should not install a driver for one, so single mode never imports `pgstore` or `db` — the import in
`create_app` is inside the cloud branch on purpose. **App Platform's Python buildpack installs
`requirements.txt` on its own**, which is deliberately the smaller list, so the app spec carries a
`build_command` that installs `requirements-cloud.txt` instead. `gunicorn` is in that file for the
same reason: a Pi serves with Flask's own server and should not carry a production WSGI server it
never starts.

## What the payload holds, and what it does not

The payload stores only what cannot be recomputed: the model's `headline` and `note`, plus the
fetched calendar window (14 days, not just today). Chores, countdowns and ages are pure functions of
config + date, so `board.build_view` recomputes them on every render.

That split is deliberate and load-bearing: when a morning's generation fails, the times, turns and
countdowns on the wall are still **today's** — only the written line is old, and the board says so.
Yesterday's fetch reached 14 days ahead, so today's agenda is still in it. The stale headline is
replaced by a computed one (`"3 things on today, starting at 08:20."`) because a day-old AI headline
can be actively wrong.

That same 14-day window is where **tomorrow's** agenda comes from, so it survives a failed run too.

The payload carries two stamps, **both in UTC**: `generated_at` (when the brief was written) and
`calendars_fetched_at` (when the feeds were last fetched, and what `schedule.due` reads). UTC
because the server is routinely not on the family's clock — a Pi is often left on UTC, and hosted
the server is nowhere near them. They are rendered in the family's timezone at the point of display,
which on the settings home is `_clock(stamp, tzinfo)`. It used to slice the characters out of the
ISO string, which showed the server's hour (PLAN.md bug 9).

## Two cadences, one tick

The fetch and the model call ran together only because history put them there, and it meant an
appointment added at 09:00 was not on the wall until the next morning. They now run on their own
clocks, chosen by the family (PLAN.md decision 11, single-mode half):

```
[cron */5m] -> generate.py --tick -> schedule.due(config, payload, now)
                                       refresh? -> runner.refresh_calendars()
                                                     fetch every enabled feed, merge, sort
                                                     write events + calendars_fetched_at
                                       brief?   -> runner.write_brief()
                                                     build the prompt, call Claude
                                                     write headline + note, append to history
                                       neither  -> exit 0, silently

[browser]   -> app.py             -> board.build_view(config, payload, today)
                                       renders web/templates/board.html
```

`refresh_minutes` (default 60) and `brief_time` (default `"06:00"`, on the family's clock) are
ordinary config keys, so they migrate through `with_defaults` and will survive as a `jsonb` column.
`runner.run` is still both halves in order, which is what a plain `python generate.py` and the
settings page's **Rewrite now** do — the old `0 6 * * *` line keeps working, it just never sees a
same-day change. **Refresh calendars**, beside it, is `refresh_calendars` alone: no key needed, no
money spent, and the thing most people pressing the other button actually wanted.

Both keys are edited at `/settings/refresh` rather than in YAML. The select offers five intervals
and nothing else, but it also offers **whatever the file already says** — a hand-edited
`refresh_minutes: 45` has to survive somebody opening the page and pressing Save, or the UI quietly
overrules the file. `brief_time` is written back through `config.quoted()`: bare `06:00` is a string
to ruamel and a sexagesimal integer to a YAML 1.1 parser, and this file is meant to be hand-editable
with either.

**The board's own reload is derived, not stored** (`board.reload_seconds`). Five minutes is the
ceiling; only a `refresh_minutes` shorter than that lowers it, because reloading faster than the
calendars are fetched just redraws the same thing. A parent picks "how soon does a change show up",
not a browser knob — so there is no separate setting for it and the template reads
`view.reload_seconds` rather than deciding.

These rules hold this together:

- **`due()` is pure and takes `now` as an aware datetime.** No clock, no I/O. That is what lets the
  same function drive a Pi's cron tick and, later, a worker loop walking every family. A brief is
  due when `generated_for_date` is not today *in the family's timezone* and the local clock has
  passed `brief_time`; a refresh is due when `calendars_fetched_at` is missing or older than
  `refresh_minutes`.
- **The first brief is due immediately** when `generated_for_date` is absent. Calendar-only
  payloads still qualify. See [The first board](../PLAN.md#the-first-board) for retry behaviour.
- **A refresh must not touch `headline`, `note` or `generated_for_date`**, and it now cannot: it
  writes through `store.save_agenda`, which only accepts `store.AGENDA_KEYS`. A fresh agenda under
  yesterday's brief is exactly the amber-banner state `board.build_view` already handles, and the
  whole point of the split.
- **A failure is not handled, it is simply due again.** Nothing is written, so the next tick asks
  the same question and gets the same answer. That is the retry, and it is why there is no backoff
  or attempt counter anywhere.

Two consequences worth knowing.

**A feed that does not answer keeps its own last-known events**, because a missing event is
invisible while a stale one is still on the right day. The keeping is per feed, not per fetch: the
feeds that answered are always fresh, or one dead URL would freeze the whole board for as long as
nobody fixed it. `runner._with_last_known` does the merge, keyed on the `calendar` label each event
carries, and only inside the current window — so a permanently broken feed empties out over a
fortnight instead of growing a tail of appointments that already happened. A *paused* feed keeps
nothing: switching a calendar off means switching it off. The failure is recorded in
`calendar_statuses` and shown on the settings page, and the stamp is written either way, so a broken
feed is retried on the configured cadence rather than every tick.

**A tick takes an exclusive `flock` on `.tick.lock` and skips itself if another holds it**
(`generate.only_one_tick`). Its job is money, not consistency — the storage split is what stops two
writers clobbering each other, and this stops a second tick paying Anthropic for a brief the first
one is already writing. A tick can outlive its five-minute slot — several feeds timing out, then
a slow model call — and the next one would find the brief still unwritten, pay for it a second time,
write a second history entry, and race the first over the payload. The overlapping tick exits 0
instead: whatever is owed is still owed five minutes later. It is deliberately only around the tick.
**Rewrite now** is a person asking for something, and should do it.

## The guest list on a calendar

A calendar entry's `shared_with` is a list of email addresses, and `parse_feed` keeps only the
events with one of them on the guest list or as the organiser. A personal calendar full of work
and private appointments then contributes the family things and nothing else:

- **It is per feed, not global.** The school calendar has no guests, and the global
  `calendar_filter_emails` this replaced emptied it — which is why that key was dropped.
- **It matches `ORGANIZER` as well as `ATTENDEE`, and any one address is enough.** An event the
  partner arranged lists them as organiser, and a Google feed does not always list the organiser
  as a guest of their own event. The old filter looked at `ATTENDEE` alone and required every
  address, so it missed everything they had arranged.
- **It runs before the event dict is built** (`calendars._events`), so a hidden event is never in
  the payload, on the board or in the prompt — and the guest list itself is never stored. The
  dict carries no addresses, and the log says how many addresses a feed has, never which.
- **`describe_feed` counts before and after**, so **Check this link** can say a working link has
  24 events and none of them match. A list that matches nobody looks exactly like an empty
  calendar from the board, and that silent zero was the old filter's failure mode.
- **Saving or removing a calendar forgets what it last said**, through the store's config save.
  Its events, statuses and the fetch stamp go, so the next tick owes a refresh. Publication checks
  also reject a fetch still using the previous settings, including failed-fetch fallback data.
  A rejected refresh stops the tick before the model call; the next tick loads the new config.
  The stored events cannot be re-filtered instead: they carry no addresses, by design.

`addresses()` is the one normaliser — list or comma-separated string in, lowercase list out, with
`mailto:` stripped — and both the form and the engine go through it, so a hand-written
`shared_with: jess@example.com` works the same as the list the settings UI writes.

## Config

`config.yaml` is the single source of truth, and the settings UI writes it back. Loads and saves go
through ruamel round-trip mode with `indent(mapping=2, sequence=4, offset=2)`, so comments, key
order and indentation all survive an edit made from a phone. There is a test asserting a save
changes exactly the lines it means to.

`config.example.yaml` documents every key. Two are migrated on load: a single `calendar_url` becomes
the first entry in `calendars`, and `calendar_filter_emails` becomes that entry's `shared_with` — or
is dropped with a warning when there is no single URL to attach it to.

Every item in the five edited lists — people, pets, recurring, special_dates, calendars — carries a
short `id`. The settings UI addresses items by it, because a position is not an identity: delete the
first person and everyone below renumbers onto somebody else's edit form. Ids are backfilled by
`ensure_ids`, which the settings UI calls on load and saves once if it added any. Deliberately not
part of `load_config` — loading must not rewrite the file, and the engine never reads ids.
`_add_id` puts the id *first* in the mapping: ruamel hangs the comment introducing the next section
off the last item of the previous one, so an appended key lands under the wrong heading.

Ids are also what lets one settings UI serve both modes later. `PLAN.md` decision 10: the config
dict is the storage contract, a file in self-hosted mode and a `jsonb` column when hosted.
