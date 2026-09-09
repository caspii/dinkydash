-- The display grace period starts when access ends, not when a worker next runs.
ALTER TABLE families ADD COLUMN lapsed_at TIMESTAMPTZ;
UPDATE families SET lapsed_at = updated_at WHERE status = 'lapsed';
UPDATE families SET trial_ends_at = created_at + interval '14 days'
WHERE status = 'trialing' AND trial_ends_at IS NULL;
ALTER TABLE families ADD CONSTRAINT families_lapse_matches_status
    CHECK ((status = 'lapsed') = (lapsed_at IS NOT NULL));
ALTER TABLE families ADD CONSTRAINT families_trial_has_deadline
    CHECK (status <> 'trialing' OR trial_ends_at IS NOT NULL);

-- Keep direct status changes consistent too, including later payment webhooks.
CREATE FUNCTION stamp_family_lapse() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status = 'trialing' AND NEW.trial_ends_at IS NULL THEN
        NEW.trial_ends_at := NEW.created_at + interval '14 days';
    END IF;
    IF NEW.status = 'lapsed' THEN
        NEW.lapsed_at := coalesce(NEW.lapsed_at, now());
    ELSE
        NEW.lapsed_at := NULL;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER stamp_family_lapse
BEFORE INSERT OR UPDATE OF status, trial_ends_at ON families
FOR EACH ROW EXECUTE FUNCTION stamp_family_lapse();
