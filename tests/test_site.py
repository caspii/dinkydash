"""The marketing site, served by Flask rather than built to `docs/`.

These assert the things `build.py` used to guarantee and that a search engine
would notice going missing: clean URLs with a trailing slash, a canonical tag
that matches, `noindex` pages rendered but kept out of the sitemap, the root
files a browser asks for unprompted, and intrinsic image dimensions.

Deliberately not "compare against docs/": that directory is being retired, and
a test that pins the new renderer to the old output would have to be deleted
with it. Parity was verified once, page by page — all 17 byte-identical — and
these assert the properties that mattered rather than the artefact.
"""

import html
import json
from pathlib import Path
import re

import pytest

from website import render
from website.site import create_site_app


@pytest.fixture(autouse=True)
def as_production(monkeypatch):
    """The site as deployed, whatever shell the tests run in.

    A Conductor shell carries CONDUCTOR_PORT, and `site.py` reads it as "the
    dashboard is on this port" — so without this, every hosted link in the
    suite would point at a local port on a developer's machine and at
    production in CI. The tests that want the preview behaviour set the
    variables themselves.
    """
    monkeypatch.delenv("CONDUCTOR_PORT", raising=False)
    monkeypatch.delenv("DINKYDASH_APP_URL", raising=False)


@pytest.fixture
def client():
    app = create_site_app(site_url="https://dinkydash.co")
    app.config["TESTING"] = True
    return app.test_client()


def test_every_content_file_is_reachable(client):
    for page in render.pages():
        assert client.get(page["url"]).status_code == 200, page["url"]


