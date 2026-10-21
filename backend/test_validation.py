import json
import pytest
from validation import validate_api_payload, verify_ui_numbers


@pytest.mark.parametrize('payload', [
    {'success': False, 'message': 'This API version has been deprecated', 'data': [{'population': 123}]},
    {'status': 'error', 'message': 'Service unavailable'},
    {'error': {'code': 410, 'message': 'Endpoint removed'}},
    {'errors': ['Invalid API key']},
    {'message': 'This API version has been deprecated'},
    {'data': []}, {'data': {}}, {'data': {'results': [], 'total': 0}},
    [], {}, {'success': True, 'data': []},
    {'success': True, 'message': 'OK'},
])
def test_reject_invalid_or_empty_provider_data(payload):
    with pytest.raises(ValueError):
        validate_api_payload(json.dumps(payload))


@pytest.mark.parametrize('payload', [
    [{'mag': 5.2, 'place': 'Japan'}],
    {'success': True, 'data': [{'year': 2004, 'value': 0}]},
    {'precipitation_sum': [0, 1.2, 0]},
    {'population': 0, 'country': 'Japan'},
    {'rate': 0.923457},
])
def test_accept_valid_observations(payload):
    assert validate_api_payload(json.dumps(payload)) == payload


def test_reject_fabricated_stat_and_chart():
    payload = {'data': [{'year': 2020, 'value': 12.0}, {'year': 2021, 'value': 16.0}]}
    with pytest.raises(ValueError, match='unverified number'):
        verify_ui_numbers({'summary': 'Average GDP 99 trillion', 'blocks': []}, payload)
    with pytest.raises(ValueError, match='unverified number'):
        verify_ui_numbers({'blocks': [{'type': 'chart', 'series': [{'key': 'value'}],
                                        'data': [{'year': 2021, 'value': 5000}]}]}, payload)


def test_allows_actual_data_rounded_values_and_record_counts():
    payload = {'data': [{'rate': 0.92451}, {'rate': 0.93421}]}
    verify_ui_numbers({'summary': '2 observations', 'blocks': [
        {'type': 'stats', 'items': [{'label': 'Exchange rate', 'value': '0.925'}]},
        {'type': 'chart', 'series': [{'key': 'rate'}], 'data': [{'rate': 0.92451}]},
    ]}, payload)


def test_non_numeric_labels_are_allowed():
    verify_ui_numbers({'summary': 'Historical observations from the provider', 'blocks': [
        {'type': 'table', 'rows': [['Japan', '0']]}]}, {'population': 0, 'country': 'Japan'})


TODAY = __import__('datetime').date(2026, 10, 21)


def _ms(y, m, d):
    from datetime import datetime, timezone
    return int(datetime(y, m, d, 12, tzinfo=timezone.utc).timestamp() * 1000)


USGS = {'metadata': {'generated': _ms(2026, 10, 21), 'count': 2}, 'features': [
    {'properties': {'mag': 6.1, 'place': 'Tonga', 'time': _ms(2026, 10, 16)}},
    {'properties': {'mag': 5.4, 'place': 'Chile', 'time': _ms(2026, 10, 19)}}]}
RATES = {'amount': 1.0, 'base': 'USD', 'date': '2026-10-20', 'rates': {'EUR': 0.9212, 'JPY': 151.37}}


@pytest.mark.parametrize('ui,payload', [
    # Regression: titles with the current date were rejected as "unverified number (21)".
    ({'subtitle': 'Rates as of October 21, 2026 (published 2026-10-20)', 'summary': '1 USD = 0.92 EUR at 16:00 CET'}, RATES),
    ({'subtitle': 'Magnitude 5+ earthquakes, Oct 14–21, 2026', 'summary': 'Strongest: 6.1 near Tonga on October 16'}, USGS),
    ({'summary': 'Latest 2026 rates: 0.92 EUR'}, RATES),
    ({'blocks': [{'type': 'table', 'rows': [['16/10/2026', '6.1'], ['2026-10-19', '5.4']]}]}, USGS),
])
def test_dates_from_payload_or_question_period_are_allowed(ui, payload):
    verify_ui_numbers({'blocks': [], **ui}, payload, today=TODAY)


@pytest.mark.parametrize('ui,payload,match', [
    ({'summary': 'Strongest quake on March 3, 2019 was 6.1'}, USGS, 'unverified date'),
    ({'summary': 'Strongest quake on Oct 16 was 7.9'}, USGS, 'unverified number'),
    ({'summary': 'Rates in 1999: 0.92'}, RATES, 'unverified number'),
])
def test_invented_dates_and_numbers_still_rejected(ui, payload, match):
    with pytest.raises(ValueError, match=match):
        verify_ui_numbers({'blocks': [], **ui}, payload, today=TODAY)


def test_number_before_full_stop_is_checked():
    # Regression: "(?![\w.])" skipped any number followed by a period, so this invented total passed.
    with pytest.raises(ValueError, match=r'unverified number \(99\)'):
        verify_ui_numbers({'summary': 'Total: 99.', 'blocks': []}, RATES, today=TODAY)


@pytest.mark.parametrize('text', [
    'The rate is 0.92.', 'Rates as of October 21, 2026.', 'Published 2026-10-20.', 'Updated at 16:00.', 'Ends... 151.37...',
])
def test_real_values_and_dates_at_sentence_end_pass(text):
    verify_ui_numbers({'summary': text, 'blocks': []}, RATES, today=TODAY)


def _quakes(mags):
    return {'metadata': {'generated': _ms(2026, 10, 21), 'count': len(mags)}, 'features': [
        {'properties': {'mag': m, 'place': f'Place {i}', 'time': _ms(2026, 10, 14 + i)}, 'geometry': {'coordinates': [10.1, -5.2, 35.0]}}
        for i, m in enumerate(mags)]}


def test_payload_facts_count_and_aggregate_the_full_response():
    from validation import payload_facts
    facts = payload_facts(_quakes([5.0, 6.4, 5.2]))
    assert {'collection': 'features', 'records': 3} in facts
    mag = next(f for f in facts if f.get('field') == 'properties.mag')
    assert (mag['min'], mag['max'], mag['mean'], mag['sum']) == (5.0, 6.4, 5.5333, 16.6)
    assert not any(f.get('field', '').endswith('time') for f in facts)  # timestamps are dates, not measurements
    rain = payload_facts({'daily': {'precipitation_sum': [0.0, 1.2, 3.0]}})
    assert rain == [{'collection': 'daily.precipitation_sum', 'records': 3, 'field': '', 'min': 0.0, 'max': 3.0, 'mean': 1.4, 'sum': 4.2}]


def test_derived_counts_and_averages_pass_but_invented_counts_do_not():
    quakes = _quakes([5.0, 6.4, 5.2])
    verify_ui_numbers({'summary': '3 earthquakes; average magnitude 5.53, strongest 6.4. Total rain 4.2 mm.', 'blocks': []},
                      {**quakes, 'daily': {'rain': [0.0, 1.2, 3.0]}}, today=TODAY)
    with pytest.raises(ValueError, match=r'unverified number \(192\)'):
        verify_ui_numbers({'summary': '192 earthquakes of magnitude 5+ this week.', 'blocks': []}, quakes, today=TODAY)
