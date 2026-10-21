/** Living tablet alarm keypad. No configured PIN or authentication token belongs here.
 * Loaded by frontend.extra_module_url, rather than a single Lovelace view.
 * This is a kiosk UI guard; HA permissions and Fully escape controls remain separate.
 */
export const ALARM = 'alarm_control_panel.house_alarm';
export const COUNTDOWN = 'timer.house_alarm_countdown';
export const TABLET_ID = '69e040b7-b03fba6f';
// Filled only with the independently verified dedicated HA account ID, if supplied.
export const TABLET_USER_ID = 'dc67919f472e44a4a621ed622de4026e';
const MARKER = 'living-alarm-lock-device';
const TIMEOUT = 6000;

export function identifyTablet(host, storage) {
  try {
    if (typeof host.fully?.getDeviceId === 'function') {
      const id = String(host.fully.getDeviceId()).toLowerCase();
      if (id) {
        if (id === TABLET_ID) {
          try { storage?.setItem(MARKER, id); } catch (_) { /* Native identity still applies. */ }
          return true;
        }
        return false;
      }
    }
  } catch (_) { /* Retain the known tablet boundary if its native bridge is unavailable. */ }
  try { return storage?.getItem(MARKER) === TABLET_ID; } catch (_) { return false; }
}

function deadline(promise, ms = TIMEOUT) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('timeout')), ms); }),
  ]).finally(() => clearTimeout(timer));
}

// Match Home Assistant's structured Manual Alarm rejection, never arbitrary text.
export function isRejectedPin(error) {
  return error?.code === 'service_validation_error'
    && error?.translation_domain === 'manual'
    && error?.translation_key === 'invalid_code';
}

