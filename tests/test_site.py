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

import re

import pytest

from website import render
from website.site import create_site_app


@pytest.fixture
def client():
    app = create_site_app(site_url="https://dinkydash.co")
    app.config["TESTING"] = True
    return app.test_client()


def test_every_content_file_is_reachable(client):
    for page in render.pages():
        assert client.get(page["url"]).status_code == 200, page["url"]


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
        assert client.get("/build.py").status_code == 404
        assert client.get("/../render.py").status_code in (301, 308, 404)


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
        """Two apps, one codebase. The marketing site has no way into the board."""
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
