"""The emoji picker: the quick picks, None, and a dialog with the rest.

Every place an emoji can be set — a person's avatar, a pet's, a chore's, a special
date's — is the one `emoji` field kind, so the four sections go through one template
branch. The dialog itself is JavaScript; what these tests hold in place is the markup
it hangs off, the list it reads, and what the server does with what it sends back.
"""

import json
import pathlib
import re

import pytest

from dinkydash import config as config_module
from dinkydash.store import FileStore
from tests.conftest import client_for
from tests.test_settings_improvements import Form
from web import create_app
from web.assets import CACHED_FOR_A_YEAR, static_url
from web.emoji import LONGEST_EMOJI, one_emoji
from web.routes.settings import EMOJI_SUGGESTIONS, SECTIONS

REPO = pathlib.Path(__file__).resolve().parent.parent
LIST = REPO / "web" / "static" / "emoji.json"
DIALOG = REPO / "web" / "templates" / "settings" / "_emoji_picker.html"

EMOJI_SECTIONS = [name for name, section in SECTIONS.items()
                  if any(kind == "emoji" for _n, _l, kind, _r, _h in section["fields"])]

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
    avatar_emoji: "🦖"
pets:
  - id: biscuit1
    name: "Biscuit"
    type: "dog"
    avatar_emoji: "🦩"
recurring:
  - id: table123
    title: "Set the table"
    choices: ["Mia"]
special_dates:
  - id: xmas1234
    title: "Christmas"
    emoji: "🎄"
    date: "12/25"