export class AlarmLockController {
  constructor(render) {
    this.render = render;
    this.connection = null;
    this.state = null;
    this.trusted = false;
    this.busy = false;
    this.error = '';
    this.generation = 0;
    this.countdown = null;
    this.unsub = null;
    this.syncing = false;
    this.pinging = false;
    this.nextRetry = 0;
    this.onReady = () => { this.invalidate(); void this.synchronize(); };
    this.onDisconnected = () => this.invalidate();
    this.publish();
  }
  get locked() { return !(this.trusted && this.connection?.connected === true && this.state?.state === 'disarmed'); }
  publish() {
    this.render({ locked: this.locked, state: this.state?.state || 'unknown', attributes: this.state?.attributes || {},
      pinReady: this.state?.attributes?.code_format === 'number',
      connected: this.trusted && this.connection?.connected === true, countdown: this.countdown, busy: this.busy, error: this.error });
  }
  invalidate() {
    this.generation += 1;
    this.trusted = false;
    this.busy = false;
    this.syncing = false;
    this.pinging = false;
    this.state = null;
    this.countdown = null;
    this.error = '';
    const unsub = this.unsub; this.unsub = null;
    if (unsub) Promise.resolve(unsub()).catch(() => {});
    this.publish();
  }
  connect(connection) {
    if (connection === this.connection) return;
    if (this.connection) {
      this.connection.removeEventListener('ready', this.onReady);
      this.connection.removeEventListener('disconnected', this.onDisconnected);
    }
    this.invalidate();
    this.connection = connection || null;
    if (this.connection) {
      this.connection.addEventListener('ready', this.onReady);
      this.connection.addEventListener('disconnected', this.onDisconnected);
      if (this.connection.connected) void this.synchronize();
    }
  }
  current(generation) { return generation === this.generation && this.connection?.connected === true; }
  accept(state) {
    const incoming = state?.entity_id === ALARM ? state : null;
    // A concurrent re-arm event must not be undone by an older disarm snapshot.
    if (!incoming || !this.state || !incoming.last_updated || !this.state.last_updated || incoming.last_updated >= this.state.last_updated) this.state = incoming;
    this.trusted = true;
    if (this.state?.state === 'disarmed') { this.busy = false; this.error = ''; }
    this.publish();
  }
  async synchronize() {
    if (this.syncing || !this.connection?.connected) return;
    this.syncing = true;
    const generation = this.generation;
    const connection = this.connection;
    let newestEvent = null;
    let eventReceived = false;
    let newestTimerEvent = null;
    let timerEventReceived = false;
    let ready = false;
    try {
      const pendingSubscription = connection.subscribeMessage(event => {
        if (!this.current(generation)) return;
        if (event?.data?.entity_id === COUNTDOWN) {
          newestTimerEvent = event.data.new_state; timerEventReceived = true;
          if (ready) { this.countdown = newestTimerEvent; this.publish(); }
        }
        if (event?.data?.entity_id !== ALARM) return;
        newestEvent = event.data.new_state;
        eventReceived = true;
        if (ready) this.accept(newestEvent);
      }, { type: 'subscribe_events', event_type: 'state_changed' }, { resubscribe: false });
      pendingSubscription.then(unsub => { if (!this.current(generation)) Promise.resolve(unsub()).catch(() => {}); }).catch(() => {});
      const unsub = await deadline(pendingSubscription);
      if (!this.current(generation)) { Promise.resolve(unsub()).catch(() => {}); return; }
      this.unsub = unsub;
      const states = await deadline(connection.sendMessagePromise({ type: 'get_states' }));
      if (!this.current(generation)) return;
      const snapshot = states.find(item => item.entity_id === ALARM) || null;
      // Events can arrive while the snapshot request is in flight. Never overwrite a
      // newer event with an older cached-looking snapshot, especially an armed state.
      const eventWins = eventReceived && (!newestEvent || !snapshot || newestEvent.last_updated >= snapshot.last_updated);
      const timerSnapshot = states.find(item => item.entity_id === COUNTDOWN) || null;
      this.countdown = timerEventReceived && (!newestTimerEvent || !timerSnapshot || newestTimerEvent.last_updated >= timerSnapshot.last_updated) ? newestTimerEvent : timerSnapshot;
      ready = true;
      this.accept(eventWins ? newestEvent : snapshot);
    } catch (_) {
      if (generation === this.generation) {
        this.invalidate();
        this.nextRetry = Date.now() + 3000;
      }
    } finally {
      if (generation === this.generation) this.syncing = false;
    }
  }
  tick() {
    if (!this.connection?.connected) {
      if (this.trusted || this.syncing) this.invalidate();
      return;
    }
    if (!this.trusted && !this.syncing && Date.now() >= this.nextRetry) void this.synchronize();
  }
  async heartbeat() {
    if (!this.trusted || this.pinging || !this.connection?.connected) return;
    const generation = this.generation;
    this.pinging = true;
    try { await deadline(this.connection.sendMessagePromise({ type: 'ping' }), 2500); }
    catch (_) {
      if (generation === this.generation) { this.invalidate(); this.nextRetry = Date.now() + 3000; }
    } finally { if (generation === this.generation) this.pinging = false; }
  }
  async submit(code) {
    if (!/^\d{6}$/.test(code) || !this.locked || !this.trusted || !this.connection?.connected || ['unknown', 'unavailable'].includes(this.state?.state || 'unknown') || this.busy) return false;
    if (this.state?.attributes?.code_format !== 'number') {
      this.error = 'PIN setup required'; this.publish(); return false;
    }
    const generation = this.generation;
    const connection = this.connection;
    this.busy = true; this.error = ''; this.publish();
    const message = { type: 'call_service', domain: 'alarm_control_panel', service: 'alarm_disarm',
      target: { entity_id: ALARM }, service_data: { code } };
    code = '';
    let awaitingService = true;
    try {
      // No optimistic unlock: service success alone is not proof of a correct code.
      const pending = connection.sendMessagePromise(message);
      await deadline(pending);
      awaitingService = false;
      if (!this.current(generation)) return false;
      const states = await deadline(connection.sendMessagePromise({ type: 'get_states' }));
      if (!this.current(generation)) return false;
      this.accept(states.find(item => item.entity_id === ALARM) || null);
      if (this.locked) this.error = 'Code not accepted';
      return !this.locked;
    } catch (error) {
      if (this.current(generation) && this.locked) {
        this.error = awaitingService && isRejectedPin(error)
          ? 'Code not accepted'
          : 'Unable to verify. Try again.';
      }
      return false;
    } finally {
      // Do not retain entered digits in the UI/controller after submission.
      message.service_data.code = '';
      if (generation === this.generation) { this.busy = false; this.publish(); }
    }
  }
}

