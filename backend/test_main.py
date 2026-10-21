import json
import pytest
from fastapi.testclient import TestClient
from main import app,parse_catalog,safe_host,same_provider,readable,clean_ui


def test_catalog_auth_and_https():
    sample='''## Index\n### Weather\n| [Weather](https://example.com/) | Rain | No | Yes | Yes |\n| [Keyed](https://foo.com/) | Rain | `apiKey` | Yes | Yes |\n## MCP Servers\n| [Bad](https://bad.com/) | Anything | No | Yes | Yes |'''
    assert [x['name'] for x in parse_catalog(sample)]==['Weather']

@pytest.mark.parametrize('url',['http://example.com','https://127.0.0.1','https://localhost','https://example.com:8080','https://user:pass@example.com','file:///etc/passwd'])
def test_bad_urls(url):
    with pytest.raises(ValueError): safe_host(url)

def test_provider_boundary():
    assert same_provider('api.open-meteo.com','www.open-meteo.com')
    assert not same_provider('api.evil.com','open-meteo.com')
    assert not same_provider('a.github.io','b.github.io')

def test_strip_scripts():
    assert 'alert' not in readable('<script>alert(1)</script><p>Rain data</p>','text/html')

def test_bounded_ui():
    ui=clean_ui({'blocks':[{'type':'script','code':'alert(1)'},{'type':'stats','items':[{'label':'rain','value':'3 mm'}]}]})
    assert len(ui['blocks'])==1

def test_access_password(monkeypatch):
    monkeypatch.setenv('APP_ACCESS_KEY','test-secret')
    client=TestClient(app)
    assert client.get('/api/health').status_code==200
    assert client.post('/api/ask',json={'question':'Rainfall yesterday'}).status_code==401

def test_chart_numbers_coerced():
    ui=clean_ui({'blocks':[{'type':'chart','xKey':'day','series':[{'key':'mm','label':'Rain','unit':'mm'},{'key':'missing'}],
        'data':[{'day':'Mon','mm':'1,204.5'},{'day':'Tue','mm':3}]}]})
    chart=ui['blocks'][0]
    assert [s['key'] for s in chart['series']]==['mm']
    assert [row['mm'] for row in chart['data']]==[1204.5,3]

def test_chart_without_numbers_dropped():
    assert clean_ui({'blocks':[{'type':'chart','series':[{'key':'v'}],'data':[{'v':'n/a'}]}]})['blocks']==[]

def test_stream_emits_trace_then_result(monkeypatch):
    import main
    monkeypatch.delenv('APP_ACCESS_KEY',raising=False)
    async def fake_explore(question,preferred='',listener=None):
        main.log(main.Trace(listener),'CATALOG','indexed')
        return {'ui':{'title':'ok'}}
    monkeypatch.setattr(main,'explore',fake_explore)
    with TestClient(app).stream('POST','/api/ask/stream',json={'question':'Rainfall yesterday'}) as resp:
        assert resp.headers['content-type'].startswith('text/event-stream')
        body=resp.read().decode()
    assert body.index('event: trace')<body.index('event: result')

def test_stream_reports_errors(monkeypatch):
    import main
    monkeypatch.delenv('APP_ACCESS_KEY',raising=False)
    async def failing(question,preferred='',listener=None): raise ValueError('No matching API')
    monkeypatch.setattr(main,'explore',failing)
    with TestClient(app).stream('POST','/api/ask/stream',json={'question':'Rainfall yesterday'}) as resp:
        body=resp.read().decode()
    assert 'event: error' in body and 'No matching API' in body

@pytest.fixture
def fake_web(monkeypatch):
    """Serve canned responses through public_get with every host resolving to a public IP."""
    import asyncio, httpx, main
    routes={}
    monkeypatch.setattr(main,'_transport',httpx.MockTransport(lambda request: routes[str(request.url)]()))
    monkeypatch.setattr(main,'_responses',{})  # No cached responses between tests.
    monkeypatch.setattr(main.socket,'getaddrinfo',lambda *a,**k:[(None,None,None,None,('93.184.216.34',443))])
    return routes, lambda *args: asyncio.run(main.public_get(*args))

def redirect(to):
    import httpx
    return lambda: httpx.Response(301,headers={'location':to})

