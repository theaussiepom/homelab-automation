/** Render the current people in a Home Assistant group using the existing cards/badges. */
class GroupPersonPills extends HTMLElement {
  constructor() {
    super();
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `<style>
      :host { display: block; min-width: 0; }
      .people { display: flex; gap: 8px; align-items: center; }
      :host([variant="badge"]) { width: min(calc(100vw - 64px), 520px); max-width: 100%; }
      :host([variant="badge"]) .people { flex-wrap: wrap; justify-content: center; }
      :host([variant="card"]) .people { gap: 4px; overflow-x: auto; scrollbar-width: thin; }
      :host([variant="card"]) button-card { flex: 1 0 88px; min-width: 88px; }
      .empty { color: var(--secondary-text-color); font-size: 14px; padding: 8px; }
    </style><div class="people" role="list" aria-label="People presence"></div>`;
    this._row = root.querySelector('.people');
    this._items = new Map();
  }

  setConfig(config) {
    if (!config.entity?.startsWith('group.')) throw new Error('A people group is required');
    if (!['badge', 'card'].includes(config.variant)) throw new Error('Choose badge or card');
    if (config.variant === 'card' && config.card?.type !== 'custom:button-card') {
      throw new Error('A button-card template is required');
    }
    this._config = config;
    this.setAttribute('variant', config.variant);
    this._items.clear();
    this._row.replaceChildren();
    this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  getCardSize() { return 1; }

  _render() {
    if (!this._config || !this._hass) return;
    const tag = this._config.variant === 'badge' ? 'hui-entity-badge' : 'button-card';
    if (!customElements.get(tag)) {
      if (!this._waiting) {
        this._waiting = true;
        customElements.whenDefined(tag).then(() => { this._waiting = false; this._render(); });
      }
      return;
    }
    const group = this._hass.states[this._config.entity];
    const raw = group?.attributes.entity_id;
    const available = group && !['unknown', 'unavailable'].includes(group.state);
    const members = available && Array.isArray(raw)
      ? [...new Set(raw.filter(id => typeof id === 'string' && id.startsWith('person.')))] : [];
    for (const [id, element] of this._items) {
      if (!members.includes(id)) { element.remove(); this._items.delete(id); }
    }
    if (!members.length) {
      this._row.replaceChildren();
      const empty = document.createElement('span');
      empty.className = 'empty';
      empty.textContent = available ? 'No people configured' : 'People unavailable';
      this._row.append(empty);
      return;
    }
    this._row.querySelector('.empty')?.remove();
    for (const [index, id] of members.entries()) {
      let element = this._items.get(id);
      if (!element) {
        element = document.createElement(tag);
        element.setAttribute('role', 'listitem');
        element.setConfig(this._config.variant === 'badge' ? {
          type: 'entity', entity: id, icon: 'mdi:account',
          show_name: true, show_state: true, show_icon: true,
          tap_action: { action: 'none' }, hold_action: { action: 'none' },
          double_tap_action: { action: 'none' },
        } : { ...this._config.card, entity: id });
        this._items.set(id, element);
      }
      // A stale group member must remain visible as unavailable, rather than disappear.
      element.hass = this._hass.states[id] ? this._hass : {
        ...this._hass, states: { ...this._hass.states, [id]: {
          entity_id: id, state: 'unavailable', attributes: { friendly_name: id.slice(7) },
        } },
      };
      // Preserve child elements on state updates and move them only when membership order changes.
      if (this._row.children[index] !== element) {
        this._row.insertBefore(element, this._row.children[index] || null);
      }
    }
  }
}
customElements.define('group-person-pills', GroupPersonPills);
