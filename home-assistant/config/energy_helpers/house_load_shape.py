"""Read-only Influx learner for the 06:00–11:00 non-EV load shape.

Only a local cache is written. No HA service, inverter or forecast provider calls.
The query uses 30 completed Brisbane calendar days. Day ages 1–3, 4–7, 8–14
and 15–30 receive respective weights 4, 3, 2 and 1. Missing or ineligible days
do not enter either weighted sum. Normalized slot weights preserve the planner's
separately supplied shoulder-energy expectation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Australia/Brisbane")
VERSION = 3
MIN_DAYS = 3
TRAINING_DAYS = 30
RECENT_DAYS = 7
RECENT_DAY_WEIGHT = 3
LATEST_DAYS = 3
LATEST_DAY_WEIGHT = 4
FORTNIGHT_DAYS = 14
FORTNIGHT_DAY_WEIGHT = 2
BASE_DAY_WEIGHT = 1
LIMITATION = "Influx numeric state-hold coverage does not prove historical device uptime: unavailable events are omitted and the house-load template can turn unavailable native readings into zero."


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def cutoff_at(now):
    return now.astimezone(ZONE).replace(hour=0, minute=0, second=0, microsecond=0)


def parse_csv(body):
    """Parse annotated Flux CSV using named columns, including repeated headers."""
    header = None
    rows = []
    for cells in csv.reader(io.StringIO(body)):
        if not cells or cells[0].startswith("#"):
            continue
        if "day" in cells and "slot" in cells and "energy" in cells:
            if not {"day", "slot", "energy", "samples", "clamped", "invalid"}.issubset(cells):
                raise ValueError("incomplete_csv_schema")
            header = cells
            continue
        if header is None or len(cells) != len(header):
            raise ValueError("unexpected_csv_schema")
        raw = dict(zip(header, cells))
        day = datetime.fromisoformat(raw["day"].replace("Z", "+00:00"))
        if day.tzinfo is None or day.astimezone(ZONE).time().isoformat() != "00:00:00":
            raise ValueError("invalid_day_boundary")
        rows.append(dict(day=day.astimezone(ZONE).date().isoformat(),
                         slot=int(raw["slot"]), energy=float(raw["energy"]),
                         samples=int(raw["samples"]), clamped=int(raw["clamped"]),
                         invalid=int(raw["invalid"])))
    return rows


def build_profile(rows, cutoff, generated_at, query_hash):
    begin = cutoff - timedelta(days=TRAINING_DAYS)
    recent_begin = (cutoff - timedelta(days=RECENT_DAYS)).date().isoformat()
    latest_begin = (cutoff - timedelta(days=LATEST_DAYS)).date().isoformat()
    fortnight_begin = (cutoff - timedelta(days=FORTNIGHT_DAYS)).date().isoformat()
    groups = defaultdict(dict)
    for row in rows:
        day = row["day"]
        if not begin.date().isoformat() <= day < cutoff.date().isoformat():
            raise ValueError("training_day_outside_closed_window")
        slot = row["slot"]
        if type(slot) is not int or not 0 <= slot < 10 or slot in groups[day]:
            raise ValueError("invalid_or_duplicate_slot")
        if not finite(row["energy"]) or not 0 <= row["energy"] <= 50:
            raise ValueError("invalid_slot_energy")
        for key in ("samples", "clamped", "invalid"):
            if type(row[key]) is not int or not 0 <= row[key] <= 30:
                raise ValueError("invalid_slot_counts")
        groups[day][slot] = row
    accepted = []
    rejected = []
    for offset in range(TRAINING_DAYS):
        day = (begin + timedelta(days=offset)).date().isoformat()
        slots = groups.get(day, {})
        reason = None
        if len(slots) != 10 or any(slots[i]["samples"] != 30 for i in range(10)):
            reason = "incomplete_numeric_coverage"
        elif any(slots[i]["invalid"] for i in range(10)):
            reason = "invalid_power_values"
        elif sum(slots[i]["clamped"] for i in range(10)) > 15:
            reason = "excess_ev_over_house_clamping"
        if reason:
            rejected.append(dict(day=day, reason=reason))
        else:
            accepted.append(dict(day=day, energy=[slots[i]["energy"] for i in range(10)],
                                 clamped=sum(slots[i]["clamped"] for i in range(10)),
                                 day_weight=LATEST_DAY_WEIGHT if day >= latest_begin else
                                 RECENT_DAY_WEIGHT if day >= recent_begin else
                                 FORTNIGHT_DAY_WEIGHT if day >= fortnight_begin else BASE_DAY_WEIGHT))
    recent_valid_days = sum(d["day"] >= recent_begin for d in accepted)
    latest_valid_days = sum(d["day"] >= latest_begin for d in accepted)
    fortnight_valid_days = sum(d["day"] >= fortnight_begin for d in accepted)
    historical_day_count = len(accepted) - fortnight_valid_days
    weighted_day_count = sum(d["day_weight"] for d in accepted)
    sums = [sum(d["energy"][i] * d["day_weight"] for d in accepted) for i in range(10)]
    total = sum(sums)
    ready = len(accepted) >= MIN_DAYS and total > 1e-9
    weights = [value / total for value in sums] if ready else []
    identity = dict(method_version=VERSION, training_end_epoch=cutoff.timestamp(),
                    recent_days=RECENT_DAYS, recent_day_weight=RECENT_DAY_WEIGHT,
                    latest_days=LATEST_DAYS, latest_day_weight=LATEST_DAY_WEIGHT,
                    fortnight_days=FORTNIGHT_DAYS, fortnight_day_weight=FORTNIGHT_DAY_WEIGHT,
                    base_day_weight=BASE_DAY_WEIGHT, accepted=accepted, query_sha256=query_hash)
    profile_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return dict(state="ready" if ready else "insufficient_history", method_version=VERSION,
                reason="closed_day_shape_ready" if ready else "need_three_complete_nonzero_mornings",
                recent_days=RECENT_DAYS, recent_day_weight=RECENT_DAY_WEIGHT,
                    latest_days=LATEST_DAYS, latest_day_weight=LATEST_DAY_WEIGHT,
                    fortnight_days=FORTNIGHT_DAYS, fortnight_day_weight=FORTNIGHT_DAY_WEIGHT,
                base_day_weight=BASE_DAY_WEIGHT, weighted_day_count=weighted_day_count,
                recent_valid_days=recent_valid_days, latest_valid_days=latest_valid_days, fortnight_valid_days=fortnight_valid_days,
                historical_day_count=historical_day_count,
                weights=weights, profile_id=profile_id, generated_at=generated_at.isoformat(), generated_epoch=generated_at.timestamp(),
                training_start_epoch=begin.timestamp(), training_end_epoch=cutoff.timestamp(), training_start_date=begin.date().isoformat(),
                training_end_date=cutoff.date().isoformat(), valid_days=len(accepted),
                contributor_days=[d["day"] for d in accepted], rejected_days=rejected,
                slot_contributor_counts=[len(accepted)] * 10, slot_numeric_coverage=[1.0] * 10 if accepted else [0.0] * 10,
                expected_shoulder_kwh=total / weighted_day_count if accepted else None,
                shoulder_start_minute=360, shoulder_end_minute=660, interval_seconds=1800,
                min_valid_days=MIN_DAYS, numeric_coverage_required=1.0,
                query_sha256=query_hash, source_limitation=LIMITATION)


def read_influx(query, config_dir):
    # Credentials stay in process memory and are never included in output/errors.
    import yaml
    secrets = yaml.safe_load((config_dir / "secrets.yaml").read_text())
    request = Request(secrets["influxdb_query_url"],
                      data=query.encode(), method="POST",
                      headers={"Authorization": secrets["influxdb_query_authorization"],
                               "Content-Type": "application/vnd.flux", "Accept": "application/csv"})
    with urlopen(request, timeout=60) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("response_too_large")
    return body.decode()


def valid_cached(cache, cutoff, now, query_hash):
    if not isinstance(cache, dict) or type(cache.get("method_version")) is not int or cache.get("method_version") != VERSION or cache.get("query_sha256") != query_hash:
        return False
    try:
        json.dumps(cache, allow_nan=False)
    except (TypeError, ValueError):
        return False
    if cache.get("training_end_epoch") != cutoff.timestamp():
        return False
    generated = datetime.fromisoformat(cache.get("generated_at", ""))
    if generated.tzinfo is None or not 0 <= (now - generated).total_seconds() < 86400:
        return False
    if cache.get("state") == "ready":
        weights = cache.get("weights")
        days = cache.get("valid_days")
        dates = cache.get("contributor_days")
        begin = cutoff - timedelta(days=TRAINING_DAYS)
        recent_begin = (cutoff - timedelta(days=RECENT_DAYS)).date().isoformat()
        latest_begin = (cutoff - timedelta(days=LATEST_DAYS)).date().isoformat()
        fortnight_begin = (cutoff - timedelta(days=FORTNIGHT_DAYS)).date().isoformat()
        if (type(days) is not int or not MIN_DAYS <= days <= TRAINING_DAYS or
            not isinstance(dates, list) or len(dates) != days or any(type(d) is not str for d in dates)):
            return False
        if len(set(dates)) != days:
            return False
        for day in dates:
            parsed = datetime.fromisoformat(day)
            if parsed.date().isoformat() != day or not begin.date() <= parsed.date() < cutoff.date():
                return False
        recent_valid_days = sum(day >= recent_begin for day in dates)
        latest_valid_days = sum(day >= latest_begin for day in dates)
        fortnight_valid_days = sum(day >= fortnight_begin for day in dates)
        historical_day_count = days - fortnight_valid_days
        weighting = dict(recent_days=RECENT_DAYS, recent_day_weight=RECENT_DAY_WEIGHT,
                    latest_days=LATEST_DAYS, latest_day_weight=LATEST_DAY_WEIGHT,
                    fortnight_days=FORTNIGHT_DAYS, fortnight_day_weight=FORTNIGHT_DAY_WEIGHT,
                         base_day_weight=BASE_DAY_WEIGHT, recent_valid_days=recent_valid_days,
                         latest_valid_days=latest_valid_days, fortnight_valid_days=fortnight_valid_days,
                historical_day_count=historical_day_count,
                         weighted_day_count=latest_valid_days * LATEST_DAY_WEIGHT +
                         (recent_valid_days - latest_valid_days) * RECENT_DAY_WEIGHT +
                         (fortnight_valid_days - recent_valid_days) * FORTNIGHT_DAY_WEIGHT +
                         historical_day_count * BASE_DAY_WEIGHT)
        if any(type(cache.get(key)) is not int or cache[key] != value for key, value in weighting.items()):
            return False
        if (cache.get("training_start_epoch") != begin.timestamp() or
            cache.get("training_start_date") != begin.date().isoformat() or
            cache.get("training_end_date") != cutoff.date().isoformat() or
            cache.get("generated_epoch") != generated.timestamp() or
            generated < cutoff or cache.get("interval_seconds") != 1800 or
            cache.get("shoulder_start_minute") != 360 or cache.get("shoulder_end_minute") != 660 or
            cache.get("slot_contributor_counts") != [days] * 10 or
            cache.get("slot_numeric_coverage") != [1.0] * 10 or
            not isinstance(cache.get("profile_id"), str) or len(cache["profile_id"]) != 64):
            return False
        if (any(type(n) is not int for n in cache['slot_contributor_counts']) or
            any(not finite(n) for n in cache['slot_numeric_coverage'])):
            return False
        return (isinstance(weights, list) and len(weights) == 10 and
                all(finite(x) and 0 <= x <= 1 for x in weights) and
                abs(sum(weights) - 1) <= 1e-9)
    # Retry failures/insufficient coverage hourly, not every sensor refresh.
    return cache.get("state") in ("error", "insufficient_history") and (now - generated).total_seconds() < 3600


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", type=Path, default=Path("/config"))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    cutoff = cutoff_at(now)
    cache_path = args.config_dir / ".storage/energy_house_shoulder_shape.json"
    query_file = Path(__file__).with_name("house_load_shape.flux")
    output = None
    query_hash = None
    try:
        query_source = query_file.read_text()
        query_hash = hashlib.sha256(query_source.encode()).hexdigest()
        try:
            cached = json.loads(cache_path.read_text())
            if valid_cached(cached, cutoff, now, query_hash):
                output = cached
        except (OSError, ValueError, TypeError, KeyError):
            pass
        if output is None:
            query = query_source.replace("__CUTOFF_UTC__", cutoff.astimezone(timezone.utc).isoformat())
            output = build_profile(parse_csv(read_influx(query, args.config_dir)), cutoff, now, query_hash)
    except Exception as exc:
        # Do not serialize exception messages: upstream errors can contain secrets.
        output = dict(state="error", reason="profile_read_failed", error_type=type(exc).__name__,
                      weights=[], method_version=VERSION, generated_at=now.isoformat(),
                      training_end_epoch=cutoff.timestamp(), query_sha256=query_hash,
                      source_limitation=LIMITATION)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_name(cache_path.name + f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(output, separators=(",", ":"), allow_nan=False))
        os.replace(temporary, cache_path)
    except OSError:
        output = dict(output, cache_warning="cache_write_failed")
    print(json.dumps(output, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()
