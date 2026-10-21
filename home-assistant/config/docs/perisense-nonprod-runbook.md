# PeriSense nonprod wake/sleep (Home Assistant)

PER-266 control surface for the **test** environment only. Erin uses scripts and sensors from the `perisense_nonprod` integration package (`integrations/perisense_nonprod.yaml`).

## Scope and guardrails

- **Nonprod only:** `https://test.perisense.app` — never prod, sandbox, or direct `execute-api` URLs in config.
- **No AWS in HA:** only an API Gateway key in `secrets.yaml` (`perisense_nonprod_ops_api_key`).
- **Platform-wide:** wake/sleep toggles web + health together; no per-service controls.
- **Status from API:** templates parse JSON only; failures show `unknown`.

## Setup

1. Obtain the nonprod ops API key (same value as GitHub secret `PERISENSE_OPS_API_KEY` in perisense-ops).
2. Add to `secrets.yaml` (see `docs/perisense-nonprod-secrets.yaml.example`):

   ```yaml
   perisense_nonprod_ops_api_key: "REPLACE_WITH_API_GATEWAY_KEY"
   ```

3. The package loads automatically via `homeassistant.yaml` → `packages: !include_dir_named integrations`.
4. Reload YAML or restart Home Assistant.
5. Confirm entities exist: `sensor.perisense_nonprod_platform_label`, `switch.perisense_nonprod_test`, `script.perisense_nonprod_wake`, etc.
6. Add the Lovelace card on the Ben room view (bind to label sensor + switch).
7. Pair **PeriSense Test Bridge** in the Home app (separate from Ben Bridge). Reload HomeKit or reset the accessory if the name does not update.

## Operator smoke (outside HA)

```bash
export KEY="REPLACE_WITH_API_GATEWAY_KEY"
curl -sS -H "x-api-key: $KEY" https://test.perisense.app/ops/platform/status
curl -sS -X POST -H "x-api-key: $KEY" -H "Content-Type: application/json" -d '{}' \
  https://test.perisense.app/ops/platform/wake
```

## Entities

| Entity | Role |
|--------|------|
| `sensor.perisense_nonprod_platform_status_raw` | REST poll (60s baseline); forced every 10s for 60s while platform is `starting`/`stopping` |
| `sensor.perisense_nonprod_platform` | Machine status (`started`, `stopped`, `degraded`, …) |
| `sensor.perisense_nonprod_platform_label` | **Display** status for dashboards (see below) |
| `sensor.perisense_nonprod_web` / `_health` | Per-service status + counts in attributes |
| `switch.perisense_nonprod_test` | Start/stop control; unavailable while busy or transitioning |
| `input_boolean.perisense_nonprod_command_in_flight` | Locks control during wake/sleep REST (max ~35s) |
| `binary_sensor.perisense_nonprod_platform_running` | On when platform is `started` |
| `binary_sensor.perisense_nonprod_platform_transitioning` | On during start/stop transitions |
| `script.perisense_nonprod_wake` / `_sleep` | Wake/sleep via REST; sets busy, refreshes status twice |
| `script.perisense_nonprod_refresh_status` | Manual status poll only |

HomeKit (**PeriSense Test Bridge**, port 21070): `switch.perisense_nonprod_test` as **PeriSense Test** (on/off/unavailable only). Pair this bridge separately in the Home app.

## Display status (`sensor.perisense_nonprod_platform_label`)

| Label | Meaning |
|-------|---------|
| `Stopped` | Platform down |
| `Starting` / `Stopping` | ECS rollout (or command in flight before API updates) |
| `Started (healthy)` | Up; web and health both `started` |
| `Started (degraded)` | Up with service mismatch |
| `Started (...)` | Up but a service still transitioning |
| `Unknown` | API/parse failure |

## Machine status (`sensor.perisense_nonprod_platform`)

API service values: `started` | `stopped` | `starting` | `stopping`.

| State | Meaning |
|-------|---------|
| `stopped` | Both services desired count 0 / stopped |
| `starting` / `stopping` | ECS rollout in progress (status polled every 10s for up to 60s, then 60s baseline) |
| `started` | Web and health agree and running |
| `degraded` | Aggregate `started` but web/health disagree, or one transitioning while the other is steady |
| `unknown` | HTTP/JSON error, missing fields, or unexpected status string |

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `unknown` on all sensors | Bad/missing secret, network, or API down |
| HTTP 403 | Invalid or rotated API key |
| HTTP 502 | Ops Lambda/API Gateway issue (see perisense-ops PER-265 / fix PRs) |
| Stale status after wake/sleep | Wait for script refresh (~4s) or next 60s poll; `script.perisense_nonprod_refresh_status` if needed |
| Switch stuck unavailable | Check `input_boolean.perisense_nonprod_command_in_flight`; failsafe clears after 35s |

## Security and key rotation

- Store the key **only** in `secrets.yaml`; never in Lovelace, git, or screenshots.
- **Rotation:** rotate API Gateway key in AWS → update `perisense_nonprod_ops_api_key` → reload REST integration or restart HA.
- **Blast radius:** nonprod ECS desiredCount only; no prod/sandbox impact.
- Never add AWS access keys or console automation to Home Assistant.

## Node-RED (`PeriSense Nonprod` tab)

Deploy flows: merge or import `nodered/data/flows/perisense-nonprod-nodes.json`, then **Deploy** in Node-RED. Uses `notify.notify_phones` and HA server **Home Assistant** (`64bb0343.71dfbc`).

| Trigger | Action |
|---------|--------|
| `sensor.perisense_nonprod_platform` → `started` | Notify: test environment has started |
| `sensor.perisense_nonprod_platform` → `stopped` | Notify: test environment has stopped |
| Cron **20:00** daily | If state is `started` or `degraded`, notify: **PeriSense is still running** |
| Cron **01:00** daily | If running, call `script.perisense_nonprod_sleep` + notify auto-stop |

Cron uses the Node-RED host timezone. Adjust inject `crontab` in the flow if needed (`0 20 * * *`, `0 1 * * *`).

## API shape note (future)

Deployed PER-265 JSON uses `aggregateStatus` and `services[]` with `key` (`web`, `health`). perisense-ops may later move to `aggregate.status` and `services.web` objects; update templates in `perisense_nonprod.yaml` when that ships—no HA blocker.
