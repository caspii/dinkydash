"""What somebody can tell us from inside the app, and where it goes.

    enabled() -> bool
    clean(message) -> str
    recipient() -> str
    submit(message, address=None, family_id=None) -> None

One form, one email, no table. A family writes a few sentences, they arrive in a
mailbox with that family's own address as the reply-to, and nothing is stored
on our side — so there is no feedback to export, none to delete, and no
migration to run. That is deliberate: **the cheapest version of this that a
person can actually reach beats a better one that is not built yet.** If enough
arrives to need triage, a table and a queue can follow it.

**The message is somebody's own words, so it is treated as theirs.** It is never
logged, never attached to an error report, and never shown back to anybody but
the person who typed it. What a log line gets is that feedback was sent, and
nothing of what it said.

**Whether the form exists at all is decided by whether there is anywhere to send
it.** Not by the mode: a Pi with no mail provider is the same case as a cloud
deployment whose key has been pulled, and both should offer nothing rather than
a button that fails. That is the same rule as "a feature that needs a database
is a cloud feature" — this one needs an email provider.
"""

import os

# The key `dinkydash.mail` sends with, named here rather than imported so that
# asking whether the form can work costs nothing and imports nothing. That is
# what keeps `mail`'s promise — single mode never imports it — true: with no key
# the pill is not drawn and the route is a 404, so nothing on that path runs.
MAIL_KEY = "SENDGRID_API_KEY"

# Where the form sends, when it should not be the address the app publishes.
# Named here for the same reason `MAIL_KEY` is: reading it costs no import.
FEEDBACK_TO = "DINKYDASH_FEEDBACK_TO"

# What one message may carry. Generous, because somebody describing a bug may
# paste the thing that went wrong, and short enough that the form is not a way
# to post arbitrary volume through our sending account. Anything longer is
# refused rather than truncated: silently dropping the end of what a person
# wrote is worse than telling them it did not fit.
LONGEST = 4000

SUBJECT = "DinkyDash feedback"


def enabled():
    """Is there anywhere to send feedback? Read at render time, never cached."""
    return bool(os.environ.get(MAIL_KEY, "").strip())


def clean(message):
    """The message as it will be sent: trimmed, and with no stray carriage returns.

    Line endings are normalised because a browser posts `\\r\\n` and the body is
    read in a mail client, not a terminal. Nothing else is stripped — this is
    somebody's own sentence and it is not ours to edit.
    """
    text = (message or "").replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def compose(message, address=None, family_id=None):
    """The body of the email: what was written, then who wrote it.

    The message goes first, because that is what is being read. Under it sit the
    two things that make an answer possible — the address, which is also the
    reply-to, and the family id, without which "my dashboard is blank" is not a
    question anybody can look into. Nothing from the dashboard goes with it: no
    name, no calendar, no written line. If the message names a child, that is
    because the person writing it chose to.
    """
    who = address or "a self-hosted dashboard"
    trailer = [f"From: {who}"]
    if family_id:
        trailer.append(f"Family: {family_id}")
    return f"{message}\n\n--\n" + "\n".join(trailer) + "\n"


def subject_for(address=None):
    """One subject per sender, so a mailbox threads two messages and not twenty."""
    return f"{SUBJECT} from {address}" if address else f"{SUBJECT} (self-hosted)"


def recipient():
    """Where a message goes, which need not be the address the pages give out.

    Defaults to the support mailbox, so a self-hosted dashboard and a deployment
    that sets nothing behave as they always have. `DINKYDASH_FEEDBACK_TO` moves
    what the form sends to another mailbox — one that is read every day rather
    than the one printed on the policy — and moves nothing else:
    `support_address()` stays the reply-to on our own mail, the contact address
    in the legal pages, and what this page offers when a send fails.

    **The two can diverge without stranding anybody**, because a reply is sent
    from wherever the message was read and carries that family's own address, so
    an answer and its thread stay together whichever mailbox answered. What must
    not diverge is this and the privacy policy: the mailbox a message lands in
    is something that page states, so a deployment that sets this says so there.

    Read at send time and never cached, like `enabled()`: the address behind a
    form is operational, and moving it should not need a restart.
    """
    chosen = os.environ.get(FEEDBACK_TO, "").strip()
    return chosen or support_address()


def submit(message, address=None, family_id=None):
    """Send one message to the feedback mailbox. Raises `mail.MailError` if it did not go.

    Imported here rather than at the top of the module, so that a deployment
    with no key never reaches `dinkydash.mail` at all.
    """
    from dinkydash import mail

    mail.send(recipient(), subject_for(address),
              compose(message, address=address, family_id=family_id),
              reply_to=address)


def support_address():
    """The address the app gives out: the fallback for a send that did not go.

    Where feedback lands as well, unless `recipient()` has been pointed
    elsewhere.
    """
    from dinkydash import mail

    return mail.support_address()
