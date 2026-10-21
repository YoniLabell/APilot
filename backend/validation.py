"""Fail-closed validation for public API responses and generated dashboard numbers."""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

DATA_KEYS = frozenset({'data', 'results', 'result', 'records', 'items', 'features', 'observations', 'entries'})
META_KEYS = frozenset({'success', 'ok', 'status', 'message', 'error', 'errors', 'code', 'detail', 'pagination', 'links', 'meta', 'metadata', 'timestamp', 'api_version', 'version'})
ERROR_STATUS = frozenset({'error', 'failed', 'failure', 'deprecated', 'unauthorized', 'forbidden', 'not_found'})
BAD_MESSAGE = re.compile(r'(deprecated|no longer (available|supported)|invalid api|api key required|unauthori[sz]ed|endpoint not found|not found|rate limit exceeded)', re.I)
MONTH = (r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|'
         r'sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?')
MONTHS = {m: i for i, m in enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'), 1)}
DATE_PATTERNS = (  # Each yields (kind, regex); groups are read by _dates_in.
    ('iso', re.compile(r'(?<![\w.])(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?(?!\w|\.\d)')),
    ('mdy', re.compile(r'\b' + MONTH + r'\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*[-\u2013\u2014]\s*(\d{1,2})(?:st|nd|rd|th)?)?(?:,?\s+(\d{4}))?(?!\w|\.\d)', re.I)),
    ('dmy', re.compile(r'(?<![\w.])(\d{1,2})(?:st|nd|rd|th)?\s+' + MONTH + r'(?:,?\s+(\d{4}))?(?!\w|\.\d)', re.I)),
    ('my', re.compile(r'\b' + MONTH + r',?\s+(\d{4})(?!\w|\.\d)', re.I)),
    ('slash', re.compile(r'(?<![\w.])(\d{1,2})[/.](\d{1,2})[/.](\d{4})(?!\w|\.\d)')),
    ('time', re.compile(r'(?<![\w.])\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]\.?m\.?)?(?!\w|\.\d)', re.I)),
)
TIME_KEY = re.compile(r'(time|date|updated|generated|created|_at$|^dt$|timestamp)', re.I)
# Patterns end with (?!\w|\.\d): a decimal point stops a match, but a sentence-ending period
# does not, so "Total: 99." is still checked.
NUMBER = re.compile(r'(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?(?!\w|\.\d)')


def _empty(value: Any) -> bool:
    return value is None or value == '' or value == [] or value == {}


def _has_error(value: Any) -> bool:
    return value is not None and value is not False and value != 0 and value != '' and value != [] and value != {}


def _has_data(value: Any, depth: int = 0) -> bool:
    if depth > 9: return False
    if isinstance(value, list):
        return any(_has_data(v, depth + 1) for v in value)
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() not in META_KEYS and _has_data(item, depth + 1):
                return True
        return False
    if isinstance(value, bool): return False
    if isinstance(value, (int, float)): return math.isfinite(value)
    return isinstance(value, str) and bool(value.strip())


def _reject_empty_collections(value: Any, depth: int = 0) -> None:
    if depth > 6 or not isinstance(value, dict): return
    for key, item in value.items():
        if str(key).lower() in DATA_KEYS and _empty(item):
            raise ValueError('API returned an empty data collection')
        if isinstance(item, dict): _reject_empty_collections(item, depth + 1)


def validate_api_payload(body: str) -> Any:
    """A syntactically valid JSON error or empty envelope is NOT successful data."""
    try:
        payload = json.loads(body)
    except (ValueError, TypeError) as exc:
        raise ValueError('API returned invalid JSON') from exc
    if not isinstance(payload, (dict, list)):
        raise ValueError('API returned no structured records')
    if isinstance(payload, dict):
        for node in (payload, payload.get('data'), payload.get('response')):
            if not isinstance(node, dict): continue
            if node.get('success') is False or node.get('ok') is False:
                raise ValueError('API reported success:false')
            status = node.get('status')
            if isinstance(status, str) and status.lower().strip() in ERROR_STATUS:
                raise ValueError('API reported an error status')
            if _has_error(node.get('error')) or _has_error(node.get('errors')):
                raise ValueError('API returned an error')
            msg = str(node.get('message') or node.get('detail') or '')
            if BAD_MESSAGE.search(msg):
                raise ValueError('API reported an unavailable or deprecated endpoint')
        _reject_empty_collections(payload)
    if not _has_data(payload):
        raise ValueError('API returned no usable records')
    return payload


def earthquake_scope_count(payload: Any, question: str) -> dict[str, float | int] | None:
    """Count qualifying USGS GeoJSON features rather than trusting feed metadata.count.

    Provider metadata often counts all returned events. If the question requests
    M5+, counting only properties.mag >= 5 is the defensible scoped answer.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get('features'), list):
        return None
    if not re.search(r'earthquakes?|quakes?|seismic', question, re.I):
        return None
    match = re.search(
        r'\bmagnitude\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(?:or\s+(?:more|higher|greater)|and\s+above|\+)|'
        r'\b(?:at\s+least|above)\s+magnitude\s*(\d+(?:\.\d+)?)|'
        r'\bM\s*(\d+(?:\.\d+)?)\s*\+',
        question, re.I)
    if not match:
        return None
    minimum = float(next(value for value in match.groups() if value is not None))
    features = payload['features']
    total = sum(
        1 for feature in features if isinstance(feature, dict)
        and isinstance(feature.get('properties'), dict)
        and _is_number(feature['properties'].get('mag'))
        and float(feature['properties']['mag']) >= minimum
    )
    return {'minimum_magnitude': minimum, 'matched_count': total,
            'returned_features': len(features)}


def scoped_facts_text(payload: Any, question: str) -> str:
    scope = earthquake_scope_count(payload, question)
    if scope is None:
        return ''
    return (f"EARTHQUAKE SCOPE (computed from ALL features): magnitude >= {scope['minimum_magnitude']:g}: "
            f"{scope['matched_count']} matching events from {scope['returned_features']} returned features. "
            "Never use metadata.count as the magnitude-filtered event count unless it agrees with this calculation.")


def _source_numbers(value: Any, bag: list[float], depth: int = 0) -> None:
    if depth > 12 or len(bag) > 15000: return
    if isinstance(value, dict):
        for v in value.values(): _source_numbers(v, bag, depth + 1)
    elif isinstance(value, list):
        if value: bag.append(float(len(value)))
        for v in value[:1000]: _source_numbers(v, bag, depth + 1)
    elif isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
        bag.append(float(value))
    elif isinstance(value, str):
        # Numbers inside text are sourced too, e.g. "place": "81 km SW of Port-Vila".
        bag.extend(n for n, _ in _numeric_tokens(value[:500]))


def _flatten(record: dict, prefix: str = '', depth: int = 0) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in record.items():
        name = f'{prefix}{key}'
        if isinstance(value, dict) and depth < 2: out.update(_flatten(value, name + '.', depth + 1))
        elif isinstance(value, list) and 0 < len(value) <= 4 and all(_is_number(v) for v in value):
            out.update((f'{name}.{i}', v) for i, v in enumerate(value))  # e.g. coordinates [lon, lat, depth]
        elif not isinstance(value, (dict, list)): out[name] = value
    return out


def _collections(value: Any, path: str = '', depth: int = 0) -> list[tuple[str, list]]:
    if depth > 6: return []
    if isinstance(value, list):
        if value and (all(isinstance(v, dict) for v in value[:50]) or all(_is_number(v) for v in value[:50])):
            return [(path or 'records', value)]
        return []
    if isinstance(value, dict):
        return [c for k, v in value.items() for c in _collections(v, f'{path}.{k}' if path else str(k), depth + 1)]
    return []


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _stats(values: list[float]) -> dict[str, float]:
    return {'min': min(values), 'max': max(values), 'mean': round(sum(values) / len(values), 4), 'sum': round(sum(values), 4)}


def payload_facts(payload: Any) -> list[dict]:
    """Exact counts and aggregates over the FULL response, computed by code.

    The models only see a truncated sample, so a count or average they work out themselves is a guess.
    These facts are given to them instead, and verify_ui_numbers accepts them.
    """
    facts: list[dict] = []
    for path, items in _collections(payload)[:10]:
        if all(_is_number(v) for v in items):
            facts.append({'collection': path, 'records': len(items), 'field': '', **_stats([float(v) for v in items])})
            continue
        records = [_flatten(r) for r in items if isinstance(r, dict)]
        facts.append({'collection': path, 'records': len(items)})
        fields = {k for r in records for k in r}
        for field in sorted(fields)[:40]:
            if TIME_KEY.search(field.rsplit('.', 1)[-1]): continue  # Timestamps are checked as dates.
            values = [float(r[field]) for r in records if _is_number(r.get(field))]
            if len(values) >= 2: facts.append({'collection': path, 'records': len(items), 'field': field, **_stats(values)})
    return facts[:60]


def describe_facts(facts: list[dict]) -> str:
    lines = []
    for f in facts:
        where = f"{f['collection']}{'.' + f['field'] if f.get('field') else ''}"
        if 'min' in f: lines.append(f"{where}: min {f['min']:g}, max {f['max']:g}, mean {f['mean']:g}, sum {f['sum']:g} ({f['records']} records)")
        else: lines.append(f"{where}: {f['records']} records")
    return '\n'.join(lines) or 'none'


def _numeric_tokens(value: str) -> list[tuple[float, int]]:
    out = []
    for m in NUMBER.finditer(value):
        raw = m.group(0).replace(',', '')
        try:
            n = float(raw)
            if not math.isfinite(n): continue
            digits = len(raw.split('.', 1)[1].split('e')[0].split('E')[0]) if '.' in raw else 0
            out.append((n, min(digits, 8)))
        except ValueError: pass
    return out


def _known_dates(value: Any, found: set[date], key: str = '', depth: int = 0) -> None:
    """Dates the payload itself contains: ISO date strings and epoch timestamps under time-like keys."""
    if depth > 12 or len(found) > 5000: return
    if isinstance(value, dict):
        for k, v in value.items(): _known_dates(v, found, str(k), depth + 1)
    elif isinstance(value, list):
        for v in value[:1000]: _known_dates(v, found, key, depth + 1)
    elif isinstance(value, str):
        m = re.match(r'\s*(\d{4})-(\d{2})-(\d{2})', value)
        if m:
            try: found.add(date(int(m[1]), int(m[2]), int(m[3])))
            except ValueError: pass
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and TIME_KEY.search(key):
        seconds = value / 1000 if 1e12 <= value < 1e13 else value if 1e9 <= value < 1e10 else None
        if seconds is not None:
            found.add(datetime.fromtimestamp(seconds, timezone.utc).date())


def _month(name: str) -> int:
    return MONTHS[name.lower()[:3]]


def _dates_in(text: str) -> tuple[list[tuple[int | None, int | None, int | None]], str]:
    """Find date and time expressions. Returns their (year, month, day) parts and the text with them blanked out."""
    found: list[tuple[int | None, int | None, int | None]] = []
    for kind, pattern in DATE_PATTERNS:
        def blank(m: re.Match) -> str:
            g = m.groups()
            if kind == 'iso': found.append((int(g[0]), int(g[1]), int(g[2])))
            elif kind == 'mdy':
                year = int(g[3]) if g[3] else None
                found.append((year, _month(g[0]), int(g[1])))
                if g[2]: found.append((year, _month(g[0]), int(g[2])))
            elif kind == 'dmy': found.append((int(g[2]) if g[2] else None, _month(g[1]), int(g[0])))
            elif kind == 'my': found.append((int(g[1]), _month(g[0]), None))
            elif kind == 'slash': found.append((int(g[2]), -int(g[0]), int(g[1])))  # Month/day order is ambiguous.
            return ' ' * len(m.group(0))
        text = pattern.sub(blank, text)
    return found, text


def _date_is_known(parts: tuple[int | None, int | None, int | None], known: set[date]) -> bool:
    year, month, day = parts
    if month is not None and month < 0:  # d/m/y or m/d/y: accept either reading.
        a, b = -month, day
        return any(d.year == year and {(d.month, d.day)} & {(a, b), (b, a)} for d in known)
    return any((year is None or d.year == year) and d.month == month and (day is None or d.day == day) for d in known)


def _around(text: str, number: float) -> str:
    """A short excerpt around a rejected number, so Agent X-Ray shows where it came from."""
    for m in NUMBER.finditer(text):
        try: hit = float(m.group(0).replace(',', '')) == number
        except ValueError: hit = False
        if hit: return ' '.join(text[max(0, m.start() - 40):m.end() + 40].split())
    return ' '.join(text[:80].split())


def verify_ui_numbers(ui: dict, payload: Any, question: str = '', today: date | None = None) -> None:
    """Reject invented numbers; permit sourced numbers, rounding and returned-record counts.

    Does not independently prove nonnumeric claims. The answerability check in the agent
    is an additional gate, and should not be treated as scientific verification.
    """
    observed: list[float] = []
    _source_numbers(payload, observed)
    observed.extend(n for n, _ in _numeric_tokens(question))
    for fact in payload_facts(payload):
        observed.extend(float(fact[k]) for k in ('records', 'min', 'max', 'mean', 'sum') if k in fact)
    # Dates are labels, not measurements: a date is accepted if the payload contains it or it is
    # recent enough to be the question's own period ("today", "yesterday", "past week").
    today = today or datetime.now(timezone.utc).date()
    known: set[date] = {today + timedelta(days=offset) for offset in range(-8, 2)}
    _known_dates(payload, known)
    years = {float(d.year) for d in known}

    def require(value: str) -> None:
        dates, value = _dates_in(value)
        for parts in dates:
            if not _date_is_known(parts, known):
                raise ValueError(f'Dashboard contains an unverified date ({"-".join(str(abs(p)) for p in parts if p is not None)})')
        for number, precision in _numeric_tokens(value):
            if precision == 0 and number in years: continue
            if not any(round(source, precision) == round(number, precision)
                       for source in observed):
                raise ValueError(f'Dashboard contains an unverified number ({number:g}) in "{_around(value, number)}"')

    for field in ('summary', 'subtitle'):
        require(str(ui.get(field) or ''))
    for block in ui.get('blocks', []):
        kind = block.get('type')
        if kind == 'stats':
            for item in block.get('items', []): require(str(item.get('value') or ''))
        elif kind == 'chart':
            keys = {s.get('key') for s in block.get('series', [])}
            for row in block.get('data', []):
                for key in keys:
                    if key in row: require(str(row[key]))
        elif kind == 'table':
            for row in block.get('rows', []):
                for cell in row: require(str(cell))
        elif kind == 'text':
            require(str(block.get('content') or ''))

def audit_dashboard(ui: dict, payload: Any, question: str = '') -> list[str]:
    """Validate each rendered figure independently, returning user-visible warnings.

    Unsupported figures are hidden, not represented as sourced data. Unlike
    verify_ui_numbers(), a single unsupported claim cannot lose the entire run.
    """
    warnings: list[str] = []
    scope = earthquake_scope_count(payload, question)

    def warning(message: str) -> None:
        if message not in warnings and len(warnings) < 15:
            warnings.append(message[:240])

    def count_label(text: str) -> bool:
        return bool(re.search(r'earthquakes?|quakes?|events?|number of|total|count', text, re.I))

    def correct_scope_count(value: str, label: str) -> str:
        if scope is None or not (count_label(label) or count_label(value)):
            return value
        if re.search(r'all magnitudes|unfiltered|regardless of magnitude', label + ' ' + value, re.I):
            return value
        # Statistics and table cells with a count label identify their metric
        # directly, rather than relying on a surrounding paragraph.
        matched = re.fullmatch(r'\s*(\d[\d,]*)\s*(?:events?|earthquakes?|quakes?)?\s*', value, re.I)
        if matched:
            number = int(matched[1].replace(',', ''))
            actual = int(scope['matched_count'])
            if number != actual:
                warning(f"Corrected a magnitude >= {scope['minimum_magnitude']:g} earthquake count "
                        f"from {number} to {actual} using the returned feature records.")
                return value.replace(matched[1], str(actual), 1)
        # For narrative sentences, only numbers directly preceding a count noun
        # are considered totals; magnitude, date and depth figures remain intact.
        def replace(m: re.Match) -> str:
            stated = int(m[1].replace(',', ''))
            actual = int(scope['matched_count'])
            if stated != actual:
                warning(f"Corrected a magnitude >= {scope['minimum_magnitude']:g} earthquake count "
                        f"from {stated} to {actual} using the returned feature records.")
            return str(actual) + m[2]
        return re.sub(r'\b(\d[\d,]*)((?:\s+|\s+M\d+(?:\.\d+)?\+\s+)(?:earthquakes?|quakes?|events?))\b',
                      replace, value, flags=re.I)

    def checked(value: str, label: str, fallback: str = 'Unverified') -> str:
        value = correct_scope_count(str(value), label)
        try:
            verify_ui_numbers({'summary': value, 'blocks': []}, payload, question)
        except ValueError as exc:
            warning(f"{label}: {str(exc)[:140]}; the figure was hidden.")
            return fallback
        return value

    ui['title'] = checked(str(ui.get('title') or ''), 'Title', 'Data Explorer')
    for field in ('subtitle', 'summary', 'caveat'):
        value = str(ui.get(field) or '')
        if value:
            ui[field] = checked(value, field.title(),
                                'Some generated figures could not be verified against the API response.' if field == 'summary' else '')
    original = ui.get('blocks', [])
    cleaned = []
    for block in original:
        kind = block.get('type')
        if kind == 'stats':
            for item in block.get('items', []):
                item['value'] = checked(str(item.get('value') or ''), str(item.get('label') or 'Statistic'))
            cleaned.append(block)
        elif kind == 'table':
            columns = block.get('columns', [])
            for row in block.get('rows', []):
                for index, cell in enumerate(row):
                    label = columns[index] if index < len(columns) else 'Table value'
                    row[index] = checked(str(cell), str(label))
            cleaned.append(block)
        elif kind == 'chart':
            # Arbitrary chart aggregates are not blindly approved. Remove a chart
            # if even one plotted measurement cannot be tied to source data.
            valid = True
            for row in block.get('data', []):
                for series in block.get('series', []):
                    key = series.get('key')
                    if key in row and checked(str(row[key]), str(series.get('label') or 'Chart measurement')) == 'Unverified':
                        valid = False
            if valid:
                cleaned.append(block)
            else:
                warning(f"Chart '{block.get('title') or 'Untitled'}' was hidden because its values could not be verified.")
        elif kind == 'text':
            block['content'] = checked(str(block.get('content') or ''), str(block.get('title') or 'Text'))
            cleaned.append(block)
    ui['blocks'] = cleaned or [{'type': 'text', 'title': 'Source data retrieved',
                                 'content': 'The source returned data, but no generated figures passed automated checks. '
                                            'Open Raw JSON or the source URL to inspect the response.'}]
    return warnings
