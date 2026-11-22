// livepdf simulator: runs a PDF's form JavaScript in Node with a mock of the Acrobat JS API subset that Chrome's
// PDF viewer (PDFium) implements, and replays mouse and keyboard input in the event order Chrome uses.
// Protocol: one JSON command per line on stdin, one JSON reply per line on stdout.
import vm from 'node:vm';
import readline from 'node:readline';

let S = null;      // simulator state
let ctx = null;    // vm context = the document's global scope

const DISPLAY = { visible: 0, hidden: 1, noPrint: 2, noView: 3 };
const COLOR = {
  transparent: ['T'], black: ['G', 0], white: ['G', 1], red: ['RGB', 1, 0, 0], green: ['RGB', 0, 1, 0],
  blue: ['RGB', 0, 0, 1], cyan: ['CMYK', 1, 0, 0, 0], magenta: ['CMYK', 0, 1, 0, 0], yellow: ['CMYK', 0, 0, 1, 0],
  dkGray: ['G', 0.25], gray: ['G', 0.5], ltGray: ['G', 0.75],
};
const KNOWN_PROPS = new Set(['name', 'type', 'value', 'valueAsString', 'display', 'hidden', 'rect', 'readonly',
  'required', 'textColor', 'fgColor', 'fillColor', 'bgColor', 'strokeColor', 'borderColor', 'textSize', 'textFont',
  'alignment', 'charLimit', 'page', 'doc', 'exportValues', 'lineWidth', 'borderStyle', 'userName', 'defaultValue',
  'setFocus', 'buttonGetCaption', 'buttonSetCaption', 'isBoxChecked', 'checkThisBox', 'getArray', 'setAction',
  'toString', 'valueOf', 'constructor', 'then']);

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function warn(msg) { if (!S.warnSeen.has(msg)) { S.warnSeen.add(msg); S.warnings.push(msg); } }

const visible = r => r.display === 0 || r.display === 2;
const editable = r => r.type === 'text' && !(r.flags & 1);
const center = r => [(r.rect[0] + r.rect[2]) / 2, (r.rect[1] + r.rect[3]) / 2];

function fieldObject(rec) {
  if (rec.obj) return rec.obj;
  const target = {
    get name() { return rec.name; },
    get type() { return rec.type; },
    get value() {
      const v = rec.value;
      if (rec.type === 'text' && S.opts.numericValues && typeof v === 'string' && v.trim() !== '' && isFinite(Number(v)))
        return Number(v);   // PDFium and Acrobat return numeric-looking text as a number: "0." -> 0
      return v;
    },
    set value(v) {
      if (rec.type === 'checkbox' || rec.type === 'radiobutton') rec.value = String(v);
      else rec.value = v === null || v === undefined ? '' : String(v);
      if (S.focus === rec) S.buffer = null;
    },
    get valueAsString() { return String(rec.value); },
    get display() { return rec.display; },
    set display(d) {
      if (![0, 1, 2, 3].includes(d)) warn(`${rec.name}.display = ${d}: use display.visible/hidden/noPrint/noView`);
      rec.display = d;
    },
    get hidden() { return rec.display === 1; },
    set hidden(b) { rec.display = b ? 1 : 0; },
    // Acrobat's order: [left, top, right, bottom]. Chrome and Edge both read it back that way (2026-11-22).
    get rect() { const r = rec.rect; return [r[0], r[3], r[2], r[1]]; },
    set rect(r) {
      if (!Array.isArray(r) || r.length !== 4 || r.some(x => typeof x !== 'number' || !isFinite(x)))
        throw new TypeError(`${rec.name}.rect needs 4 finite numbers, got ${JSON.stringify(r)}`);
      rec.rect = [Math.min(r[0], r[2]), Math.min(r[1], r[3]), Math.max(r[0], r[2]), Math.max(r[1], r[3])];
      rec.moves++;
      if (r.some(v => v !== Math.round(v)))
        warn(`${rec.name}.rect = ${JSON.stringify(r)} has fractional points: Edge (Adobe engine) does not draw a field moved to fractional coordinates (Chrome does). Round them with Math.round().`);
      if (r[1] < r[3])
        warn(`${rec.name}.rect = ${JSON.stringify(r)} is bottom-first. Use Acrobat's order [left, top, right, bottom]: Edge does not draw a field set bottom-first (Chrome does).`);
      if (rec.has_ap && !rec.mk_bg && !rec.mk_ca)
        warn(`${rec.name} moved: Chrome drops a moved field's custom /AP and repaints it from /MK; it has no /MK /BG or /CA, so it will look blank. Use color_bar() or dot().`);
      if (rec.display === 0)
        warn(`${rec.name} moved while visible: hide it, set rect, then show it, or Chrome may leave a ghost at the old spot.`);
    },
    get readonly() { return !!(rec.flags & 1); },
    set readonly(b) { rec.flags = b ? rec.flags | 1 : rec.flags & ~1; },
    get page() { return rec.page; },
    get doc() { return sandbox(); },
    get exportValues() { return [rec.export_value]; },
    setFocus() { focusField(rec); },
    buttonGetCaption() { return rec.caption ?? ''; },
    buttonSetCaption(c) { rec.caption = String(c); warn(`${rec.name}.buttonSetCaption: PDFium only shows captions on fields without a custom /AP.`); },
    isBoxChecked() { return rec.value !== 'Off' && rec.value !== ''; },
    checkThisBox(i, b = true) { rec.value = b ? rec.export_value : 'Off'; },
    getArray() { return [this]; },
  };
  rec.obj = new Proxy(target, {
    get(t, p) { return p in t ? t[p] : (rec.props[p]); },
    set(t, p, v) {
      if (p in t) { t[p] = v; return true; }
      if (!KNOWN_PROPS.has(p)) warn(`${rec.name}.${String(p)} is not a field property PDFium knows; the assignment does nothing in Chrome.`);
      rec.props[p] = v; return true;
    },
  });
  return rec.obj;
}

