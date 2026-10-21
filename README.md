# Homelab automation

Home Assistant, Node-RED and related MQTT configuration share one source boundary.

- `home-assistant/config/`: entities, scripts, packages, dashboards and authored frontend helpers.
- `home-assistant/startup/`: authored startup support.
- `node-red/config/`: flows, settings and private-input loader; UI credentials and runtime state are excluded.
- `mqtt/config/`: broker configuration; credentials and retained state remain private/runtime data.
- `compose/`: the reviewed Automation service definitions, preserved for later catalog/path integration.

Dashboards call the stable HA entity and script IDs defined by the packages. Node-RED flows consume those same IDs and HA services; MQTT is the common messaging service. The split preserves source bytes and IDs. It does not reload HA, deploy flows, change credentials, or alter the Automation LXC lifecycle.

Supply real values through the existing private input mechanisms (`!secret`, environment values, private Node-RED JSON), outside these public sources. See `docs/` and `SPLIT-DRAFT.md`. WiNet application work remains with its separate owner; no WiNet source/build copy is included here.

See [split input paths](docs/split-inputs.md) for required repository roots and private assembled runtime inputs.