'''


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG)
    return path


@pytest.fixture
def client(config_path):
    return client_for(create_app(FileStore(config_path)))


def saved(config_path, key):
    return config_module.load_config(config_path)[key]


def plain(emoji):
    """A variation selector is a rendering hint, not a different emoji."""
    return emoji.replace("\ufe0f", "")


# -- every emoji field, the same way ----------------------------------------------

class TestEveryEmojiField:
    def test_four_sections_have_one(self):
        assert EMOJI_SECTIONS == ["people", "pets", "recurring", "special_dates"]

    @pytest.mark.parametrize("section", EMOJI_SECTIONS)
    def test_the_quick_picks_none_and_the_way_to_the_rest(self, client, section):
        page = client.get(f"/settings/{section}/new").get_data(as_text=True)
        for choice in EMOJI_SUGGESTIONS[section]:
            assert f'value="{choice}"' in page
        assert 'class="text">None</label>' in page
        assert "data-emoji-picker" in page
        # The button is hidden in the markup: without the script there is no dialog to open,
        # and the quick picks work as they always did.
        assert re.search(r'<button class="more" type="button" hidden data-src="/static/emoji\.json\?v=[0-9a-f]{12}"', page)
        assert 'id="emoji-dialog"' in page and "Choose an emoji" in page
        assert re.search(r'emoji-picker\.js\?v=[0-9a-f]{12}', page)

    def test_a_calendar_has_no_emoji_and_gets_none_of_it(self, client):
        page = client.get("/settings/calendars/new").get_data(as_text=True)
        assert "data-emoji-picker" not in page
        # The shared sheet styles the dialog on every page; the dialog itself is only drawn here.
        assert 'id="emoji-dialog"' not in page
        assert not re.search(r'<script src="/static/emoji-picker\.js', page)

    def test_the_dialog_sits_outside_the_form_and_puts_nothing_in_it(self, client):
        # Enter in the search box must not press Save, and a named control in the dialog
        # would ride along with it.
        page = client.get("/settings/recurring/new").get_data(as_text=True)
        assert page.index('id="emoji-dialog"') > page.index("</form>")
        assert 'name="' not in DIALOG.read_text()


# -- what is ticked when the form opens ---------------------------------------------

class TestWhatIsTicked:
    def test_a_quick_pick_is_ticked_and_the_own_chip_stays_hidden(self, client):
        form = Form(client.get("/settings/people/mia12345").get_data(as_text=True))
        [pick] = form.controls(name="avatar_emoji", value="🦖")
        assert "checked" in pick
        [own] = form.controls(id="e-avatar_emoji-own")
        assert own["value"] == "" and "hidden" in own and "checked" not in own

    def test_one_from_the_full_list_is_its_own_chip_and_ticked(self, client):
        page = client.get("/settings/pets/biscuit1").get_data(as_text=True)
        form = Form(page)
        [own] = form.controls(id="e-avatar_emoji-own")
        assert own["value"] == "🦩" and "checked" in own and "hidden" not in own
        assert '<label for="e-avatar_emoji-own" >🦩</label>' in page
        [none] = form.controls(id="e-avatar_emoji-none")
        assert "checked" not in none

    def test_nothing_saved_means_none_is_ticked(self, client):
        form = Form(client.get("/settings/recurring/table123").get_data(as_text=True))
        [none] = form.controls(id="e-emoji-none")
        assert "checked" in none
        [own] = form.controls(id="e-emoji-own")
        assert own["value"] == "" and "hidden" in own


# -- what the server accepts --------------------------------------------------------

class TestWhatTheServerAccepts:
    CHORE = "/settings/recurring/table123"

    def save(self, client, emoji):
        return client.post(self.CHORE, data={"title": "Set the table", "emoji": emoji, "choices": ["Mia"]})

    def test_any_emoji_saves(self, client, config_path):
        assert self.save(client, "🦩").status_code == 302
        [chore] = saved(config_path, "recurring")
        assert chore["emoji"] == "🦩"

    @pytest.mark.parametrize("emoji", [
        "👨‍👩‍👧‍👦",       # a family: seven code points
        "🏴󠁧󠁢󠁷󠁬󠁳󠁿",       # Wales: a flag spelt out in tags, seven
        "🧑🏻‍❤️‍💋‍🧑🏼",   # the longest there is, ten
        "1️⃣",           # a keycap has a digit in it, and is one emoji
    ])
    def test_a_long_one_is_still_one(self, client, config_path, emoji):
        assert len(emoji) <= LONGEST_EMOJI
        assert self.save(client, emoji).status_code == 302
        assert saved(config_path, "recurring")[0]["emoji"] == emoji

    @pytest.mark.parametrize("value", ["dog", "🐶 dog", "häh", "日本語", "!!!", "🐶🐱",
                                       "🐶🐱🐭🐹🐰🦊🐻🐼🐨🐯🦁"])
    def test_a_word_or_a_row_of_them_is_refused(self, client, config_path, value):
        response = self.save(client, value)
        assert response.status_code == 200
        page = response.get_data(as_text=True)
        assert "Choose one emoji." in page
        assert 'href="#f-emoji"' in page
        assert 'data-dirty-guard="changed"' in page
        assert "emoji" not in saved(config_path, "recurring")[0]

    def test_none_is_still_none(self, client, config_path):
        assert self.save(client, "").status_code == 302
        assert saved(config_path, "recurring")[0]["emoji"] == ""


# -- what one emoji is ---------------------------------------------------------------

class TestOneEmoji:
    """`web/emoji.py` checks the shape of one emoji, not its length. The same grammar
    sits in `emoji-picker.js`, so what the dialog offers is what Save accepts."""

    @pytest.mark.parametrize("value", [
        "🐶", "🍽", "🍽️", "©️", "‼️",
        "👍🏽", "☝🏽",                          # skin tones
        "1️⃣", "#️⃣", "*️⃣", "🔟",             # keycaps
        "🇫🇷", "🏴󠁧󠁢󠁷󠁬󠁳󠁿",                   # a flag, and one spelt out in tags
        "👨‍👩‍👧‍👦", "🧑‍⚕️", "🏃‍♀️", "🐈‍⬛", "🏳️‍🌈", "🏴‍☠️", "🐻‍❄️",   # joined
        "🧑🏻‍❤️‍💋‍🧑🏼",                       # the longest there is
        "🫎",                                 # newer than the list: in the space Unicode set aside
    ])
    def test_one_emoji_is_one(self, value):
        assert one_emoji(value)

    @pytest.mark.parametrize("value", [
        "", "dog", "🐶 dog", "häh", "日本語", "!!!", "1", "#",
        "🐶🐱",                                # two, with nothing joining them
        "🇫", "🇫🇷🇩🇪",                         # half a flag; two flags
        " 🐶", "🐶 ",                          # the form strips these, but this must not rely on it
        "🐶🐱🐭🐹🐰🦊🐻🐼🐨🐯🦁",                 # a row
        "🐶‍🐱‍🐭‍🐹‍🐰‍🦊",                      # joined, but longer than any emoji there is
    ])
    def test_anything_else_is_not(self, value):
        assert not one_emoji(value)

    def test_the_bound_is_the_longest_emoji(self):
        assert LONGEST_EMOJI == len("🧑🏻‍❤️‍💋‍🧑🏼") == 10


# -- the list the dialog reads ------------------------------------------------------

class TestTheList:
    def groups(self):
        return json.loads(LIST.read_text(encoding="utf-8"))["groups"]

    def test_it_is_grouped_and_every_entry_is_one_emoji_with_a_name(self):
        groups = self.groups()
        assert len(groups) >= 8
        assert len({group["name"] for group in groups}) == len(groups)
        seen = set()
        for group in groups:
            assert group["name"] and group["emoji"]
            for entry in group["emoji"]:
                emoji, name, *keywords = entry
                assert len(entry) in (2, 3), entry
                assert emoji and one_emoji(emoji), entry
                assert name and name == name.strip(), entry
                assert all(keyword.strip() for keyword in keywords), entry
                assert plain(emoji) not in seen, f"{emoji} appears twice"
                seen.add(plain(emoji))
        assert len(seen) > 1000

    def test_no_skin_tones(self):
        # A tone is a variant, not an emoji: each one is here once, in its default yellow.
        for group in self.groups():
            for emoji, *_ in group["emoji"]:
                assert not any("\U0001F3FB" <= ch <= "\U0001F3FF" for ch in emoji), emoji

    def test_the_quick_picks_are_all_in_it(self):
        listed = {plain(emoji) for group in self.groups() for emoji, *_ in group["emoji"]}
        for section, picks in EMOJI_SUGGESTIONS.items():
            for pick in picks:
                assert plain(pick) in listed, (section, pick)

    def test_the_number_keycaps_are_in_it(self):
        # A typed keycap passes the grammar; these are on the list so nobody has to type one.
        listed = {plain(emoji) for group in self.groups() for emoji, *_ in group["emoji"]}
        assert {plain(k) for k in ("0️⃣", "1️⃣", "9️⃣", "🔟")} <= listed

    def test_it_is_served_for_a_year(self, client):
        with client.application.test_request_context():
            url = static_url("emoji.json")
        assert re.search(r"\?v=[0-9a-f]{12}$", url)
        response = client.get(url)
        assert response.status_code == 200
        assert response.mimetype == "application/json"
        assert response.headers["Cache-Control"] == CACHED_FOR_A_YEAR
        assert response.get_json()["groups"]

    def test_the_script_is_versioned_too(self, client):
        with client.application.test_request_context():
            url = static_url("emoji-picker.js")
        assert client.get(url).headers["Cache-Control"] == CACHED_FOR_A_YEAR