def test_follows_redirects(fake_web):
    import httpx
    routes,get=fake_web
    routes['https://example.com/docs']=redirect('/en/docs')
    routes['https://example.com/en/docs']=redirect('https://www.example.com/en/docs')
    routes['https://www.example.com/en/docs']=lambda: httpx.Response(200,text='Rain API docs',headers={'content-type':'text/html'})
    assert get('https://example.com/docs')==('Rain API docs','text/html','https://www.example.com/en/docs')

def test_redirect_to_private_host_blocked(fake_web):
    routes,get=fake_web
    routes['https://example.com/docs']=redirect('https://localhost/admin')
    with pytest.raises(ValueError): get('https://example.com/docs')

def test_redirect_cannot_leave_provider(fake_web):
    routes,get=fake_web
    routes['https://api.example.com/rain']=redirect('https://evil.com/rain')
    with pytest.raises(ValueError,match='outside the selected API provider'): get('https://api.example.com/rain',('https://example.com',))

def test_redirect_loop_stops(fake_web):
    routes,get=fake_web
    routes['https://example.com/a']=redirect('/b')
    routes['https://example.com/b']=redirect('/a')
    with pytest.raises(ValueError,match='Too many redirects'): get('https://example.com/a')

def test_error_reason_is_reported(fake_web):
    import httpx
    routes,get=fake_web
    routes['https://api.example.com/v1/forecast?daily=rain']=lambda: httpx.Response(400,json={'error':True,'reason':'Timezone is required'})
    with pytest.raises(ValueError,match='HTTP 400 Bad Request: .*Timezone is required'): get('https://api.example.com/v1/forecast?daily=rain')

class FakeAgent:
    """Stands in for the OpenAI client: requests each URL in turn and records what it was shown."""
    def __init__(self,urls):
        self.urls=list(urls); self.seen=[]
        self.chat=self; self.completions=self
    async def create(self,messages,**kwargs):
        from types import SimpleNamespace as NS
        self.seen.append([m for m in messages if m.get('role')=='tool'])
        assert kwargs['tool_choice']=='required'
        url=self.urls.pop(0)
        call=NS(id=f'call{len(self.seen)}',function=NS(arguments=json.dumps({'url':url})))
        msg=NS(tool_calls=[call],model_dump=lambda **_: {'role':'assistant','tool_calls':[{'id':call.id,'type':'function','function':{'name':'http_get','arguments':call.function.arguments}}]})
        return NS(choices=[NS(message=msg)])

def test_agent_recovers_from_bad_parameters(fake_web):
    """The Open-Meteo failure: a 400 with a reason must reach the model, which then fixes the request."""
    import asyncio, httpx, main
    routes,_=fake_web
    bad='https://api.open-meteo.com/v1/forecast?latitude=19.4&longitude=-99.1&daily=precipitation_sum&past_days=1'
    good=bad+'&timezone=America%2FMexico_City'
    routes[bad]=lambda: httpx.Response(400,json={'error':True,'reason':'Timezone is required'})
    routes[good]=lambda: httpx.Response(200,json={'daily':{'time':['2026-10-20'],'precipitation_sum':[4.2]}})
    agent=FakeAgent([bad,good])
    url,data,payload=asyncio.run(main.get_api_data(agent,{'name':'Open-Meteo','url':'https://open-meteo.com/'},'docs',
        'How much rain fell in Mexico City yesterday?',main.Trace(),('https://open-meteo.com/',)))
    assert url==good and '4.2' in data and payload['daily']['precipitation_sum']==[4.2]
    assert 'Timezone is required' in agent.seen[1][0]['content']

def test_agent_gives_up_after_bounded_rounds(fake_web):
    import asyncio, httpx, main
    routes,_=fake_web
    urls=[f'https://api.example.com/x?try={i}' for i in range(main.AGENT_ROUNDS)]
    for u in urls: routes[u]=lambda: httpx.Response(404,text='Not found')
    agent=FakeAgent(urls)
    with pytest.raises(ValueError,match='no valid JSON'):
        asyncio.run(main.get_api_data(agent,{'name':'X','url':'https://example.com/'},'docs','q?',main.Trace(),('https://example.com/',)))
    assert len(agent.seen)==main.AGENT_ROUNDS