const CSS = `
:host{display:block;font-family:Roboto,Arial,sans-serif;color:#1B2432}
.surface{box-sizing:border-box;position:fixed;inset:0;margin:0;padding:32px;width:100vw;max-width:none;height:100dvh;max-height:none;border:0;background:#EDE5D1;color:#1B2432;overflow:hidden;outline:0}
dialog[open]{display:grid;place-items:center}dialog::backdrop{background:#EDE5D1}
.panel{box-sizing:border-box;display:grid;grid-template-columns:minmax(270px,.7fr) minmax(0,1.3fr);grid-template-areas:"status keypad";column-gap:40px;align-items:center;width:min(1176px,100%);height:calc(100dvh - 64px);padding:28px 36px;border:5px solid #1B2432;border-radius:30px;background:#EDE5D1}
.status{grid-area:status;display:flex;flex-direction:column;align-items:center;text-align:center;gap:20px;min-width:0}.shield{width:160px;height:180px;color:#E3170A}.shield svg{width:100%;height:100%}.shield.entry-countdown{animation:entry-countdown-pulse 1.2s ease-in-out infinite}@keyframes entry-countdown-pulse{0%,100%{opacity:1}50%{opacity:.15}}@media(prefers-reduced-motion:reduce){.shield.entry-countdown{animation:none}}
h1{font-size:46px;line-height:1.1;font-weight:550;margin:0}.mode{font-size:23px;min-height:27px;color:#1B2432C0}.hint{font-size:19px;color:#1B2432C0;margin:12px 0 0}
.countdown{font-size:64px;font-variant-numeric:tabular-nums;line-height:1;color:#1B2432}.countdown[hidden]{display:none}
.keypad{grid-area:keypad;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;min-width:0}.digits{grid-column:1/-1;display:flex;justify-content:center;gap:15px;padding:0 0 8px}.mask-slot{box-sizing:border-box;display:grid;place-items:center;width:76px;height:88px;border:2px solid #1B243230;border-radius:18px;color:#1B24324D;font-size:34px;line-height:1;user-select:none}.mask-dot{box-sizing:border-box;display:block;width:26px;height:26px;border:2px solid #1B24324D;border-radius:50%;background:transparent}.mask-slot.filled .mask-dot{background:#1B2432;border-color:#1B2432}.mask-slot.filled{border-color:#1B243280}
button{font:inherit;touch-action:manipulation;-webkit-tap-highlight-color:transparent;box-sizing:border-box;min-width:0;min-height:108px;border:2px solid #1B2432C0;border-radius:18px;background:transparent;color:#1B2432;font-size:52px;font-weight:550;cursor:pointer;user-select:none}button:active{background:#1B24321A}button:focus-visible{outline:4px solid #5296A5;outline-offset:3px}button:disabled{opacity:.32;cursor:default}.minor{font-size:20px}.backspace{display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1;gap:4px}.backspace small{font-size:16px;font-weight:500}.digits.jiggle{animation:pin-jiggle 400ms ease-in-out}.digits.jiggle .mask-slot{border-color:#E3170A}.digits.jiggle .mask-dot{background:#E3170A;border-color:#E3170A}@keyframes pin-jiggle{0%,100%{transform:translateX(0)}20%{transform:translateX(-14px)}40%{transform:translateX(12px)}60%{transform:translateX(-9px)}80%{transform:translateX(6px)}}.message{grid-column:1/-1;box-sizing:border-box;text-align:center;height:26px;min-height:26px;max-height:26px;line-height:26px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;font-size:17px;color:#E3170A;margin:0}
.surface.inline{position:relative;inset:auto;padding:0;width:100%;height:550px;display:block;background:transparent;overflow:hidden}.inline[hidden]{display:none}.inline .panel{width:100%;height:550px;grid-template-columns:minmax(230px,.8fr) minmax(0,1.2fr);column-gap:24px;row-gap:12px;padding:18px 20px;border:0;border-radius:20px}.inline .status{gap:16px}.inline .shield{width:105px;height:120px}.inline h1{font-size:33px}.inline .mode{font-size:20px}.inline .hint{font-size:17px;margin-top:8px}.inline .countdown{font-size:50px}.inline .keypad{gap:9px}.inline .digits{gap:10px;padding-bottom:7px}.inline .mask-slot{width:60px;height:72px;border-radius:14px;font-size:29px}.inline .mask-dot{width:22px;height:22px}.inline button{min-height:82px;font-size:44px}.inline .minor{font-size:18px}
@media(min-width:701px) and (max-height:740px){.surface:not(.inline){padding:20px}.surface:not(.inline) .panel{height:calc(100dvh - 40px);padding:20px 34px;row-gap:12px}.surface:not(.inline) .keypad{gap:8px}.surface:not(.inline) button{min-height:78px;font-size:42px}.surface:not(.inline) .digits{padding-bottom:4px}.surface:not(.inline) .mask-slot{height:68px;width:65px}.surface:not(.inline) .mask-dot{width:24px;height:24px}.surface:not(.inline) .shield{width:124px;height:142px}.surface:not(.inline) h1{font-size:38px}}
@media(max-width:700px){.surface:not(.inline){padding:14px;overflow:auto}.surface:not(.inline) .panel{height:auto;min-height:calc(100dvh - 28px);grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto;grid-template-areas:"status" "keypad";gap:18px;padding:20px;border-width:3px}.surface:not(.inline) .status{gap:6px}.surface:not(.inline) .shield{width:50px;height:56px}.surface:not(.inline) h1{font-size:28px}.surface:not(.inline) .mode{font-size:17px}.surface:not(.inline) .hint{display:none}.surface:not(.inline) .countdown{font-size:34px}.surface:not(.inline) .keypad{gap:8px}.surface:not(.inline) .digits{gap:8px;padding:0}.surface:not(.inline) .mask-slot{width:42px;height:56px;border-radius:10px;font-size:24px}.surface:not(.inline) .mask-dot{width:20px;height:20px}.surface:not(.inline) button{min-height:62px;font-size:34px}.surface:not(.inline) .minor{font-size:16px}.surface:not(.inline) .message{height:44px;min-height:44px;max-height:44px;line-height:22px;white-space:normal;overflow:hidden}}
`;