let SANDBOX = null;
function sandbox() { return SANDBOX; }

function makeSandbox() {
  const timers = S.timers;
  const addTimer = (code, ms, repeat) => {
    const id = ++S.timerId;
    const t = { id, code, ms: Math.max(1, Number(ms) || 1), next: S.clock + Math.max(1, Number(ms) || 1), repeat };
    timers.push(t);
    return { id, toString() { return `[Timer ${id}]`; } };
  };
  const clear = t => { const i = timers.findIndex(x => x.id === (t && t.id)); if (i >= 0) timers.splice(i, 1); };
  const app = {
    viewerType: S.opts.viewerType, viewerVariation: 'Full', viewerVersion: 21, platform: 'WIN', language: 'ENU',
    alert(m) { S.log.push('alert: ' + (m && typeof m === 'object' ? m.cMsg : m)); return 1; },
    beep() { S.log.push('beep'); },
    response() { return null; },
    setInterval(code, ms) { return addTimer(code, ms, true); },
    clearInterval: clear,
    setTimeOut(code, ms) { return addTimer(code, ms, false); },
    clearTimeOut: clear,
    launchURL(u) { S.log.push('launchURL: ' + u); },
  };
  const util = {
    printf(fmt, ...a) {
      let i = 0;
      return String(fmt).replace(/%([,\d]*)(?:\.(\d+))?([dfsx%])/g, (m, flags, prec, t) => {
        if (t === '%') return '%';
        const v = a[i++];
        if (t === 'd') return String(Math.trunc(Number(v)));
        if (t === 'f') return Number(v).toFixed(prec === undefined ? 6 : Number(prec));
        if (t === 'x') return Math.trunc(Number(v)).toString(16);
        return String(v);
      });
    },
    printd(fmt, d) { return d.toISOString(); },
  };
  const g = {
    getField(n) { const r = S.fields.get(String(n)); return r ? fieldObject(r) : null; },
    app, util, display: DISPLAY, color: COLOR,
    console: { println(m) { S.log.push(String(m)); }, show() {}, hide() {}, clear() {} },
    global: {
      setPersistent(name) { warn(`global.setPersistent(${JSON.stringify(name)}): do not expect values to survive a reload in Chrome (untested).`); },
      subscribe() {},
    },
    numPages: 1, pageNum: 0, dirty: false, info: {}, documentFileName: 'game.pdf', path: '/game.pdf',
    calculateNow() {}, resetForm() { S.log.push('resetForm'); }, print() { S.log.push('print'); },
    getAnnots() { warn('getAnnots: not implemented by PDFium.'); return null; },
    addField() { throw new Error('addField is not supported by Chrome/PDFium'); },
    removeField() { throw new Error('removeField is not supported by Chrome/PDFium'); },
    event: null,
  };
  return g;
}

