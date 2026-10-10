"""The dashboard still lays out in Safari 12.

A 4:3 landscape tablet takes the two-column layout (`min-aspect-ratio: 5/4`).
That engine has grid gutters, `min()` and `max()`, and the aspect-ratio
*media feature*. It does not have flex `gap`, `clamp()`, the `aspect-ratio`
property, `inset`, `:is()` / `:where()`, container queries, `dvh` / `svh`,
or CSS nesting. `@supports (gap)` is true there anyway, because grid gutters
already answer it, so it is not a guard. The script is the same file the
wall runs, and it has to parse: no optional chaining, `??`, `Array#at`,
`replaceAll`, `structuredClone` or `ResizeObserver`.

A newer feature may appear only inside an `@supports` test Safari 12 fails.
The fallbacks — margins, and a plain `3.2vh` then `max(min())` before
`clamp()` — are what that engine actually uses.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOARD = REPO / "web" / "templates" / "board.html"
FONTS = REPO / "web" / "templates" / "_fonts.html"

# A positive @supports mentioning one of these is false in Safari 12, so the
# block is not part of the page that engine reads.
_MODERN = (
    "inset", "clamp(", ":is(", ":where(", ":has(", "aspect-ratio",
    "container-type", "dvh", "svh", "lvh", "dvw", "svw", "lvw",
)

_CSS_BANS = (
    ("clamp()", re.compile(r"clamp\s*\(")),
    ("gap shorthand", re.compile(r"(?<![\w-])gap\s*:")),
    (":is()", re.compile(r":is\s*\(")),
    (":where()", re.compile(r":where\s*\(")),
    (":has()", re.compile(r":has\s*\(")),
    ("container query", re.compile(r"@container\b")),
    ("inset", re.compile(r"(?<![\w-])inset\s*:")),
    ("aspect-ratio property", re.compile(r"(?<![\w-])aspect-ratio\s*:")),
    ("dynamic viewport unit", re.compile(r"(?<![\w-])[dsl]v[hw]\b")),
    ("CSS nesting", re.compile(r"(?<![\w-])&")),
)

_JS_BANS = (
    ("optional chaining", re.compile(r"\?\.")),
    ("nullish coalescing", re.compile(r"\?\?")),
    ("Array.prototype.at", re.compile(r"\.at\s*\(")),
    ("replaceAll", re.compile(r"\breplaceAll\s*\(")),
    ("structuredClone", re.compile(r"\bstructuredClone\s*\(")),
    ("ResizeObserver", re.compile(r"\bResizeObserver\b")),
)


def _strip_comments(text, *, js=False):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    if js:
        text = re.sub(r"(^|[^:])//[^\n]*", r"\1", text, flags=re.M)
    return text


def _matching_brace(text, open_at):
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise AssertionError("unbalanced braces in a dashboard stylesheet")


def _modern_only(condition):
    """True when Safari 12 drops the @supports block rather than reading it."""
    cond = condition.strip()
    if re.match(r"not\b", cond):
        return False
    return any(token in cond for token in _MODERN)


def unguarded_css(css):
    """CSS a Safari 12 parser applies: modern-only @supports blocks removed."""
    css = _strip_comments(css)
    return _drop_modern(css)


def _drop_modern(css):
    out = []
    i = 0
    while True:
        j = css.find("@supports", i)
        if j < 0:
            out.append(css[i:])
            break
        out.append(css[i:j])
        brace = css.find("{", j)
        condition = css[j + len("@supports"):brace]
        end = _matching_brace(css, brace)
        if not _modern_only(condition):
            out.append(_drop_modern(css[brace + 1:end]))
        i = end + 1
    return "".join(out)


def css_findings(css):
    readable = unguarded_css(css)
    return [name for name, pattern in _CSS_BANS if pattern.search(readable)]


def js_findings(script):
    readable = _strip_comments(script, js=True)
    return [name for name, pattern in _JS_BANS if pattern.search(readable)]


def _blocks(text, tag):
    return re.findall(rf"<{tag}>(.*?)</{tag}>", text, flags=re.S)


class TestTheGuard:
    """The scanner is what fails the build. These pin its idea of a guard."""

    def test_gap_inside_supports_gap_still_counts(self):
        # Grid gutters make `@supports (gap)` true in Safari 12. Flex gap is
        # not there, so a block gated on gap is still read — and still broken.
        css = "@supports (gap: 1rem) { .a { gap: 1rem; } }"
        assert css_findings(css) == ["gap shorthand"]

    def test_inset_hides_flex_gap(self):
        css = (
            ".a > * + * { margin-top: 1rem; }"
            "@supports (inset: 0) { .a { gap: 1rem; } .a > * + * { margin-top: 0; } }"
        )
        assert css_findings(css) == []

    def test_clamp_is_hidden_and_the_media_feature_is_not_the_property(self):
        css = (
            "html { font-size: 3.2vh; }"
            "@supports (font-size: clamp(1px, 1px, 1px)) {"
            " html { font-size: clamp(12px, 3.2vh, 40px); } }"
            "@media (min-aspect-ratio: 5/4) { .body { column-gap: 2.2rem; } }"
        )
        assert css_findings(css) == []

    def test_a_negated_supports_is_what_the_old_engine_reads(self):
        css = "@supports not (inset: 0) { .a { gap: 1rem; } }"
        assert css_findings(css) == ["gap shorthand"]


class TestTheDashboard:
    def test_the_source_safari_12_reads_has_none_of_the_missing_features(self):
        board = BOARD.read_text()
        fonts = FONTS.read_text()
        css = "\n".join(_blocks(board, "style") + _blocks(fonts, "style"))
        script = "\n".join(_blocks(board, "script"))
        assert css_findings(css) == []
        assert js_findings(script) == []

    def test_the_fallbacks_are_the_ones_the_old_engine_uses(self):
        css = BOARD.read_text()
        # No-JS type size, in the order a parser applies them.
        assert "html { font-size: 3.2vh; }" in css
        assert "html { font-size: max(12px, min(3.2vh, 40px)); }" in css
        assert "font-size: clamp(12px, 3.2vh, 40px);" in css
        # The landscape switch is the old media feature, and the gutter is
        # named both ways so an alias-only grid still separates the columns.
        assert "@media (min-aspect-ratio: 5/4) and (min-width: 640px)" in css
        assert "grid-column-gap: 2.2rem;" in css
        assert "column-gap: 2.2rem;" in css
        # Each flex gap has a margin of the same length outside @supports.
        for fallback in (
            ".board > * + * { margin-top: 1rem; }",
            ".head > * + * { margin-left: 1rem; }",
            ".body > * + * { margin-top: 1.35rem; }",
            ".events > * + * { margin-top: 0.65rem; }",
            ".event > * + * { margin-left: 0.9rem; }",
            ".tomorrow .events > * + * { margin-top: 0.4rem; }",
            ".empty > * + * { margin-top: 0.45rem; }",
            ".side > * + * { margin-top: 1.35rem; }",
            ".chores > * + * { margin-top: 0.7rem; }",
            "margin-right: 0.6rem;",
            ".countdowns > * + * { margin-top: 0.7rem; }",
            ".countdown > * + * { margin-left: 0.7rem; }",
            ".waiting > * + * { margin-top: 1.4rem; }",
            "margin-right: 0.7rem;",
        ):
            assert fallback in css
        # Landscape must not also keep the stacked margin, or the side column drops.
        media = css.split("@media (min-aspect-ratio: 5/4) and (min-width: 640px)", 1)[1]
        media = media.split("@supports", 1)[0]
        assert ".body > * + * { margin-top: 0; }" in media
