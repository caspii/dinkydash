-- The worker's pulse: when its last pass finished, and what that pass did (DIN-54).
--
-- One row per worker loop, overwritten every pass. There is exactly one loop
-- today — `python -m worker`, which reports as 'tick' — and the key is there so
-- that a second loop on its own cadence could report without a second table.
--
-- **Why a row and not a ping to a monitoring service.** The web service is
-- already reachable from outside and already holds the database, so a row it
-- can read means "is the worker alive" can be asked by anything that can fetch
-- a URL: no account anywhere, no secret in the worker, nothing new the worker
-- has to reach. `/healthz/worker` is the read; `.github/workflows/monitor.yml`
-- is the asker. The web service's own `/healthz` stays as it is and reads
-- nothing, because that one decides whether a deploy goes live.
--
-- **No family in the row**, like `global_model_spend` (004) and `growth_by_day`
-- (006): a count of families walked, a count that raised, and how long it took.
-- Nothing here leads back to an account, so nothing here is deleted with one.
CREATE TABLE worker_heartbeat (
    name      TEXT PRIMARY KEY,
    passed_at TIMESTAMPTZ NOT NULL,
    families  INTEGER NOT NULL DEFAULT 0 CHECK (families >= 0),
    failed    INTEGER NOT NULL DEFAULT 0 CHECK (failed >= 0),
    took_ms   INTEGER NOT NULL DEFAULT 0 CHECK (took_ms >= 0)
);
