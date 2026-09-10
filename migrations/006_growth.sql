-- Signups and activations, counted per day and kept without a family (DIN-37).
--
-- Two moments in a family's life are worth counting over time: the click on
-- the emailed link that creates the family (a **signup**), and the first time
-- its settings carry a calendar link (an **activation**) — "the parent's first
-- real act in the settings UI", as `config.starter_config` puts it. The first
-- has always been `families.created_at`. The second had no record at all.
--
-- **Why a daily aggregate rather than a query over `families`.** Deleting an
-- account is a hard delete, so a chart drawn from `created_at` forgets a signup
-- the moment that family leaves. A week in which five families signed up and
-- all five deleted their accounts would then show as a week in which nothing
-- happened — which is the one week worth looking at. `global_model_spend` (004)
-- already made this trade for the spend breaker: a date and a count survive
-- deletion, and nothing in the row leads back to a family.
--
-- **Why a trigger.** Every path that writes a config runs through it — the
-- settings UI, a hand-run UPDATE, whatever imports a config one day — so the
-- count cannot drift from the truth by way of a caller that forgot to call
-- something. The same reasoning as `count_global_model_calls` and
-- `stamp_family_lapse`.
--
-- `families.activated_at` is what makes an activation count **once**: a
-- calendar removed and added again is not a second activation. It is also the
-- per-family answer to "when did they get going", which the aggregate cannot
-- give. It is a real column because it is something the platform writes,
-- not something the parent typed (001, on what earns a column).
--
-- **UTC days**, like `model_spend`: a total summed over a dozen local dates is
-- not a day, and there is no family clock to use here anyway.

-- The pre-deploy job runs while the old web code is still creating families and
-- saving settings. Block writes until the backfill and the trigger are both in
-- place, so a signup landing between the two is counted exactly once. Reads
-- carry on; the board is not affected.
LOCK TABLE families IN SHARE ROW EXCLUSIVE MODE;

ALTER TABLE families ADD COLUMN activated_at TIMESTAMPTZ;

CREATE TABLE growth_by_day (
    day         DATE PRIMARY KEY,
    signups     INTEGER NOT NULL DEFAULT 0 CHECK (signups >= 0),
    activations INTEGER NOT NULL DEFAULT 0 CHECK (activations >= 0)
);

-- Does this config connect a calendar: a `calendars` entry with a link in it?
-- Written as a CASE so the array function is never reached for a document
-- whose `calendars` is not an array. A trigger that raised on an odd document
-- would turn one family's settings save into a 500.
CREATE FUNCTION config_has_a_calendar(config JSONB) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN jsonb_typeof(config -> 'calendars') = 'array' THEN EXISTS (
            SELECT 1 FROM jsonb_array_elements(config -> 'calendars') AS entry
            WHERE jsonb_typeof(entry) = 'object'
              AND coalesce(entry ->> 'url', '') <> '')
        ELSE false
    END
$$;

-- Backfill. A family that already has a calendar was activated at some point
-- before now; the last settings save is the latest that could have been, and
-- it is the only stamp there is. Approximate for the families that predate
-- this migration, exact for every family after it.
UPDATE families SET activated_at = updated_at WHERE config_has_a_calendar(config);

INSERT INTO growth_by_day (day, signups, activations)
SELECT day, sum(signups), sum(activations)
FROM (
    SELECT (created_at AT TIME ZONE 'UTC')::date AS day, 1 AS signups, 0 AS activations
    FROM families
    UNION ALL
    SELECT (activated_at AT TIME ZONE 'UTC')::date, 0, 1
    FROM families WHERE activated_at IS NOT NULL
) AS moments
GROUP BY day;

CREATE FUNCTION count_family_growth() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO growth_by_day (day, signups)
        VALUES ((NEW.created_at AT TIME ZONE 'UTC')::date, 1)
        ON CONFLICT (day) DO UPDATE SET signups = growth_by_day.signups + 1;
    END IF;
    IF NEW.activated_at IS NULL AND config_has_a_calendar(NEW.config) THEN
        NEW.activated_at := now();
        INSERT INTO growth_by_day (day, activations)
        VALUES ((now() AT TIME ZONE 'UTC')::date, 1)
        ON CONFLICT (day) DO UPDATE SET activations = growth_by_day.activations + 1;
    END IF;
    RETURN NEW;
END;
$$;

-- BEFORE, not AFTER, because it writes `NEW.activated_at`. A family inserted
-- with a calendar already in its config counts as both on the same day.
-- Deletion is deliberately not a trigger: nothing is ever subtracted.
CREATE TRIGGER count_family_growth
BEFORE INSERT OR UPDATE OF config ON families
FOR EACH ROW EXECUTE FUNCTION count_family_growth();