function runJS(code, ev, where) {
  if (!code) return;
  SANDBOX.event = ev;
  try {
    if (typeof code === 'function') code();
    else vm.runInContext(String(code), ctx, { filename: where, timeout: S.opts.scriptTimeoutMs });
  } catch (e) {
    S.errors.push({ where, message: String(e && e.message || e), stack: String(e && e.stack || '').split('\n').slice(0, 4).join('\n') });
  } finally {
    SANDBOX.event = null;
  }
}

function fire(rec, trig, extra = {}) {
  const code = rec.actions[trig];
  if (!code) return { rc: true, ...extra };
  const names = { A: 'Mouse Up', D: 'Mouse Down', U: 'Mouse Up', E: 'Mouse Enter', X: 'Mouse Exit', Fo: 'Focus', Bl: 'Blur', K: 'Keystroke', V: 'Validate', F: 'Format', C: 'Calculate' };
  const ev = { name: names[trig] || trig, type: 'Field', target: fieldObject(rec), targetName: rec.name, rc: true,
    value: rec.value, change: '', willCommit: false, shift: false, modifier: false, ...extra };
  S.trace.push(`${rec.name}:${trig}`);
  runJS(code, ev, `${rec.name}/${trig}`);
  return ev;
}

function commit(rec) {
  if (S.buffer === null) return;
  const nv = S.buffer;
  S.buffer = null;
  const k = fire(rec, 'K', { value: nv, willCommit: true });
  if (k.rc === false) return;
  const v = fire(rec, 'V', { value: k.value ?? nv });
  if (v.rc === false) return;
  rec.value = String(v.value ?? nv);
  fire(rec, 'F', { value: rec.value });
}

function blur() {
  const rec = S.focus;
  if (!rec) return;
  if (editable(rec)) commit(rec);
  S.focus = null;
  fire(rec, 'Bl');
}

function focusField(rec) {
  if (S.focus === rec) return;
  if (S.focus) blur();
  S.focus = rec;
  S.buffer = null;
  S.selectAll = false;
  fire(rec, 'Fo');
}

// Chrome/PDFium hit testing, measured in headless Chrome (2026-11-22):
// * overlapping fields: the FIRST one in annotation order gets the click, although the last one is drawn on top;
// * a field hidden by a script still takes clicks while it has the focus, if it was visible in the file
//   (a click on empty page removes the focus); a field that was hidden in the file does not.
const inside = (r, x, y) => x >= r.rect[0] && x <= r.rect[2] && y >= r.rect[1] && y <= r.rect[3];
const hittable = r => visible(r) || (S.opts.order === 'chrome' && r === S.focus && r.initiallyVisible);
function hit(x, y) {
  const order = S.opts.order === 'chrome' ? S.order : S.order.slice().reverse();
  for (const r of order) if (hittable(r) && inside(r, x, y)) return r;
  return null;
}

function moveTo(x, y) {
  const h = hit(x, y);
  if (h !== S.hover) {
    if (S.hover) fire(S.hover, 'X');
    S.hover = h;
    if (h) fire(h, 'E');
  }
  return h;
}

function advance(ms) {
  const end = S.clock + Math.max(0, ms);
  let guard = 0;
  for (;;) {
    let t = null;
    for (const x of S.timers) if (x.next <= end && (!t || x.next < t.next)) t = x;
    if (!t) break;
    if (++guard > S.opts.maxTimerRuns) { S.errors.push({ where: 'timers', message: `more than ${S.opts.maxTimerRuns} timer runs in one advance()` }); break; }
    S.clock = t.next;
    if (t.repeat) t.next += t.ms; else S.timers.splice(S.timers.indexOf(t), 1);
    runJS(t.code, null, `timer ${t.id}`);
  }
  S.clock = end;
}

function point(target) {
  if (Array.isArray(target)) return target;
  const r = S.fields.get(target);
  if (!r) throw new Error(`no field named ${JSON.stringify(target)}`);
  return center(r);
}

