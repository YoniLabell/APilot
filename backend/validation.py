"""Fail-closed validation for public API responses and generated dashboard numbers."""
from __future__ import annotations

import json
import math
import re
from typing import Any

DATA_KEYS = frozenset({'data', 'results', 'result', 'records', 'items', 'features', 'observations', 'entries'})
META_KEYS = frozenset({'success', 'ok', 'status', 'message', 'error', 'errors', 'code', 'detail', 'pagination', 'links', 'meta', 'metadata', 'timestamp', 'api_version', 'version'})
ERROR_STATUS = frozenset({'error', 'failed', 'failure', 'deprecated', 'unauthorized', 'forbidden', 'not_found'})
BAD_MESSAGE = re.compile(r'(deprecated|no longer (available|supported)|invalid api|api key required|unauthori[sz]ed|endpoint not found|not found|rate limit exceeded)', re.I)
NUMBER = re.compile(r'(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])')


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


def _source_numbers(value: Any, bag: list[float], depth: int = 0) -> None:
    if depth > 12 or len(bag) > 15000: return
    if isinstance(value, dict):
        for v in value.values(): _source_numbers(v, bag, depth + 1)
    elif isinstance(value, list):
        if value: bag.append(float(len(value)))
        for v in value[:1000]: _source_numbers(v, bag, depth + 1)
    elif isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value):
        bag.append(float(value))
    elif isinstance(value, str) and re.fullmatch(r'-?\d+(?:,\d{3})*(?:\.\d+)?', value.strip()):
        try: bag.append(float(value.replace(',', '')))
        except ValueError: pass


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


def verify_ui_numbers(ui: dict, payload: Any, question: str = '') -> None:
    """Reject invented numbers; permit sourced numbers, rounding and returned-record counts.

    Does not independently prove nonnumeric claims. The answerability check in the agent
    is an additional gate, and should not be treated as scientific verification.
    """
    observed: list[float] = []
    _source_numbers(payload, observed)
    observed.extend(n for n, _ in _numeric_tokens(question))

    def require(value: str) -> None:
        for number, precision in _numeric_tokens(value):
            if not any(round(source, precision) == round(number, precision)
                       for source in observed):
                raise ValueError(f'Dashboard contains an unverified number ({number:g})')

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
