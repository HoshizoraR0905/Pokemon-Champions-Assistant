"""Conservative, conditional HTTP with durable current-cache receipts."""
from email.utils import parsedate_to_datetime
import json
import math
from pathlib import Path
import time
from .common import now, sha, atomic_json, immutable_raw

MAX_BODY = 16 * 1024 * 1024


class HTTPFailure(RuntimeError):
    pass


class Fetcher:
    def __init__(self, root, *, interval=2., timeout=30., retries=2,
                 session=None, clock=time.time, sleep=time.sleep):
        if not math.isfinite(interval) or interval < .1 or not math.isfinite(timeout) or timeout <= 0 or not 0 <= retries <= 5:
            raise ValueError('Invalid HTTP limits')
        if session is None:
            import requests
            session = requests.Session()
        self.root = Path(root)
        self.session, self.interval, self.timeout = session, interval, timeout
        self.retries, self.clock, self.sleep = retries, clock, sleep
        rate_path = self.root/'rate.json'
        self.last_request = json.loads(rate_path.read_text())['last_request_epoch'] if rate_path.exists() else None
        self.requests = 0
        self.cache_hits = 0

    def get(self, url, *, refresh_seconds=86400., force=False):
        if not math.isfinite(refresh_seconds) or refresh_seconds < 0:
            raise ValueError('Invalid refresh interval')
        key = sha(url.encode())
        path = self.root/'http'/(key+'.json')
        old = json.loads(path.read_text()) if path.exists() else None
        if old:
            cached = Path(old['raw_path'])
            if not cached.is_relative_to(self.root.resolve()) or sha(cached.read_bytes()) != old['raw_sha256']:
                raise ValueError('Cached raw response failed ownership/hash check')
            if not force and self.clock()-old['checked_epoch'] < refresh_seconds:
                self.cache_hits += 1
                return old
        headers = {'User-Agent': 'Pokemon-Champions-Assistant/0.1 (current statistics cache)',
                   'Accept': 'application/json'}
        if old:
            for name, target in [('etag', 'If-None-Match'), ('last-modified', 'If-Modified-Since')]:
                if old['headers'].get(name):
                    headers[target] = old['headers'][name]
        error = None
        for attempt in range(self.retries+1):
            delay = max(0., min(self.interval, self.interval-(self.clock()-self.last_request))) if self.last_request is not None else 0.
            if delay:
                self.sleep(delay)
            self.last_request = self.clock()
            atomic_json(self.root/'rate.json', dict(last_request_epoch=self.last_request))
            self.requests += 1
            response = None
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout,
                                            allow_redirects=False, stream=True)
                status = response.status_code
                incoming = {k.lower(): v for k, v in response.headers.items()}
                if status == 304 and old:
                    old.update(checked_at=now(), checked_epoch=self.clock(), status=304,
                               headers={**old['headers'], **incoming})
                    atomic_json(path, old)
                    return old
                if status == 200:
                    parts, size = [], 0
                    for part in response.iter_content(65536):
                        size += len(part)
                        if size > MAX_BODY:
                            raise ValueError('Response exceeds bounded download size')
                        parts.append(part)
                    raw = b''.join(parts)
                    raw_path, digest = immutable_raw(self.root, raw)
                    receipt = dict(url=url, retrieved_at=now(), checked_at=now(),
                        checked_epoch=self.clock(), status=status, headers=incoming,
                        raw_path=str(raw_path), raw_sha256=digest, bytes=len(raw))
                    # Raw bytes exist durably before any parsing/normalization.
                    atomic_json(path, receipt)
                    return receipt
                if status not in (429, 500, 502, 503, 504):
                    raise ValueError('Non-retryable HTTP status '+str(status))
                error = 'HTTP '+str(status)
                retry_after = incoming.get('retry-after')
                backoff = max(self.interval, 2.**attempt)
                if retry_after:
                    try:
                        requested = float(retry_after)
                    except ValueError:
                        requested = parsedate_to_datetime(retry_after).timestamp()-self.clock()
                    if not math.isfinite(requested) or requested > 60:
                        raise ValueError('Retry-After exceeds bounded foreground wait; resume later')
                    backoff = max(backoff, requested)
            except (OSError, TimeoutError) as exc:
                error = str(exc)
                backoff = max(self.interval, 2.**attempt)
            except Exception as exc:
                # requests has its own timeout/connection hierarchy.
                import requests
                if isinstance(exc, requests.RequestException):
                    error = str(exc)
                    backoff = max(self.interval, 2.**attempt)
                else:
                    self._error(url, repr(exc), attempt+1)
                    raise
            finally:
                if response is not None:
                    response.close()
            self._error(url, error, attempt+1)
            if attempt < self.retries:
                self.sleep(backoff)
        raise HTTPFailure(f'{url}: {error}; successful cached responses preserved')

    def _error(self, url, error, attempts):
        # One bounded last-error receipt per URL, no accumulating request log.
        atomic_json(self.root/'http-errors'/(sha(url.encode())+'.json'),
                    dict(url=url, error=error, attempts=attempts, at=now()))
