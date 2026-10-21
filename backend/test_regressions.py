import asyncio
import json

import httpx
import pytest

from validation import audit_dashboard, earthquake_scope_count, scoped_facts_text, validate_api_payload, verify_ui_numbers


@pytest.fixture
def quake_payload():
    return {
        'type': 'FeatureCollection',
        'metadata': {'count': 192, 'generated': 1792573200000},
        'features': [
            {'type': 'Feature', 'properties': {'mag': 4.8, 'place': 'A', 'time': 1792123200000}},
            {'type': 'Feature', 'properties': {'mag': 5.3, 'place': 'B', 'time': 1792209600000}},
            {'type': 'Feature', 'properties': {'mag': 6.1, 'place': 'C', 'time': 1792296000000}},
        ],
    }


def test_full_json_metadata_is_visible_but_magnitude_filter_takes_priority(quake_payload):
    question = 'Which earthquakes of magnitude 5 or more happened worldwide in the past week?'
    payload = validate_api_payload(json.dumps(quake_payload))
    assert earthquake_scope_count(payload, question) == {
        'minimum_magnitude': 5.0, 'matched_count': 2, 'returned_features': 3,
    }
    assert '2 matching events' in scoped_facts_text(payload, question)
    # Metadata.count is present in the raw source; that alone does NOT mean 192 M5+ events.
    verify_ui_numbers({'summary': '192', 'blocks': []}, payload, question)
    ui = {
        'title': 'Earthquake dashboard',
        'summary': '192 earthquakes of magnitude 5 or more happened this week.',
        'blocks': [
            {'type': 'stats', 'title': 'Overview',
             'items': [{'label': 'M5+ earthquake count', 'value': '192'},
                       {'label': 'Strongest earthquake', 'value': '6.1'}]},
        ],
    }
    warnings = audit_dashboard(ui, payload, question)
    assert ui['summary'].startswith('2 earthquakes')
    assert ui['blocks'][0]['items'][0]['value'] == '2'
    assert ui['blocks'][0]['items'][1]['value'] == '6.1'
    assert warnings and any('192 to 2' in w for w in warnings)


def test_unsourced_figure_hidden_without_killing_other_blocks(quake_payload):
    ui = {
        'title': 'USGS',
        'summary': '6.1 was the largest observed magnitude.',
        'blocks': [
            {'type': 'stats', 'items': [{'label': 'Maximum magnitude', 'value': '6.1'},
                                        {'label': 'Claimed depth', 'value': '98765'}]},
            {'type': 'chart', 'series': [{'key': 'mag', 'label': 'Magnitude'}],
             'data': [{'mag': 6.1}, {'mag': 99999}]},
        ],
    }
    warnings = audit_dashboard(ui, quake_payload, 'Strongest earthquakes in the past week')
    assert warnings
    assert ui['blocks'][0]['items'][0]['value'] == '6.1'
    assert ui['blocks'][0]['items'][1]['value'] == 'Unverified'
    assert not any(b['type'] == 'chart' for b in ui['blocks'])


def test_computed_mean_still_allowed(quake_payload):
    ui = {'summary': 'The mean magnitude of returned earthquakes is 5.4.',
          'blocks': [{'type': 'text', 'content': 'Mean: 5.4.'}]}
    assert audit_dashboard(ui, quake_payload, 'Earthquakes in the past week') == []


def test_forbidden_provider_host_is_explained_and_agent_switches(fake_web_unused=None):
    # Self-contained mock: first tool call is forbidden; the next is an allowed endpoint.
    import main
    from test_main import FakeAgent

    bad = 'https://forbidden-provider.net/v1/earthquakes'
    good = 'https://api.example.com/v1/earthquakes'
    routes = {good: lambda: httpx.Response(200, json={'features': [{'properties': {'mag': 5.4}}]})}
    old_transport = main._transport
    old_getaddrinfo = main.socket.getaddrinfo
    try:
        main._transport = httpx.MockTransport(lambda request: routes[str(request.url)]())
        main.socket.getaddrinfo = lambda *a, **kw: [(None, None, None, None, ('93.184.216.34', 443))]
        agent = FakeAgent([bad, good])
        result = asyncio.run(main.get_api_data(agent, {'name': 'A', 'url': 'https://example.com'},
                                               'docs', 'earthquakes', main.Trace(),
                                               ('https://example.com',)))
        assert result[0] == good
        assert 'allowed_provider_hosts' in agent.seen[1][0]['content']
        assert 'forbidden-provider.net' in agent.seen[1][0]['content']
    finally:
        main._transport = old_transport
        main.socket.getaddrinfo = old_getaddrinfo


def test_repeated_forbidden_host_stops_early(monkeypatch):
    import main
    from test_main import FakeAgent
    agent = FakeAgent(['https://bad.example.net/a?x=1', 'https://bad.example.net/a?x=2'])
    calls = []
    async def fake_get(*args):
        calls.append(args)
        raise ValueError('Endpoint is outside the selected API provider')
    monkeypatch.setattr(main, 'public_get', fake_get)
    with pytest.raises(ValueError, match='already forbidden'):
        asyncio.run(main.get_api_data(agent, {'name': 'A','url': 'https://example.com'},
                                      'docs','earthquake count',main.Trace(),('https://example.com',)))
    assert len(calls) == 1