def test_documented_api_links_stop_at_whitespace():
    from main import documented_api_links
    docs='See https://docs.example.com/guide and https://api.example.com/v1/items?a=1&b=2 for details.'
    assert documented_api_links(docs,'text/plain')==('https://api.example.com',)


def _explore_with(monkeypatch, dashboards):
    """Run explore() for a pinned provider with HTTP and both models stubbed; dashboards are returned in turn."""
    import asyncio, main
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    monkeypatch.delenv('APP_ACCESS_KEY', raising=False)
    entry = {'name': 'USGS', 'url': 'https://earthquake.usgs.gov/fdsnws/event/1/', 'description': '', 'category': 'Science'}
    payload = {'features': [{'properties': {'mag': m}} for m in (5.0, 6.4, 5.2)]}
    async def catalog(): return [entry]
    async def public_get(url, providers=()): return 'USGS event API documentation with query parameters', 'text/html', url
    async def get_api_data(*args): return 'https://earthquake.usgs.gov/q', json.dumps(payload), payload
    prompts = []
    async def json_model(ai, model, system, prompt, budget=1400):
        prompts.append(prompt)
        if system.startswith('Strict analyst'): return {'answerable': True, 'summary': 'Quakes', 'caveat': ''}
        return dashboards.pop(0)
    for name, fn in [('catalog', catalog), ('public_get', public_get), ('get_api_data', get_api_data), ('json_model', json_model)]:
        monkeypatch.setattr(main, name, fn)
    return asyncio.run(main.explore('Magnitude 5+ earthquakes in the past week?', 'USGS')), prompts

def test_dashboard_with_unsourced_number_is_redesigned_once(monkeypatch):
    invented = {'title': 'Quakes', 'summary': '192 earthquakes this week.', 'blocks': [{'type': 'text', 'content': 'x'}]}
    fixed = {'title': 'Quakes', 'summary': '3 earthquakes; strongest 6.4.', 'blocks': [{'type': 'text', 'content': 'x'}]}
    result, prompts = _explore_with(monkeypatch, [invented, fixed])
    assert result['verified'] and result['ui']['summary'].startswith('3 earthquakes')
    assert 'COMPUTED FACTS' in prompts[0] and 'features: 3 records' in prompts[0]
    assert 'REJECTED: Dashboard contains an unverified number (192)' in prompts[-1]
    assert any(e['stage'] == 'RETRY' and '192' in e['detail'] for e in result['trace'])

def test_dashboard_still_failing_after_redesign_is_rejected(monkeypatch):
    invented = {'title': 'Quakes', 'summary': '192 earthquakes this week.', 'blocks': [{'type': 'text', 'content': 'x'}]}
    with pytest.raises(ValueError, match='unverified number'):
        _explore_with(monkeypatch, [dict(invented), dict(invented)])

def test_agent_is_told_to_use_a_forecast_for_a_forecast_question(fake_web):
    """QA P0-1: the agent must not answer a forecast question from the archive."""
    import asyncio, httpx, main
    routes,_=fake_web
    archive='https://archive-api.open-meteo.com/v1/archive?latitude=31.77&longitude=35.21&start_date=2020-10-15&end_date=2020-10-21&daily=temperature_2m_max&timezone=auto'
    forecast='https://api.open-meteo.com/v1/forecast?latitude=31.77&longitude=35.21&daily=temperature_2m_max&timezone=auto'
    routes[forecast]=lambda: httpx.Response(200,json={'daily':{'time':['2099-01-01'],'temperature_2m_max':[24.1]}})
    agent=FakeAgent([archive,forecast])
    url,data,payload=asyncio.run(main.get_api_data(agent,{'name':'Open-Meteo','url':'https://open-meteo.com/'},'docs',
        'What is the weather forecast for Jerusalem this week?',main.Trace(),('https://open-meteo.com/',)))
    assert url==forecast
    assert 'archive endpoint' in agent.seen[1][0]['content']  # the archive request was never sent


