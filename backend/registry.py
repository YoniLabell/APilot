"""Curated "golden" providers, tried before the public-apis catalog.

Each entry has hand-written documentation with exact URL templates, so the agent does not have to
scrape and interpret a docs page, and the hosts its data calls may reach. All are keyless.
The data step ends at the first valid JSON, so every template answers a question in ONE call
(no geocoding or ID-then-detail chains).
"""
from __future__ import annotations

import re

GOLDEN: list[dict] = [
    {
        'name': 'Open-Meteo', 'topic': 'weather', 'category': 'Weather',
        'url': 'https://open-meteo.com/en/docs',
        'description': 'Weather forecasts, current conditions, recent days and historical weather for any coordinates',
        'hosts': ('https://api.open-meteo.com', 'https://archive-api.open-meteo.com'),
        'match': r'weather|forecast|temperature|\brain|precipitation|snow|wind|humidity|sunny|מזג האוויר|תחזית|גשם|טמפרטורה',
        'docs': '''Open-Meteo weather API (no key).
Use the place's latitude and longitude directly (you know them for cities); do NOT call a geocoding API.
"timezone=auto" is REQUIRED whenever daily= is used.
- Forecast, today and up to 16 days ahead:
  https://api.open-meteo.com/v1/forecast?latitude=31.77&longitude=35.21&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code&timezone=auto&forecast_days=7
- Current conditions: add &current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code
- Yesterday or the last few days: the SAME forecast endpoint with &past_days=N&forecast_days=1 (N up to 92).
  Use this for "yesterday": the archive lags several days behind.
- Older history (more than 5 days ago):
  https://archive-api.open-meteo.com/v1/archive?latitude=..&longitude=..&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&daily=temperature_2m_max,precipitation_sum&timezone=auto
  Never use the archive for a forecast.
Daily variables: temperature_2m_max, temperature_2m_min, precipitation_sum, rain_sum, snowfall_sum, wind_speed_10m_max, weather_code.
Hourly variables: temperature_2m, precipitation, relative_humidity_2m, wind_speed_10m.''',
    },
    {
        'name': 'CoinGecko', 'topic': 'crypto', 'category': 'Cryptocurrency',
        'url': 'https://docs.coingecko.com/v3.0.1/reference/introduction',
        'description': 'Cryptocurrency prices, market caps and price history',
        'hosts': ('https://api.coingecko.com',),
        'match': r'bitcoin|ethereum|crypto|\bcoins?\b|\bbtc\b|\beth\b|solana|dogecoin|ביטקוין|קריפטו',
        'docs': '''CoinGecko public API v3 (no key, rate limited). Coin ids: bitcoin, ethereum, solana, dogecoin, ripple, cardano, tether.
- Current price: https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd,eur&include_24hr_change=true&include_market_cap=true
- Price history: https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=30&interval=daily
  (prices is a list of [unix_ms, price])
- Top coins by market cap: https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=10&page=1''',
    },
    {
        'name': 'REST Countries', 'topic': 'countries', 'category': 'Geography',
        'url': 'https://restcountries.com/',
        'description': 'Country facts: population, area, capital, region, languages, currencies',
        'hosts': ('https://restcountries.com',),
        'match': r'population|\barea\b|capital|countr|languages? spoken|borders|אוכלוסיה|שטח|מדינ',
        'docs': '''REST Countries v3.1 (no key). ALWAYS add &fields= (at most 10 fields) to keep responses small. Never use v2: it is deprecated.
- Several countries by ISO code: https://restcountries.com/v3.1/alpha?codes=jp,in,br&fields=name,population,area,capital,region
- One country by name: https://restcountries.com/v3.1/name/japan?fields=name,population,area
- A region: https://restcountries.com/v3.1/region/europe?fields=name,population,area (africa, americas, asia, europe, oceania)
- A subregion: https://restcountries.com/v3.1/subregion/South%20America?fields=name,population,area
Population figures are the latest the service has, not live counts.''',
    },
    {
        'name': 'World Bank', 'topic': 'economy', 'category': 'Economics',
        'url': 'https://datahelpdesk.worldbank.org/knowledgebase/articles/889392',
        'description': 'Economic and development indicators by country and year: GDP, inflation, unemployment, population',
        'hosts': ('https://api.worldbank.org',),
        'match': r'\bgdp\b|inflation|unemployment|economy|economic|world bank|life expectancy|\bco2\b|emissions|poverty|תמ"ג|אינפלציה|אבטלה',
        'docs': '''World Bank Indicators API v2 (no key). ALWAYS add format=json. The response is [metadata, records];
each record has date (the year, as a string), value (may be null) and country.value. Use ISO3 country codes.
- https://api.worldbank.org/v2/country/ISR/indicator/NY.GDP.MKTP.CD?format=json&date=2004:2023&per_page=100
- Several countries: https://api.worldbank.org/v2/country/JPN;IND;BRA/indicator/SP.POP.TOTL?format=json&date=2023&per_page=100
Indicators: NY.GDP.MKTP.CD (GDP, current US$), NY.GDP.PCAP.CD (GDP per capita), NY.GDP.MKTP.KD.ZG (GDP growth %),
SP.POP.TOTL (population), FP.CPI.TOTL.ZG (inflation %), SL.UEM.TOTL.ZS (unemployment %), SP.DYN.LE00.IN (life expectancy),
EN.ATM.CO2E.PC (CO2 tonnes per capita). The latest complete year is usually one or two years ago.''',
    },
    {
        'name': 'Hacker News (Algolia)', 'topic': 'hacker_news', 'category': 'News',
        'url': 'https://hn.algolia.com/api',
        'description': 'Hacker News stories: front page, top stories, search, points and comments',
        'hosts': ('https://hn.algolia.com',),
        'match': r'hacker ?news|\bhn\b|ycombinator',
        'docs': '''Hacker News search API by Algolia (no key). Each hit has title, url, points, num_comments, author, created_at.
- Current front page (top stories): https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=30
- Search stories: https://hn.algolia.com/api/v1/search?query=rust&tags=story&hitsPerPage=20
- Newest stories: https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=20''',
    },
    {
        'name': 'Launch Library 2', 'topic': 'space_launches', 'category': 'Science',
        'url': 'https://ll.thespacedevs.com/docs/',
        'description': 'Rocket launches: SpaceX and all providers, recent and upcoming',
        'hosts': ('https://ll.thespacedevs.com',),
        'match': r'spacex|launch(es)?\b|rocket|falcon|starship|שיגור',
        'docs': '''Launch Library 2 by The Space Devs (no key, about 15 requests per hour). ALWAYS add mode=list for small responses.
- Recent SpaceX launches: https://ll.thespacedevs.com/2.2.0/launch/previous/?lsp__name=SpaceX&limit=10&mode=list
- Upcoming SpaceX launches: https://ll.thespacedevs.com/2.2.0/launch/upcoming/?lsp__name=SpaceX&limit=10&mode=list
- Any provider: omit lsp__name. Each result has name, net (launch time, UTC), status.name, pad and mission fields.''',
    },
    {
        'name': 'PokéAPI', 'topic': 'pokemon', 'category': 'Games',
        'url': 'https://pokeapi.co/docs/v2',
        'description': 'Pokémon data: base stats, types, abilities, height and weight',
        'hosts': ('https://pokeapi.co',),
        'match': r'pok[eé]mon|pikachu|charizard|bulbasaur|squirtle|mewtwo|eevee|pok[eé]dex',
        'docs': '''PokéAPI v2 (no key). Names are lowercase.
- A Pokémon: https://pokeapi.co/api/v2/pokemon/pikachu
  stats[] has base_stat and stat.name (hp, attack, defense, special-attack, special-defense, speed); types[].type.name; height (decimetres); weight (hectograms).
- A type: https://pokeapi.co/api/v2/type/electric''',
    },
    {
        'name': 'Open Library', 'topic': 'books', 'category': 'Books',
        'url': 'https://openlibrary.org/developers/api',
        'description': 'Books, authors, editions and first publication years',
        'hosts': ('https://openlibrary.org',),
        'match': r'\bbooks?\b|novels?|author|tolkien|asimov|publish|ספר',
        'docs': '''Open Library (no key). ALWAYS pass fields= and limit= to keep responses small.
- Books by an author: https://openlibrary.org/search.json?author=isaac+asimov&fields=title,first_publish_year,edition_count&limit=10&sort=editions
- Search by title: https://openlibrary.org/search.json?q=the+hobbit&fields=title,author_name,first_publish_year&limit=10''',
    },
    {
        'name': 'USGS Earthquake Hazards Program', 'topic': 'earthquakes', 'category': 'Science',
        'url': 'https://earthquake.usgs.gov/fdsnws/event/1/',
        'description': 'Earthquakes worldwide: magnitude, place, depth and time',
        'hosts': ('https://earthquake.usgs.gov',),
        'match': r'earthquake|seismic|quake|tremor|רעיד',
        'docs': '''USGS earthquake catalog (no key). GeoJSON; properties.time is epoch milliseconds, geometry.coordinates is [lon, lat, depth_km].
- https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=YYYY-MM-DD&endtime=YYYY-MM-DD&minmagnitude=5&orderby=magnitude&limit=100
- Summary feeds: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson (also significant_week, 2.5_day, all_hour)''',
    },
    {
        'name': 'Frankfurter', 'topic': 'currency', 'category': 'Currency Exchange',
        'url': 'https://frankfurter.dev/',
        'description': 'Foreign exchange rates from the European Central Bank, latest and historical',
        'hosts': ('https://api.frankfurter.app', 'https://api.frankfurter.dev'),
        'match': r'exchange rate|currenc|\busd\b|\beur\b|\bgbp\b|\bjpy\b|\bils\b|dollar|euro\b|shekel|שער|דולר|מטבע',
        'docs': '''Frankfurter: European Central Bank reference rates (no key). Published on working days around 16:00 CET.
- Latest: https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY
- On a date: https://api.frankfurter.app/2026-01-15?from=EUR&to=USD
- Time series: https://api.frankfurter.app/2026-09-21..2026-10-21?from=EUR&to=USD
- Supported currencies: https://api.frankfurter.app/currencies''',
    },
    {
        'name': 'GitHub REST API', 'topic': 'github', 'category': 'Development',
        'url': 'https://docs.github.com/en/rest/search/search',
        'description': 'GitHub repositories: stars, forks, languages and search',
        'hosts': ('https://api.github.com',),
        'match': r'github|repositor|\brepos?\b',
        'docs': '''GitHub REST API (no key, 10 search requests per minute).
- Most-starred repositories in a language: https://api.github.com/search/repositories?q=language:python&sort=stars&order=desc&per_page=5
- Search by topic: https://api.github.com/search/repositories?q=topic:machine-learning&sort=stars&order=desc&per_page=10
- One repository: https://api.github.com/repos/python/cpython
items[] have full_name, stargazers_count, forks_count, language, description.''',
    },
]

TOPICS = {g['topic']: g for g in GOLDEN}
_MATCHERS = [(g, re.compile(g['match'], re.I)) for g in GOLDEN]


def golden_for(question: str, keywords: list[str], topic: str = '') -> list[dict]:
    """Golden providers relevant to a question: the model's chosen topic first, then regex matches."""
    text = f'{question} {" ".join(keywords)}'
    found = [TOPICS[topic]] if topic in TOPICS else []
    found += [g for g, pattern in _MATCHERS if pattern.search(text) and g not in found]
    return found


def golden_by_name(name: str) -> dict | None:
    return next((g for g in GOLDEN if g['name'].lower() == name.lower()), None)
