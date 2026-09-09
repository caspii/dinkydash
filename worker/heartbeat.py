"""An empty HTTPS ping after a completed worker pass; no tenant data leaves."""

import logging
import os
from urllib.parse import urlsplit

import requests

log = logging.getLogger("dinkydash.worker")
ENVIRONMENT_KEY = "DINKYDASH_WORKER_HEARTBEAT_URL"


def configured_url():
    url = os.environ.get(ENVIRONMENT_KEY, "").strip()
    if not url:
        log.warning("Worker heartbeat is not configured; missed passes cannot alert.")
        return None
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == "https" and parts.hostname and not parts.username
                 and not parts.password and not parts.fragment)
        parts.port  # Reject malformed ports without including the URL in the error.
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"{ENVIRONMENT_KEY} must be an HTTPS URL without userinfo or a fragment.")
    return url


def ping(url):
    """Try once, with no body, redirects, proxy, or credential-bearing logging.

    The monitor should expect a pass every five minutes plus its duration, and
    allow a redeploy grace period. Failure never stops the next family's board.
    """
    if not url:
        return False
    try:
        with requests.Session() as session:
            session.trust_env = False
            with session.post(url, data=b"", timeout=5, allow_redirects=False,
                              stream=True) as response:
                if 200 <= response.status_code < 300:
                    return True
                log.warning("Worker heartbeat failed (HTTP %s).", response.status_code)
    except requests.RequestException:
        log.warning("Worker heartbeat could not reach the monitor; retrying after the next pass.")
    return False