@pytest.mark.parametrize('question,expected', [
    # QA P1-3: these picked irrelevant catalog providers by name.
    ('What is the current Bitcoin price?', 'CoinGecko'),
    ('Compare the populations of Japan, India and Brazil', 'REST Countries'),
    ('What are the top stories on Hacker News right now?', 'Hacker News (Algolia)'),
    ('Show me Pikachu stats', 'PokéAPI'),
    ('What was the GDP of Israel over the last 20 years?', 'World Bank'),
    ('When are the next SpaceX launches?', 'Launch Library 2'),
    ('מה מזג האוויר בירושלים היום?', 'Open-Meteo'),
    ('What is the weather forecast for Jerusalem this week?', 'Open-Meteo'),
    ('Which earthquakes of magnitude 5 or more happened worldwide in the past week?', 'USGS Earthquake Hazards Program'),
    ('What is the EUR/USD exchange rate over the last 30 days?', 'Frankfurter'),
])
def test_curated_provider_is_tried_first(question, expected):
    from registry import golden_for
    assert golden_for(question, [])[0]['name'] == expected

def test_model_topic_selects_a_curated_provider_without_keywords():
    from registry import golden_for
    assert [g['name'] for g in golden_for('Wie ist das Wetter in Berlin?', [], 'weather')] == ['Open-Meteo']
    assert golden_for('Random cat facts please', [], 'other') == []

def test_semantic_rank_uses_descriptions_not_names():
    import asyncio, main
    from types import SimpleNamespace as NS
    vocab = ['crypto', 'price', 'halving', 'countdown', 'holiday', 'weather']
    def vec(text):
        v = [float(w in text.lower()) for w in vocab]; n = sum(x*x for x in v) ** .5 or 1
        return [x/n for x in v]
    class Embeddings:
        async def create(self, model, input, dimensions): return NS(data=[NS(embedding=vec(t)) for t in input])
    entries = [{'name': 'Bitcoin Halving', 'url': 'https://a', 'description': 'Countdown to the next halving', 'category': 'Cryptocurrency'},
               {'name': 'Holidays', 'url': 'https://b', 'description': 'UK bank holiday dates', 'category': 'Calendar'},
               {'name': 'CoinCap', 'url': 'https://c', 'description': 'Real-time crypto price data', 'category': 'Cryptocurrency'}]
    main._embeddings.clear()
    ranked = asyncio.run(main.semantic_rank(NS(embeddings=Embeddings()), entries, 'bitcoin crypto price'))
    assert [e['name'] for e in ranked][0] == 'CoinCap'

def test_dead_catalog_providers_are_skipped_but_curated_never_are(monkeypatch):
    import main
    from registry import GOLDEN
    catalog_entry = {'name': 'CityAlert', 'url': 'https://cityalert.example/docs'}
    main.mark_dead(catalog_entry, 'SSL error'); main.mark_dead(GOLDEN[0], 'transient')
    assert main.is_dead(catalog_entry) and not main.is_dead(GOLDEN[0])
    monkeypatch.setattr(main.time, 'monotonic', lambda: 10**12)  # 24 hours later
    assert not main.is_dead(catalog_entry)

def test_sample_keeps_fields_after_huge_lists():
    """PokéAPI lists hundreds of moves before stats; the model must still see the stats."""
    from main import readable
    pikachu = {'moves': [{'move': {'name': 'thunder-shock', 'url': 'https://pokeapi.co/api/v2/move/84/'}, 'version_group_details': [{'level_learned_at': 1}] * 5}] * 120,
               'name': 'pikachu', 'stats': [{'base_stat': 90, 'stat': {'name': 'speed'}}]}
    text = readable(json.dumps(pikachu), 'application/json')
    assert '"stats"' in text and '"base_stat": 90' in text and len(text) <= 16000

def test_curated_provider_runs_first_without_scraping_docs(monkeypatch):
    import asyncio, main
    monkeypatch.setenv('OPENAI_API_KEY', 'test')
    attempts = []
    async def catalog(): return [{'name': 'Bitcoin Halving', 'url': 'https://halving.example/', 'description': 'Countdown', 'category': 'Cryptocurrency'}]
    async def public_get(url, providers=()): raise AssertionError('curated docs must not be scraped')
    async def semantic_rank(ai, entries, query, limit=22): return entries
    async def get_api_data(ai, entry, docs, question, trace, providers):
        attempts.append((entry['name'], providers))
        payload = {'bitcoin': {'usd': 67000.5}}
        return 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd', json.dumps(payload), payload
    async def json_model(ai, model, system, prompt, budget=1400):
        if system.startswith('Translate'): return {'search_terms': ['bitcoin', 'price'], 'category': 'Cryptocurrency', 'topic': 'crypto'}
        if system.startswith('Strict analyst'): return {'answerable': True, 'summary': 'BTC'}
        return {'title': 'Bitcoin', 'summary': 'Bitcoin is $67000.5.', 'blocks': [{'type': 'text', 'content': 'x'}]}
    for name, fn in [('catalog', catalog), ('public_get', public_get), ('semantic_rank', semantic_rank), ('get_api_data', get_api_data), ('json_model', json_model)]:
        monkeypatch.setattr(main, name, fn)
    result = asyncio.run(main.explore('What is the current Bitcoin price?'))
    assert result['verified'] and result['provider']['name'] == 'CoinGecko'
    assert attempts[0][0] == 'CoinGecko' and 'https://api.coingecko.com' in attempts[0][1]