/** One view/controller implementation for both the tablet guard and its inline card. */
export function createKeypadView(shadow, { inline = false, onModel = () => {} } = {}) {
  const doc = shadow.ownerDocument;
  const style = doc.createElement('style'); style.textContent = CSS;
  const surface = doc.createElement(inline ? 'section' : 'dialog');
  surface.className = 'surface' + (inline ? ' inline' : '');
  surface.setAttribute('aria-label', 'Disarm to unlock home controls');
  if (inline) surface.tabIndex = 0;
  surface.innerHTML = `<section class="panel"><div class="status"><div class="shield" aria-hidden="true"><svg viewBox="0 0 120 140" fill="none"><path d="M60 7 108 25v38c0 32-20 52-48 69C32 115 12 95 12 63V25L60 7Z" stroke="currentColor" stroke-width="7" stroke-linejoin="round"/><rect x="39" y="59" width="42" height="34" rx="7" fill="currentColor"/><path d="M46 58V47a14 14 0 0 1 28 0v11" stroke="currentColor" stroke-width="7"/><circle cx="60" cy="73" r="4" fill="#EDE5D1"/><path d="M60 75v7" stroke="#EDE5D1" stroke-width="4"/></svg></div><h1 id="heading">Connecting</h1><div class="mode" id="mode">Checking protection</div><div class="countdown" aria-label="Alarm countdown" hidden></div><p class="hint">Enter 6-digit code to disarm</p></div><div class="keypad"><div class="digits" role="img" aria-label="No digits entered">${'<span class="mask-slot" aria-hidden="true"><span class="mask-dot"></span></span>'.repeat(6)}</div><p class="message" role="status" aria-live="polite"></p>${[1,2,3,4,5,6,7,8,9].map(n => `<button type="button" data-key="${n}" aria-label="${n}">${n}</button>`).join('')}<button type="button" data-key="clear" class="minor">Clear</button><button type="button" data-key="0" aria-label="0">0</button><button type="button" data-key="back" aria-label="Backspace" class="backspace"><span aria-hidden="true">⌫</span><small>Backspace</small></button></div></section>`;
  shadow.append(style, surface);
  let code = '';
  let visibleCount = 0;
  let phase = 'entry';
  let attempt = 0;
  let shakeTimer = null;
  let feedbackTimer = null;
  let feedbackGeneration = 0;
  let incorrectFeedback = false;
  let dismissedError = '';
  let model = { locked: true, connected: false, busy: false };
  let controller;
  const digits = shadow.querySelector('.digits');
  const slots = [...shadow.querySelectorAll('.mask-slot')];
  const buttons = [...shadow.querySelectorAll('button')];
  const status = shadow.querySelector('.message');
  const heading = shadow.querySelector('#heading');
  const mode = shadow.querySelector('#mode');
  const shield = shadow.querySelector('.shield');
  const countdown = shadow.querySelector('.countdown');
  function paintCountdown() {
    const finishes = Date.parse(model.countdown?.attributes?.finishes_at || '');
    const active = model.connected && ['arming', 'pending'].includes(model.state) && model.countdown?.state === 'active' && Number.isFinite(finishes);
    countdown.hidden = !active;
    if (active) {
      const seconds = Math.max(0, Math.ceil((finishes - Date.now()) / 1000));
      countdown.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    }
  }
  function clearIncorrectFeedback() {
    feedbackGeneration += 1; clearTimeout(feedbackTimer); feedbackTimer = null;
    incorrectFeedback = false;
  }
  function showIncorrectFeedback() {
    clearIncorrectFeedback();
    incorrectFeedback = true;
    dismissedError = model.error;
    const generation = feedbackGeneration;
    feedbackTimer = setTimeout(() => {
      if (generation !== feedbackGeneration) return;
      feedbackTimer = null; incorrectFeedback = false; paintStatus();
    }, 3000);
  }
  function clearCode(options = {}) {
    attempt += 1; clearTimeout(shakeTimer); shakeTimer = null;
    if (options?.preserveIncorrectFeedback !== true) clearIncorrectFeedback();
    code = ''; visibleCount = 0; phase = 'entry';
    digits.classList.remove('jiggle'); paintDigits(); paintStatus();
  }
  function paintStatus() {
    status.textContent = phase === 'pending' || model.busy ? 'Checking code…' : incorrectFeedback ? 'Incorrect code' : !model.connected ? 'Waiting for Home Assistant' : !model.pinReady ? 'PIN setup required' : model.error && model.error !== dismissedError ? model.error : '\u00a0';
    const errorVisible = incorrectFeedback || (phase !== 'pending' && !model.busy && ((model.connected && !model.pinReady) || (model.error && model.error !== dismissedError)));
    status.style.color = errorVisible ? '#E3170A' : '#1B2432C0';
  }
  function paintDigits() {
    slots.forEach((slot, i) => { const filled = i < visibleCount; slot.classList.toggle('filled', filled); });
    digits.setAttribute('aria-label', `${visibleCount} of 6 digits entered`);
    buttons.forEach(button => { button.disabled = !model.locked || !model.connected || !model.pinReady || ['unknown', 'unavailable'].includes(model.state) || model.busy || phase !== 'entry'; });
  }
  function render(next) {
    const newlyLocked = next.locked && !model.locked;
    const connectionLost = !next.connected && model.connected;
    model = next;
    if (!model.locked || newlyLocked || connectionLost) clearCode();
    const pending = ['arming', 'pending'].includes(model.state);
    const available = !['unknown', 'unavailable'].includes(model.state);
    heading.textContent = !model.connected ? 'Connecting' : !available ? 'Unavailable' : model.state === 'triggered' ? 'Alarm activated' : model.state === 'pending' ? 'Enter code' : pending ? 'Arming' : 'Protected';
    mode.textContent = !model.connected ? 'Controls locked' : model.state === 'armed_home' || model.attributes?.next_state === 'armed_home' ? 'Axl is home' : model.state === 'armed_away' || model.attributes?.next_state === 'armed_away' ? 'Away' : model.state === 'pending' ? 'Enter code to disarm' : '';
    shield.style.color = !model.connected ? '#5296A5' : model.state === 'arming' ? '#E57A44' : '#E3170A';
    shield.classList.toggle('entry-countdown', model.connected && model.state === 'pending');
    paintStatus();
    if (inline) surface.hidden = !model.locked;
    paintDigits(); paintCountdown(); onModel(model, surface);
  }
  async function submitCompleteCode() {
    if (code.length !== 6 || phase !== 'entry' || model.busy) return;
    const token = ++attempt;
    const entered = code;
    code = ''; phase = 'pending'; dismissedError = '';
    paintDigits(); paintStatus();
    const accepted = await controller.submit(entered);
    if (token !== attempt || !model.locked) return;
    if (accepted) return; // Only the authoritative state can actually hide the view.
    if (!model.connected) { clearCode(); return; }
    if (model.error === 'Code not accepted') {
      phase = 'incorrect'; showIncorrectFeedback(); digits.classList.add('jiggle'); paintDigits(); paintStatus();
      shakeTimer = setTimeout(() => {
        if (token !== attempt) return;
        clearCode({ preserveIncorrectFeedback: true });
      }, 400);
    } else {
      // A transport/configuration failure is not evidence of an incorrect PIN.
      clearCode();
    }
  }
  function key(value) {
    if (!model.locked || model.busy || phase !== 'entry' || !model.connected || !model.pinReady) return;
    if (/^\d$/.test(value) && code.length < 6) code += value;
    else if (value === 'clear') code = '';
    else if (value === 'back') code = code.slice(0, -1);
    else return;
    clearIncorrectFeedback();
    visibleCount = code.length;
    dismissedError = model.error;
    paintDigits(); paintStatus();
    if (code.length === 6) void submitCompleteCode();
  }
  function handleKey(event) {
    if (!model.locked || event.key === 'Tab') return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (/^\d$/.test(event.key)) key(event.key);
    else if (event.key === 'Backspace') key('back');
    else if (event.key === 'Delete' || event.key === 'Escape') key('clear');
  }
  surface.addEventListener('click', event => { const button = event.target.closest('button'); if (button && !button.disabled) key(button.dataset.key); });
  if (inline) surface.addEventListener('keydown', handleKey);
  controller = new AlarmLockController(render);
  return { controller, surface, clearCode, paintCountdown, handleKey, get locked() { return model.locked; } };
}

