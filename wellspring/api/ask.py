"""Ask orchestration: secret read, atomic daily quota, model and guarded query."""
from __future__ import annotations
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
import signal
import threading
import time

from .provider import generate_sql, ProviderRefused, ProviderUnavailable
from .query import execute_readonly

WALL_SECONDS = 9.5  # Leave response encoding/runtime overhead within the 10s wall budget.
MAX_BODY_BYTES = 8192
MAX_QUESTION_CHARS = 1200
_secret_cache = None


class AskRefusal(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def unavailable():
    return AskRefusal('ASK_UNAVAILABLE', 'Question answering is temporarily unavailable.')


def _timeout(*_):
    raise AskRefusal('QUERY_TIMEOUT', 'The question exceeded the time limit.')


@contextmanager
def hard_deadline(deadline):
    """Interrupt SDK/socket waits as well as Python work in Lambda's main thread."""
    if threading.current_thread() is not threading.main_thread():
        raise unavailable()
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _timeout()
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    signal.signal(signal.SIGALRM, _timeout)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL,
                             max(0.001, previous_timer[0] - (time.monotonic() - started)),
                             previous_timer[1])


def question_from_event(event):
    raw = event.get('body', '')
    if not isinstance(raw, str) or len(raw.encode()) > MAX_BODY_BYTES * 2:
        raise AskRefusal('INVALID_QUESTION', 'Provide a short question as JSON.')
    try:
        raw = base64.b64decode(raw, validate=True) if event.get('isBase64Encoded') else raw.encode()
        if len(raw) > MAX_BODY_BYTES:
            raise ValueError()
        body = json.loads(raw)
        question = body['question']
        if (not isinstance(question, str) or not question.strip()
                or len(question) > MAX_QUESTION_CHARS or '\x00' in question):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise AskRefusal('INVALID_QUESTION', 'Provide a question of at most 1200 characters.') from None
    return question.strip()


def configured():
    return bool(os.environ.get('ASK_KEY_PARAMETER') and os.environ.get('ASK_QUOTA_TABLE'))


def read_key(parameter, *, client=None):
    global _secret_cache
    if parameter != '/wellspring/ask/provider_key':
        raise unavailable()
    if _secret_cache and _secret_cache[0] == parameter and time.monotonic() < _secret_cache[2]:
        return _secret_cache[1]
    if client is None:
        import boto3
        client = boto3.client('ssm')
    try:
        value = client.get_parameter(Name=parameter, WithDecryption=True)['Parameter']['Value']
        if not isinstance(value, str) or not value:
            raise ValueError()
    except AskRefusal:
        raise
    except Exception:
        raise unavailable() from None
    _secret_cache = (parameter, value, time.monotonic() + 300)
    return value


def acquire_quota(table, cap, *, client=None, now=None):
    if not table or not isinstance(cap, int) or not 1 <= cap <= 1000:
        raise unavailable()
    if client is None:
        import boto3
        client = boto3.client('dynamodb')
    today = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()
    expiry = int(datetime.combine(today + timedelta(days=2), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    try:
        result = client.update_item(
            TableName=table, Key={'quota_key': {'S': 'ASK#' + today.isoformat()}},
            UpdateExpression='SET #expires = if_not_exists(#expires, :expiry) ADD #calls :one',
            ConditionExpression='attribute_not_exists(#calls) OR #calls < :cap',
            ExpressionAttributeNames={'#calls': 'calls', '#expires': 'expires_at'},
            ExpressionAttributeValues={':one': {'N': '1'}, ':cap': {'N': str(cap)},
                                       ':expiry': {'N': str(expiry)}},
            ReturnValues='UPDATED_NEW')
        count = int(result['Attributes']['calls']['N'])
        if not 1 <= count <= cap:
            raise ValueError()
        return count
    except AskRefusal:
        raise
    except Exception:
        # Exhaustion and store failure both prevent any model call.
        raise unavailable() from None


def answer(event, records, deadline, *, date_range=None):
    if not configured():
        raise unavailable()
    question = question_from_event(event)
    try:
        cap = int(os.environ.get('ASK_DAILY_LIMIT', '100'))
    except ValueError:
        raise unavailable() from None
    key = read_key(os.environ['ASK_KEY_PARAMETER'])
    acquire_quota(os.environ['ASK_QUOTA_TABLE'], cap)
    if time.monotonic() >= deadline:
        _timeout()
    model = os.environ.get('ASK_MODEL', 'deepseek-chat')
    base_url = os.environ.get('ASK_PROVIDER_URL', 'https://api.deepseek.com')
    try:
        sql, served_model = generate_sql(question, api_key=key, base_url=base_url,
                                         model=model, deadline=deadline, date_range=date_range)
    except ProviderRefused:
        raise AskRefusal('READ_ONLY_REQUIRED', 'Only read-only questions about the licence data are supported.') from None
    except ProviderUnavailable:
        raise unavailable() from None
    except TimeoutError:
        _timeout()
    result = execute_readonly(records, sql, deadline)
    return {'status': 'ok', 'sql': sql, **result, 'model': served_model,
            'row_limit': 200, 'refusal': None}
