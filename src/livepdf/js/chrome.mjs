// livepdf Chrome driver: starts headless Chrome, opens a PDF in Chrome's own PDF viewer and sends real mouse and
// keyboard input through the DevTools protocol. No npm packages; needs Node 22+ (global WebSocket and fetch).
// Protocol: argv[2] = JSON launch options; then one JSON command per line on stdin, one JSON reply per line.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import readline from 'node:readline';

const opt = JSON.parse(process.argv[2] || '{}');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const profile = mkdtempSync(join(tmpdir(), 'livepdf-chrome-'));
const port = opt.port || 9300 + Math.floor(Math.random() * 600);
const args = [`--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, `--window-size=${opt.width},${opt.height}`,
  '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--mute-audio'];
if (!opt.headful) args.unshift('--headless=new');
const chrome = spawn(opt.chrome, [...args, 'about:blank'], { stdio: 'ignore' });

let ws, nextId = 0;
const pending = new Map();
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function connect() {
  let tabs = null;
  for (let i = 0; i < 100 && !tabs; i++) {
    try { tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(100); }
  }
  if (!tabs) throw new Error('Chrome did not open its DevTools port');
  const page = tabs.find(t => t.type === 'page');
  ws = new WebSocket(page.webSocketDebuggerUrl);
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    const p = m.id && pending.get(m.id);
    if (!p) return;
    pending.delete(m.id);
    if (m.error) p.reject(new Error(m.error.message)); else p.resolve(m.result);
  };
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  await send('Page.enable');
}

const KEYS = {
  Enter: { key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r' },
  Tab: { key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 },
  Escape: { key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 },
  Backspace: { key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8 },
  End: { key: 'End', code: 'End', windowsVirtualKeyCode: 35 },
  Home: { key: 'Home', code: 'Home', windowsVirtualKeyCode: 36 },
  SelectAll: { key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 2 },
};

async function handle(m) {
  switch (m.cmd) {
    case 'open':
      await send('Page.navigate', { url: m.url });
      await sleep(m.waitMs ?? 2500);
      return null;
    case 'mouse':
      await send('Input.dispatchMouseEvent', { type: m.type, x: m.x, y: m.y, button: m.button ?? (m.type === 'mouseMoved' ? 'none' : 'left'),
        buttons: m.buttons ?? (m.type === 'mousePressed' ? 1 : 0), clickCount: 1 });
      return null;
    case 'click':
      await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: m.x, y: m.y, button: 'none' });
      await sleep(m.moveMs ?? 40);
      await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: m.x, y: m.y, button: 'left', buttons: 1, clickCount: 1 });
      await sleep(m.holdMs ?? 80);
      await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: m.x, y: m.y, button: 'left', buttons: 0, clickCount: 1 });
      return null;
    case 'text':
      for (const ch of m.text) { await send('Input.dispatchKeyEvent', { type: 'char', text: ch }); await sleep(m.charMs ?? 15); }
      return null;
    case 'key': {
      const k = KEYS[m.key];
      if (!k) throw new Error(`unknown key ${m.key}; use ${Object.keys(KEYS).join(', ')}`);
      const base = { key: k.key, code: k.code, windowsVirtualKeyCode: k.windowsVirtualKeyCode, modifiers: k.modifiers || 0 };
      await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...base });
      if (k.text) await send('Input.dispatchKeyEvent', { type: 'char', text: k.text, ...base });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', ...base });
      return null;
    }
    case 'wait': await sleep(m.ms); return null;
    case 'shot': {
      const r = await send('Page.captureScreenshot', { format: 'png' });
      writeFileSync(m.path, Buffer.from(r.data, 'base64'));
      return m.path;
    }
    default: throw new Error(`unknown command ${m.cmd}`);
  }
}

function shutdown() {
  try { ws && ws.close(); } catch { }
  try { chrome.kill(); } catch { }
  setTimeout(() => { try { rmSync(profile, { recursive: true, force: true }); } catch { } process.exit(0); }, 300);
}

try {
  await connect();
  process.stdout.write(JSON.stringify({ ok: true, result: 'ready' }) + '\n');
} catch (e) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(e.message || e) }) + '\n');
  shutdown();
}

// Commands run strictly one after another, in the order they arrive.
const rl = readline.createInterface({ input: process.stdin });
let chain = Promise.resolve();
rl.on('line', line => {
  if (!line.trim()) return;
  chain = chain.then(async () => {
    let reply;
    try { reply = { ok: true, result: await handle(JSON.parse(line)) }; } catch (e) { reply = { ok: false, error: String(e.message || e) }; }
    process.stdout.write(JSON.stringify(reply) + '\n');
  });
});
rl.on('close', () => chain.then(shutdown));