def _stub_explore(monkeypatch):
    import main
    monkeypatch.setenv('OPENAI_API_KEY', 'test'); monkeypatch.delenv('APP_ACCESS_KEY', raising=False)
    async def explore(question, preferred='', listener=None): return {'verified': True}
    monkeypatch.setattr(main, 'explore', explore)
    monkeypatch.setattr(main, '_hits', {}); monkeypatch.setattr(main, '_today', {'date': '', 'count': 0})
    return main

def test_rate_limit_per_client_and_per_day(monkeypatch):
    """QA P2-5: anyone could spend the OpenAI credits."""
    main = _stub_explore(monkeypatch)
    monkeypatch.setattr(main, 'RATE_LIMIT_PER_HOUR', 2); monkeypatch.setattr(main, 'DAILY_REQUEST_CAP', 3)
    client = TestClient(app)
    ask = lambda ip: client.post('/api/ask', json={'question': 'Rain yesterday?'}, headers={'X-Forwarded-For': f'1.1.1.1, {ip}'})
    assert [ask('9.9.9.9').status_code for _ in range(3)] == [200, 200, 429]
    assert ask('8.8.8.8').status_code == 200          # another client, 3rd request today
    r = ask('7.7.7.7')                                # daily cap reached
    assert r.status_code == 429 and 'daily' in r.json()['detail']

@pytest.mark.parametrize('error,expected', [
    ('No verified JSON obtained from available APIs. X: ValueError: Retrieved JSON does not answer the requested location, metric or period', 'do not have data'),
    ('No verified JSON obtained from available APIs. X: ValueError: Dashboard contains an unverified number (81)', 'figures match'),
    ('No verified JSON obtained from available APIs. X: ConnectError: [Errno -2] Name or service not known', 'did not respond'),
    ('No matching no-auth HTTPS API found', 'could not find a public API'),
    ('Something unexpected', 'Try rephrasing'),
])
def test_errors_are_friendly(error, expected):
    """QA P2-6: raw "ValueError ... | ConnectError ..." was shown to users."""
    from main import friendly
    message = friendly(ValueError(error))
    assert expected in message and 'Error' not in message

def test_stream_error_has_friendly_detail_and_technical_text(monkeypatch):
    import main
    monkeypatch.delenv('APP_ACCESS_KEY', raising=False); monkeypatch.setattr(main, '_hits', {})
    async def failing(question, preferred='', listener=None): raise ValueError('No verified JSON obtained from available APIs. X: ConnectError: boom')
    monkeypatch.setattr(main, 'explore', failing)
    with TestClient(app).stream('POST', '/api/ask/stream', json={'question': 'Rainfall yesterday'}) as resp:
        body = resp.read().decode()
    event = json.loads(body.split('event: error\ndata: ')[1].split('\n')[0])
    assert 'did not respond' in event['detail'] and 'ConnectError: boom' in event['technical']

