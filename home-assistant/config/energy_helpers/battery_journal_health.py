#!/usr/bin/env python3
"""Bounded health/rotation for the native HA File JSONL decision journal.

Fixed CLI path; no credentials, network or Home Assistant imports. Renaming
preserves an in-flight writer's open descriptor in its archive. Native File
opens/closes per append; retention assumes an append finishes well before four
rotations (at least twenty minutes at the configured polling interval).
"""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

PATH = Path('/config/energy_logs/battery-decisions.jsonl')
ROTATE_BYTES = 5 * 1024 * 1024
ARCHIVES = 4
TAIL_BYTES = 128 * 1024
MAX_ERROR = 800
NATIVE_HEADER = re.compile(r'^Home Assistant notifications \(Log started: ([^)]+)\)$')


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def compact(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be a UTC ISO string')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError('timestamp must include UTC timezone')
    return result.timestamp()


def validate_record(value):
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value.get('schema') != 1:
        raise ValueError('unsupported record schema')
    for field, cap in [('event', 128), ('event_id', 256)]:
        if not isinstance(value.get(field), str) or not 0 < len(value[field]) <= cap:
            raise ValueError('invalid ' + field)
    timestamp(value.get('recorded_at'))
    timestamp(value.get('captured_at'))
    if not isinstance(value.get('payload'), dict):
        raise ValueError('payload must be an object')
    return value


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def regular_or_missing(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise OSError('Expected a regular journal file: ' + path.name)
    return info


def initialize_if_missing(path, *, now=utc_now):
    """Publish a complete first JSON line without replacing a racing HA writer."""
    if regular_or_missing(path) is not None:
        return
    stamp = now()
    record = dict(schema=1, event='journal_initialized', event_id=str(uuid.uuid4()),
                  recorded_at=stamp, captured_at=stamp,
                  payload={'writer':'journal_health','purpose':'Initialize private JSONL file; avoid native File header'})
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.init', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write((compact(record) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        try:
            # link is atomic and refuses an existing destination. os.replace
            # would discard a new file concurrently opened by the HA writer.
            os.link(temporary, path, follow_symlinks=False)
            fsync_directory(path.parent)
        except FileExistsError:
            # Another appender created the live path after our existence check.
            # Preserve it byte-for-byte; the bounded reader tolerates HA's header.
            regular_or_missing(path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def archive_path(path, index):
    return path.with_name(path.name + '.' + str(index))


def rotate(path, *, threshold=ROTATE_BYTES, now=utc_now):
    current = regular_or_missing(path)
    if current is None or current.st_size < threshold:
        return False
    for index in range(1, ARCHIVES + 1):
        regular_or_missing(archive_path(path, index))
    # No copy/truncate. An already-open native writer continues into the renamed
    # inode, while a new writer creates/opens the replacement live pathname.
    archive_path(path, ARCHIVES).unlink(missing_ok=True)
    for index in range(ARCHIVES - 1, 0, -1):
        old = archive_path(path, index)
        if old.exists():
            os.replace(old, archive_path(path, index + 1))
    os.replace(path, archive_path(path, 1))
    fsync_directory(path.parent)
    initialize_if_missing(path, now=now)
    return True


def read_tail(path):
    """At most128KiB per known file; do not load journal history or payloads."""
    info = regular_or_missing(path)
    if info is None:
        return [], []
    with path.open('rb') as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        # Reserve one byte to distinguish a boundary from a truncated first
        # line, keeping total reads at or below TAIL_BYTES per file.
        offset = max(0, size - (TAIL_BYTES - 1))
        previous = b'\n'
        if offset:
            stream.seek(offset - 1)
            previous = stream.read(1)
        stream.seek(offset)
        data = stream.read(TAIL_BYTES - 1)
    errors = []
    if offset and previous != b'\n':
        boundary = data.find(b'\n')
        if boundary < 0:
            return [], [path.name + ': tail line exceeds bounded reader size']
        data = data[boundary + 1:]
        if not data:
            return [], [path.name + ': no complete record inside bounded tail']
    # A concurrent native append can produce a transient incomplete tail. Do
    # not declare it good or silently discard it; the next poll may resolve it.
    if data and not data.endswith(b'\n'):
        errors.append(path.name + ': incomplete trailing line (writer may still be active)')
        data = data[:data.rfind(b'\n') + 1] if b'\n' in data else b''
    records = []
    for line in data.splitlines():
        if not line.strip():
            continue
        try:
            text = line.decode('utf-8')
            if text == '-' * 80:
                continue
            header = NATIVE_HEADER.fullmatch(text)
            if header:
                timestamp(header.group(1))
                continue
            def invalid_constant(value):
                raise ValueError('non-finite JSON number')
            record = validate_record(json.loads(text, parse_constant=invalid_constant))
            records.append((timestamp(record['recorded_at']), record['event'], record['recorded_at']))
        except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError) as exc:
            errors.append(path.name + ': malformed tail record (' + str(exc)[:100] + ')')
    return records, errors


def inspect_journal(path=PATH, *, rotate_bytes=ROTATE_BYTES, now=utc_now):
    """Optional function arguments are for temp-directory tests; CLI stays fixed."""
    path = Path(path)
    result = dict(state='error', last_event=None, last_recorded_at=None,
                  records_bytes=None, archive_count=None, path=str(path), error=None)
    lock_fd = None
    try:
        if path.parent.is_symlink():
            raise OSError('Journal directory must not be a symlink')
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        lock_path = path.with_name(path.name + '.health.lock')
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
            raise OSError('Journal health lock must be a regular file')
        os.fchmod(lock_fd, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OSError('Another journal health/rotation check is running') from exc
        initialize_if_missing(path, now=now)
        rotate(path, threshold=rotate_bytes, now=now)
        known = [path] + [archive_path(path, index) for index in range(1, ARCHIVES + 1)]
        for candidate in known:
            if regular_or_missing(candidate) is not None:
                candidate.chmod(0o600)
        # Check append-open permission without emitting a test record into history.
        # This cannot prove free disk space or the success of a future native write.
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        os.close(fd)
        records, errors = [], []
        for candidate in known:
            found, failed = read_tail(candidate)
            records.extend(found)
            errors.extend(failed)
        if records:
            _, result['last_event'], result['last_recorded_at'] = max(records, key=lambda record:record[0])
        result['records_bytes'] = path.stat().st_size
        result['archive_count'] = sum(archive_path(path, index).is_file() for index in range(1, ARCHIVES + 1))
        result['state'] = 'error' if errors else 'ready'
        result['error'] = '; '.join(errors)[:MAX_ERROR] if errors else None
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        result['error'] = str(exc)[:MAX_ERROR]
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
    return result


if __name__ == '__main__':
    print(compact(inspect_journal()))
