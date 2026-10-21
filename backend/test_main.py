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
