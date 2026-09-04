"""The orchestrator and the model call, with a stand-in for the API.

Nothing here touches the network. The fake client records what it was asked so
the prompt's contents can be asserted on.
"""

import json
from datetime import date

import pytest

from dinkydash.claude_client import GenerationError, call_claude
from dinkydash.generate import generate
from dinkydash.prompt import (RESPONSE_SCHEMA, NOTE_KINDS, build_user_prompt,
                              choose_note_kind, note_instruction)

CONFIG = {
    "family_name": "The Wilsons",
    "timezone": "Europe/Berlin",
    "location": "Berlin, Germany",
    "claude_model": "claude-haiku-4-5",
    "max_tokens": 1024,
    "people": [
        {"name": "Mia", "date_of_birth": "2017-03-15", "interests": "dinosaurs"},
        {"name": "Theo", "date_of_birth": "2019-06-20"},
    ],
    "pets": [{"name": "Biscuit", "type": "dog"}],
    "recurring": [{"title": "Set the table", "emoji": "🍽", "choices": ["Mia", "Theo"]}],
    "special_dates": [{"title": "Christmas", "emoji": "🎄", "date": "12/25"}],
}

TODAY = date(2026, 9, 3)

EVENTS = [
    {"title": "School run", "date": "2026-09-03", "time": "08:20", "all_day": False,
     "start": "2026-09-03T08:20:00+02:00", "location": None, "calendar": "Family"},
    {"title": "Swimming", "date": "2026-09-03", "time": "15:45", "all_day": False,
     "start": "2026-09-03T15:45:00+02:00", "location": None, "calendar": "Family"},
    {"title": "Dentist", "date": "2026-09-05", "time": "11:00", "all_day": False,
     "start": "2026-09-05T11:00:00+02:00", "location": None, "calendar": "Family"},
    {"title": "Far off", "date": "2026-09-30", "time": "09:00", "all_day": False,
     "start": "2026-09-30T09:00:00+02:00", "location": None, "calendar": "Family"},
]


class Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class Usage:
    input_tokens = 1200
    output_tokens = 90


class FakeMessages:
    def __init__(self, reply, raises=None):
        self.reply = reply
        self.raises = raises
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        response = type("Response", (), {})()
        response.content = [Block(self.reply)]
        response.usage = Usage()
        return response


class FakeClient:
    def __init__(self, reply='{"headline": "Big morning", "note": "An octopus fact."}',
                 raises=None):
        self.messages = FakeMessages(reply, raises)


@pytest.fixture
def client():
    return FakeClient()


class TestCallClaude:
    def test_returns_the_parsed_content(self, client):
        result = call_claude("prompt", CONFIG, client=client)
        assert result["headline"] == "Big morning"
        assert result["note"] == "An octopus fact."
        assert result["model"] == "claude-haiku-4-5"
        assert result["input_tokens"] == 1200

    def test_asks_for_a_schema_constrained_response(self, client):
        call_claude("prompt", CONFIG, client=client)
        sent = client.messages.calls[0]
        assert sent["output_config"] == {
            "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}
        }

    def test_sends_no_thinking_parameter(self, client):
        # Haiku 4.5 takes no thinking config; sending one would be an error, and
        # adaptive thinking would compete with max_tokens on other models.
        call_claude("prompt", CONFIG, client=client)
        assert "thinking" not in client.messages.calls[0]

    def test_uses_the_configured_model_and_budget(self, client):
        call_claude("prompt", dict(CONFIG, claude_model="claude-sonnet-5", max_tokens=2048),
                    client=client)
        sent = client.messages.calls[0]
        assert sent["model"] == "claude-sonnet-5"
        assert sent["max_tokens"] == 2048

    def test_an_api_failure_becomes_a_generation_error(self):
        with pytest.raises(GenerationError, match="API call failed"):
            call_claude("prompt", CONFIG, client=FakeClient(raises=RuntimeError("503")))

    def test_an_empty_response_is_an_error_not_a_blank_board(self):
        with pytest.raises(GenerationError, match="empty"):
            call_claude("prompt", CONFIG, client=FakeClient(reply="   "))

    def test_unparseable_json_is_an_error(self):
        with pytest.raises(GenerationError, match="invalid JSON"):
            call_claude("prompt", CONFIG, client=FakeClient(reply="{not json"))


