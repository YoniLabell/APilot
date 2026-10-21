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
