# InfluxDB private inputs

The energy REST sensors and `energy_helpers/house_load_shape.py` use the same two
keys in the private HA configuration-root `secrets.yaml`:

```yaml
influxdb_query_url: "http://influx.example.invalid:8086/api/v2/query?org=example"
influxdb_query_authorization: "Token EXAMPLE_ONLY"
```

These are examples, not deployment values. Keep the real file outside the public
Git tree. The URL includes both the deployment endpoint and organisation query.
The existing authorization key is unchanged.

Before deploying these source changes, add `influxdb_query_url` to the existing
private file using the exact URL from the current live `read_influx` request.
Check that all three existing REST resources have that same value. Preserve
every existing secret, file owner, mode and ACL. Refuse a conflicting existing
key; do not replace the whole file or expose its contents.

The branch preparation has not installed this private key or changed live HA.
Validate the resolved resources and helper in the target environment before a
separately approved deployment. The isolated tests use synthetic inputs and
never contact InfluxDB:

```sh
python3 -B tools/ha-source-history/test_influx_private_inputs.py
```