def _hedged(monkeypatch, behaviours):
    """Run explore() over providers whose attempts behave as given: ('ok'|'fail', delay seconds)."""
    import asyncio, main
    monkeypatch.setenv('OPENAI_API_KEY', 'test'); monkeypatch.setattr(main, 'HEDGE_AFTER', 0.05); monkeypatch.setattr(main, '_dead', {})
    entries = [{'name': f'P{i}', 'url': f'https://p{i}.example/', 'description': '', 'category': 'X'} for i in range(len(behaviours))]
    started, cancelled = [], []
    async def catalog(): return entries
    async def public_get(url, providers=()): return 'Documentation for this provider: GET /data returns JSON values.', 'text/html', url
    async def get_api_data(ai, entry, docs, question, trace, providers):
        i = int(entry['name'][1:]); outcome, delay = behaviours[i]; started.append(entry['name'])
        try: await asyncio.sleep(delay)
        except asyncio.CancelledError: cancelled.append(entry['name']); raise
        if outcome == 'fail': raise ValueError('HTTP 500')
        payload = {'v': [1, 2]}; return f'https://p{i}.example/data', json.dumps(payload), payload
    async def json_model(ai, model, system, prompt, budget=1400):
        if system.startswith('Strict analyst'): return {'answerable': True}
        return {'title': 'T', 'summary': '2 values.', 'blocks': [{'type': 'text', 'content': 'x'}]}
    for name, fn in [('catalog', catalog), ('public_get', public_get), ('get_api_data', get_api_data), ('json_model', json_model)]:
        monkeypatch.setattr(main, name, fn)
    return main, entries, started, cancelled

def test_slow_provider_is_hedged_and_first_verified_result_wins(monkeypatch):
    """QA P2-7: a slow provider no longer blocks the next one."""
    import asyncio
    main, entries, started, cancelled = _hedged(monkeypatch, [('ok', 5), ('ok', 0.01)])
    async def semantic_rank(ai, entries, query, limit=22): return entries
    async def json_model(ai, model, system, prompt, budget=1400):
        if system.startswith('Translate'): return {'search_terms': ['x'], 'topic': 'other'}
        if system.startswith('Choose'): return {'indexes': [0, 1]}
        if system.startswith('Strict analyst'): return {'answerable': True}
        return {'title': 'T', 'summary': '2 values.', 'blocks': [{'type': 'text', 'content': 'x'}]}
    monkeypatch.setattr(main, 'semantic_rank', semantic_rank); monkeypatch.setattr(main, 'json_model', json_model)
    result = asyncio.run(main.explore('A question about nothing curated'))
    assert result['provider']['name'] == 'P1' and started == ['P0', 'P1'] and cancelled == ['P0']
    assert {e.get('provider') for e in result['trace'] if e['stage'] == 'DONE'} == {'P1'}

def test_failed_provider_starts_the_next_immediately(monkeypatch):
    import asyncio
    main, entries, started, cancelled = _hedged(monkeypatch, [('fail', 0), ('ok', 0)])
    async def semantic_rank(ai, entries, query, limit=22): return entries
    async def json_model(ai, model, system, prompt, budget=1400):
        if system.startswith('Translate'): return {'search_terms': ['x'], 'topic': 'other'}
        if system.startswith('Choose'): return {'indexes': [0, 1]}
        if system.startswith('Strict analyst'): return {'answerable': True}
        return {'title': 'T', 'summary': '2 values.', 'blocks': [{'type': 'text', 'content': 'x'}]}
    monkeypatch.setattr(main, 'semantic_rank', semantic_rank); monkeypatch.setattr(main, 'json_model', json_model)
    result = asyncio.run(main.explore('A question about nothing curated'))
    assert result['provider']['name'] == 'P1' and any(e['stage'] == 'FALLBACK' for e in result['trace'])

def test_identical_requests_are_served_from_cache(fake_web):
    import httpx
    routes, get = fake_web
    calls = []
    routes['https://api.example.com/rates'] = lambda: calls.append(1) or httpx.Response(200, json={'eur': 0.92})
    assert get('https://api.example.com/rates')[0] == get('https://api.example.com/rates')[0]
    assert len(calls) == 1
    with pytest.raises(ValueError, match='outside the selected API provider'):  # the cache still enforces the boundary
        get('https://api.example.com/rates', ('https://other.org',))

def test_static_files_are_served_but_never_outside_the_folder(tmp_path):
    """QA P2-8: /favicon.ico and /robots.txt returned index.html."""
    from main import static_file
    (tmp_path / 'robots.txt').write_text('User-agent: *')
    (tmp_path.parent / 'secret.txt').write_text('x')
    assert static_file(tmp_path, 'robots.txt') == (tmp_path / 'robots.txt').resolve()
    assert static_file(tmp_path, '../secret.txt') is None
    assert static_file(tmp_path, 'missing.png') is None and static_file(tmp_path, '') is None