function click(target, holdMs) {
  const [x, y] = point(target);
  const intended = Array.isArray(target) ? null : target;
  const h = moveTo(x, y);
  if (S.lost > 0) { S.lost--; return { hit: null, lost: true }; }
  if (intended && (!h || h.name !== intended)) {
    const why = !h ? 'nothing (is it hidden?)'
      : !visible(h) ? `the hidden field "${h.name}" (it still has the focus, so Chrome keeps giving it clicks on its spot; a click on empty page clears that)`
        : `"${h.name}" (it comes first in the annotation order, so it gets clicks on the shared area)`;
    warn(`click on "${intended}" hit ${why}`);
  }
  if (!h) { if (S.focus) blur(); advance(holdMs); return { hit: null }; }
  if (S.opts.order === 'acrobat') {          // blur/commit, focus, then mouse down
    if (S.focus !== h) focusField(h);
    fire(h, 'D');
  } else {                                   // Chrome: mouse down first, then the old field commits and blurs
    fire(h, 'D');
    if (S.focus !== h) focusField(h);
  }
  advance(holdMs);
  fire(h, 'U');
  if ((h.type === 'checkbox' || h.type === 'radiobutton') && !(h.flags & 1))
    h.value = h.value === 'Off' ? h.export_value : (h.type === 'radiobutton' ? h.value : 'Off');
  fire(h, 'A');
  return { hit: h.name };
}

// A drag, as measured in headless Chrome (2026-11-22): mouse down on the pressed field; while the button is held,
// exit/enter go to the fields under the pointer; on release mouse up goes first to the pressed field, then to the
// field under the pointer (if that is another one). No activate (/A) unless the release is on the pressed field.
function drag(start, end, steps, stepMs) {
  const [x0, y0] = point(start), [x1, y1] = point(end);
  const h = moveTo(x0, y0);
  if (S.lost > 0) { S.lost--; return { hit: null, lost: true }; }
  if (!h) { if (S.focus) blur(); return { hit: null, end: null }; }
  fire(h, 'D');
  if (S.focus !== h) focusField(h);
  for (let i = 1; i <= steps; i++) {
    advance(stepMs);
    moveTo(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps);
  }
  advance(stepMs);
  fire(h, 'U');
  const under = S.hover;
  if (under === h) fire(h, 'A');
  else if (under) fire(under, 'U');
  return { hit: h.name, end: under ? under.name : null };
}

function typeText(text) {
  const rec = S.focus;
  if (!rec || !editable(rec)) throw new Error(`type(): no editable text field has the focus (focus: ${rec ? rec.name : 'none'})`);
  for (const ch of String(text)) {
    let cur = S.buffer ?? String(rec.value);
    if (S.selectAll) { cur = ''; S.selectAll = false; }
    const ev = fire(rec, 'K', { value: cur, change: ch, willCommit: false, selStart: cur.length, selEnd: cur.length });
    if (ev.rc === false) continue;
    const next = cur + (ev.change ?? ch);
    if (rec.max_len && next.length > rec.max_len) continue;
    S.buffer = next;
  }
}

function key(k) {
  const rec = S.focus;
  if (k === 'SelectAll') { S.selectAll = true; return; }
  if (!rec) return;
  if (k === 'Enter') { if (editable(rec)) commit(rec); return; }
  if (k === 'Tab') { blur(); return; }
  if (k === 'Escape') { S.buffer = null; return; }
  if (k === 'Backspace' && editable(rec)) {
    const cur = S.selectAll ? '' : (S.buffer ?? String(rec.value));
    S.selectAll = false;
    S.buffer = cur.slice(0, -1);
    return;
  }
  throw new Error(`unknown key ${k}; use Enter, Tab, Escape, Backspace, SelectAll`);
}

function fieldState(r) {
  return { name: r.name, type: r.type, value: r.type === 'text' && S.focus === r && S.buffer !== null ? S.buffer : r.value,
    display: r.display, visible: visible(r), rect: r.rect, moves: r.moves, props: r.props };
}

