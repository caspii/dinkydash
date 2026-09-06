"""The settings routes, which are the only thing that writes config.yaml.

The claim being tested: an item's URL means the same person tomorrow as it did
when the page was rendered. It used to be a list position, so deleting anyone
above shifted everybody below onto somebody else's edit form.
"""

import pytest

from dinkydash import config as config_module
from web import create_app

CONFIG = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"

people:
  - name: "Mia"
    date_of_birth: "2017-03-15"
  - name: "Theo"
    date_of_birth: "2019-06-20"
  - name: "Ines"
    date_of_birth: "2022-01-09"

recurring:
  - title: "Set the table"
    choices: ["Mia", "Theo"]
  - title: "Feed the dog"
    choices: ["Theo", "Mia"]
"""


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG)
    monkeypatch.setenv("DINKYDASH_CONFIG", str(path))
    return path


@pytest.fixture
def client(config_path):
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def people(config_path):
    return config_module.load_config(config_path)["people"]


def ids_for(config_path, key="people"):
    return [item["id"] for item in config_module.load_config(config_path)[key]]


class TestBackfill:
    def test_opening_a_list_gives_the_file_ids(self, client, config_path):
        assert "id" not in people(config_path)[0]
        assert client.get("/settings/people").status_code == 200
        assert all(p["id"] for p in people(config_path))

    def test_the_ids_do_not_change_on_a_second_visit(self, client, config_path):
        client.get("/settings/people")
        first = ids_for(config_path)
        client.get("/settings/people")
        assert ids_for(config_path) == first

    def test_the_list_links_to_ids_not_positions(self, client, config_path):
        html = client.get("/settings/people").get_data(as_text=True)
        for person_id in ids_for(config_path):
            assert f"/settings/people/{person_id}" in html


class TestEditing:
    def test_an_edit_form_opens_by_id(self, client, config_path):
        client.get("/settings/people")
        theo = ids_for(config_path)[1]
        page = client.get(f"/settings/people/{theo}").get_data(as_text=True)
        assert "Theo" in page

    def test_saving_keeps_the_id(self, client, config_path):
        client.get("/settings/people")
        theo = ids_for(config_path)[1]
        client.post(f"/settings/people/{theo}",
                    data={"name": "Theodore", "date_of_birth": "2019-06-20"})
        after = people(config_path)
        assert after[1]["name"] == "Theodore"
        assert after[1]["id"] == theo

    def test_a_new_person_gets_an_id_of_their_own(self, client, config_path):
        client.get("/settings/people")
        before = set(ids_for(config_path))
        client.post("/settings/people/new",
                    data={"name": "Otto", "date_of_birth": "2024-04-02"})
        after = ids_for(config_path)
        assert len(after) == 4
        assert after[3] not in before

    def test_an_unknown_id_is_a_404(self, client, config_path):
        client.get("/settings/people")
        assert client.get("/settings/people/nosuchid").status_code == 404


class TestDeleting:
    def test_delete_removes_the_named_person(self, client, config_path):
        client.get("/settings/people")
        theo = ids_for(config_path)[1]
        client.post(f"/settings/people/{theo}/delete")
        assert [p["name"] for p in people(config_path)] == ["Mia", "Ines"]

    def test_a_deletion_does_not_move_anyone_elses_url(self, client, config_path):
        # The bug this whole change exists to prevent: with positions, removing
        # Mia turned Theo's open edit form into Ines's.
        client.get("/settings/people")
        mia, _theo, ines = ids_for(config_path)
        client.post(f"/settings/people/{mia}/delete")
        page = client.get(f"/settings/people/{ines}").get_data(as_text=True)
        assert "Ines" in page

    def test_deleting_a_stranger_is_a_404(self, client, config_path):
        client.get("/settings/people")
        assert client.post("/settings/people/nosuchid/delete").status_code == 404


class TestReordering:
    """Chore rotation follows list order, so moving a job has to be exact."""

    def test_moving_down_swaps_with_the_next_one(self, client, config_path):
        client.get("/settings/recurring")
        first = ids_for(config_path, "recurring")[0]
        client.post(f"/settings/recurring/{first}/move", data={"direction": "down"})
        titles = [c["title"] for c in config_module.load_config(config_path)["recurring"]]
        assert titles == ["Feed the dog", "Set the table"]

    def test_moving_the_top_one_up_does_nothing(self, client, config_path):
        client.get("/settings/recurring")
        first = ids_for(config_path, "recurring")[0]
        client.post(f"/settings/recurring/{first}/move", data={"direction": "up"})
        titles = [c["title"] for c in config_module.load_config(config_path)["recurring"]]
        assert titles == ["Set the table", "Feed the dog"]

    def test_moving_a_stranger_is_a_404(self, client, config_path):
        client.get("/settings/recurring")
        assert client.post("/settings/recurring/nosuchid/move",
                           data={"direction": "up"}).status_code == 404
