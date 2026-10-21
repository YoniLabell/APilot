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

def test_unsourced_figure_flags_but_does_not_abort_dashboard(monkeypatch):
    invented = {'title': 'Quakes', 'summary': '192 earthquakes this week.',
                'blocks': [{'type': 'stats', 'items': [{'label': 'Total earthquakes', 'value': '192'}]}]}
    result, _ = _explore_with(monkeypatch, [invented])
    assert result['verified'] is True
    assert result['validation_warnings']
    assert '192' not in result['ui']['summary']
    assert result['ui']['blocks'][0]['items'][0]['value'] == 'Unverified'
    assert any(e['stage'] == 'VALIDATION' for e in result['trace'])


def test_unsourced_dashboard_stays_visible_with_caveat(monkeypatch):
    invented = {'title': 'Quakes', 'summary': '192 earthquakes this week.',
                'blocks': [{'type': 'text', 'title': 'Overview', 'content': 'No numeric data here.'}]}
    result, _ = _explore_with(monkeypatch, [invented])
    assert result['verified'] is True
    assert result['validation_warnings']
    assert result['ui']['blocks'][0]['content'] == 'No numeric data here.'

