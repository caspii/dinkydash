-- First-touch attribution: the campaign parameters that first brought a
-- family here (dinkydash/attribution.py, web/attribution.py), captured once
-- at signup. `accounts.set_first_touch` only ever writes this while it is
-- still `NULL`, so later sign-ins can never replace it.

ALTER TABLE families
    ADD COLUMN first_touch JSONB;
