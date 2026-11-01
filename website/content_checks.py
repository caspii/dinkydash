"""What a public page must not say, as data both the tests and the live check read.

`tests/test_site.py` runs these against every page as rendered from the
working tree, and blocks a merge. `website/check_live.py` runs the same ones
against the pages as served from production, once a week. One set of rules, so
the gate before publishing and the check after it cannot disagree.

Standard library only: the live check runs on a bare Python with nothing
installed.
"""

import html
import re

# Draft text that has reached a public page at least once on a sister product.
# Case-sensitive for the shouted markers, so "todo list" is fine.
DRAFT = re.compile(r"\bTBD\b|\bTODO\b|\bFIXME\b|\bXXX\b|\bTKTK\b")
DRAFT_ANY_CASE = re.compile(
    r"lorem ipsum|internal note|note to self|\[insert|\[placeholder|"
    r"citation needed|as an ai language model|\bplaceholder\b",
    re.I)
# Markdown that failed to render: a bare `[text](url)` or `[text]` left in the
# visible text.
UNRENDERED = re.compile(r"\]\(|\[[^\]\n]{1,60}\](?!\()")
# A contraction can't end a clause: "where it's." reads as a typo.
CLAUSE_FINAL_CONTRACTION = re.compile(
    r"\b(?:there|it|that|here|what|where|who)'s[ \t]*[.,;:!?)]", re.I)

# A sentence that names DinkyDash or the hosted plan, and a price in it.
OURS = re.compile(r"DinkyDash|hosted|we host|Start free|free trial|14-day|fourteen days", re.I)
PRICE = re.compile(r"\$(\d+(?:\.\d+)?)\s*(?:a|per|/)\s*(year|yr|month|mo)\b", re.I)
ALLOWED_PRICES = {("39", "year"), ("6", "month")}
# A competitor's price in the same sentence is fine as long as the sentence
# doesn't attach it to us.
THEIRS = re.compile(r"Skylight|Hearth|DAKboard|Mango|Cozyla|Cozi|Dæly|Plus|"
                    r"Essential|Pro\b|membership|Anthropic|AI key|API")
# The retired launch offer, anywhere in the page source.
RETIRED_PRICE = re.compile(r"\$29(?![\d.])")


def visible(html_text):
    """The text a visitor reads: no script, style, code block or tag attribute,
    so an `<input placeholder=...>` or a shell command cannot trip a check."""
    text = re.sub(r"<(script|style|pre|code)\b.*?</\1>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text).replace("’", "'")


def draft_markers(text):
    return [m.group(0) for pattern in (DRAFT, DRAFT_ANY_CASE) for m in pattern.finditer(text)]


def unrendered_markdown(text):
    return [m.group(0) for m in UNRENDERED.finditer(text)]


def clause_final_contractions(text):
    return [text[max(0, m.start() - 30):m.end()]
            for m in CLAUSE_FINAL_CONTRACTION.finditer(text)]


def wrong_prices(text):
    """Every price attached to DinkyDash that is not $39 a year or $6 a month,
    read a sentence or a table row at a time — the unit a reader takes a price
    from."""
    wrong = []
    for chunk in re.split(r"(?<=[.!?])\s+|\n", text):
        if not OURS.search(chunk):
            continue
        for amount, period in PRICE.findall(chunk):
            period = "year" if period.lower() in ("year", "yr") else "month"
            if (amount, period) in ALLOWED_PRICES or THEIRS.search(chunk):
                continue
            wrong.append(f"${amount}/{period} in {chunk.strip()[:120]!r}")
    return wrong


def retired_price(html_text):
    return bool(RETIRED_PRICE.search(html_text))


def problems(html_text):
    """Every check above, on one served page, as readable lines."""
    text = visible(html_text)
    found = [f"draft marker {m!r}" for m in draft_markers(text)]
    found += [f"unrendered Markdown {m!r}" for m in unrendered_markdown(text)]
    found += [f"contraction ends a clause {m!r}" for m in clause_final_contractions(text)]
    found += [f"wrong price {m}" for m in wrong_prices(text)]
    if retired_price(html_text):
        found.append("the retired $29 offer")
    return found
