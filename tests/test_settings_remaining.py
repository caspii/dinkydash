"""Destructive confirmations and the remaining setup/copy corrections."""
from datetime import date

import pytest

from tests.test_settings_improvements import household  # both stores and modes
from web import setup


def test_removal_needs_confirmation_and_names_dependent_chores(household):
    client, store, _ = household
    config = store.load_config()
    config['recurring'][0]['choices'] = ['Avery']
    store.save_config(config)
    url = '/settings/people/averyaaa/delete'
    for data in ({}, {'confirmed': 'no'}):
        page = client.post(url, data=data)
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'Remove Avery?' in html and 'Keep Avery' in html
        assert 'removed from chore rotations' in html
        assert 'These chores will have nobody assigned: Set the table.' in html
        assert len(store.load_config()['people']) == 3
    assert client.post(url, data={'confirmed': 'yes'}).status_code == 302
    config = store.load_config()
    assert len(config['people']) == 2
    assert config['recurring'][0]['choices'] == []


def test_removal_prompt_escapes_the_item_name(household):
    client, store, _ = household
    config = store.load_config()
    config['recurring'][0]['title'] = '<script>example</script>'
    store.save_config(config)
    for url in ['/settings/recurring/tableaaa', '/settings/recurring/tableaaa/delete']:
        response = client.post(url) if url.endswith('/delete') else client.get(url)
        html = response.get_data(as_text=True)
        assert '<script>example</script>' not in html
        assert '&lt;script&gt;example&lt;/script&gt;' in html


def test_calendar_check_keeps_changed_drafts_protected_without_saving(household, monkeypatch):
    client, store, _ = household
    config = store.load_config()
    calendar = {'id': 'familyxx', 'label': 'Family', 'url': 'https://example.com/calendar.ics',
                'enabled': True}
    config['calendars'] = [calendar]
    store.save_config(config)
    monkeypatch.setattr('web.routes.settings.check_feed', lambda *_: {'ok': True, 'message': 'Connected.'})
    data = {'label': 'Family', 'url': calendar['url'], 'enabled': 'on', 'action': 'check'}
    html = client.post('/settings/calendars/familyxx', data=data).get_data(as_text=True)
    assert 'data-dirty-guard=""' in html
    data['label'] = 'School'
    html = client.post('/settings/calendars/familyxx', data=data).get_data(as_text=True)
    assert 'data-dirty-guard="changed"' in html
    assert 'Remove Family?' in html and 'Remove School?' not in html
    assert store.load_config()['calendars'][0]['label'] == 'Family'


def test_invalid_save_keeps_draft_protected_and_removal_names_the_saved_item(household):
    client, store, _ = household
    response = client.post('/settings/people/averyaaa', data={
        'name': 'Draft name', 'date_of_birth': '0017-03-15', 'interests': 'Unsaved interests',
    })
    html = response.get_data(as_text=True)
    assert 'data-dirty-guard="changed"' in html
    assert 'Remove Avery?' in html and 'Remove Draft name?' not in html
    assert store.load_config()['people'][0]['name'] == 'Avery'


def test_screen_replacement_requires_confirmation_before_revocation(household):
    client, _, dashboard = household
    if dashboard == '/':
        assert client.post('/settings/screen', data={'action': 'rotate'}).status_code == 404
        return
    response = client.post('/settings/screen', data={'action': 'rotate'})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Keep current link' in html and 'Replace screen link' in html
    assert 'Every connected screen will stop' in html
    assert client.get(dashboard).status_code == 200
    response = client.post('/settings/screen', data={'action': 'rotate', 'confirmed': 'yes'})
    assert response.status_code == 302
    assert client.get(dashboard).status_code == 404
    assert 'New screen link.' in client.get('/settings/screen').get_data(as_text=True)


def test_only_successful_account_deletion_shows_success(household):
    client, _, dashboard = household
    if dashboard == '/':
        pytest.skip('Account deletion is hosted only')
    response = client.post('/settings/account', data={'confirm': 'wrong@example.com'}, follow_redirects=True)
    assert 'Your account and dashboard data have been deleted.' not in response.get_data(as_text=True)
    assert client.get(dashboard).status_code == 200
    response = client.post('/settings/account', data={'confirm': 'ux-test@example.com'}, follow_redirects=True)
    html = response.get_data(as_text=True)
    assert 'Your account and dashboard data have been deleted.' in html
    assert 'All screen links have stopped working.' in html
    assert client.get(dashboard).status_code == 404
    assert client.get('/settings/').status_code == 302
    # It is a one-time result of a real deletion, not a claim triggered by a URL flag.
    assert 'Your account and dashboard data have been deleted.' not in client.get('/login?deleted=1').get_data(as_text=True)


@pytest.mark.parametrize('invented_people,invented_pets,destination,other', [
    (True, False, 'people', False), (False, True, 'pets', False),
    (True, True, 'people', True), (False, False, 'people', False),
])
def test_setup_points_at_the_examples_that_need_attention(household, invented_people, invented_pets, destination, other):
    client, store, _ = household
    config = store.load_config()
    config['people'][0]['invented'] = invented_people
    config['pets'] = [{'id': 'biscuitx', 'name': 'Biscuit', 'invented': invented_pets}]
    with client.application.test_request_context():
        step = setup.household(config)
    assert step['href'] == '/settings/' + destination
    assert bool(step['other_href']) == other
    store.save_config(config)
    if invented_people or invented_pets:
        html = client.get('/settings/').get_data(as_text=True)
        if other:
            assert 'Review example pets too' in html
        assert 'Who lives here' in html


@pytest.mark.parametrize('age', [0, 1, 2])
def test_age_grammar(household, monkeypatch, age):
    client, store, _ = household
    monkeypatch.setattr('web.routes.settings.config_module.today_for', lambda _: date(2026, 9, 11))
    config = store.load_config()
    config['people'][0]['date_of_birth'] = f'{2026-age}-09-11'
    store.save_config(config)
    html = client.get('/settings/people').get_data(as_text=True)
    assert f'{age} {"year" if age == 1 else "years"} old' in html
    assert '1 years old' not in html


def test_current_user_labels_distinguish_chores_calendars_and_daily_message(household):
    client, _, _ = household
    html = client.get('/settings/recurring/new').get_data(as_text=True)
    assert 'New chore' in html and '>Chore</label>' in html
    home = client.get('/settings/').get_data(as_text=True)
    assert 'Rewrite daily message' in home
    assert 'daily message at' in home
    assert 'Rewrite now' not in home and 'brief at' not in home
    refresh = client.get('/settings/refresh').get_data(as_text=True)
    assert 'Write the daily message at' in refresh
    assert 'Fetch the calendars' in refresh