export function installGuard(host = window, doc = document) {
  let storage;
  try { storage = host.localStorage; } catch (_) { /* Identity can still use Fully. */ }
  const dedicatedUser = Boolean(TABLET_USER_ID && doc.querySelector('home-assistant')?.hass?.user?.id === TABLET_USER_ID);
  if ((!identifyTablet(host, storage) && !dedicatedUser) || doc.querySelector('living-alarm-lock')) return null;
  if (dedicatedUser) { try { storage?.setItem(MARKER, TABLET_ID); } catch (_) { /* HA identity remains authoritative for scope. */ } }
  const root = doc.createElement('living-alarm-lock');
  const shadow = root.attachShadow({ mode: 'closed' });
  const originalInert = new Map();
  let locked = true;
  let surface;
  function enforceBoundary() {
    if (!root.isConnected) (doc.body || doc.documentElement).append(root);
    const apps = [...doc.querySelectorAll('home-assistant, home-assistant-main')];
    apps.forEach(app => {
      if (locked) { if (!originalInert.has(app)) originalInert.set(app, app.inert); app.inert = true; }
      else if (originalInert.has(app)) { app.inert = originalInert.get(app); originalInert.delete(app); }
    });
    if (locked && surface && !surface.open) surface.showModal();
    if (!locked && surface?.open) surface.close();
  }
  enforceBoundary();
  const view = createKeypadView(shadow, { onModel: (model, dialog) => { locked = model.locked; surface = dialog; enforceBoundary(); } });
  surface.addEventListener('cancel', event => event.preventDefault());
  surface.addEventListener('close', () => { if (locked) enforceBoundary(); });
  doc.addEventListener('keydown', view.handleKey, true);
  doc.addEventListener('contextmenu', event => { if (locked) { event.preventDefault(); event.stopImmediatePropagation(); } }, true);
  const observer = new MutationObserver(enforceBoundary);
  observer.observe(doc.body || doc.documentElement, { childList: true });
  function poll() {
    const hass = doc.querySelector('home-assistant')?.hass;
    view.controller.connect(host.navigator?.onLine === false || doc.hidden ? null : hass?.connection);
    view.controller.tick(); view.paintCountdown(); enforceBoundary();
  }
  host.addEventListener('offline', () => { view.clearCode(); view.controller.invalidate(); });
  host.addEventListener('online', () => { view.clearCode(); view.controller.invalidate(); poll(); });
  host.addEventListener('popstate', view.clearCode);
  host.addEventListener('location-changed', view.clearCode);
  host.addEventListener('pagehide', () => { view.clearCode(); view.controller.invalidate(); });
  doc.addEventListener('visibilitychange', () => { view.clearCode(); view.controller.invalidate(); if (!doc.hidden) poll(); });
  host.setInterval(poll, 250);
  host.setInterval(() => { void view.controller.heartbeat(); }, 3000);
  poll();
  return { controller: view.controller, element: root };
}

