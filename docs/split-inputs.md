# Split source inputs

Compose source now uses explicit `HOMELAB_IMPLEMENTATION_ROOT`, `HOMELAB_CONFIG_ROOT`
and `HOMELAB_AUTOMATION_ROOT` paths. Supply them from a private `.env` alongside the
other required deployment inputs. There is no implicit sibling checkout or old
monolithic source fallback. Build contexts and authored read-only binds point to
the repository that owns that source.

HA config, Node-RED config, MQTT config, MQTT Explorer config, rendered Traefik and
ZigbeeLens configuration remain **private assembled runtime inputs**. Copy/render
the reviewed authored source into those runtime locations with its private inputs;
do not mount a public checkout as a replacement for a complete writable config tree.
HA `.storage`, secrets, HACS assets, Node-RED credentials and retained broker state
are not supplied by these repositories.

The backup reader consumes the **installed** database and automation Compose files
and private recovery manifests, supplied through the corresponding required file
variables. A source template is not a deployed recovery record. Other data paths,
volume subpaths, container targets, mount flags, IDs and networks are retained.

These are source-only integration changes. No directory, data, service or live mount
has moved. Actual installation still needs immutable release pins and the existing
deployment/admission review. WiNet runtime/build settings are unchanged.
