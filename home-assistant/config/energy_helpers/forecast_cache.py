#!/usr/bin/env python3
"""Durable planning snapshot admitted only from native acquisition proof.

No network, HA credentials, native state-event assumptions or bootstrap bypass.
Legacy saved snapshots are preserved with their original age and explicitly
unproved provenance. Only a newer committed native proof can replace them.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

_proof_module_path = Path(__file__).with_name('energy_forecast_proof.py')
if not _proof_module_path.is_file():
    _proof_module_path = Path('/config/custom_components/solcast_solar/energy_forecast_proof.py')
_proof_spec = importlib.util.spec_from_file_location('energy_native_proof', _proof_module_path)
_proof_module = importlib.util.module_from_spec(_proof_spec)
_proof_spec.loader.exec_module(_proof_module)

SCHEMA = 1
INTERVAL = 1800
COUNT = 144
MAX_BYTES = 14500
DEFAULT_PATH = '/config/.storage/energy_solcast_planning_snapshot.json'
DEFAULT_PROOF_PATH = '/config/.storage/energy_solcast_native_proof.json'
PAYLOAD_KEYS = ('schema_version','source_generation_utc','valid_from','valid_to','interval_seconds','rows')
PROVENANCE_KEYS = ('native_proof_schema','native_hook_revision','native_proof_hash','native_integration_version','fresh_from','fresh_to','admission')
epoch = _proof_module.timestamp


class Invalid(ValueError):
    pass


def compact(value):
    # Preserve schema-1 legacy digest field order for read-only migration.
    return json.dumps(value, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(record):
    payload = {k: record[k] for k in PAYLOAD_KEYS}
    if 'native_proof_schema' in record:
        payload.update({k: record[k] for k in PROVENANCE_KEYS})
    return hashlib.sha256(compact(payload).encode()).hexdigest()


def validate_saved(record):
    if not isinstance(record, dict) or record.get('status') != 'accepted':
        raise Invalid('saved cache is not an accepted snapshot')
    if record.get('schema_version') != SCHEMA or record.get('interval_seconds') != INTERVAL:
        raise Invalid('saved cache schema mismatch')
    epoch(record.get('source_generation_utc'))
    epoch(record.get('accepted_at'))
    start, end = epoch(record.get('valid_from')), epoch(record.get('valid_to'))
    if start != int(start) or start % INTERVAL or end - start != COUNT * INTERVAL:
        raise Invalid('saved cache horizon invalid')
    rows = record.get('rows')
    if not isinstance(rows, list) or len(rows) != COUNT:
        raise Invalid('saved cache row count invalid')
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 3 or row[0] != start + index * INTERVAL:
            raise Invalid('saved cache continuity invalid')
        _proof_module.number(row[1])
        _proof_module.number(row[2])
    if 'native_proof_schema' in record:
        if record['native_proof_schema'] != 1 or record.get('native_hook_revision') != _proof_module.REVISION or record.get('admission') != 'native_acquisition_proof':
            raise Invalid('saved provenance revision invalid')
        proof_hash = record.get('native_proof_hash')
        if not isinstance(proof_hash, str) or len(proof_hash) != 64 or any(c not in '0123456789abcdef' for c in proof_hash):
            raise Invalid('saved provenance hash invalid')
        if not start <= epoch(record.get('fresh_from')) < end or epoch(record.get('fresh_to')) != end:
            raise Invalid('saved provenance range invalid')
    if record.get('snapshot_id') != digest(record):
        raise Invalid('saved cache content hash mismatch')
    if len(compact(record).encode()) > MAX_BYTES:
        raise Invalid('saved cache too large')
    return record


ERRORS = (Invalid, _proof_module.InvalidProof, ValueError, TypeError, OSError, OverflowError, KeyError)


def load(path):
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_BYTES:
        raise Invalid('saved cache too large')
    return validate_saved(json.loads(path.read_text()))


def read_slot(path):
    try:
        return load(path), None
    except ERRORS as exc:
        return None, str(exc)[:160]


def atomic_save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(compact(record) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def result_view(record, ingest_status, error=None):
    result = dict(record) if record else dict(schema_version=SCHEMA, status='missing', rows=[], snapshot_id=None, source_generation_utc=None, accepted_at=None, valid_from=None, valid_to=None, interval_seconds=INTERVAL)
    result.update(ingest_status=ingest_status, ingest_error=error)
    result['provenance_status'] = 'proved_native_cycle' if result.get('native_proof_schema') == 1 and result.get('admission') == 'native_acquisition_proof' else 'legacy_snapshot_unproven' if record else 'no_snapshot'
    return result


def execute_native_proof(path, proof_path, now=None):
    """Read a committed proof; repeated reads preserve age and acceptance time."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    old, old_error = read_slot(path)
    try:
        if not proof_path.is_file():
            raise Invalid('No proved native acquisition has been published')
        if proof_path.stat().st_size > _proof_module.MAX_PROOF_BYTES:
            raise Invalid('native proof is too large')
        proof = _proof_module.validate_proof(json.loads(proof_path.read_text()), now)
        generation = epoch(proof['source_generation_utc'])
        if old and generation < epoch(old['source_generation_utc']):
            return result_view(old, 'older_native_proof')
        if old and generation == epoch(old['source_generation_utc']) and old.get('native_proof_hash') == proof['proof_hash']:
            return result_view(old, 'same_proven_generation')
        if old and generation <= epoch(old['source_generation_utc']):
            raise Invalid('proof does not advance the immutable acquisition generation')
        if not proof['fresh_from'] <= now < proof['range_end']:
            raise Invalid('native proof does not cover current time')
        ne, sw = dict(proof['ne']), dict(proof['sw'])
        new = dict(schema_version=SCHEMA, source_generation_utc=proof['source_generation_utc'],
            accepted_at=_proof_module.iso(now), valid_from=proof['range_start'], valid_to=proof['range_end'],
            interval_seconds=INTERVAL, rows=[[t, ne[t], sw[t]] for t in sorted(ne)], status='accepted',
            admission='native_acquisition_proof', native_proof_schema=proof['proof_schema'],
            native_hook_revision=proof['hook_revision'], native_proof_hash=proof['proof_hash'],
            native_integration_version=proof['integration_version'], fresh_from=proof['fresh_from'], fresh_to=proof['range_end'])
        new['snapshot_id'] = digest(new)
        validate_saved(new)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            latest, latest_error = read_slot(path)
            if latest and generation <= epoch(latest['source_generation_utc']):
                return result_view(latest, 'same_or_older_generation')
            atomic_save(path, new)
        return result_view(new, 'accepted_native_proof', old_error or latest_error)
    except ERRORS as exc:
        out = result_view(old, 'native_proof_unavailable', str(exc)[:180])
        if old_error:
            out['status'] = 'invalid'
        return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default=DEFAULT_PATH)
    parser.add_argument('--native-proof', default=DEFAULT_PROOF_PATH)
    args = parser.parse_args()
    print(compact(execute_native_proof(Path(args.path), Path(args.native_proof))))


if __name__ == '__main__':
    main()
