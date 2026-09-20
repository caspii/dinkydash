# Voice and copy

How anything a customer reads should sound: the marketing site, the settings UI, email,
the model's system prompt, and the README. [doc/terminology.md](terminology.md) settles
*which word*; this file settles *how the sentence sounds*.

**The register of this repository's own documentation is not the product's voice.**
`CLAUDE.md` and its siblings are dense, formal and written without contractions, because
they are engineering documentation read by somebody making a change. Copy is read by a
parent deciding whether to trust us with their children's birthdays. Writing the second
in the voice of the first is the most common way this goes wrong, and matching the
surrounding page is not a defence when the surrounding page has the same fault.

The fuller craft guide these rules come from is
`~/repos/keepthescore/documentation/copywriting/` — `writing-style.md` for voice,
`page-types.md` for the shape of a marketing page. Read them before a large piece of
writing. Take the craft and leave the rest: keyword research, conversion arguments and
plan-naming there are another product's, and the commercial half belongs in Linear
either way.

## Who is reading

A parent who priced up a wall calendar, balked, and has a spare tablet in a drawer. They
are not technical, they are not stupid, and they are giving a stranger their children's
names. Write to one of them, not to "families".

## The rules

**1. Use contractions.** "It's", "don't", "we'll", "aren't". Read the sentence aloud: if
you would not say it to somebody in a kitchen, rewrite it. This one rule fixes most stiff
copy on its own.

> Not: *It is the same dashboard either way. The only difference is who keeps it running.*
> But: *It's the same dashboard either way. The only difference is who keeps it running.*

Keep the full form when the weight is the point — "Nothing is sold" lands harder than
"Nothing's sold" — but that is the exception you reach for, not the default.

**2. Vary the length.** A three-word sentence after a long one creates rhythm. Fragments
are fine. If three sentences in a row start the same way, rewrite two.

**3. Cut the hedging.** Delete "typically", "generally", "often", "in many cases",
"it is important to note". If something is true, say it is true, and name the exception
rather than softening everything around it.

**4. Be specific.** "Under a dollar a month" beats "inexpensive". "An old iPad" beats
"a compatible device". Replace "various" and "several" with the actual examples, or cut
the sentence.

**5. Say the awkward part.** Setting up a Pi is an afternoon. There is no login on the
self-hosted app. An Echo Show closes its browser and we say so on its own page. A caveat
stated plainly is worth more than the sentence it complicates, and the honesty is the
product's argument, not a cost of making it.

**6. Three strong points beat seven weak ones.** Skip the obvious, merge the related.
A list that runs to seven bullets is usually four bullets and some throat-clearing.

**7. "You" and "we", not "users" and "the platform".** We run the machine. You paste a
link. Nobody is a user.

**8. British English, and the house conventions.** `%-d %B` dates ("25 December"), 24-hour
times by default, and the nouns in [terminology.md](terminology.md) — a **dashboard** is
the display, a **screen** is the device it is on.

**9. No backstage language.** "The worker", "the payload", "single mode", "the tick",
"cloud mode", "the store" — every one of those is an implementation name and none of them
mean anything to a reader. Describe what happens instead.

## Every claim is checked against the code

This is the rule with teeth, because a plausible sentence about a feature that does not
exist is indistinguishable from one about a feature that does — right up until a customer
relies on it.

**Before writing any sentence that says the product does something, find it in the code.**
Not in another page of copy, which may have the same fault. The usual places:

| A claim about | Read |
|---|---|
| When anything happens on a schedule | `dinkydash/schedule.py` — there are two cadences, and one of them is a time the family chooses |
| What is stored, sent, or kept | `website/content/privacy.md`, and the code it describes |
| The link a wall screen uses | `dinkydash/screens.py` |
| What a family can change | `web/routes/settings.py` and `web/templates/settings/` |
| What the trial does and what billing can do | `doc/billing.md`, `dinkydash/billing.py` |

Three claims that are wrong in ways that read as right:

- **"Every morning."** The daily message is written once a day at a time the family sets.
  The calendars refresh on their own, separate, much shorter cycle. "The morning job" is
  neither of those things.
- **"Backed up."** There is an **Export** button. Infrastructure snapshots are a deletion
  caveat in the privacy policy, not a feature somebody can use.
- **"Never leaves your house."** Self-hosting still sends the day's agenda to Anthropic,
  under the reader's own key. What is true is that *we* never see it.

If a claim would be good and you cannot find it in the code, it is a feature request.
Write the sentence that is true instead.

## What is not written here

Prices may appear; the argument for a price may not. Positioning, keyword research,
competitor tables and anything framing the site as a funnel are Linear documents on the
**Dinky Dash (`DIN`)** team, per the root [CLAUDE.md](../CLAUDE.md). This file is craft.

## Before you ship it

- [ ] Read it aloud. Did you run out of breath, or say a phrase you never say?
- [ ] Contractions where you would use them in speech?
- [ ] Any hedging words left?
- [ ] Every capability claim traced to the code?
- [ ] Any implementation name leaking through?
- [ ] British spelling, `%-d %B` dates, the terminology.md nouns?
