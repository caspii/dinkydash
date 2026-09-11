"""Date recovery, rotation integrity and accessible form errors in both modes."""

from copy import deepcopy
from datetime import date
from html.parser import HTMLParser

import pytest
from werkzeug.datastructures import MultiDict

from dinkydash import config as config_module
from dinkydash.context import build_countdowns, compute_chore_assignments
from dinkydash.store import FileStore
from tests.conftest import board_path, client_for
from web import create_app

CONFIG = {
    "family_name": "The Wilsons", "timezone": "Europe/Berlin",
    "people": [
        {"id": "averyaaa", "name": "Avery", "date_of_birth": "1990-03-15"},
        {"id": "rileyaaa", "name": "Riley", "date_of_birth": "1992-06-20"},
        {"id": "jordanaa", "name": "Jordan", "date_of_birth": "1994-07-21"},
    ],
    "recurring": [
        {"id": "tableaaa", "title": "Set the table", "choices": ["Riley", "Avery"]},
        {"id": "plantsaa", "title": "Water the plants", "choices": ["Avery", "Riley"]},
    ],
    "special_dates": [{"id": "holidaya", "title": "Camping", "date": "07/01"}],
    "calendars": [],
}


class Form(HTMLParser):
    """Read the controls a browser would submit, without assuming their order."""

    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def controls(self, **attributes):
        return [attrs for tag, attrs in self.elements
                if tag in ("input", "select", "textarea", "fieldset", "button")
                and all(attrs.get(k) == v for k, v in attributes.items())]

    def checked_people(self):
        return [x['value'] for x in self.controls(name='choices') if 'checked' in x]


@pytest.fixture(params=['file', 'postgres'])
def household(request, tmp_path, monkeypatch):
    if request.param == 'file':
        monkeypatch.setenv('DINKYDASH_MODE', 'single')
        store = FileStore(tmp_path / 'config.yaml')
        app = create_app(store)
        client = client_for(app)
        dashboard = '/'
    else:
        from dinkydash.pgstore import PostgresStore
        pool = request.getfixturevalue('pg_pool')
        family = request.getfixturevalue('pg_family')
        store = PostgresStore(pool, family)
        with pool.connection() as conn, conn.transaction():
            user = conn.execute('INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id',
                                (family, 'ux-test@example.com')).fetchone()[0]
        monkeypatch.setenv('DINKYDASH_MODE', 'cloud')
        monkeypatch.setenv('DINKYDASH_SECRET_KEY', 'isolated-test-key')
        client = client_for(create_app(pool=pool))
        with client.session_transaction() as session:
            session['family_id'] = str(family)
            session['user_id'] = user
        dashboard = board_path(pool, family)
    config = config_module.with_defaults(deepcopy(CONFIG))
    store.save_config(config)
    today = config_module.today_for(config).isoformat()
    store.save_brief(config, {'generated_for_date': today, 'headline': 'A good day', 'note': 'Hello.'})
    return client, store, dashboard


@pytest.mark.parametrize('item_id', ['new', 'holidaya'])
@pytest.mark.parametrize('month,day', [('2', '31'), ('4', '31'), ('13', '1'), ('0', '1'),
                                      ('2', ''), ('', '1'), ('oops', '3'), ('2', '0'),
                                      ('2.5', '3'), ('9' * 100, '1')])
def test_invalid_annual_dates_are_not_saved(household, item_id, month, day):
    client, store, dashboard = household
    before = store.load_config()['special_dates']
    page = client.post(f'/settings/special_dates/{item_id}',
                       data={'title': 'Keep this title', 'date_month': month, 'date_day': day})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'Choose a valid day and month' in html
    assert 'Keep this title' in html
    form = Form(html)
    for part in ('day', 'month'):
        control = form.controls(id=f'f-date-{part}')[0]
        assert control['aria-invalid'] == 'true'
        assert 'error-date' in control['aria-describedby'].split()
    assert store.load_config()['special_dates'] == before
    assert client.get(dashboard).status_code == 200


@pytest.mark.parametrize('month,day,display', [('2', '29', '29 February'), ('2', '28', '28 February'),
                                             ('4', '30', '30 April'), ('12', '31', '31 December')])
def test_valid_dates_save_and_use_named_months(household, month, day, display):
    client, store, dashboard = household
    response = client.post('/settings/special_dates/holidaya',
                           data={'title': 'Camping', 'date_month': month, 'date_day': day})
    assert response.status_code == 302
    assert store.load_config()['special_dates'][0]['date'] == f'{int(month):02}/{int(day):02}'
    assert display in client.get('/settings/special_dates').get_data(as_text=True)
    assert client.get(dashboard).status_code == 200


@pytest.mark.parametrize('value', ['02/31', '04/31', 'nonsense', None, '99/99', '2/3/4'])
def test_bad_stored_date_is_repairable_without_breaking_dashboard(household, value):
    client, store, dashboard = household
    config = store.load_config()
    config['special_dates'][0]['date'] = value
    store.save_config(config)
    assert client.get(dashboard).status_code == 200
    html = client.get('/settings/special_dates').get_data(as_text=True)
    assert 'Check this date' in html
    assert client.get('/settings/special_dates/holidaya').status_code == 200
    assert store.load_config()['special_dates'][0]['date'] == value
    assert client.post('/settings/special_dates/holidaya',
                       data={'title': 'Camping', 'date_month': '7', 'date_day': '1'}).status_code == 302
    assert '1 July' in client.get('/settings/special_dates').get_data(as_text=True)


