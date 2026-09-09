-- Keep charged calls after a family's personal data is deleted (DIN-49).
-- Only a UTC date and a total survive; there is no link back to an account.
CREATE TABLE global_model_spend (
    day   DATE PRIMARY KEY,
    calls BIGINT NOT NULL DEFAULT 0 CHECK (calls >= 0)
);

-- The pre-deploy job runs while the old worker/web code may still be writing.
-- Block writes during the backfill and install a trigger in the same transaction
-- so those callers also contribute until the new code takes over.
LOCK TABLE model_spend IN SHARE ROW EXCLUSIVE MODE;

INSERT INTO global_model_spend (day, calls)
SELECT day, sum(calls) FROM model_spend GROUP BY day;

CREATE FUNCTION count_global_model_calls() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    charged BIGINT := NEW.calls;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        charged := NEW.calls - OLD.calls;
    END IF;
    IF charged > 0 THEN
        INSERT INTO global_model_spend (day, calls) VALUES (NEW.day, charged)
        ON CONFLICT (day) DO UPDATE
            SET calls = global_model_spend.calls + EXCLUDED.calls;
    END IF;
    RETURN NULL;
END;
$$;

-- Refused upserts and token bookkeeping charge nothing. Deletion never refunds
-- an attempt; a rolled-back write rolls back its contribution too.
CREATE TRIGGER count_global_model_calls
AFTER INSERT OR UPDATE OF calls ON model_spend
FOR EACH ROW EXECUTE FUNCTION count_global_model_calls();
