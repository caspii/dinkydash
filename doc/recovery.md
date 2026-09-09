# Database recovery drills

Run a restore drill on the **first day of each month at 07:00 UTC**, and after a
PostgreSQL major upgrade or a change to migrations/storage. The operator owns the
result: a non-zero exit or a missing monthly success is a failed drill requiring
investigation that day. A backup policy alone is not evidence that the app can
read restored data.

## Run the drill

Install the cloud requirements and PostgreSQL **17 server and client tools**.
Use the same major as production. On macOS, `brew install postgresql@17` provides
these under `/opt/homebrew/opt/postgresql@17/bin`; installing them need not start
or replace the machine's existing PostgreSQL service. On Linux, pass the bin
directory containing `initdb`, `pg_ctl`, `createdb`, `pg_dump` and `pg_restore`.
Run as an ordinary user, not root.

Supply the **direct** source connection in `DATABASE_URL_DIRECT` from the
operator's private secret storage, then run:

```bash
python -m ops.restore_drill --pg-bin /opt/homebrew/opt/postgresql@17/bin
```

`--source-env NAME` selects a different environment variable. The tool never
loads `.env` implicitly. It requires an explicit database name and refuses
service indirection. Prefer a dedicated read-only source role with permission
to dump the application's schema and data. Do not paste a connection string
into a command argument, commit it, or put it in a CI log.

There is **no target URL argument**. Every run creates a fresh local cluster
under `/tmp`, in an owner-only directory. The cluster accepts only Unix socket
connections from that directory; it has no TCP listener. A short
`--scratch-parent` outside every repository can override `/tmp`. This cannot
restore over an existing local or production database.

The drill:

1. Takes a fresh custom-format logical backup through a read-only source
   session, with a bounded lock wait and connection timeout.
2. Restores it into the newly created scratch database using `--no-owner`,
   `--no-acl`, `--exit-on-error` and one transaction. The source's database name,
   owners, grants and connection settings cannot redirect this restore.
3. Applies any pending checked-out migrations **to the scratch copy only**,
   checks migration records, and reads config, agenda, brief and recent history
   through family-scoped stores for up to three restored families. An empty
   source fails because there is no representative family to verify.
4. Starts the real cloud WSGI dispatcher in-process, checks both hostnames,
   renders the sampled boards and checks rejection of an unknown family.
   All inherited app credentials are removed, model caps are zero, and Python
   network connections and DNS are blocked. It never starts the worker, sends
   a login request, or opens a browser to restored calendar URLs.
5. Stops the scratch PostgreSQL server and removes the dump, connection service
   file, server logs and restored data, including after normal failures and
   SIGTERM. Success is reported only after cleanup succeeds.

The report contains timestamps, counts and check results, never credentials,
family identifiers or content. Keep even these reports in operator storage,
not the public repository. Raw subprocess output is discarded: a PostgreSQL
error can quote a connection string or an entire failed data row.

A malformed stored screen token is counted separately in
`sampled_invalid_screen_tokens`. Its scoped board must still render and its
URL must still return 404. This is a source-data defect to investigate; do not
rotate a production screen URL merely to make a drill green.

## Schedule and failure reporting

Use a private operator host with the source secret already available. A cron
wrapper can load an owner-only environment file, change to the checked-out
release and run the command above. Set the host's timezone to UTC or use a
scheduler with an explicit UTC timezone. The cron expression is `0 7 1 * *`.
Keep the report/log outside the checkout with mode 0600.

Configure the external monitor to expect one successful monthly run (first of
the month, 07:00 UTC), allowing a 24-hour grace period for maintenance. Send an
empty success ping **only after exit 0**. The monitor must alert the operator
if that ping is missing; a failed cron job must not report success. Test the
alert destination before relying on it. The monitor/account destination is
operator configuration, not a credential committed with this tool.

On failure, retain the sanitised report, check tool/server version compatibility
and source connectivity, then repeat the drill. Do not try a production restore
as a troubleshooting step. If `pg_ctl` cannot stop the scratch server, the tool
leaves its private directory in place and reports that path: stop that exact
server before deleting the directory. After a machine crash or SIGKILL, check
for `dinkydash-restore-*` directories under the chosen parent and remove them
only after confirming their scratch server has stopped.

This verifies a **fresh logical backup**, not DigitalOcean's managed
point-in-time recovery interface, its retention, or a production cutover.
It deliberately omits owner/ACL restoration. A disaster-recovery cutover also
needs the managed cluster's roles/grants, application secrets, endpoint changes
and a separately approved plan for reconciling deletions that postdate a backup.

## Validation record — 9 September 2026

A fresh read-only backup of the managed PostgreSQL 17 database was restored into
an isolated PostgreSQL 17.11 instance. Schema checks, family-scoped reads, board
rendering and cloud startup passed with outbound connections blocked. Cleanup
completed. A legacy screen-token defect was recorded separately; production
credentials and data were not changed. The detailed count/timing report lives
with the DIN-56 issue, not in this repository.

The monthly cadence and failure procedure are defined above. External scheduled
execution and notification delivery still require the operator's monitoring
configuration; this record does not claim a monthly job is already installed.
