-- An activation is a dashboard on a screen, not a calendar in a form.
--
-- A family is **activated** the first time one of its screens keeps the
-- dashboard open long enough to refresh it: the refresh is what reports a
-- screen size (009), so the first `screen_sizes` row is the first evidence that
-- the dashboard is up somewhere and staying up. Saving a calendar link says
-- nothing about either — the link may not work, no dashboard may have been
-- written, and no screen may ever have opened it.
--
-- **Only a screen the size of one counts.** The parent's own phone opens the
-- same URL from "View dashboard", and a tab left open there refreshes like a
-- panel does. Phones are narrower than 480 CSS pixels on their short side; the
-- smallest panel this dashboard is laid out for, a Pi's 800x480, is not. A
-- phone propped on a fridge is missed by this, which is the cheaper mistake:
-- counting every parent who looked at the preview would make the number mean
-- "opened the link".
--
-- The calendar moment is still worth knowing, as the step before. It keeps the
-- counting rules it had: `families.calendar_added_at` is stamped once by the
-- trigger on `families`, and `growth_by_day.calendars` counts it per UTC day
-- and survives deletion. Both are filled from the old activation columns, so
-- nothing counted so far is lost — it is moved to the column that describes it.
--
-- **The activations are recounted from the screens.** A family deleted before
-- now leaves no screen row to recount from, so its activation is not in the
-- totals. That is a smaller error than keeping calendar counts under a heading
-- that now means something else.

-- Old web code keeps saving settings and recording screen sizes while the
-- pre-deploy job runs. Hold writes to both until the backfill and the triggers
-- are in place, so nothing lands between the recount and the trigger.
LOCK TABLE families IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE screen_sizes IN SHARE ROW EXCLUSIVE MODE;

ALTER TABLE families ADD COLUMN calendar_added_at TIMESTAMPTZ;
ALTER TABLE growth_by_day
    ADD COLUMN calendars INTEGER NOT NULL DEFAULT 0 CHECK (calendars >= 0);

-- Neither UPDATE touches `config`, `status` or `trial_ends_at`, so no trigger
-- on `families` fires for them.
UPDATE families SET calendar_added_at = activated_at;
UPDATE growth_by_day SET calendars = activations;

CREATE FUNCTION is_a_screen_size(width INTEGER, height INTEGER) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
    SELECT LEAST(width, height) >= 480
$$;

UPDATE families SET activated_at = NULL;
UPDATE families f SET activated_at = first.seen
FROM (SELECT family_id, min(first_seen_at) AS seen
      FROM screen_sizes
      WHERE is_a_screen_size(width, height)
      GROUP BY family_id) AS first
WHERE first.family_id = f.id;

UPDATE growth_by_day SET activations = 0;
INSERT INTO growth_by_day (day, activations)
SELECT (activated_at AT TIME ZONE 'UTC')::date, count(*)
FROM families WHERE activated_at IS NOT NULL
GROUP BY 1
ON CONFLICT (day) DO UPDATE SET activations = EXCLUDED.activations;

-- The trigger on `families` counts signups and calendars. Activations are the
-- trigger on `screen_sizes`, below.
CREATE OR REPLACE FUNCTION count_family_growth() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO growth_by_day (day, signups)
        VALUES ((NEW.created_at AT TIME ZONE 'UTC')::date, 1)
        ON CONFLICT (day) DO UPDATE SET signups = growth_by_day.signups + 1;
    END IF;
    IF NEW.calendar_added_at IS NULL AND config_has_a_calendar(NEW.config) THEN
        NEW.calendar_added_at := now();
        INSERT INTO growth_by_day (day, calendars)
        VALUES ((now() AT TIME ZONE 'UTC')::date, 1)
        ON CONFLICT (day) DO UPDATE SET calendars = growth_by_day.calendars + 1;
    END IF;
    RETURN NEW;
END;
$$;

-- `WHERE activated_at IS NULL` is what makes an activation count once, and it
-- holds under concurrency: two screens reporting together both reach the
-- UPDATE, the second waits on the first's row lock, re-reads the row, finds it
-- stamped and updates nothing — so only the first adds to the day's count.
CREATE FUNCTION count_activation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT is_a_screen_size(NEW.width, NEW.height) THEN
        RETURN NULL;
    END IF;
    UPDATE families SET activated_at = NEW.first_seen_at
    WHERE id = NEW.family_id AND activated_at IS NULL;
    IF FOUND THEN
        INSERT INTO growth_by_day (day, activations)
        VALUES ((NEW.first_seen_at AT TIME ZONE 'UTC')::date, 1)
        ON CONFLICT (day) DO UPDATE SET activations = growth_by_day.activations + 1;
    END IF;
    RETURN NULL;
END;
$$;

-- On INSERT only: a size seen again takes the upsert's UPDATE path, and by
-- then the size has already had its chance to activate the family.
CREATE TRIGGER count_activation
AFTER INSERT ON screen_sizes
FOR EACH ROW EXECUTE FUNCTION count_activation();
