# Node-RED dependency upgrade candidate

This source snapshot updates the installed-node manifest to the stable npm releases
reviewed on 21 October 2026. It does not update the running palette, container image,
flows, credentials or devices.

## Runtime requirements

The complete set requires **Node-RED 5 or later and Node.js 22.9 or later**. In
particular, theme-collection 5 requires Node-RED 5; Modbus 5.61 requires Node-RED 4
and Node.js 22. Select and qualify an immutable compatible private
`HOMELAB_NODE_RED_IMAGE` before deploying this candidate. Do not install the theme
upgrade into a Node-RED 4 runtime. The project manifest does not install or upgrade
Node-RED core, including its own expression engine.

| Package | Previous snapshot | Reviewed release |
| --- | --- | --- |
| @node-red-contrib-themes/theme-collection | 4.0.9 | 5.0.1 |
| node-red-contrib-home-assistant-websocket | 0.80.3 | 0.82.0 |
| node-red-contrib-modbus | 5.42.0 | 5.61.0 |
| node-red-contrib-xstate-machine | 1.3.3 | 1.3.4 |
| node-red-dashboard | 3.6.5 | 3.6.6 |
| node-red-node-base64 | 0.3.0 | 1.0.0 |
| node-red-node-email | 3.0.2 | 5.2.5 |
| node-red-node-feedparser | 0.3.0 | 1.0.7 |
| node-red-node-suncalc | 1.1.2 | 1.2.0 |

The other fifteen direct dependencies were already at their stable latest release.
Compatible transitive dependencies have also been refreshed in the lockfile.
The legacy dashboard remains deprecated upstream; replacing it is a separate flow
and UI migration, not part of this update.

## Security overrides

The HA node still declares JSONata 2.1.0 even in release 0.82.0. Its scoped override
uses 2.2.2 to address the published expression code-execution and resource-exhaustion
advisories. JSONata now produces objects without inherited prototype properties;
consumers must use normal property access or `Object.hasOwn`/the safe
`Object.prototype.hasOwnProperty.call` pattern, not `result.hasOwnProperty()`.
The existing Cast-only protobuf 7.6.6 override remains in place.

The state-machine renderer pins Handlebars 4.7.7 upstream. A scoped override now
selects 4.7.10. Tests exercise its actual precompiled DOT and state-machine text
templates, preserve transitions and labels, and confirm invalid input is rejected.

Cast's speech helper also pins Axios 0.21.x. Its scoped override selects the
[patched 0.34.0 release](https://github.com/axios/axios/releases/tag/v0.34.0).
The inherited-request-data regression fails against 0.21.4 and passes after the
update. A second regression reproduces inherited form-serializer behavior on
0.33.0 and passes on 0.34.0. GitHub dependency review reported this additional
advisory even though npm audit did not, so both checks remain required.
In-memory adapter tests preserve the speech helper's URL construction,
request serialization, audio response parsing and transport-error behavior; they
contact neither Google nor a speaker.

The tests use the dependency resolved from the HA node, its actual JSONata service
with a synthetic Node-RED utility adapter, synthetic states and public flow
expression parsing. They verify that prototype lookup/function construction is
rejected and ordinary transformations and HA bindings continue to work. They do
not prove compatibility with the expression engine bundled in a selected runtime.

## Validation and remaining work

A clean `npm ci --ignore-scripts` and 31 focused Cast, credential-store, JSONata
and renderer tests pass on Node.js 24. The same 31 tests pass in an isolated
Node-RED 5.0.8 image using Node.js 24.21.0. A separate network-disabled safe-mode
check loads the serial and Modbus modules, registers all 22 node packages and the
theme plugin, and finds all 23 node types used by the public flow snapshot.
The HA expression service also passes a binding check using the actual Node-RED 5
utility implementation. Core JSONata resolves to 2.2.2 and rejects the harmless
function-construction regression.

The refreshed npm audit has 21 affected dependency entries, down from 48: zero
critical, ten high and eleven moderate. JSONata, protobuf, Handlebars and Axios
are absent from that audit. Remaining chains include InfluxDB, email and the
state-machine renderer's other dependencies.
These counts include parent packages affected by a dependency, not independent
exploits. Latest node releases do not necessarily contain patched transitive
dependencies. No advisories have been suppressed and no forced downgrade or broad
major-version override has been applied.

These isolated checks used public fixtures, not the protected live settings and
credentials, and did not execute flows or connect to devices. Before deployment,
complete a private-copy rehearsal, preserve a consistent rollback backup, and
assess the remaining advisories. After deployment, verify live connections and
existing automation behavior separately; palette registration does not establish
successful device communication.
