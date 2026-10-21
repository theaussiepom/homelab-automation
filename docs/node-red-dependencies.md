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

The tests use the dependency resolved from the HA node, its actual JSONata service
with a synthetic Node-RED utility adapter, synthetic states and public flow
expression parsing. They verify that prototype lookup/function construction is
rejected and ordinary transformations and HA bindings continue to work. They do
not prove compatibility with the expression engine bundled in a selected runtime.

## Validation and remaining work

A clean `npm ci --ignore-scripts` and 21 focused Cast, credential-store and JSONata
tests pass on Node.js 24. Package lifecycle scripts are deliberately disabled in
this source review; native serial dependencies and actual flows still need an
isolated runtime rehearsal before deployment.

The refreshed npm audit has 25 affected dependency entries, down from 48: one
critical, fourteen high and ten moderate. JSONata and protobuf are absent from
that audit. The remaining critical entry is Handlebars through the state-machine
node's dependencies; other remaining chains include Cast, InfluxDB and email.
These counts include parent packages affected by a dependency, not independent
exploits. Latest node releases do not necessarily contain patched transitive
dependencies. No advisories have been suppressed and no forced downgrade or broad
major-version override has been applied.

Before deployment, qualify the selected runtime, native modules, private credential
restore, HA nodes, Modbus, email, feed parsing, dashboard and existing automations
without connecting the rehearsal to production devices. Deployment remains a
separate decision after the remaining advisories are assessed.
