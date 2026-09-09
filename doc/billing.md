# Hosted billing

Billing is cloud-only. `requirements-cloud.txt` pins the official Stripe SDK;
single mode neither imports it nor registers payment routes. The 14-day trial
lives in Postgres and creates no Stripe customer. Checkout starts paid access
immediately, even during a trial. The return URL never grants access.
The MVP accepts cards and their supported wallets. Delayed bank-payment methods
need separate invoice-based access handling: Stripe can leave those subscriptions
active even after a failed payment ([subscription lifecycle](https://docs.stripe.com/billing/subscriptions/overview)).

## Configuration

Set the variables in `.env.example` on both the web service and the worker.
Credentials and price/account decisions belong in private configuration and the
Linear strategy document, never in this repository. Missing configuration keeps
Checkout disabled while login, settings, export and unbilled account deletion work.
Existing subscribers still need the secret key and portal configuration to manage
billing or delete their accounts safely.

Before enabling payments, check the intended Stripe account in **test mode**:

1. Create the agreed monthly and annual USD recurring prices on one product,
   with explicit inclusive/exclusive tax behaviour. Set their IDs. Existing
   subscriptions keep their original price when the configured IDs change.
   Checkout accepts promotion codes; configure any agreed offer in Stripe.
2. Confirm the business's tax settings, product tax code and registrations.
   Explicitly choose `STRIPE_AUTOMATIC_TAX=true` or `false`; there is no default.
   Automatic tax requires active Stripe Tax settings. Code cannot decide whether
   the business needs a tax registration.
3. Create a dedicated Customer Portal configuration. Enable invoice history,
   card updates, cancellation **at period end**, and subscription price
   changes for both prices on this product. Configure and review prorations for
   billing-period changes in Stripe. Set `STRIPE_PORTAL_CONFIGURATION_ID`.
   Checkout checks these cancellation and management capabilities before charging.
4. Configure payment recovery in Stripe: retry failed renewals, then cancel or
   mark unpaid. DinkyDash gives seven days from the unpaid invoice's creation
   before pausing board updates, and does not itself retry card charges.
5. Set `DINKYDASH_APP_HOST` to the trusted app hostname. Checkout/portal returns
   and notification links use this origin, never a form field or Host header.
6. Register `POST /stripe/webhook` as a snapshot event destination using the
   SDK's API version, **2026-08-26.dahlia**. Subscribe only to the event types in
   `dinkydash.billing.EVENTS` and set that destination's signing secret.
   Use matching test or live keys, prices, portal configuration and signing secret;
   connected-account events and events from the wrong mode are rejected.

The webhook verifies signatures against the raw, size-limited body before any
database work. It is the only CSRF exemption; Checkout, portal and status-refresh
POSTs still require a signed-in family and its CSRF token.

## State and recovery

Payment writes serialize on the family row, including account deletion. Unlike
calendar fetching, these short billing operations hold the row lock across a
bounded Stripe call to prevent competing purchases. Checkout stores its exact
request and idempotency key before the API call; a retry reuses that request.
An open Checkout is reused for up to an hour, including if another tab chooses
a different billing period. Expired Checkouts can be replaced after checking
there is no existing payable subscription.

Webhooks record processed IDs and reconcile current Stripe subscriptions in the
same transaction. They do not apply event timestamps or stale payload state.
Canceled older subscriptions cannot overwrite a replacement. A failed transaction
returns a retryable response and does not mark the event processed. The worker
also reconciles up to twenty accounts per pass whose last check was over an hour
ago, recovering missed deliveries.

Active subscriptions update boards; scheduled cancellation ends access at its
deadline. Failed renewals get seven days from invoice creation, which repeated
payment attempts cannot extend. Unpaid, paused and canceled subscriptions lapse.
Access deadlines are checked on the request/tick path even if housekeeping is late.
The existing 30-day frozen-board display applies after access ends.

The worker queues a reminder three days before an app-managed trial ends and
delivers payment-failure, cancellation and ended-subscription notices through
SendGrid. Delivery records deduplicate ordinary webhook retries; failures retry
after fifteen minutes and stale notices are skipped after recovery. Delivery is
at least once: a crash after SendGrid accepts mail but before the database commits
can repeat a message. Bodies and webhook payloads are not stored.

Account deletion removes the Stripe customer first, which stops its subscriptions
and prevents new ones. If Stripe fails, the local account remains so deletion can
be retried. A delayed webhook for a deleted family cannot recreate it. Stripe may
retain payment records under its own policy; local billing rows cascade with the
family. Exports include subscription identifiers, status and dates, but exclude
Checkout URLs and session credentials.

## Verification before the first real payment

`tests/test_billing.py` exercises real database transactions and signed webhooks
with simulated Stripe/email responses. That is not a Stripe test-mode checkout.
On the configured test account, complete a fresh signup, trial, Checkout payment,
portal billing-period change, failed renewal/recovery, period-end cancellation,
and account deletion. Resend duplicate and older events after state changes;
verify access and notification delivery. Check the final tax totals and invoices.
Keep the test customer, destination and account identifiers in private notes.

Use [Stripe's testing guide](https://docs.stripe.com/testing),
[webhook delivery guidance](https://docs.stripe.com/webhooks), and
[Customer Portal setup](https://docs.stripe.com/customer-management/integrate-customer-portal).
Only enable live credentials after that account-specific verification succeeds.
