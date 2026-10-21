# Node-RED private deployment inputs

The maintained flows use Node-RED's native `${HOMELAB_NR_...}` environment
references. Personal device identifiers, notification targets and deployment
URLs belong in private inputs. Node IDs, wiring, service logic and package
manifests remain ordinary Git source.

Provide the values either through the service's environment or through
`/data/deployment.private.json`. The latter is a JSON object whose keys match the
empty `config/deployment.private.json.example`. `config/private-inputs.js` loads
the file at startup and makes the required values available to Node-RED.
An existing environment value takes precedence. Missing or empty required
values stop startup with the key name only.

Keep the populated file in the private Node-RED data directory, outside this
repository. Use mode `0600` and the Node-RED service owner. Keep
`settings.private.json` and flow credentials private too; this change does not
replace their credential storage. Do not put private values into tab/group
environment settings in the editor: those settings are saved into `flows.json`.

For a new machine, supply its values privately and restore the private runtime
data before starting Node-RED. For the existing deployment, preserve its current
values exactly and validate resolution before deploying the prepared source.
Replacing a device identifier in the public source does not rename an HA entity.

The config directory must stay mounted as a directory so Node-RED can save flows
atomically. Keep runtime `/data` separate. Back up private inputs with the
existing protected service backups.

Run the loader tests with:

```sh
node --test tools/node-red-private-inputs/test-private-inputs.js
```

Before deployment, test the prepared flow through the installed Node-RED
resolver with the private values and compare the resolved JSON with the
original. This verifies configuration equivalence, not physical device
behaviour. Deploy/restart remains a separate operational step.

This uses normal Git and `.gitignore`. There is no publication list. Review
staged content and scan it before creating the clean public repository;
ignore rules alone do not remove already tracked files or old history.
