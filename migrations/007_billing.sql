ALTER TABLE families
    ADD COLUMN stripe_subscription_id TEXT UNIQUE,
    ADD COLUMN subscription_status TEXT,
    ADD COLUMN subscription_period_end TIMESTAMPTZ,
    ADD COLUMN subscription_cancel_at TIMESTAMPTZ,
    ADD COLUMN billing_access_until TIMESTAMPTZ,
    ADD COLUMN billing_synced_at TIMESTAMPTZ;

-- Save the exact request before contacting Stripe. A timeout or a failed local
-- commit must retry the same Checkout, even if the parent changes their choice.
CREATE TABLE billing_checkouts (
    family_id UUID PRIMARY KEY REFERENCES families (id) ON DELETE CASCADE,
    attempt UUID NOT NULL DEFAULT gen_random_uuid(),
    params JSONB NOT NULL,
    session_id TEXT
);

-- No webhook payloads: they contain billing details we do not need to retain.
CREATE TABLE stripe_events (
    event_id TEXT PRIMARY KEY,
    family_id UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Delivery belongs to the worker, never the webhook's response transaction.
CREATE TABLE billing_notifications (
    family_id UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    notice_key TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('trial_ending', 'payment_failed',
                                      'cancellation_scheduled', 'subscription_ended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    PRIMARY KEY (family_id, notice_key)
);
CREATE INDEX billing_notifications_pending ON billing_notifications (created_at)
    WHERE sent_at IS NULL;
