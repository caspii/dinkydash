-- The hard breaker on what the model costs (DIN-43).
--
-- Nothing bounded the Anthropic bill before this. The worker walks every
-- non-lapsed family and calls Claude; "Rewrite now" calls it from a web
-- request. A bug that ticks in a loop, a bad deploy, or somebody who signed up
-- ten thousand mailboxes all cost the same, and none of them met a ceiling.
--
-- **Calls, not money.** A price table in the schema would go stale silently and
-- in the wrong direction — it under-counts after a price rise, which is exactly
-- when a breaker matters. A call is exact, is knowable *before* it is made, and
-- the product's design already says how many there should be: one brief a day
-- per family. Turning calls into pounds is a multiplication somebody does in a
-- query, and the rate lives in the docs where it can be corrected.
--
-- **One row per family per day, not one per call.** A daily cap needs a
-- counter, not an audit log, and an aggregate never needs a retention sweep.
-- Token counts ride along because they cost nothing to add and answer "what did
-- last month actually cost" without a second table.
--
-- **UTC, not the family's clock.** `generations.generated_for_date` is the
-- family's local date, which is right for "is today's board written" and wrong
-- here: a global daily total summed over a dozen different local dates is not a
-- day. A family near midnight has their allowance split across two UTC days,
-- which is fine for a limit set well above what anybody legitimately uses.

CREATE TABLE model_spend (
    day           DATE NOT NULL,
    family_id     UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,

    -- Incremented on the **attempt**, in the same statement that checks the
    -- limit. Counting successes instead would mean an expired API key retried
    -- every five minutes for ever, paying for input tokens each time, and
    -- never tripping anything.
    calls         INTEGER NOT NULL DEFAULT 0 CHECK (calls >= 0),

    -- Added afterwards, when the response says what it used. Nullable in
    -- effect — a call that failed leaves these at whatever they were, because
    -- a failure reports no usage.
    input_tokens  BIGINT NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
    output_tokens BIGINT NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),

    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (day, family_id)
);

-- **No second index.** The global half of the breaker sums one day across every
-- family, and the primary key already leads on `day` — so `WHERE day = %s` is
-- served by the index Postgres built for the key. An explicit
-- `model_spend (day)` beside it would be a second copy of the same thing, kept
-- up to date on every write, answering nothing new.
