# Node-RED source and private state

Node-RED reads live flows and settings from `config/`, mounted as `/config`.
The directory mount supports the editor's atomic flow saves. Edits to the six
reviewed source files appear directly in Git; commits remain deliberate manual
checkpoints. No automatic staging, commit, push, or service restart is configured.

Credentials, private settings, module installations, sessions, context, timers,
and generated state live outside this repository under
`/mnt/nas/docker/homelab-data/services/node-red/data`, mounted as `/data`.
Do not add encrypted credentials or private values to a flow or settings file.

Before adopting these settings, the private deployment must provide `/data` as
an owner-only directory (0700) and `/data/flows_cred.json` as an owner-only regular
file (0600), accessible by the Node-RED runtime user. Startup refuses other modes
or symbolic links and never changes private files or permissions automatically.
If the writer's pending `flows_cred.json.$$$` file already exists, it must also be
a regular 0600 file; stale permissive files require reviewed remediation.
After validation, the process uses umask 0077 so subsequent credential saves do
not recreate a broadly readable file. This also restricts other new runtime
files and directories to their owner.

Existing installations may have 0644 credential files. Back up and verify their
ownership, content and directory permissions before a separately reviewed
deployment; source checks do not establish that a live installation meets this
contract. Rehearse the changed settings against a private copy before restart.
The example private-settings file contains placeholders only.

`config/package.json` and `config/package-lock.json` are maintained dependency
snapshots. Node-RED's live palette manifests and installed modules remain in
`/data`; palette updates do not silently update these source snapshots.
The current upgrade candidate requires Node-RED 5 and Node.js 22.9 or later;
see [dependency changes and validation limits](../docs/node-red-dependencies.md)
before selecting a deployment image or installing these packages.

The local ignore policy admits only the reviewed six files. Review and screen
any additional source before adding an explicit exception. Check the exact
staged diff for private values before each commit; ignore rules do not inspect
values inside allowed files. Existing private history is not sanitised by this
layout. Do not use a broad `git add` or restore the entire repository to undo a
Node-RED change. Review the selected historical diff and restore only the intended
source, preserving any more recent state; deployment is a separate action.
