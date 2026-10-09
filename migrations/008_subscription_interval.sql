-- Which of the two prices a subscription is on. Copied from the Stripe
-- subscription when its status snapshot is written, so the operator's page
-- can split paying families without asking Stripe.
ALTER TABLE families
    ADD COLUMN subscription_interval TEXT
        CHECK (subscription_interval IS NULL OR subscription_interval IN ('month', 'year'));
