"""Acceptance test against a deployed APilot: the 15 QA questions, each must return verified data in time.

    python scripts/qa_acceptance.py https://apilot-7h3z.onrender.com --key YOUR_APP_ACCESS_KEY

Uses only the standard library. Each question costs several OpenAI calls. The server allows
RATE_LIMIT_PER_HOUR questions per client (default 20), so a second full run within an hour
needs a higher limit on the server.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from validation import FUTURE, period_problem  # noqa: E402  (same rule the agent enforces)

# (question, expected provider). The provider is a hint for "correct data": a mismatch is a warning.
QUESTIONS = [
    ('Which earthquakes of magnitude 5 or more happened worldwide in the past week?', 'USGS Earthquake Hazards Program'),
    ('How did the EUR/USD exchange rate change over the last 30 days?', 'Frankfurter'),
    ('What is the weather in Berlin today?', 'Open-Meteo'),
    ('מה מזג האוויר בירושלים היום?', 'Open-Meteo'),
    ('Which books did J.R.R. Tolkien write?', 'Open Library'),
    ('What is the weather forecast for Jerusalem this week?', 'Open-Meteo'),
    ("Show me Pikachu's base stats", 'PokéAPI'),
    ("What was Israel's GDP over the last 20 years?", 'World Bank'),
    ('What is the current Bitcoin price?', 'CoinGecko'),
    ('How much rain fell in Mexico City yesterday?', 'Open-Meteo'),
    ('Compare the populations of Japan, India and Brazil', 'REST Countries'),
    ('What are the population and area of the countries in South America?', 'REST Countries'),
    ("What were SpaceX's most recent launches?", 'Launch Library 2'),
    ('What are the top stories on Hacker News right now?', 'Hacker News (Algolia)'),
    ('What are the 5 most-starred Python repositories on GitHub?', 'GitHub REST API'),
]


def ask(base: str, key: str, question: str, timeout: float) -> tuple[int, dict, float]:
    request = urllib.request.Request(f'{base.rstrip("/")}/api/ask', method='POST',
                                     data=json.dumps({'question': question}).encode(),
                                     headers={'Content-Type': 'application/json', 'X-APilot-Key': key})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.load(response), time.monotonic() - started
    except urllib.error.HTTPError as error:
        body = error.read().decode('utf-8', 'replace')
        try: return error.code, json.loads(body), time.monotonic() - started
        except ValueError: return error.code, {'detail': body[:200]}, time.monotonic() - started
    except Exception as error:  # Timeout or connection failure.
        return 0, {'detail': f'{type(error).__name__}: {error}'}, time.monotonic() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('base_url')
    parser.add_argument('--key', default='', help='APP_ACCESS_KEY, if the site is protected')
    parser.add_argument('--max-seconds', type=float, default=20, help='latency target per question')
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()

    failures = 0
    for i, (question, expected) in enumerate(QUESTIONS, 1):
        status, body, seconds = ask(args.base_url, args.key, question, args.timeout)
        provider = (body.get('provider') or {}).get('name', '')
        problems = []
        if status != 200: problems.append(f'HTTP {status}: {body.get("detail", "")}')
        elif body.get('verified') is not True: problems.append('not verified')
        if status == 200 and FUTURE.search(question):
            issue = period_problem(question, body.get('source_url', ''))
            if issue: problems.append(f'wrong period: {issue}')
        if seconds > args.max_seconds: problems.append(f'slow: {seconds:.1f} s > {args.max_seconds:g} s')
        warning = f'  (expected {expected})' if status == 200 and provider != expected else ''
        failures += bool(problems)
        print(f'{"FAIL" if problems else "PASS"} {i:2}. {question}\n'
              f'      {seconds:5.1f} s  provider: {provider or "-"}{warning}  source: {body.get("source_url", "-")}')
        for problem in problems: print(f'      - {problem}')
    print(f'\n{len(QUESTIONS) - failures}/{len(QUESTIONS)} passed')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
