# Local hosted development

From the repository root, install the existing dependencies and prepare a local
Postgres database (Postgres must already be running):

```bash
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt -r requirements-cloud.txt
createdb dinkydash_dev
export DATABASE_URL=postgresql:///dinkydash_dev
export DINKYDASH_SECRET_KEY="$(venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
venv/bin/python migrate.py --database-url "$DATABASE_URL"
venv/bin/python dev.py
```

Use a separate database name for each workspace. For Conductor's Run action, put
the development `DATABASE_URL` and `DINKYDASH_SECRET_KEY` in the workspace's
gitignored `.env`, or supply them in the run environment. A terminal export alone
does not change Conductor's environment. Explicit environment values override
`.env`; inspect which database you selected before migrating or signing in.
The launcher never applies migrations or creates sample accounts.

The single **dev** run action starts both existing Flask apps:

| App | In Conductor | Outside Conductor |
|---|---|---|
| Hosted dashboard | `CONDUCTOR_PORT` | `DINKYDASH_PORT`, default `5000` |
| Marketing website | `CONDUCTOR_PORT + 1` | `DINKYDASH_WEBSITE_PORT`, default dashboard port + 1 |

Both bind to `127.0.0.1`. The launcher prints labeled URLs after both servers
have initialized and bound their ports. `CONDUCTOR_PORT` takes precedence over
both port overrides; an empty, invalid, out-of-range or conflicting port fails.
For example, outside Conductor:

```bash
DINKYDASH_PORT=5100 DINKYDASH_WEBSITE_PORT=5101 venv/bin/python dev.py
```

The dashboard always runs in cloud mode. A missing database URL, missing session
key, unreachable database or unapplied migration fails startup; it never falls
back to the self-hosted dashboard. Website login and trial/signup links, including
those in Markdown pages, open this local dashboard's `/login`. The launcher
overrides `DINKYDASH_APP_URL` and clears the production `DINKYDASH_APP_HOST` for
its child processes.

Stop the Conductor run action or press Ctrl-C to stop both servers. If either
cannot start, times out during startup, or exits unexpectedly (even with status
zero), the launcher stops the other and exits with an error. Restart the run
action after Python, template or Markdown changes; there is no automatic reloader
or interactive debugger.

Use Chrome or Firefox for local sign-in. Hosted sessions retain their Secure
cookie policy; Safari does not support this HTTP loopback workflow. Email delivery
requires `SENDGRID_API_KEY`. For an existing account in your development database,
you can instead mint a link without email (substitute the printed dashboard port):

```bash
venv/bin/python login_link.py you@example.com \
  --database-url "$DATABASE_URL" --base-url http://127.0.0.1:5000
```

Neither an email key nor an Anthropic key is required to start the servers.
Generation still requires an Anthropic key when you request it.

Conductor reads shared `.conductor/settings.toml` from the remote default branch.
Merge the configuration into `main` for the shared run action to take effect.
Until then, run `venv/bin/python dev.py` in this workspace's terminal or set that
command as a repository-local run override. Higher-precedence Conductor settings
can override the shared action. Runs are nonconcurrent because copied `.env`
files can share a database; only enable concurrent runs when every workspace has
its own database as well as its allocated ports.

Production still uses `wsgi.py` to route the two apps by hostname. Self-hosted
Raspberry Pis still use `app.py` / `run_app.sh` and need only `requirements.txt`.
