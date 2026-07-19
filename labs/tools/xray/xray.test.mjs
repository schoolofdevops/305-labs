#!/usr/bin/env node
// LLM Stack X-Ray — Tokens lens LIVE assertion harness.
// Drives the real page against the real serve.py proxy and the real Ollama —
// nothing mocked. Zero runtime deps: hand-rolled CDP client (Node built-ins).
// Preconditions: `bash serve.sh` running on :8010, Ollama up, qwen3:0.6b pulled.
// Run: node labs/tools/xray/xray.test.mjs

import { spawn } from 'node:child_process';
import http from 'node:http';
import net from 'node:net';
import crypto from 'node:crypto';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PAGE_URL = process.env.XRAY_URL || 'http://127.0.0.1:8010/';
const PORT = 9410 + (process.pid % 400);

const CHROME = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
].find(p => { try { fs.accessSync(p); return true; } catch { return false; } });
if (!CHROME) { console.error('No Chrome/Chromium found'); process.exit(2); }

let PASS = 0, FAIL = 0;
const results = [];
function ok(name, cond, detail) {
  if (cond) { PASS++; results.push('  PASS  ' + name); }
  else { FAIL++; results.push('  FAIL  ' + name + (detail ? '  — ' + detail : '')); }
}

function httpJSON(method, urlPath) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: PORT, path: urlPath, method,
      headers: { 'Content-Type': 'application/json' } }, res => {
      let b = ''; res.on('data', d => b += d); res.on('end', () => {
        try { resolve(JSON.parse(b)); } catch { resolve(b); }
      });
    });
    req.on('error', reject); req.end();
  });
}
function connectWS(wsUrl) {
  return new Promise((resolve, reject) => {
    const u = new URL(wsUrl);
    const sock = net.connect(Number(u.port), u.hostname, () => {
      const key = crypto.randomBytes(16).toString('base64');
      sock.write(
        `GET ${u.pathname}${u.search} HTTP/1.1\r\nHost: ${u.host}\r\nUpgrade: websocket\r\n` +
        `Connection: Upgrade\r\nSec-WebSocket-Key: ${key}\r\nSec-WebSocket-Version: 13\r\n` +
        `Origin: http://127.0.0.1:${PORT}\r\n\r\n`);
    });
    let handshaken = false; let buf = Buffer.alloc(0);
    const listeners = new Map(); let idc = 1; const evwaiters = [];
    function send(method, params = {}) {
      const id = idc++;
      sock.write(encodeFrame(JSON.stringify({ id, method, params })));
      return new Promise(res => listeners.set(id, res));
    }
    sock.on('data', chunk => {
      buf = Buffer.concat([buf, chunk]);
      if (!handshaken) {
        const idx = buf.indexOf('\r\n\r\n');
        if (idx === -1) return;
        handshaken = true; buf = buf.slice(idx + 4);
        resolve({ send, onEvent: (m, cb) => evwaiters.push({ m, cb }), close: () => sock.destroy() });
      }
      let f;
      while ((f = decodeFrame(buf))) {
        buf = f.rest;
        if (f.opcode === 8) { sock.destroy(); break; }
        if (f.opcode === 1 || f.opcode === 2) {
          let m; try { m = JSON.parse(f.payload.toString()); } catch { continue; }
          if (m.id && listeners.has(m.id)) { listeners.get(m.id)(m); listeners.delete(m.id); }
          if (m.method) evwaiters.filter(w => w.m === m.method).forEach(w => w.cb(m.params));
        }
      }
    });
    sock.on('error', reject);
  });
}
function encodeFrame(str) {
  const p = Buffer.from(str); const len = p.length;
  const mask = crypto.randomBytes(4); let header;
  if (len < 126) header = Buffer.from([0x81, 0x80 | len]);
  else if (len < 65536) { header = Buffer.alloc(4); header[0] = 0x81; header[1] = 0x80 | 126; header.writeUInt16BE(len, 2); }
  else { header = Buffer.alloc(10); header[0] = 0x81; header[1] = 0x80 | 127; header.writeBigUInt64BE(BigInt(len), 2); }
  const masked = Buffer.alloc(len);
  for (let i = 0; i < len; i++) masked[i] = p[i] ^ mask[i & 3];
  return Buffer.concat([header, mask, masked]);
}
function decodeFrame(buf) {
  if (buf.length < 2) return null;
  const opcode = buf[0] & 0x0f; const masked = (buf[1] & 0x80) !== 0;
  let len = buf[1] & 0x7f; let off = 2;
  if (len === 126) { if (buf.length < 4) return null; len = buf.readUInt16BE(2); off = 4; }
  else if (len === 127) { if (buf.length < 10) return null; len = Number(buf.readBigUInt64BE(2)); off = 10; }
  let mask; if (masked) { if (buf.length < off + 4) return null; mask = buf.slice(off, off + 4); off += 4; }
  if (buf.length < off + len) return null;
  let payload = buf.slice(off, off + len);
  if (masked) { const o = Buffer.alloc(len); for (let i = 0; i < len; i++) o[i] = payload[i] ^ mask[i & 3]; payload = o; }
  return { opcode, payload, rest: buf.slice(off + len) };
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const child = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${PORT}`, '--remote-allow-origins=*',
    '--no-sandbox', '--disable-gpu', '--window-size=1200,760',
    '--user-data-dir=/tmp/xray-chrome-' + process.pid, 'about:blank',
  ], { stdio: 'ignore' });

  let version;
  for (let i = 0; i < 60; i++) {
    try { version = await httpJSON('GET', '/json/version'); if (version && version.webSocketDebuggerUrl) break; } catch {}
    await sleep(150);
  }
  if (!version || !version.webSocketDebuggerUrl) { console.error('devtools endpoint never came up'); child.kill('SIGKILL'); process.exit(2); }

  const tab = await httpJSON('PUT', '/json/new?' + encodeURIComponent(PAGE_URL));
  const cdp = await connectWS(tab.webSocketDebuggerUrl);

  const consoleErrors = [], pageErrors = [], externalReqs = [];
  await cdp.send('Runtime.enable');
  await cdp.send('Page.enable');
  await cdp.send('Network.enable');
  cdp.onEvent('Runtime.consoleAPICalled', p => { if (p.type === 'error') consoleErrors.push(JSON.stringify(p.args)); });
  cdp.onEvent('Runtime.exceptionThrown', p => pageErrors.push(p.exceptionDetails && p.exceptionDetails.text));
  cdp.onEvent('Network.requestWillBeSent', p => {
    const u = p.request.url;
    if (!u.startsWith(PAGE_URL) && !u.startsWith('data:') && !u.startsWith('about:')) externalReqs.push(u);
  });

  await cdp.send('Emulation.setDeviceMetricsOverride',
    { width: 1200, height: 760, deviceScaleFactor: 1, mobile: false });
  await cdp.send('Page.navigate', { url: PAGE_URL });
  await sleep(1200); // first poll() round-trip

  async function ev(expr) {
    const r = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
    if (r.result && r.result.result) return r.result.result.value;
    return undefined;
  }
  async function waitFor(expr, timeoutMs, label) {
    const t0 = Date.now();
    for (;;) {
      if (await ev(expr)) return true;
      if (Date.now() - t0 > timeoutMs) { ok(label + ' (timed out waiting)', false, expr); return false; }
      await sleep(250);
    }
  }
  const gauge = id => ev(`document.getElementById("${id}").textContent`);
  const pct = id => ev(`parseFloat(document.getElementById("${id}").style.width)||0`);

  // ---------- 1. loads clean against the REAL endpoint ----------
  ok('loads: no console errors', consoleErrors.length === 0, consoleErrors.join(' | '));
  ok('loads: no page exceptions', pageErrors.length === 0, pageErrors.join(' | '));
  ok('loads: zero non-same-origin requests', externalReqs.length === 0, externalReqs.join(' | '));
  ok('lens tabs: 1 active + 2 live lenses + 7 stubs', await ev('document.querySelectorAll("#tabs .tab.active").length') === 1
      && await ev('document.querySelectorAll("#tabs .tab[data-lens]").length') === 2
      && await ev('document.querySelectorAll("#tabs .tab.stub").length') === 7);

  // ---------- 2. real connection state ----------
  await waitFor('document.getElementById("connInd").className === "connected"', 12000, 'conn: indicator connected');
  ok('conn: real ollama version shown', /^ollama \d+\.\d+/.test(await gauge('verInfo')), await gauge('verInfo'));
  ok('conn: offline banner hidden', !(await ev('document.getElementById("offline").classList.contains("show")')));
  await waitFor('document.getElementById("modelSel").value.length > 0', 5000, 'models: dropdown populated');
  const model = await ev('document.getElementById("modelSel").value');
  ok('models: course model auto-selected', model.startsWith('qwen3:0.6b'), model);

  // ---------- 3. prefill-heavy run (the M1 experiment, for real) ----------
  await ev('document.getElementById("presetPf").click()');
  await ev('document.getElementById("sendBtn").click()');
  await waitFor('!document.getElementById("sendBtn").disabled && document.getElementById("pTok").textContent !== "—"',
    60000, 'prefill run: completes');
  const pTok1 = parseInt(await gauge('pTok'), 10), oTok1 = parseInt(await gauge('oTok'), 10);
  ok('prefill run: large prompt measured (>300 tokens)', pTok1 > 300, String(pTok1));
  ok('prefill run: short output (<30 tokens)', oTok1 > 0 && oTok1 < 30, String(oTok1));
  ok('prefill run: TTFT client gauge set', (await gauge('ttftC')) !== '—');
  ok('prefill run: TTFT server gauge set', (await gauge('ttftS')) !== '—');
  const pf1 = await pct('phasePrefill'), dc1 = await pct('phaseDecode');
  ok('prefill run: phase bar dominated by prefill', pf1 > dc1 && pf1 > 60, `prefill=${pf1}% decode=${dc1}%`);
  ok('prefill run: token stream rendered text', (await ev('document.getElementById("streamOut").textContent.trim().length')) > 0);
  ok('prefill run: request log has entries', (await ev('document.querySelectorAll("#evList .ev").length')) >= 3);
  ok('prefill run: context bar advanced', (await pct('ctxFill')) > 0);

  // ---------- 4. decode-heavy run (the contrast) ----------
  await ev('document.getElementById("presetDc").click()');
  await ev('document.getElementById("sendBtn").click()');
  await waitFor('!document.getElementById("sendBtn").disabled && parseInt(document.getElementById("oTok").textContent,10) > 50',
    90000, 'decode run: completes with long output');
  const pf2 = await pct('phasePrefill'), dc2 = await pct('phaseDecode');
  ok('decode run: phase bar flips to decode', dc2 > pf2 && dc2 > 60, `prefill=${pf2}% decode=${dc2}%`);
  ok('decode run: tok/s gauge is a real number', parseFloat(await gauge('toks')) > 1, await gauge('toks'));
  ok('decode run: TPOT gauge set', /ms/.test(await gauge('tpot')), await gauge('tpot'));

  // ---------- 5. thinking-mode cost is visible ----------
  await ev('document.getElementById("thinkChk").checked = true');
  await ev('document.getElementById("prompt").value = "Answer in one word: what colour is the sky on a clear day?"');
  await ev('document.getElementById("sendBtn").click()');
  await waitFor('!document.getElementById("sendBtn").disabled && document.getElementById("oTok").textContent !== "—"',
    90000, 'thinking run: completes');
  ok('thinking run: italic thinking text rendered', (await ev('document.querySelectorAll("#streamOut .think").length')) > 0);
  ok('thinking run: one-word answer cost many tokens', parseInt(await gauge('oTok'), 10) > 30, await gauge('oTok'));

  // ---------- 6. Engine lens (M3) — live vs real llama-server ----------
  await ev('document.querySelector("#tabs .tab[data-lens=engine]").click()');
  ok('engine: lens switches (body class + panel visible)',
    (await ev('document.body.classList.contains("lens-engine")')) === true
    && (await ev('getComputedStyle(document.getElementById("engMain")).display')) === 'grid');
  ok('engine: tokens main hidden', (await ev('getComputedStyle(document.getElementById("main")).display')) === 'none');
  await waitFor('document.getElementById("egPT").textContent !== "—"', 10000, 'engine: metrics populate');
  ok('engine: offline banner hidden with server up', !(await ev('document.getElementById("engOffline").classList.contains("show")')));
  const pt0 = parseInt(await gauge('egPT'), 10);
  ok('engine: prompt-token counter is a number', Number.isFinite(pt0), await gauge('egPT'));
  // drive one real request THROUGH the page's own origin and watch counters move
  await ev(`fetch('/llamacpp/v1/chat/completions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:'qwen3-0.6b',messages:[{role:'user',content:'Reply with one word: hello /no_think'}],max_tokens:20})})`);
  await waitFor(`parseInt(document.getElementById("egPT").textContent,10) > ${pt0}`, 20000, 'engine: counters advance after a real request');
  ok('engine: decode-rate gauge shows tok/s', /tok\/s/.test(await gauge('egRate')), await gauge('egRate'));
  ok('engine: engine log has entries', (await ev('document.querySelectorAll("#engEvList .ev").length')) >= 1);
  ok('engine: chart polyline rendered', (await ev('document.querySelectorAll("#engChart polyline").length')) >= 1);
  // switch back for the screenshot
  await ev('document.querySelector("#tabs .tab[data-lens=tokens]").click()');
  ok('engine: switch back to Tokens works', (await ev('document.body.className')) === '');

  // ---------- screenshot for the evidence file ----------
  const shot = await cdp.send('Page.captureScreenshot', { format: 'png' });
  const outPng = path.join(__dirname, '..', '..', '..', 'planning', 'lab-tests', 'm1-xray.png');
  fs.writeFileSync(outPng, Buffer.from(shot.result.data, 'base64'));

  console.log(results.join('\n'));
  console.log(`\n${PASS}/${PASS + FAIL} assertions passed · screenshot → ${path.relative(process.cwd(), outPng)}`);
  cdp.close(); child.kill('SIGKILL');
  process.exit(FAIL ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(2); });
