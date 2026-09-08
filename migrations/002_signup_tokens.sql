-- Sign-up: let a token exist before the family it will create (DIN-41).
--
-- Until now a `login_tokens` row needed a `user_id`, so nothing could be sent
-- to somebody who did not already have an account. That is why the only family
-- in production was inserted by hand with SQL.
--
-- **Why the family is created when the link is clicked, not when the address is
-- submitted.** A `families` row starts a 14-day trial, and the worker calls
-- Anthropic daily for every family that is not lapsed. If a POST to /login
-- created one, ten thousand scripted sign-ups would be a real and rising daily
-- bill with no card behind it and nothing to charge back. Verifying first makes
-- an unverified sign-up cost one row here and one email — no trial, no API call,
-- and nothing to sweep up afterwards that the existing sweep does not already
-- take. It also makes "signing in through the link *is* email verification"
-- (PLAN.md phase 1) true of sign-up as well: without it a family exists for an
-- address nobody has proved they can read.
--
-- **Why this is one table and not two.** A `signup_tokens` table beside this one
-- would need its own single-use UPDATE, its own expiry, its own sweep and its own
-- rate limit — and single use is the one property the whole design rests on
-- (`UPDATE ... WHERE used_at IS NULL RETURNING`, decided and marked in one
-- statement). Written twice, one copy drifts. What both kinds of token prove is
-- identical: whoever clicked it reads that mailbox. Only what happens next
-- differs, and that branch belongs in one place in `accounts.consume_link`.
--
-- The cost is the column below plus a CHECK, which is cheaper than a second
-- table's worth of the same care.

-- A sign-up token has no user yet. Every existing row has one and keeps it.
ALTER TABLE login_tokens ALTER COLUMN user_id DROP NOT NULL;

-- Who the token is for when there is no user: the address it was mailed to.
-- Same 320-character bound as `users.email`, because it becomes one.
ALTER TABLE login_tokens ADD COLUMN email TEXT CHECK (length(email) <= 320);

-- Exactly one of the two, never both and never neither. A row with both would
-- be a token that could sign one person in and create an account for another;
-- a row with neither is a credential belonging to nobody.
ALTER TABLE login_tokens ADD CONSTRAINT login_tokens_one_subject
    CHECK ((user_id IS NULL) <> (email IS NULL));

-- The per-address rate limit on sign-up counts live tokens for one address, the
-- way `login_tokens_user_idx` serves the same limit for one user. Partial,
-- because every sign-in token has a NULL here and none of them is ever counted.
CREATE INDEX login_tokens_email_idx ON login_tokens (email) WHERE email IS NOT NULL;
