/** Read-only Security Activity card. Episode grouping and photo association belong to HA. */
const TAG = 'security-activity-card';
const RETENTION = 43200;
const CSS = `
:host{display:block;--sa-fg:var(--primary-text-color,#1B2432);--sa-muted:var(--secondary-text-color,#677181);--sa-bg:var(--ha-card-background,var(--card-background-color,#fff));--sa-line:var(--divider-color,#d5d9df);--sa-radius:22px;font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif);color:var(--sa-fg)}
:host([tablet]){--sa-fg:var(--primary-base-color,#1B2432);--sa-muted:var(--secondary-base-color,#626D77);--sa-bg:var(--opaque-background-color,#EDE5D1);--sa-line:var(--secondary-base-color,#626D77);--sa-radius:20px}
*{box-sizing:border-box}ha-card{display:flex;flex-direction:column;height:var(--sa-height,440px);min-height:220px;overflow:hidden;border:1px solid var(--sa-line);border-radius:var(--sa-radius);background:var(--sa-bg);color:var(--sa-fg);box-shadow:none}h2{font-size:20px;font-weight:600;line-height:1.25;margin:0;min-width:0}header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:18px 18px 12px;flex:none}:host([tablet]) h2{font-size:22px;font-weight:650}.window{font-size:13px;color:var(--sa-muted);white-space:nowrap}.notice{margin:0;padding:0 18px 10px;color:var(--sa-muted);font-size:14px}.notice:empty{display:none}.rows{overflow:auto;min-height:0;flex:1;overscroll-behavior:contain;scrollbar-width:thin;padding:0 10px 8px}.row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:center;width:100%;min-height:62px;margin:0;padding:10px 8px;text-align:left;border:0;border-top:1px solid color-mix(in srgb,var(--sa-line) 30%,transparent);background:transparent;color:var(--sa-fg);font:inherit;font-size:16px;cursor:pointer;border-radius:0}.row:first-of-type{border-top:0}.row:hover,.row:focus-visible{background:color-mix(in srgb,var(--sa-fg) 6%,transparent);border-radius:10px}.row:focus-visible,button:focus-visible{outline:2px solid var(--primary-color,#5296A5);outline-offset:-2px}.row-text{min-width:0}.row-area{display:block;color:var(--sa-muted);font-size:13px;margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.name{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row time{font-size:14px;color:var(--sa-muted);font-variant-numeric:tabular-nums;white-space:nowrap}:host([tablet]) .row{font-size:18px}:host([tablet]) .row time{font-size:16px}.day{margin:10px 8px 3px;color:var(--sa-muted);font-size:12px;font-weight:600;letter-spacing:.02em}.empty{display:grid;place-items:center;text-align:center;min-height:150px;padding:24px;color:var(--sa-muted);font-size:15px}.empty button{margin-top:12px}
button{font:inherit;touch-action:manipulation;-webkit-tap-highlight-color:transparent}.retry{min-height:44px;padding:8px 16px;border:1px solid var(--sa-line);border-radius:12px;color:var(--sa-fg);background:transparent;cursor:pointer}
.backdrop{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:24px;background:rgba(0,0,0,.56);color:var(--sa-fg);font-family:Roboto,Arial,sans-serif}.dialog{width:min(1040px,100%);max-height:calc(100dvh - 48px);overflow:auto;overscroll-behavior:contain;border:1px solid var(--sa-line);border-radius:24px;background:var(--sa-bg);box-shadow:0 16px 64px #0005}.dialog.compact{width:min(620px,100%)}.dialog-header{position:sticky;top:0;z-index:1;background:var(--sa-bg);display:flex;align-items:center;gap:16px;padding:20px 24px 12px}.dialog-heading{flex:1;min-width:0}.dialog-heading h2{font-size:24px;overflow-wrap:anywhere}.area{margin:5px 0 0;font-size:14px;color:var(--sa-muted)}.close{display:grid;place-items:center;flex:none;width:48px;height:48px;border:1px solid var(--sa-line);border-radius:14px;background:transparent;color:var(--sa-fg);cursor:pointer}.close svg{width:24px;height:24px}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;padding:4px 24px 18px;margin:0}.facts.single{grid-template-columns:1fr}.facts div{min-width:0}.facts dt{color:var(--sa-muted);font-size:13px;margin-bottom:5px}.facts dd{margin:0;font-size:17px;line-height:1.4;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}.event-type{margin:0;padding:0 24px 16px;color:var(--sa-muted);font-size:14px}.photo{margin:0 16px 16px;min-height:200px;display:grid;place-items:center;background:color-mix(in srgb,var(--sa-fg) 5%,transparent);border-radius:14px;overflow:hidden}.photo img{display:block;max-width:100%;width:auto;max-height:calc(100dvh - 260px);height:auto;object-fit:contain}.photo-message{padding:32px 18px;text-align:center;color:var(--sa-muted)}.photo-message p{margin:0 0 14px}.captured{padding:0 24px 18px;margin:0;font-size:13px;color:var(--sa-muted)}.detail-notice{padding:0 24px 14px;margin:0;color:var(--sa-muted);font-size:14px}
.detections{margin:0 24px 20px;padding-top:14px;border-top:1px solid var(--sa-line)}.detections h3{font-size:15px;font-weight:600;margin:0 0 12px}.detection-group+.detection-group{margin-top:16px}.detection-line{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin:0 0 8px;font-size:15px;overflow-wrap:anywhere}.report-count{color:var(--sa-muted);font-size:13px;white-space:nowrap}.detection-source{margin:0 0 5px;font-size:13px;color:var(--sa-muted)}.detection-times{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:0}.detection-times dt{font-size:12px;color:var(--sa-muted);margin-bottom:3px}.detection-times dd{margin:0;font-size:13px;line-height:1.4;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
@media(max-width:600px){.backdrop{padding:12px}.dialog{max-height:calc(100dvh - 24px);border-radius:20px}.dialog-header{padding:16px 16px 12px;gap:10px}.dialog-heading h2{font-size:21px}.facts{padding:4px 16px 16px;gap:12px}.facts dd{font-size:15px}.photo{margin:0 10px 12px;min-height:180px}.photo img{max-height:calc(100dvh - 250px)}.captured,.event-type,.detail-notice{padding-left:16px;padding-right:16px}.detections{margin-left:16px;margin-right:16px}.detection-times{gap:12px}}
`;
const html = (tag, text, className) => { const e = document.createElement(tag); if (text != null) e.textContent = text; if (className) e.className = className; return e; };
function formatOptions(hass) {
  const locale = hass?.locale || {};
  const options = {};
  if (locale.time_zone === 'server' && hass?.config?.time_zone) options.timeZone = hass.config.time_zone;
  else if (locale.time_zone && !['local', 'server'].includes(locale.time_zone)) options.timeZone = locale.time_zone;
  if (locale.time_format === '12') options.hour12 = true;
  if (locale.time_format === '24') options.hour12 = false;
  return { language: locale.language || hass?.language || navigator.language, options };
}
export function formatActivityTime(value, hass, detailed = false) {
  const date = new Date(value); if (!Number.isFinite(date.getTime())) return 'Time not recorded';
  const { language, options } = formatOptions(hass);
  try { return new Intl.DateTimeFormat(language, { ...options, ...(detailed ? { dateStyle: 'medium', timeStyle: 'medium' } : { timeStyle: 'medium' }) }).format(date); }
  catch (_) { return new Intl.DateTimeFormat(undefined, detailed ? { dateStyle: 'medium', timeStyle: 'medium' } : { timeStyle: 'medium' }).format(date); }
}
function dateLabel(value, hass) {
  const { language, options } = formatOptions(hass);
  try { return new Intl.DateTimeFormat(language, { timeZone: options.timeZone, month: 'short', day: 'numeric' }).format(new Date(value)); }
  catch (_) { return new Date(value).toLocaleDateString(); }
}
export function activityDisplayTime(event) {
  const display = typeof event?.display_time === 'string' ? Date.parse(event.display_time) : NaN;
  return Number.isFinite(display) && display >= Date.parse(event.start) ? event.display_time : event.start;
}
export function validPhotoUrl(value, id, origin = location.origin) {
  if (typeof value !== 'string') return null;
  try { const url = new URL(value, origin); return url.origin === origin && url.pathname === `/api/security_activity/photo/${encodeURIComponent(id)}` && !url.search && !url.hash ? url.pathname : null; }
  catch (_) { return null; }
}
export class SecurityActivityCard extends HTMLElement {
  constructor() {
    super(); this.attachShadow({ mode: 'open' });
    const style = html('style', CSS); this._card = html('ha-card'); this.shadowRoot.append(style, this._card);
    this._hass = null; this._config = null; this._conn = null; this._events = []; this._retention = RETENTION; this._offset = 0;
    this._session = 0; this._pending = false; this._again = false; this._unsubscribe = null; this._refreshTimer = null; this._expiryTimer = null;
    this._selectedId = null; this._overlay = null; this._photoGeneration = 0; this._photoAbort = null; this._photoUrl = null; this._photoKey = null; this._photoError = false;
    this._loading = false; this._error = ''; this._notice = ''; this._scroll = 0; this._mounted = false;
    this._ready = () => this._begin(); this._disconnected = () => this._end(true);
    this._visibility = () => { if (document.hidden) this._clearPhoto(); else { this._expire(); void this._refresh(); this._renderDetail(); } };
  }
  setConfig(config) {
    if (!config || !['front_door', 'entrances'].includes(config.feed)) throw Error('Choose the front_door or entrances Activity feed.');
    const feedChanged = this._config?.feed !== config.feed;
    this._config = { feed: config.feed, title: String(config.title || (config.feed === 'front_door' ? 'Front Door activity' : 'Doors, gate & garage')), tablet: config.layout === 'tablet' || config.tablet === true, height: config.height ?? 440 };
    const height = Number.parseInt(this._config.height, 10); if (!Number.isFinite(height) || height < 220 || height > 1200) throw Error('Activity height must be between 220 and 1200 pixels.');
    this.style.setProperty('--sa-height', `${height}px`); this.toggleAttribute('tablet', this._config.tablet);
    if (feedChanged) { this._closeDetail(false); this._events = []; this._scroll = 0; if (this._conn?.connected && this._mounted) this._begin(); }
    this._render();
  }
  set hass(value) {
    const identity = value?.user?.id || null;
    if (this._identity !== undefined && identity !== this._identity) {
      this._detachConnection(); this._closeDetail(false); this._events = []; this._scroll = 0; this._error = ''; this._notice = '';
    }
    this._identity = identity; this._hass = value;
    const locale = JSON.stringify([value?.locale, value?.language, value?.config?.time_zone]);
    if (this._mounted) this._syncConnection();
    if (locale !== this._locale) { this._locale = locale; this._render(); this._renderDetail(); }
  }
  getCardSize() { return Math.ceil((Number.parseInt(this._config?.height, 10) || 440) / 50); }
  getGridOptions() { return { columns: 12, rows: 'auto', min_columns: 6 }; }
  connectedCallback() { this._mounted = true; document.addEventListener('visibilitychange', this._visibility); this._syncConnection(); this._render(); }
  disconnectedCallback() { this._mounted = false; document.removeEventListener('visibilitychange', this._visibility); this._detachConnection(); this._closeDetail(false); }
  _syncConnection() {
    const next = this._hass?.connection || null; if (next === this._conn) return;
    this._detachConnection(); this._conn = next;
    if (next) { next.addEventListener('ready', this._ready); next.addEventListener('disconnected', this._disconnected); if (next.connected) this._begin(); else this._end(true); }
  }
  _detachConnection() {
    if (this._conn) { this._conn.removeEventListener('ready', this._ready); this._conn.removeEventListener('disconnected', this._disconnected); }
    this._end(false); this._conn = null;
  }
  _end(offline) {
    this._session++; this._pending = false; this._again = false;
    clearInterval(this._refreshTimer); clearTimeout(this._expiryTimer); this._refreshTimer = null; this._expiryTimer = null;
    const unsub = this._unsubscribe; this._unsubscribe = null; if (unsub) Promise.resolve().then(unsub).catch(() => {});
    this._clearPhoto(); this._loading = false;
    if (offline) { this._error = 'Connection lost'; this._render(); this._renderDetail(); this._scheduleExpiry(); }
  }
  _begin() {
    this._end(false); if (!this._mounted || !this._config || !this._conn?.connected) return;
    const session = this._session; this._error = ''; this._loading = !this._events.length;
    try {
      Promise.resolve(this._conn.subscribeMessage(() => { if (session === this._session) void this._refresh(); }, { type: 'security_activity/subscribe', feed: this._config.feed }, { resubscribe: false })).then(unsub => {
        if (session !== this._session || !this._mounted) { Promise.resolve().then(unsub).catch(() => {}); return; }
        this._unsubscribe = unsub;
      }).catch(() => {}); // The visible-card refresh remains available if event subscription fails.
    } catch (_) {}
    this._refreshTimer = setInterval(() => { if (!document.hidden) void this._refresh(); }, 30000);
    this._scheduleExpiry(); void this._refresh();
  }
  _now() { return Date.now() + this._offset; }
  async _refresh() {
    if (!this._mounted || !this._config || !this._conn?.connected || document.hidden) return;
    if (this._pending) { this._again = true; return; }
    this._pending = true; const session = this._session; const feed = this._config.feed;
    if (!this._events.length) { this._loading = true; this._render(); }
    try {
      const result = await this._hass.callWS({ type: 'security_activity/list', feed });
      if (session !== this._session || !this._mounted) return;
      if (!result || !Array.isArray(result.events)) throw Error('Invalid Activity response');
      const serverTime = Date.parse(result.server_time); if (Number.isFinite(serverTime)) this._offset = serverTime - Date.now();
      this._retention = Number.isFinite(result.retention_seconds) && result.retention_seconds > 0 ? result.retention_seconds : RETENTION;
      const unique = new Map();
      for (const event of result.events) if (typeof event?.id === 'string' && event.id && event.feed === feed && Number.isFinite(Date.parse(event.start))) unique.set(event.id, event);
      this._events = [...unique.values()].filter(event => Date.parse(event.start) + this._retention * 1000 > this._now()).sort((a, b) => Date.parse(activityDisplayTime(b)) - Date.parse(activityDisplayTime(a)) || a.id.localeCompare(b.id));
      this._error = ''; this._notice = ''; this._loading = false;
      if (this._selectedId && !this._event()) { this._closeDetail(false); this._notice = 'This activity is no longer available.'; }
      this._render(); this._renderDetail(); this._scheduleExpiry();
    } catch (_) {
      if (session === this._session && this._mounted) { this._clearPhoto(); this._loading = false; this._error = 'Activity could not load'; this._render(); this._renderDetail(); }
    } finally {
      if (session === this._session) { this._pending = false; if (this._again) { this._again = false; void this._refresh(); } }
    }
  }
  _scheduleExpiry() {
    clearTimeout(this._expiryTimer); this._expiryTimer = null; if (!this._mounted || !this._events.length) return;
    const first = Math.min(...this._events.map(event => Date.parse(event.start) + this._retention * 1000));
    this._expiryTimer = setTimeout(() => this._expire(), Math.max(0, first - this._now()) + 10);
  }
  _expire() {
    const before = this._events.length;
    this._events = this._events.filter(event => Date.parse(event.start) + this._retention * 1000 > this._now());
    if (this._selectedId && !this._event()) { this._closeDetail(false); this._notice = 'This activity is no longer available.'; }
    if (before !== this._events.length) this._render(); this._scheduleExpiry();
  }
  _event() { return this._events.find(event => event.id === this._selectedId); }
  _name(event) { return String(event.name || event.area || 'Activity'); }
  _render() {
    if (!this._config) return;
    if (this._list) this._scroll = this._list.scrollTop;
    this._card.replaceChildren();
    const header = html('header'); header.append(html('h2', this._config.title), html('span', '12 hours', 'window'));
    const notice = html('p', this._error ? `${this._error}${this._events.length ? ' · Showing the last update' : ''}` : this._notice, 'notice'); notice.setAttribute('role', 'status');
    this._list = html('div', null, 'rows'); this._list.setAttribute('aria-label', this._config.title);
    this._card.append(header, notice, this._list);
    if (!this._events.length) {
      const empty = html('div', this._loading ? 'Loading activity…' : this._error ? 'Activity is unavailable' : 'No activity in the last 12 hours', 'empty');
      if (this._error && this._conn?.connected) { const retry = html('button', 'Try again', 'retry'); retry.addEventListener('click', () => void this._refresh()); empty.append(retry); }
      this._list.append(empty); return;
    }
    let day = null;
    for (const event of this._events) {
      const displayTime = activityDisplayTime(event);
      const label = dateLabel(displayTime, this._hass); if (label !== day) { day = label; this._list.append(html('div', label, 'day')); }
      const row = html('button', null, 'row'); row.type = 'button'; row.dataset.eventId = event.id;
      row.setAttribute('aria-label', `${this._name(event)}, ${formatActivityTime(displayTime, this._hass, true)}`);
      const time = html('time', formatActivityTime(displayTime, this._hass)); time.dateTime = displayTime;
      const text = html('span', null, 'row-text'); text.append(html('span', this._name(event), 'name'));
      if (event.area && event.area !== event.name) text.append(html('span', String(event.area), 'row-area'));
      row.append(text, time); row.addEventListener('click', () => this._openDetail(event.id, row)); this._list.append(row);
    }
    this._list.scrollTop = this._scroll;
  }
  _homeRoot() {
    let node = this;
    while (node) { if (node.localName === 'home-assistant') return node; const root = node.getRootNode?.(); node = node.parentNode || (root?.host !== node ? root?.host : null); }
    return null;
  }
  _openDetail(id, trigger) {
    this._expire(); if (!this._events.some(event => event.id === id)) return;
    this._closeDetail(false); this._selectedId = id; this._trigger = trigger; this._scroll = this._list?.scrollTop || 0;
    this._overlay = html('security-activity-detail'); const shadow = this._overlay.attachShadow({ mode: 'open' }); shadow.append(html('style', CSS));
    const computed = getComputedStyle(this);
    for (const name of ['--sa-fg', '--sa-muted', '--sa-bg', '--sa-line', '--primary-color']) { const value = computed.getPropertyValue(name); if (value.trim()) this._overlay.style.setProperty(name, value); }
    this._backdrop = html('div', null, 'backdrop'); this._dialog = html('section', null, 'dialog'); this._dialog.setAttribute('role', 'dialog'); this._dialog.setAttribute('aria-modal', 'true'); this._dialog.setAttribute('aria-label', this._name(this._event()));
    this._backdrop.append(this._dialog); shadow.append(this._backdrop);
    this._backdrop.addEventListener('click', event => { if (event.target === this._backdrop) this._closeDetail(); });
    this._backdrop.addEventListener('keydown', event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); this._closeDetail(); }
      if (event.key === 'Tab') { const focusable = [...this._dialog.querySelectorAll('button')].filter(e => !e.disabled); const first = focusable[0], last = focusable.at(-1); if (event.shiftKey && shadow.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && shadow.activeElement === last) { event.preventDefault(); first?.focus(); } }
    });
    const app = this._homeRoot(); (app?.shadowRoot || this.shadowRoot).append(this._overlay);
    this._renderDetail(); this._dialog.querySelector('.close')?.focus();
  }
  _closeDetail(restore = true) {
    const id = this._selectedId; this._clearPhoto(); this._selectedId = null; this._overlay?.remove(); this._overlay = null; this._dialog = null; this._backdrop = null;
    if (restore && this._mounted && !this._homeRoot()?.inert) { const row = [...(this._list?.querySelectorAll('.row') || [])].find(r => r.dataset.eventId === id); row?.focus({ preventScroll: true }); }
    this._trigger = null;
  }
  _renderDetail() {
    const event = this._event(); if (!event || !this._dialog) return;
    const expectedPhotoKey = event.photo?.status === 'ready' && validPhotoUrl(event.photo.url, event.id) ? `${event.id}|${event.photo.url}|${event.photo.captured_at || ''}` : null;
    if (this._photoKey && this._photoKey !== expectedPhotoKey) this._clearPhoto();
    const detailScroll = this._dialog.scrollTop;
    const focusedClose = this._overlay.shadowRoot.activeElement?.classList.contains('close');
    this._dialog.replaceChildren(); this._dialog.setAttribute('aria-label', this._name(event));
    const withPhoto = event.kind === 'motion' || ['ready', 'pending'].includes(event.photo?.status); this._dialog.classList.toggle('compact', !withPhoto);
    const header = html('div', null, 'dialog-header'); const heading = html('div', null, 'dialog-heading'); heading.append(html('h2', this._name(event)));
    if (event.area && event.area !== event.name) heading.append(html('p', String(event.area), 'area'));
    const close = html('button', null, 'close'); close.type = 'button'; close.setAttribute('aria-label', 'Close activity details'); close.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'; close.addEventListener('click', () => this._closeDetail()); header.append(heading, close); this._dialog.append(header);
    if (this._error) this._dialog.append(html('p', `${this._error} · Showing the last update`, 'detail-notice'));
    this._renderDoorbell(event);
    const instant = event.phase === 'instant'; const facts = html('dl', null, 'facts' + (instant ? ' single' : ''));
    const add = (label, value) => { const item = html('div'); item.append(html('dt', label), html('dd', value)); facts.append(item); };
    add(instant ? 'Occurred' : event.kind === 'motion' ? 'Detected' : event.kind === 'door' ? 'Opened' : 'Started', formatActivityTime(event.start, this._hass, true));
    if (!instant) {
      const knownEnd = event.end && Number.isFinite(Date.parse(event.end)) && Date.parse(event.end) >= Date.parse(event.start);
      const observed = event.details?.inactive_observed_at;
      const observedEnd = !knownEnd && event.phase === 'incomplete' && Number.isFinite(Date.parse(observed)) && Date.parse(observed) >= Date.parse(event.start);
      const label = observedEnd ? event.kind === 'motion' ? 'Clear by' : event.kind === 'door' ? 'Closed by' : 'Inactive by' : event.kind === 'motion' ? 'Cleared' : event.kind === 'door' ? 'Closed' : 'Ended';
      add(label, knownEnd ? formatActivityTime(event.end, this._hass, true) : observedEnd ? formatActivityTime(observed, this._hass, true) : event.phase === 'active' ? 'Ongoing' : 'End not recorded');
    }
    this._dialog.append(facts);
    if (event.details?.event_type) this._dialog.append(html('p', String(event.details.event_type), 'event-type'));
    if (withPhoto) { this._photoContainer = html('div', null, 'photo'); this._dialog.append(this._photoContainer); if (event.photo?.captured_at) this._dialog.append(html('p', `Captured ${formatActivityTime(event.photo.captured_at, this._hass, true)}`, 'captured')); this._paintPhoto(); void this._loadPhoto(); }
    else { this._photoContainer = null; this._clearPhoto(); }
    this._renderDetections(event); this._dialog.scrollTop = detailScroll;
    if (focusedClose) close.focus({ preventScroll: true });
  }
  _renderDoorbell(event) {
    const bell = event.details?.doorbell;
    if (!bell || !Number.isInteger(bell.count) || bell.count < 1 || !Number.isFinite(Date.parse(bell.first))) return;
    const repeated = bell.count > 1; const facts = html('dl', null, 'facts doorbell-facts' + (repeated ? '' : ' single')); facts.setAttribute('aria-label', 'Doorbell presses');
    const add = (label, value) => { const item = html('div'); item.append(html('dt', label), html('dd', formatActivityTime(value, this._hass, true))); facts.append(item); };
    add(repeated ? 'First press' : 'Doorbell pressed', bell.first);
    if (repeated) add(`Last press · ${bell.count.toLocaleString(formatOptions(this._hass).language)} presses`, bell.last);
    this._dialog.append(facts);
  }
  _renderDetections(event) {
    if (event.kind !== 'motion' || !Array.isArray(event.details?.detections)) return;
    const groups = event.details.detections.filter(group => group && Number.isInteger(group.count) && group.count > 0);
    if (!groups.length) return;
    const section = html('section', null, 'detections'); section.setAttribute('aria-label', 'Object detections'); section.append(html('h3', 'Object detections'));
    for (const group of groups) {
      const item = html('div', null, 'detection-group');
      if (groups.length > 1) {
        const name = this._hass?.states?.[group.entity_id]?.attributes?.friendly_name;
        if (name) item.append(html('p', String(name), 'detection-source'));
      }
      const types = Array.isArray(group.types) ? group.types.filter(type => typeof type === 'string' && type.trim()).map(type => { const text = type.replace(/[_-]/g, ' '); return text.charAt(0).toUpperCase() + text.slice(1); }) : [];
      const line = html('p', null, 'detection-line'); line.append(html('span', types.length ? types.join(' · ') : 'Detection reports'), html('span', `${group.count.toLocaleString(formatOptions(this._hass).language)} ${group.count === 1 ? 'report' : 'reports'}`, 'report-count')); item.append(line);
      const times = html('dl', null, 'detection-times');
      for (const [label, value] of [['First', group.first], ['Last', group.last]]) { if (!Number.isFinite(Date.parse(value))) continue; const pair = html('div'); pair.append(html('dt', label), html('dd', formatActivityTime(value, this._hass, true))); times.append(pair); }
      if (times.childElementCount) item.append(times); section.append(item);
    }
    this._dialog.append(section);
  }
  _clearPhoto() {
    this._photoGeneration++; this._photoAbort?.abort(); this._photoAbort = null;
    if (this._photoUrl) URL.revokeObjectURL(this._photoUrl);
    this._photoUrl = null; this._photoKey = null; this._photoError = false;
    if (this._photoContainer) this._photoContainer.replaceChildren();
  }
  _paintPhoto() {
    const event = this._event(); if (!this._photoContainer || !event) return;
    this._photoContainer.replaceChildren();
    if (this._photoUrl) { const image = html('img'); image.src = this._photoUrl; image.alt = `${this._name(event)} at ${formatActivityTime(event.photo?.captured_at || event.start, this._hass, true)}`; image.addEventListener('error', () => { if (image.src === this._photoUrl) { this._clearPhoto(); this._photoError = true; this._paintPhoto(); } }); this._photoContainer.append(image); return; }
    const status = event.photo?.status; const message = this._photoError ? 'Photo could not load' : this._error ? 'Photo temporarily unavailable' : !this._conn?.connected ? 'Photo unavailable while disconnected' : status === 'ready' ? 'Loading photo…' : status === 'pending' ? 'Photo being prepared…' : status === 'unavailable' ? 'Photo unavailable' : 'No photo recorded';
    const box = html('div', null, 'photo-message'); box.append(html('p', message));
    if (this._photoError && this._conn?.connected) { const retry = html('button', 'Try again', 'retry'); retry.type = 'button'; retry.addEventListener('click', () => { this._clearPhoto(); this._paintPhoto(); void this._loadPhoto(); }); box.append(retry); }
    this._photoContainer.append(box);
  }
  async _loadPhoto() {
    const event = this._event(); if (!event || event.photo?.status !== 'ready' || this._error || !this._conn?.connected || document.hidden || !this._overlay) return;
    const key = `${event.id}|${event.photo.url}|${event.photo.captured_at || ''}`; if (key === this._photoKey) return;
    this._clearPhoto(); this._photoKey = key; const generation = this._photoGeneration; const session = this._session; const id = event.id;
    const url = validPhotoUrl(event.photo.url, id); if (!url) { this._photoError = true; this._paintPhoto(); return; }
    this._photoAbort = new AbortController(); this._paintPhoto();
    try {
      const response = await this._hass.fetchWithAuth(url, { cache: 'no-store', signal: this._photoAbort.signal });
      if (!response.ok) throw Error('Photo request failed');
      const blob = await response.blob(); if (!['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(blob.type.split(';')[0])) throw Error('Invalid image');
      if (generation !== this._photoGeneration || session !== this._session || this._selectedId !== id || !this._overlay || !this._mounted) return;
      if (Date.parse(event.start) + this._retention * 1000 <= this._now()) { this._expire(); return; }
      this._photoUrl = URL.createObjectURL(blob); this._photoAbort = null; this._paintPhoto();
    } catch (_) {
      if (generation === this._photoGeneration && session === this._session && this._selectedId === id && this._overlay) { this._photoAbort = null; this._photoError = true; this._paintPhoto(); }
    }
  }
}
if (!customElements.get(TAG)) customElements.define(TAG, SecurityActivityCard);
