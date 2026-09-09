# Worker and web liveness

The web service's `/healthz` says that its process can answer a request. It
intentionally does not query Postgres or the worker, because App Platform uses
it for deployment/restart decisions. Monitor it externally at
`https://app.dinkydash.co/healthz`; an HTTP response outside 200–299, a timeout,
or a TLS error must count as downtime. Use a one-minute check and a two-minute
failure threshold, with both failure and recovery notifications.

The worker sends an **empty HTTPS POST** after a completed pass when
`DINKYDASH_WORKER_HEARTBEAT_URL` is configured. Store this URL as a secret: it
may be a credential allowing someone to mask a stopped worker. Configure it on
the worker component, not in family settings. No family ID, calendar URL,
headline, exception text or count is sent to the monitor.

For the default five-minute worker interval, configure the monitor with an
expected period of **10 minutes and a 10-minute grace period**. This allows up
to five minutes for a pass plus the normal five-minute sleep, and ten more
minutes for a redeploy or transient delay. A pass that regularly takes longer
requires capacity investigation and an explicit timeout adjustment. Keep this
in sync if `DINKYDASH_WORKER_INTERVAL` changes.

A heartbeat means every eligible family was considered. Handled calendar/model
failures still count as a live worker; diagnosing those is separate from a
stopped process (DIN-55). A database failure that aborts family enumeration or
a shutdown that interrupts the pass sends no heartbeat. Ping failures log a
sanitised warning and never stop future passes. Pings have a five-second HTTP
timeout, no redirects, no environment proxy and no immediate retries.

When the URL is absent, the worker starts normally and logs that missed passes
cannot alert. When it is malformed, startup fails without printing its value.
Installing the code is not the same as enabling an external alert.

## Set up and prove the alerts

1. Create a missed-heartbeat check with the period/grace above and an explicit
   operator destination. Put its HTTPS ping URL in the worker's secret env var.
2. Create a separate uptime check for the app's `/healthz` with the thresholds
   above. Keep the external account/check IDs and recipient details in Linear.
3. Create a **temporary independent test heartbeat** with a short period and
   grace. Run an isolated test worker against synthetic data with model/email
   credentials removed. After a completed pass, stop that test worker and wait
   for the external failure notification; restart it and verify recovery.
4. Test web downtime against an isolated endpoint, then recovery. Do not stop
   the production worker or web service for either test.
5. Record alert and recovery timestamps and the destination's receipt privately,
   then delete or pause the temporary checks. A local HTTP stub proves request
   formatting; it does not prove that an external notification arrives.

No external monitoring account or destination is supplied by the repository.
Do not mark DIN-54 complete until the configured checks and delivery drill have
been recorded. See [recovery.md](recovery.md) for monthly restore monitoring.

On 9 September 2026, both live `/healthz` endpoints returned HTTP 200 with
`Cache-Control: no-store`. This is a point-in-time reachability check, not
evidence of installed monitoring or notification delivery.
