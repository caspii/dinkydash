# Publishing content

How a public page gets from a draft to dinkydash.co, and what stops it on the way. This covers
everything a visitor can read without signing in: `website/content/*.md`, `website/templates/*.html`
and the root `README.md`. [voice.md](voice.md) settles how a sentence sounds; this file settles
whether it's allowed out.

Written after the content audit of 6 October 2026 (DIN-119 to DIN-129). That audit found an About
page saying there's no DinkyDash cloud twelve days after the hosted plan started charging, a
competitor's hardware priced 20% under its own shop, and a dozen pages selling "free" without
the price after the trial. Every one of them passed review, because nobody was checking against
anything.

## Who does what

| Step | Who | What it means |
|---|---|---|
| Draft | The CEO agent, through a cloud agent, or Caspar | A branch off `main` and a pull request. Never a direct push. |
| Check | The CEO agent | Works through the checklist below on the PR, and writes in the PR description what was verified and how (code path, competitor URL, date). |
| Approve | Caspar | Merging is the approval. **Nothing merges without Caspar**, including fixes. |
| Re-check | The CEO agent, monthly | Re-verifies every competitor price and the "checked" dates on the pages that carry them. Stale dates are a content issue in Linear. |

Fixes found later go in Linear on the **Dinky Dash** team: status Todo, the single label
**Content**, no assignee, and no customer details, because issues sync to public GitHub.

## The checklist

Every item, on every page the PR touches:

1. **Audience.** Written for the page's real reader in plain language, per voice.md: a parent, not
   a developer. Code blocks and implementation names (cron, JSON, payload, the worker) only on the
   self-hosting pages (`getting-started`, `raspberry-pi-family-calendar`) and the README.
2. **One point.** The page has one clear point, an opening that states it, and a structure that
   follows from it. No list in the first screen that a reader has to decode.
3. **Our claims are true.** Every sentence about what DinkyDash does is traced to the code
   (voice.md's table says where). Prices: hosted $39 a year or $6 a month after a 14-day trial
   with no card; self-hosted $0 plus about $0.13 a month of the reader's own Anthropic key.
   Nothing unbuilt is described as built. A page that says "free" also says which version.
4. **Their claims are checked.** Every competitor price or feature is read off that competitor's
   own site or store on the day, and the page says "checked <date>". If it can't be verified,
   it's softened or removed.
5. **Nothing unfinished.** No TBD, TODO, placeholder, internal note, draft text, unrendered
   Markdown, or AI filler ("both companies would rather you didn't know", "game-changer").
6. **Links and CTAs work.** Internal links resolve. The trial link goes to
   `https://app.dinkydash.co/login`, and a non-technical reader is never sent only to GitHub or
   a Raspberry Pi build.
7. **Legal pages** (`privacy`, `terms`) change in the same PR as the code they describe, and
   their "Last updated" date moves with them.

## What blocks publishing

A PR doesn't merge while any of these is true:

- **CI fails.** `tests/test_site.py` fails the build on:
  - draft markers on any rendered page or the README (`TBD`, `TODO`, `FIXME`, `XXX`, lorem ipsum,
    "internal note", "note to self", `[insert`, placeholder)
  - unrendered Markdown in visible text (`](` or a bare `[text]`)
  - a contraction that ends a clause ("where it's.")
  - any DinkyDash price other than $39 a year or $6 a month, and the retired $29 offer
  - an internal link to a page that doesn't exist, or an example calendar address without `xxxx`
  - "payments aren't live" language, or a hosted offer that isn't $39 in the page's data
- **The checklist isn't in the PR description**, with what was verified against what.
- **Caspar hasn't merged it.**

After a merge, the CEO agent crawls the live site (every sitemap page and every link on it) and
records any non-200 status in Linear.

## What a test can't catch

Whether a sentence is true, whether a competitor changed their price yesterday, and whether a
page makes sense to a parent. Items 1 to 4 are a person's job, and the date on the page is the
record that somebody did it.