class TestPrompt:
    def build(self, **kwargs):
        defaults = dict(
            config=CONFIG, today=TODAY, events_today=EVENTS[:2], events_soon=EVENTS[2:3],
            chores=[{"title": "Set the table", "assigned_to": "Mia", "emoji": "🍽"}],
            countdowns=[{"title": "Christmas", "days": 113, "emoji": "🎄"}],
            recent_notes=["An old fact about cats."], note_kind="fact",
        )
        defaults.update(kwargs)
        return build_user_prompt(**defaults)

    def test_includes_todays_events_with_times(self):
        prompt = self.build()
        assert "08:20: School run" in prompt
        assert "15:45: Swimming" in prompt

    def test_includes_ages_and_interests(self):
        prompt = self.build()
        assert "Mia, 9" in prompt  # born March 2017, so 9 by September 2026
        assert "dinosaurs" in prompt

    def test_lists_recent_notes_to_avoid(self):
        prompt = self.build()
        assert "An old fact about cats." in prompt
        assert "must not resemble" in prompt

    def test_says_so_plainly_when_the_day_is_empty(self):
        prompt = self.build(events_today=[])
        assert "Nothing at all on today's calendar." in prompt

    def test_all_day_events_read_as_all_day(self):
        prompt = self.build(events_today=[
            {"title": "Inset day", "all_day": True, "time": None, "location": None}
        ])
        assert "All day: Inset day" in prompt


class TestNoteKind:
    def test_pets_are_only_offered_when_there_is_a_pet(self):
        petless = dict(CONFIG, pets=[])
        kinds = {choose_note_kind(petless) for _ in range(40)}
        assert "pet" not in kinds
        assert kinds <= set(NOTE_KINDS)

    def test_a_pet_household_can_get_a_pet_note(self):
        kinds = {choose_note_kind(CONFIG) for _ in range(60)}
        assert "pet" in kinds

    def test_each_kind_produces_its_own_instruction(self):
        assert "challenge" in note_instruction("challenge", CONFIG).lower()
        assert "Biscuit" in note_instruction("pet", CONFIG)
        assert "fact" in note_instruction("fact", CONFIG).lower()


class TestGenerate:
    def test_builds_a_complete_payload(self, client):
        payload = generate(CONFIG, TODAY, EVENTS, client=client)
        assert payload["generated_for_date"] == "2026-09-03"
        assert payload["headline"] == "Big morning"
        assert payload["note"] == "An octopus fact."
        assert payload["note_kind"] in NOTE_KINDS
        assert payload["family_name"] == "The Wilsons"
        assert payload["model"] == "claude-haiku-4-5"

    def test_keeps_the_whole_fetched_window_not_just_today(self):
        # This is what lets a stale board still show a correct agenda tomorrow.
        payload = generate(CONFIG, TODAY, EVENTS, client=FakeClient())
        assert len(payload["events"]) == len(EVENTS)

    def test_omits_chores_and_countdowns_from_the_payload(self, client):
        # They are pure functions of config + date, so the board recomputes them
        # at render time rather than trusting a possibly-stale copy.
        payload = generate(CONFIG, TODAY, EVENTS, client=client)
        assert "chores" not in payload
        assert "countdowns" not in payload

    def test_the_prompt_sees_todays_events_and_the_near_future(self, client):
        generate(CONFIG, TODAY, EVENTS, client=client, note_kind="fact")
        prompt = client.messages.calls[0]["messages"][0]["content"]
        assert "School run" in prompt
        assert "Dentist" in prompt        # two days out, inside the horizon
        assert "Far off" not in prompt    # 27 days out, beyond it

    def test_the_payload_is_json_serialisable(self, client):
        payload = generate(CONFIG, TODAY, EVENTS, client=client)
        assert json.loads(json.dumps(payload))["headline"] == "Big morning"

    def test_a_requested_note_kind_is_honoured(self, client):
        payload = generate(CONFIG, TODAY, EVENTS, client=client, note_kind="pet")
        assert payload["note_kind"] == "pet"
        assert "Biscuit" in client.messages.calls[0]["messages"][0]["content"]

    def test_a_day_with_no_events_still_generates(self, client):
        payload = generate(CONFIG, TODAY, [], client=client)
        assert payload["events"] == []
        assert payload["headline"] == "Big morning"

    def test_a_failed_call_propagates_rather_than_writing_a_blank_board(self):
        with pytest.raises(GenerationError):
            generate(CONFIG, TODAY, EVENTS, client=FakeClient(raises=RuntimeError("boom")))
