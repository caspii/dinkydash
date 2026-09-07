-- The hosted schema: one row per family, and the platform's own bookkeeping.
--
-- Config is one jsonb document rather than five tables (PLAN.md decision 10 and
-- the data model sketch). Nothing in the product ever asks which families have a
-- child born in March, so a table each for people, pets, chores, dates and
-- calendars would buy five sets of CRUD code and no answers. Real columns are
-- for what the *platform* queries or writes; the parent's own settings stay in
-- the dict the engine already takes.
--
-- Conventions, matching the ones used across these projects: TEXT with a CHECK
-- rather than VARCHAR(n), GENERATED ALWAYS AS IDENTITY rather than SERIAL, and
-- TIMESTAMPTZ rather than TIMESTAMP so a server that is nowhere near the family
-- still stores an unambiguous instant.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()


-- Families ------------------------------------------------------------------
--
-- The tenant. Its id is a uuid rather than an integer because it is the one key
-- that reaches a URL and a log line, and a sequential id there would publish how
-- many families we have and invite somebody to walk them. Every other table is
-- addressed only from inside a family, so those keep cheap bigint identities.

CREATE TABLE families (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- One plan at MVP (PLAN.md decision 6). A column rather than a constant
    -- because the first thing a second plan needs is somewhere to be recorded.
    plan                    TEXT NOT NULL DEFAULT 'standard'
                            CHECK (plan IN ('standard')),

    -- The trial lives here, not in Stripe (PLAN.md phase 4): a family that never
    -- converts never becomes a Stripe customer.
    status                  TEXT NOT NULL DEFAULT 'trialing'
                            CHECK (status IN ('trialing', 'active', 'past_due',
                                              'canceled', 'lapsed')),
    trial_ends_at           TIMESTAMPTZ,
    stripe_customer_id      TEXT UNIQUE CHECK (length(stripe_customer_id) <= 255),

    -- A bearer credential: whoever holds it sees the board. 12 characters of
    -- dinkydash.config.ID_ALPHABET is ~59 bits and still readable off a TV
    -- screen (PLAN.md, Screen URLs). Rotatable, so the column is not immutable.
    screen_token            TEXT NOT NULL UNIQUE
                            CHECK (length(screen_token) BETWEEN 10 AND 32),
    screen_token_rotated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The same dict config.yaml holds. with_defaults migrates old shapes on
    -- load, in both modes, so a new setting needs no migration here.
    config                  JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- What the worker selects on every five minutes: whose local clock has passed
-- their brief_time. An expression index is as fast as a column here and leaves
-- no second copy of the timezone to drift out of step with the config.
CREATE INDEX families_timezone_idx ON families ((config ->> 'timezone'));

-- Phase 6's admin view and the lapse sweep both walk this.
CREATE INDEX families_status_idx ON families (status);


-- Users ---------------------------------------------------------------------
--
-- One parent per family at MVP; shared edit access is explicitly out of scope.
-- Email is globally unique because a magic link has to resolve to exactly one
-- person without being told which family they belong to.

CREATE TABLE users (
    id            BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    family_id     UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    email         TEXT NOT NULL UNIQUE CHECK (length(email) <= 320),
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX users_family_idx ON users (family_id);


-- Login tokens --------------------------------------------------------------
--
-- Hashed at rest, single use, short lived (PLAN.md phase 1). Only the hash is
-- stored, so a database leak does not hand anybody a working login link; the
-- plaintext exists for the length of one email.

CREATE TABLE login_tokens (
    id         BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id    BIGINT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash) <= 128),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The sweep that deletes expired tokens, and the rate limit on requesting one.
CREATE INDEX login_tokens_expires_idx ON login_tokens (expires_at);
CREATE INDEX login_tokens_user_idx ON login_tokens (user_id);


-- Agendas -------------------------------------------------------------------
--
-- The fetched calendar window: one row per family, overwritten on every
-- refresh. Calendar contents therefore never accumulate — the most we ever hold
-- about a family is one fourteen-day window, which is what makes Phase 5's
-- retention answer short.

CREATE TABLE agendas (
    family_id  UUID PRIMARY KEY REFERENCES families (id) ON DELETE CASCADE,
    events     JSONB NOT NULL DEFAULT '[]'::jsonb,
    statuses   JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Nullable on purpose: "never fetched" has to be representable, because it
    -- is one of the two cases `schedule.due` asks about (missing, or older than
    -- refresh_minutes). A DEFAULT now() here would claim a fetch that a brief
    -- written before the first refresh never made.
    fetched_at TIMESTAMPTZ
);

-- The worker's other question: whose calendars are older than their interval.
CREATE INDEX agendas_fetched_at_idx ON agendas (fetched_at);


-- Calendar health -----------------------------------------------------------
--
-- Keyed on the calendar's id *inside the config*, which exists precisely because
-- list items carry stable ids. Fetch state is something the platform writes, so
-- it does not belong in the parent's document.

CREATE TABLE calendar_health (
    id                   BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    family_id            UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    calendar_id          TEXT NOT NULL CHECK (length(calendar_id) <= 64),
    last_fetch_at        TIMESTAMPTZ,
    last_fetch_status    TEXT CHECK (last_fetch_status IN ('ok', 'failed', 'paused')),
    -- Never the URL, and never the exception text that contains it: a failed
    -- fetch formats the secret address into its message (CLAUDE.md gotcha).
    last_fetch_detail    TEXT CHECK (length(last_fetch_detail) <= 500),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,

    UNIQUE (family_id, calendar_id)
);


-- Generations ---------------------------------------------------------------
--
-- One row per family per day: the model's words, and what they cost.

CREATE TABLE generations (
    id                 BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    family_id          UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    generated_for_date DATE NOT NULL,

    -- Nullable for the same reason agendas.fetched_at is: a payload whose stamp
    -- is missing or unreadable has to be storable, or cloud mode would reject a
    -- board that single mode accepts. The settings page already renders it as
    -- "written earlier".
    generated_at       TIMESTAMPTZ,
    status             TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'error')),

    -- headline, note, note_kind — the only part of the payload that cannot be
    -- recomputed from config + date. Dropped after 90 days (PLAN.md phase 5);
    -- the token counts below stay, because they are the cost record.
    brief              JSONB,

    input_tokens       INTEGER,
    output_tokens      INTEGER,
    cost_cents         NUMERIC(10, 4),
    model              TEXT CHECK (length(model) <= 100),
    error              TEXT CHECK (length(error) <= 500),

    -- The daily idempotency, and it is a constraint rather than a check in the
    -- worker because the worker will one day run twice at once.
    UNIQUE (family_id, generated_for_date)
);

-- "The latest brief for this family", which is every board render.
CREATE INDEX generations_family_date_idx
    ON generations (family_id, generated_for_date DESC);


-- Content history -----------------------------------------------------------
--
-- What was written recently, fed back into the prompt so the board does not
-- repeat the same octopus fact every fortnight. Trimmed to the last 30 entries
-- per family.

CREATE TABLE content_history (
    id         BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    family_id  UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    date       DATE NOT NULL,
    headline   TEXT CHECK (length(headline) <= 500),
    note       TEXT CHECK (length(note) <= 1000),
    note_kind  TEXT CHECK (length(note_kind) <= 50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Reading the last N, and trimming everything past them.
CREATE INDEX content_history_family_id_idx ON content_history (family_id, id DESC);
