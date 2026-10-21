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