def test_invalid_countdown_does_not_hide_other_dates_or_coerce_leap_day():
    dates = [{'title': 'Invalid', 'date': '02/31'}, {'title': 'Leap day', 'date': '02/29'},
             {'title': 'Camping', 'date': '03/01'}]
    assert build_countdowns([], dates, date(2027, 2, 28)) == [
        {'emoji': '📅', 'title': 'Leap day', 'days': 0},
        {'emoji': '📅', 'title': 'Camping', 'days': 1},
    ]
    assert build_countdowns([], dates, date(2028, 2, 28))[0]['days'] == 1


def test_unchanged_and_cosmetic_chore_edits_keep_each_rotation(household):
    client, store, _ = household
    config = store.load_config()
    today = config_module.today_for(config)
    before = compute_chore_assignments(config['recurring'], today)
    # Rendering after the People list moves must still follow each chore's own order.
    client.post('/settings/people/averyaaa/move', data={'direction': 'down'})
    for chore in config['recurring']:
        url = '/settings/recurring/' + chore['id']
        html = client.get(url).get_data(as_text=True)
        posted_choices = Form(html).checked_people()
        assert posted_choices == chore['choices']
        data = MultiDict([('title', chore['title']), ('emoji', '🌱')]
                         + [('choices', p) for p in posted_choices])
        assert client.post(url, data=data).status_code == 302
    after = store.load_config()['recurring']
    assert [c['choices'] for c in after] == [c['choices'] for c in config['recurring']]
    assert [c['assigned_to'] for c in compute_chore_assignments(after, today)] == [c['assigned_to'] for c in before]


def test_reordering_a_draft_keeps_other_fields_and_only_save_persists(household):
    client, store, _ = household
    url = '/settings/recurring/tableaaa'
    draft = MultiDict([('title', 'New title'), ('choices', 'Riley'), ('choices', 'Avery'),
                      ('choices', 'Jordan'), ('move_choice', 'up:Jordan')])
    html = client.post(url, data=draft).get_data(as_text=True)
    assert Form(html).checked_people() == ['Riley', 'Jordan', 'Avery']
    assert Form(html).controls(name='title')[0]['value'] == 'New title'
    assert store.load_config()['recurring'][0]['choices'] == ['Riley', 'Avery']
    assert store.load_config()['recurring'][0]['title'] == 'Set the table'
    # Save the explicit new order while removing Riley.
    data = MultiDict([('title', 'New title'), ('choices', 'Jordan'), ('choices', 'Avery')])
    assert client.post(url, data=data).status_code == 302
    assert store.load_config()['recurring'][0]['choices'] == ['Jordan', 'Avery']
    assert store.load_config()['recurring'][1]['choices'] == ['Avery', 'Riley']


def test_no_script_membership_update_is_not_a_save(household):
    client, store, _ = household
    data = MultiDict([('title', 'New chore'), ('choices', 'Jordan'), ('action', 'update_choices')])
    html = client.post('/settings/recurring/new', data=data).get_data(as_text=True)
    assert Form(html).checked_people() == ['Jordan']
    assert len(store.load_config()['recurring']) == 2


def test_enter_defaults_to_save_not_a_rotation_action(household):
    client, _, _ = household
    controls = Form(client.get('/settings/recurring/tableaaa').get_data(as_text=True))
    first = controls.controls(type='submit')[0]
    assert (first['name'], first['value']) == ('action', 'save')
    assert 'disabled' not in first


def test_empty_participants_and_bad_email_link_errors_to_controls(household):
    client, store, _ = household
    html = client.post('/settings/recurring/tableaaa', data={'title': 'Keep this'}).get_data(as_text=True)
    assert 'Choose at least one person.' in html
    for field in Form(html).controls(name='choices'):
        assert field['aria-invalid'] == 'true'
        assert 'error-choices' in field['aria-describedby'].split()
    assert store.load_config()['recurring'][0]['choices'] == ['Riley', 'Avery']
    html = client.post('/settings/calendars/new', data={
        'label': 'Family', 'url': 'https://example.com/calendar.ics', 'shared_with': 'bad-address',
    }).get_data(as_text=True)
    field = Form(html).controls(name='shared_with')[0]
    assert field['value'] == 'bad-address'
    assert field['aria-invalid'] == 'true'
    assert 'error-shared_with' in field['aria-describedby'].split()
    assert 'href="#f-shared_with"' in html
    assert 'id="form-errors" role="alert" tabindex="-1"' in html
    assert not store.load_config()['calendars']


def test_picker_names_and_disabled_list_boundaries(household):
    client, _, _ = household
    html = client.get('/settings/people/new').get_data(as_text=True)
    assert '<legend>Colour</legend>' in html
    for colour in config_module.AVATAR_COLORS:
        assert f'<span class="sr-only">{colour.capitalize()}</span>' in html
    html = client.get('/settings/special_dates/new').get_data(as_text=True)
    assert '<legend>Date</legend>' in html
    assert 'for="f-date-day">Day</label>' in html
    assert 'for="f-date-month">Month</label>' in html
    controls = Form(client.get('/settings/recurring').get_data(as_text=True)).controls(type='submit')
    assert 'disabled' in controls[0] and 'disabled' not in controls[1]
    assert 'disabled' not in controls[2] and 'disabled' in controls[3]
    assert controls[1]['aria-label'] == 'Move Set the table down'
