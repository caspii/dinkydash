"""The weekly crawl of the live site, against a fake site with no network.

What matters is that it reports every failure and stays quiet otherwise: a
check that prints on a pass gets ignored, and one that misses a 404 is worse
than none.
"""

import pytest

from website import check_live

SITE = "https://site.example"
APP = "https://app.example"
SITEMAP = f"<urlset><url><loc>{SITE}/</loc></url><url><loc>{SITE}/about/</loc></url></urlset>"
FINE = "<p>DinkyDash hosted is $39 a year or $6 a month.</p>"


@pytest.fixture
def served(monkeypatch):
    pages = {
        f"{SITE}/sitemap.xml": (200, SITEMAP),
        f"{SITE}/": (200, FINE + '<a href="/about/">About</a> <a href="/faq/#price">FAQ</a>'
                          '<a href="https://elsewhere.example/">Out</a>'),
        f"{SITE}/about/": (200, FINE),
        f"{SITE}/faq/": (200, FINE + '<img src="/images/x.png">'),
        f"{APP}/login": (200, "<p>Sign in</p>"),
    }
    fetched = []

    def fetch(url):
        fetched.append(url)
        return pages.get(url, (404, ""))

    monkeypatch.setattr(check_live, "fetch", fetch)
    return pages, fetched


def test_a_clean_site_reports_nothing(served, capsys):
    assert check_live.main(["--site", SITE, "--app", APP]) == 0
    assert capsys.readouterr().out == ""


def test_it_follows_internal_links_once_and_leaves_other_hosts_alone(served):
    _, fetched = served
    check_live.check(SITE, APP)
    assert f"{SITE}/faq/" in fetched
    assert len(fetched) == len(set(fetched))
    assert not any("elsewhere" in url for url in fetched)


def test_a_broken_internal_link_fails(served, capsys):
    pages, _ = served
    pages[f"{SITE}/about/"] = (200, FINE + '<a href="/gone/">Gone</a>')
    assert check_live.main(["--site", SITE, "--app", APP]) == 1
    assert capsys.readouterr().out == f"{SITE}/gone/: status 404\n"


def test_the_app_pages_are_checked_too(served):
    pages, _ = served
    pages[f"{APP}/login"] = (500, "")
    assert check_live.check(SITE, APP) == [f"{APP}/login: status 500"]


@pytest.mark.parametrize("copy", ["<p>Hosted is $29 a year.</p>", "<p>TODO: price</p>",
                                  "<p>See [the guide](/x/)</p>"])
def test_the_content_rules_apply_to_what_is_served(served, copy):
    pages, _ = served
    pages[f"{SITE}/about/"] = (200, copy)
    failures = check_live.check(SITE, APP)
    assert failures and all(line.startswith(f"{SITE}/about/: ") for line in failures)


def test_cloudflare_email_obfuscation_is_not_ours(served):
    pages, _ = served
    pages[f"{SITE}/about/"] = (200, FINE + '<a href="/cdn-cgi/l/email-protection" '
                               'class="__cf_email__" data-cfemail="8c">[email&#160;protected]</a>')
    assert check_live.check(SITE, APP) == []


def test_a_missing_sitemap_is_a_failure(served):
    pages, _ = served
    del pages[f"{SITE}/sitemap.xml"]
    assert f"{SITE}/sitemap.xml: status 404" in check_live.check(SITE, APP)
