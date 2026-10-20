"""Small durable-artifact helpers, independent of recording-owned paths."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(encode(value) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def immutable_raw(root, raw):
    digest = sha(raw)
    path = Path(root) / 'raw' / (digest + '.bin')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if sha(path.read_bytes()) != digest:
            raise ValueError('Raw snapshot hash mismatch: ' + str(path))
    return path.resolve(), digest