class TestHostedSignup:
    URL = "https://app.dinkydash.co/login"
    HOSTED_PAGES = {
        "/", "/about/", "/android-tablet-calendar-display/",
        "/best-digital-family-calendar/", "/dakboard-alternatives/",
        "/dakboard-vs-skylight/", "/digital-calendar-and-chore-chart/",
        "/diy-skylight-calendar/", "/echo-show-calendar-display/",
        "/fire-tv-calendar-display/", "/ipad-calendar-display/",
        "/raspberry-pi-family-calendar/", "/smart-tv-calendar-display/",
        "/skylight-calendar-alternatives/",
    }

    def test_public_pages_send_visitors_to_signup(self, client):
        for page in render.pages():
            body = client.get(page["url"]).get_data(as_text=True)
            assert not re.search(r"typeform\.com|waitlist|waiting[ -]list|join the list",
                                 body, re.I), page["url"]
            if page["url"] in self.HOSTED_PAGES:
                assert f'href="{self.URL}"' in body, page["url"]
                assert 'href="/getting-started/"' in body, page["url"]

    def test_the_app_address_is_configurable(self):
        """A preview runs the dashboard on a local port; its trial button must not
        land on production. Only the app's origin moves — the privacy and terms
        pages name `app.dinkydash.co` as a fact about production and keep it."""
        local = create_site_app(site_url="https://dinkydash.co",
                                app_url="http://127.0.0.1:5000/").test_client()
        for page in render.pages():
            body = local.get(page["url"]).get_data(as_text=True)
            assert self.URL not in body, page["url"]
            if page["url"] in self.HOSTED_PAGES:
                assert 'href="http://127.0.0.1:5000/login"' in body, page["url"]
        assert "app.dinkydash.co" in local.get("/privacy/").get_data(as_text=True)

    def test_and_read_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_APP_URL", "http://127.0.0.1:5000")
        body = create_site_app().test_client().get("/").get_data(as_text=True)
        assert 'href="http://127.0.0.1:5000/login"' in body

    def test_a_conductor_preview_finds_the_dashboard_on_its_own(self, monkeypatch):
        # Conductor runs its scripts from the main checkout, so the script on
        # this branch may never run — but it sets CONDUCTOR_PORT for whatever
        # it starts, and that is the dashboard's port.
        monkeypatch.delenv("DINKYDASH_APP_URL", raising=False)
        monkeypatch.setenv("CONDUCTOR_PORT", "55030")
        body = create_site_app().test_client().get("/").get_data(as_text=True)
        assert 'href="http://127.0.0.1:55030/login"' in body

    def test_an_explicit_address_beats_the_port(self, monkeypatch):
        monkeypatch.setenv("CONDUCTOR_PORT", "55030")
        monkeypatch.setenv("DINKYDASH_APP_URL", "https://staging.app.dinkydash.co")
        body = create_site_app().test_client().get("/").get_data(as_text=True)
        assert 'href="https://staging.app.dinkydash.co/login"' in body

    def test_production_is_untouched_by_either(self, monkeypatch):
        monkeypatch.delenv("DINKYDASH_APP_URL", raising=False)
        monkeypatch.delenv("CONDUCTOR_PORT", raising=False)
        body = create_site_app().test_client().get("/").get_data(as_text=True)
        assert f'href="{self.URL}"' in body

    def test_readme_sends_visitors_to_signup(self):
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
        assert f"]({self.URL})" in readme
        assert not re.search(r"typeform\.com|waitlist|waiting list", readme, re.I)
        assert "$39 a year or $6 a month" in readme
        assert "still being built" not in readme

    def test_every_faq_answer_in_the_schema_is_on_the_page(self, client):
        """Google requires FAQPage markup to describe content the visitor can
        see. Both copies render from one `faqs` list in the template, and this
        is what fails if somebody splits them again. Unescaped because Jinja
        writes an apostrophe as an entity and `tojson` does not."""
        body = html.unescape(client.get("/").get_data(as_text=True))
        faq = next(schema for schema in self._schemas(client)
                   if schema.get("@type") == "FAQPage")
        assert len(faq["mainEntity"]) >= 6
        for question in faq["mainEntity"]:
            assert f"<p>{question['acceptedAnswer']['text']}</p>" in body, question["name"]
            assert f"<summary>{question['name']}</summary>" in body, question["name"]

    def test_the_faq_answers_what_a_trial_visitor_asks_first(self, client):
        """The two questions somebody about to sign up actually has. Both were
        missing while the page was selling the repository rather than the
        trial, and the answers are claims about `accounts.py` and Stripe."""
        faq = next(schema for schema in self._schemas(client)
                   if schema.get("@type") == "FAQPage")
        answers = {q["name"]: q["acceptedAnswer"]["text"] for q in faq["mainEntity"]}
        after = next(a for name, a in answers.items() if "14 days" in name)
        assert "$39 a year" in after and "$6 a month" in after
        assert "Checkout" in after
        assert "still being built" not in after
        card = next(a for name, a in answers.items() if name == "Do I need a card?")
        assert "We don't ask for a card" in card
        assert "nowhere to put one" not in card

    def test_the_hosted_subscription_can_be_bought(self, client):
        """Checkout sells the hosted plan, so the offer is in stock."""
        graph = next(schema["@graph"] for schema in self._schemas(client)
                     if "@graph" in schema)
        app = next(node for node in graph
                   if node["@type"] == "SoftwareApplication")
        offers = {offer["name"]: offer for offer in app["offers"]}
        assert offers["Self-hosted"]["price"] == "0"
        assert offers["Self-hosted"]["availability"].endswith("/InStock")
        assert offers["Hosted"]["price"] == "39"
        assert offers["Hosted"]["availability"].endswith("/InStock")
        assert "PreOrder" not in offers["Hosted"]["availability"]

    def test_public_copy_does_not_say_payments_are_unbuilt(self, client):
        """The live price is $39 a year or $6 a month, and Checkout takes it."""
        stale = re.compile(
            r"still being built|aren't switched on|still in development|"
            r"planned pricing|planned \$39|nothing to charge with|PreOrder",
            re.I,
        )
        for page in render.pages():
            body = client.get(page["url"]).get_data(as_text=True)
            assert not stale.search(body), page["url"]
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
        assert not stale.search(readme)

    def test_every_page_offers_the_trial_in_the_navigation(self, client):
        """Most visitors arrive on a guide, not the home page, so the button in
        `base.html` is the only one they are shown. It sits outside `.nav-links`
        because those collapse into the hamburger on a phone."""
        checked = 0
        for page in render.pages():
            body = client.get(page["url"]).get_data(as_text=True)
            if "<nav>" not in body:
                continue     # the full-screen countdown has no site chrome
            nav = body.split("<body>")[1].split("</nav>")[0]
            assert f'class="btn btn-nav" href="{self.URL}"' in nav, page["url"]
            assert nav.index("</ul>") < nav.index('class="nav-actions"'), page["url"]
            checked += 1
        assert checked >= 20

    def _schemas(self, client):
        body = client.get("/").get_data(as_text=True)
        return [json.loads(raw) for raw in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', body, re.S)]


class TestTheNavigation:
    """What the nav is for, asserted rather than assumed.

    It is the short list of pages somebody already on the site would open, plus
    the two doors into the app. The competitor comparisons are not on it: they
    are written to be arrived at from a search, and in the nav they pointed a
    reader half-way through our own pitch at pages about the competition. They
    stay linked site-wide from the footer, which is where an entry page belongs,
    so nothing is lost to a crawler either.
    """

    LOGIN = "https://app.dinkydash.co/login"
    # Entry pages, not destinations. Named here so that adding a fourth
    # comparison and quietly putting it in the nav fails.
    COMPARISONS = (
        "/diy-skylight-calendar/",
        "/skylight-calendar-alternatives/",
        "/dakboard-alternatives/",
        "/dakboard-vs-skylight/",
        "/hearth-vs-skylight/",
    )

    def _chrome(self, client, url):
        """The nav and the footer of a page, or None where there is neither."""
        body = client.get(url).get_data(as_text=True)
        if "<nav>" not in body:
            return None      # the full-screen countdown has no site chrome
        return (body.split("<nav>")[1].split("</nav>")[0],
                body.split("<footer>")[1].split("</footer>")[0])

    def test_every_page_offers_the_way_back_in(self, client):
        """A family whose dashboard is already running arrives on a guide as
        often as anybody else, and "Start free" is not a door they would try.
        Both links go to /login, which signs in and signs up alike, so the
        labels are the only thing telling the two readers apart."""
        checked = 0
        for page in render.pages():
            chrome = self._chrome(client, page["url"])
            if chrome is None:
                continue
            nav, _ = chrome
            assert f'class="nav-signin" href="{self.LOGIN}"' in nav, page["url"]
            checked += 1
        assert checked >= 20

    def test_the_sign_in_link_moves_with_the_app_address(self):
        """Same reason as the trial button: a preview must not send anybody to
        production."""
        local = create_site_app(site_url="https://dinkydash.co",
                               app_url="http://127.0.0.1:5000/").test_client()
        body = local.get("/").get_data(as_text=True)
        assert 'class="nav-signin" href="http://127.0.0.1:5000/login"' in body
        assert self.LOGIN not in body

    def test_price_is_one_click_from_every_page(self, client):
        """Price is the answer to the question the rest of the home page argues
        about, and it used to be reachable only by scrolling. An anchor rather
        than a page, so there is only ever one copy of the number to keep true —
        which is what this asserts: the link lands on a section that exists."""
        home = client.get("/").get_data(as_text=True)
        assert 'id="pricing"' in home
        for page in render.pages():
            chrome = self._chrome(client, page["url"])
            if chrome is None:
                continue
            assert 'href="/#pricing"' in chrome[0], page["url"]

    def test_the_comparisons_are_in_the_footer_and_not_the_nav(self, client):
        for page in render.pages():
            chrome = self._chrome(client, page["url"])
            if chrome is None:
                continue
            nav, footer = chrome
            for url in self.COMPARISONS:
                assert f'href="{url}"' not in nav, f"{page['url']} -> {url}"
                assert f'href="{url}"' in footer, f"{page['url']} -> {url}"

    def test_the_menu_button_says_whether_the_menu_is_open(self, client):
        """It was an inline toggle, which left the button claiming
        aria-expanded="false" over an open menu and gave a reader no way out of
        it but the button. The script that fixes that is also what opens the
        menu at all, so a page cannot ship one without the other."""
        body = client.get("/").get_data(as_text=True)
        nav = body.split("<nav>")[1].split("</nav>")[0]
        assert 'aria-expanded="false"' in nav
        assert 'aria-controls="nav-links"' in nav
        assert 'id="nav-links"' in nav
        assert "onclick" not in nav
        assert "aria-expanded" in body.split("</nav>")[1], "nothing keeps it in step"

    def test_the_page_you_are_on_is_marked(self, client):
        """`aria-current` on the entry, which is also what colours it."""
        for url, label in (("/about/", "About"), ("/getting-started/", "Self-hosting")):
            nav = self._chrome(client, url)[0]
            assert f'href="{url}" aria-current="page">{label}<' in nav
        # Not on a page the nav does not list, and never on the anchor.
        nav = self._chrome(client, "/dakboard-alternatives/")[0]
        assert "aria-current" not in nav


class TestUrls:
    def test_the_home_page_is_the_root(self, client):
        assert client.get("/").status_code == 200

    def test_pages_live_under_a_trailing_slash(self, client):
        assert client.get("/about/").status_code == 200

    def test_a_missing_slash_redirects_rather_than_404s(self, client):
        response = client.get("/about")
        assert response.status_code == 308
        assert response.headers["Location"].endswith("/about/")

    def test_a_nested_page_keeps_its_path(self, client):
        # The birthday countdown tool is /birthday-countdown/display/.
        assert client.get("/birthday-countdown/display/").status_code == 200

    def test_an_unknown_page_is_a_branded_404(self, client):
        response = client.get("/no-such-page/")
        assert response.status_code == 404
        assert "That page is not here" in response.get_data(as_text=True)


class TestWhatSearchEnginesRead:
    def test_the_canonical_tag_matches_the_url(self, client):
        page = client.get("/dakboard-alternatives/").get_data(as_text=True)
        assert '<link rel="canonical" href="https://dinkydash.co/dakboard-alternatives/">' in page

    def test_the_sitemap_lists_the_real_pages(self, client):
        sitemap = client.get("/sitemap.xml").get_data(as_text=True)
        assert sitemap.startswith('<?xml version="1.0"')
        assert "<loc>https://dinkydash.co/</loc>" in sitemap
        assert "<loc>https://dinkydash.co/getting-started/</loc>" in sitemap

    def test_noindex_pages_are_served_but_not_listed(self, client):
        noindex = [p for p in render.pages() if p["front_matter"].get("noindex")]
        assert noindex, "the fixture for this test is a real noindex page"
        sitemap = client.get("/sitemap.xml").get_data(as_text=True)
        for page in noindex:
            assert client.get(page["url"]).status_code == 200
            assert f"<loc>https://dinkydash.co{page['url']}</loc>" not in sitemap

    def test_robots_points_at_the_sitemap(self, client):
        assert "Sitemap: https://dinkydash.co/sitemap.xml" in \
            client.get("/robots.txt").get_data(as_text=True)

    def test_a_page_carries_its_faq_as_data(self, client):
        # Not a rich-result play; it is so answer engines get the Q&A as data.
        with_faq = [p for p in render.pages() if p["front_matter"].get("faq")]
        assert with_faq
        page = client.get(with_faq[0]["url"]).get_data(as_text=True)
        assert '"@type": "FAQPage"' in page

    def test_the_origin_is_configurable(self):
        """A staging copy must not tell Google it is production."""
        staging = create_site_app(site_url="https://staging.app.dinkydash.co").test_client()
        assert "https://staging.app.dinkydash.co/" in \
            staging.get("/sitemap.xml").get_data(as_text=True)


class TestTheFilesBrowsersAskForUnprompted:
    @pytest.mark.parametrize("path,kind", [
        ("/favicon.ico", "image"),
        ("/favicon.svg", "image"),
        ("/apple-touch-icon.png", "image"),
        ("/fonts.css", "text/css"),
        ("/fonts/nunito-latin.woff2", "font"),
    ])
    def test_it_is_served(self, client, path, kind):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["Content-Type"].startswith(kind[:5]) or kind in \
            response.headers["Content-Type"]

    def test_an_image_is_served(self, client):
        assert client.get("/images/og-board-kitchen.jpg").status_code == 200

    def test_the_root_route_cannot_be_used_to_browse_the_directory(self, client):
        # It is narrowed to a known list, so it can neither swallow a page URL
        # nor hand out anything else that happens to sit in static/.
        assert client.get("/render.py").status_code == 404
        assert client.get("/site.py").status_code == 404
        assert client.get("/../site.py").status_code in (301, 308, 404)


class TestLayoutStability:
    def test_content_images_carry_intrinsic_dimensions(self, client):
        """Without width and height the text below jumps when an image loads."""
        page = client.get("/").get_data(as_text=True)
        images = re.findall(r'<img[^>]*src="(/images/[^"]+)"[^>]*>', page)
        assert images, "the home page should have content images"
        for tag in re.findall(r'<img[^>]*src="/images/[^"]+"[^>]*>', page):
            assert 'width="' in tag and 'height="' in tag, tag[:100]

    def test_everything_after_the_first_image_is_lazy(self, client):
        tags = re.findall(r'<img[^>]*src="/images/[^"]+"[^>]*>',
                          client.get("/").get_data(as_text=True))
        assert 'loading="lazy"' not in tags[0]        # usually the LCP element
        assert all('loading="lazy"' in t for t in tags[1:])


class TestItIsNotTheBoard:
    def test_the_site_app_serves_no_settings_ui(self, client):
        """Two apps, one codebase. The marketing site has no way into the dashboard."""
        assert client.get("/settings/").status_code == 404

    def test_it_promises_not_to_leak_the_referrer(self, client):
        assert client.get("/").headers["Referrer-Policy"] == "no-referrer"

    def test_healthz_reads_nothing(self, client):
        body = client.get("/healthz").get_json()
        assert body["status"] == "ok"


class TestOnlyTheRealSiteIsIndexable:
    """App Platform always hands out an .ondigitalocean.app name, and a preview
    domain is a second crawlable copy of the pages the funnel rests on."""

    def test_the_canonical_host_is_indexable(self, client):
        response = client.get("/", headers={"Host": "dinkydash.co"})
        assert "X-Robots-Tag" not in response.headers

    def test_www_redirects_rather_than_serving(self, client):
        """GitHub Pages 301'd www to the apex; the app has to keep doing it."""
        response = client.get("/getting-started/", headers={"Host": "www.dinkydash.co"})
        assert response.status_code == 301
        assert response.headers["Location"] == "https://dinkydash.co/getting-started/"

    @pytest.mark.parametrize("host", ["preview.dinkydash.co",
                                      "dinkydash-site-mgk6u.ondigitalocean.app"])
    def test_every_other_copy_asks_not_to_be_indexed(self, client, host):
        response = client.get("/", headers={"Host": host})
        assert response.headers["X-Robots-Tag"] == "noindex"


class TestInternalLinksResolve:
    """Every `/path/` written in content or a template is a page that exists.

    The provider guides and the device pages cross-link each other and the
    footer lists all of them, so one renamed slug now silently 404s from a
    dozen places. Nothing else notices: the sitemap is built from the files
    that exist, not from the links pointing at them.
    """

    # `[text](/url/)` in Markdown, and `href="/url/"` in a template.
    LINK = re.compile(r'\]\((/[^)#\s]*)(?:#[^)]*)?\)|href="(/[^"#]*)"')
    # Served by their own routes rather than by a content file.
    NOT_A_PAGE = ("/images/", "/fonts/")
    NOT_A_PAGE_SUFFIX = (".xml", ".txt", ".ico", ".svg", ".png", ".css", ".webmanifest")

    def test_no_internal_link_points_at_a_missing_page(self):
        pages = {page["url"] for page in render.pages()}
        broken = set()
        sources = sorted(render.CONTENT.rglob("*.md")) + sorted(render.TEMPLATES.rglob("*.html"))
        for path in sources:
            for markdown_url, href in self.LINK.findall(path.read_text(encoding="utf-8")):
                url = markdown_url or href
                if not url or url.startswith(self.NOT_A_PAGE) \
                        or url.endswith(self.NOT_A_PAGE_SUFFIX):
                    continue
                if url not in pages:
                    broken.add(f"{path.name} -> {url}")
        assert not broken, sorted(broken)


class TestExampleCalendarUrlsAreVisiblyFake:
    """The per-provider setup guides exist to show what a calendar link looks
    like, so the site now carries several example feed URLs on purpose.

    A real one pasted in here would be a permanent, world-readable password to
    somebody's calendar, in every clone and every fork. gitleaks catches the
    Google and iCloud shapes over the whole history; this catches the rest
    before it is committed, by requiring every feed URL on the site to carry
    the same visible `xxxx` marker `config.example.yaml` uses.

    It cannot check a screenshot. Read the address bar before publishing one.
    """

    # A feed address: an .ics file, or one of the provider paths that serves a
    # calendar without the extension.
    FEED_URL = re.compile(
        r"(?:https?|webcal)://[^\s`\"')<>]*\.ics\b"
        r"|(?:https?|webcal)://[^\s`\"')<>]*/(?:ical|published)/[^\s`\"')<>]*",
        re.I)

    def _sources(self):
        return sorted(render.CONTENT.rglob("*.md")) + sorted(render.TEMPLATES.rglob("*.html"))

    def test_the_site_carries_example_feed_urls_at_all(self):
        """The fixture for the test below is the provider guides themselves."""
        found = [url for path in self._sources()
                 for url in self.FEED_URL.findall(path.read_text(encoding="utf-8"))]
        assert len(found) >= 4, found

    def test_every_one_of_them_is_marked_fake(self):
        for path in self._sources():
            for url in self.FEED_URL.findall(path.read_text(encoding="utf-8")):
                assert "xxxx" in url.lower(), f"{path.name}: {url}"


class TestCloudflareDoesNotEatShellCommands:
    """App Platform serves through Cloudflare, whose Email Address Obfuscation
    rewrote `ssh pi@raspberrypi.local` in the setup guide into a JavaScript
    link. Found on the live site, not in review."""

    def test_code_blocks_opt_out_of_obfuscation(self, client):
        page = client.get("/getting-started/").get_data(as_text=True)
        assert "<!--email_off-->" in page
        assert "ssh pi@raspberrypi.local" in page

    def test_the_marker_wraps_the_block_rather_than_the_page(self, client):
        page = client.get("/getting-started/").get_data(as_text=True)
        assert page.count("<!--email_off-->") == page.count("<!--email_on-->")
        assert page.count("<!--email_off-->") > 1, "one pair per code block"


class TestThePrivacyPageNamesEverySubProcessor:
    """A sub-processor list is a promise that nothing else is called (CLAUDE.md).

    Every service the hosted app sends anything to is on it — including the
    one that only ever sees an error report (DIN-35).
    """

    @pytest.mark.parametrize("who", ["Anthropic", "DigitalOcean", "SendGrid",
                                     "Cloudflare", "Sentry"])
    def test_it_names(self, client, who):
        page = client.get("/privacy/").get_data(as_text=True)
        assert who in page

    def test_it_says_what_sentry_never_sees(self, client):
        page = client.get("/privacy/").get_data(as_text=True)
        assert "Sentry sees that something broke" in page