export function registerInlineCard(registry = customElements) {
  if (registry.get('living-alarm-keypad')) return;
  class LivingAlarmKeypad extends HTMLElement {
    constructor() {
      super();
      this._view = createKeypadView(this.attachShadow({ mode: 'closed' }), { inline: true });
      this._hass = null;
      this._pollTimer = null;
      this._heartbeatTimer = null;
    }
    setConfig(config) {
      if (config?.entity && config.entity !== ALARM) throw new Error('This keypad controls the house alarm only.');
    }
    set hass(value) { this._hass = value; if (this.isConnected) this._poll(); }
    getCardSize() { return 10; }
    connectedCallback() {
      this._pollTimer = setInterval(() => this._poll(), 250);
      this._heartbeatTimer = setInterval(() => { void this._view.controller.heartbeat(); }, 3000);
      this._poll();
    }
    disconnectedCallback() {
      clearInterval(this._pollTimer); clearInterval(this._heartbeatTimer);
      this._pollTimer = null; this._heartbeatTimer = null;
      this._view.clearCode(); this._view.controller.connect(null);
    }
    _poll() {
      this._view.controller.connect(navigator.onLine === false ? null : this._hass?.connection);
      this._view.controller.tick(); this._view.paintCountdown();
    }
  }
  registry.define('living-alarm-keypad', LivingAlarmKeypad);
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  registerInlineCard();
  // Native or enrolled device identity protects initial load independently of route.
  // The dedicated HA user also identifies the first load without the Fully bridge.
  const boot = () => { if (installGuard() || document.querySelector('living-alarm-lock')) window.clearInterval(timer); };
  const timer = window.setInterval(boot, 250);
  boot();
}
