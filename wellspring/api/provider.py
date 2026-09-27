"""Bounded DeepSeek SQL generation. Provider output is never trusted as SQL."""
from __future__ import annotations
import json
import re
import time
from urllib import error, parse, request

from .query import SCHEMA_TEXT

MAX_RESPONSE_BYTES = 32768
MAX_SQL_BYTES = 16384


class ProviderUnavailable(Exception):
    pass


class ProviderRefused(Exception):
    pass


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the Authorization header to a redirect destination.
        return None


def generate_sql(question, *, api_key, base_url, model, deadline, date_range=None):
    url = parse.urlsplit(base_url)
    if (url.scheme != 'https' or url.hostname != 'api.deepseek.com'
            or url.port not in (None, 443) or url.username or url.password
            or url.query or url.fragment or url.path.rstrip('/') not in ('', '/v1')):
        raise ProviderUnavailable()
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    system = (
        'Translate the question to exactly one SQLite SELECT statement over the public events table. '
        'Return only SQL, without Markdown, comments, explanation or tools. '
        'If the question requests modification, private/system data, current well status, or anything '
        'not supported by this schema, return REFUSE instead. '
        'Rows are licence events, not a current well inventory. By default include '
        "event_type = 'issued' unless the question explicitly asks for other event types. "
        'Use report_date for dates, count(*) for events, and SQLite strftime for weekly grouping. '
        'Company and substance text may be matched with lower(column) LIKE a quoted pattern. '
        'Only documented table columns exist. Do not use CTEs, PRAGMA, extensions or system tables. '
        + SCHEMA_TEXT
    )
    if date_range:
        system += f' Available report-date window: {date_range[0]} through {date_range[1]}.'
    body = {
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': question}],
        'temperature': 0, 'max_tokens': 512, 'stream': False,
        'thinking': {'type': 'disabled'},
    }
    req = request.Request(base_url.rstrip('/') + '/chat/completions',
                          data=json.dumps(body).encode(),
                          headers={'Authorization': 'Bearer ' + api_key,
                                   'Content-Type': 'application/json'})
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=min(remaining, 8.0)) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (error.URLError, OSError):
        raise ProviderUnavailable() from None
    if time.monotonic() >= deadline:
        raise TimeoutError()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderUnavailable()
    try:
        data = json.loads(raw)
        sql = data['choices'][0]['message']['content']
        served_model = data['model']
        if (not isinstance(sql, str) or not sql.strip()
                or len(sql.encode()) > MAX_SQL_BYTES
                or not isinstance(served_model, str)
                or not re.fullmatch(r'deepseek-[a-z0-9][a-z0-9._-]{0,63}', served_model)
                or api_key in sql or api_key in served_model):
            raise ValueError()
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderUnavailable() from None
    if sql.strip().upper().startswith('REFUSE'):
        raise ProviderRefused()
    return sql.strip(), served_model