function load(spec) {
  const o = spec.options || {};
  S = {
    opts: { numericValues: o.numericValues ?? true, viewerType: o.viewerType ?? 'Exchange-Pro', scriptTimeoutMs: o.scriptTimeoutMs ?? 2000,
      maxTimerRuns: o.maxTimerRuns ?? 200000, order: o.order ?? 'chrome' },
    fields: new Map(), order: [], clock: o.startTime ?? 1767225600000, timers: [], timerId: 0,
    focus: null, hover: null, buffer: null, selectAll: false, lost: o.lostClicks ?? 0,
    log: [], errors: [], warnings: [], warnSeen: new Set(), trace: [],
  };
  const fs = spec.fields.slice().sort((a, b) => a.page - b.page || a.order - b.order);
  for (const f of fs) {
    if (S.fields.has(f.name)) { warn(`two widgets share the field name "${f.name}"; the simulator keeps the first`); continue; }
    const rec = { ...f, display: f.hidden ? 1 : 0, initiallyVisible: !f.hidden, rect: f.rect.slice(), props: {}, moves: 0, obj: null };
    S.fields.set(f.name, rec);
    S.order.push(rec);
  }
  SANDBOX = makeSandbox();
  ctx = vm.createContext(SANDBOX);
  const rnd = mulberry32(o.seed ?? 1);
  vm.runInContext(`(function (nowFn, rnd) {
    const RealDate = Date;
    class D extends RealDate { constructor(...a) { if (a.length === 0) super(nowFn()); else super(...a); } static now() { return nowFn(); } }
    globalThis.Date = D; Math.random = rnd;
  })`, ctx)(() => S.clock, rnd);
  for (const s of spec.scripts) runJS(s.source, null, `doc/${s.name}`);
  return { fields: S.order.length };
}

function syntaxCheck(spec) {
  const problems = [];
  const check = (src, where) => { try { new vm.Script(String(src), { filename: where }); } catch (e) { problems.push({ where, message: String(e.message) }); } };
  for (const s of spec.scripts) check(s.source, `doc/${s.name}`);
  for (const f of spec.fields) for (const [t, src] of Object.entries(f.actions)) check(src, `${f.name}/${t}`);
  return problems;
}

function handle(m) {
  switch (m.cmd) {
    case 'load': return load(m.spec);
    case 'syntax': return syntaxCheck(m.spec);
    case 'click': return click(m.target, m.holdMs ?? 80);
    case 'drag': return drag(m.start, m.end, m.steps ?? 10, m.stepMs ?? 16);
    case 'move': { const h = moveTo(m.x, m.y); return { hit: h ? h.name : null }; }
    case 'type': typeText(m.text); return null;
    case 'key': key(m.key); return null;
    case 'fill': click(m.target, m.holdMs ?? 80); key('SelectAll'); typeText(m.text); return null;
    case 'focus': { const r = S.fields.get(m.target); if (!r) throw new Error(`no field ${m.target}`); focusField(r); return null; }
    case 'blur': blur(); return null;
    case 'advance': advance(m.ms); return { clock: S.clock };
    case 'get': { const r = S.fields.get(m.name); if (!r) throw new Error(`no field ${m.name}`); return fieldState(r); }
    case 'state': return Object.fromEntries(S.order.map(r => [r.name, fieldState(r)]));
    case 'eval': {
      SANDBOX.event = null;
      const v = vm.runInContext(String(m.js), ctx, { filename: 'eval', timeout: S.opts.scriptTimeoutMs });
      return v === undefined ? null : JSON.parse(JSON.stringify(v, (k, x) => typeof x === 'function' ? `[function ${x.name}]` : x) ?? 'null');
    }
    case 'run': runJS(m.js, null, 'run'); return null;
    case 'hit': { const h = hit(m.x, m.y); return h ? h.name : null; }
    case 'timers': return S.timers.map(t => ({ id: t.id, ms: t.ms, next: t.next, repeat: t.repeat }));
    case 'trace': { const t = S.trace; S.trace = []; return t; }
    default: throw new Error(`unknown command ${m.cmd}`);
  }
}

const rl = readline.createInterface({ input: process.stdin });
rl.on('line', line => {
  if (!line.trim()) return;
  let m, reply;
  try {
    m = JSON.parse(line);
    const nErr = S ? S.errors.length : 0, nLog = S ? S.log.length : 0, nWarn = S ? S.warnings.length : 0;
    const result = handle(m);
    reply = { ok: true, result, errors: S ? S.errors.slice(nErr) : [], log: S ? S.log.slice(nLog) : [],
      warnings: S ? S.warnings.slice(nWarn) : [], clock: S ? S.clock : 0 };
  } catch (e) {
    reply = { ok: false, error: String(e && e.message || e), errors: [], log: [], warnings: [] };
  }
  process.stdout.write(JSON.stringify(reply) + '\n');
});
