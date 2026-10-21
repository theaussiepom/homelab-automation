# HA private values

The public YAML uses native `!secret` references for private addresses,
person/tracker identities, notification targets and deployment URLs.
`secrets.public-source.example.yaml` documents required keys with placeholders.
Keep real values in the private `secrets.yaml`; preserve existing secret entries.

The dashboard-display script was moved from `scripts.yaml` to the existing
`integrations` package directory. Its `script.display_living_show` identity is
unchanged. This one script is maintained in YAML; all other scripts remain
UI-editable. Set `ha_display_base_url` to the private HA origin without a
dashboard path. The script appends the checked path and uses the security path
while the alarm is armed; the old fixed full-URL secret is no longer used.
No `!secret` tags were added to UI-managed `automations.yaml` or
`scripts.yaml`.

The conversion was checked by resolving each newly introduced secret to the
private original and comparing YAML nodes, including scalar types and existing
include/secret tags. These are preparation checks, not a live HA reload.

References:
- https://www.home-assistant.io/docs/configuration/secrets/
- https://www.home-assistant.io/docs/configuration/packages/

The private prepared values stay on BenBeast. Their merge into the protected
live secrets file and deployment require a separately reviewed action.
