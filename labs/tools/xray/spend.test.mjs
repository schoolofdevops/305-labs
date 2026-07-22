#!/usr/bin/env node
// LLM Stack X-Ray — Spend lens (M12) LIVE assertion harness.
// Drives the real page against the real serve.py proxy and the REAL LiteLLM
// gateway — nothing mocked. Zero runtime deps (hand-rolled CDP, Node built-ins).
// Preconditions: serve.py on :8010, the M12 gateway stack up on :4000, and at
// least one completion (ideally with one repeated request for a cache hit)
// already sent through the gateway so /spend/logs has rows.
// Run: node labs/tools/xray/spend.test.mjs

import { spawn } from 'node:child_process';
import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';

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
  else { FAIL++; results.push('  FAIL  ' + name + (detail ? '  [' + detail + ']' : '')); }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

function httpJSON(method, urlPath) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: PORT, path: urlPath, method }, res => {
      let b = ''; res.on('data', c => b += c); res.on('end', () => { try { resolve(JSON.parse(b)); } catch (e) { reject(e); } });
    });
    req.on('error', reject); req.end();
  });
}

function connectWS(wsUrl) {
  return new Promise((resolve, reject) => {
    const u = new URL(wsUrl);
    const key = crypto.randomBytes(16).toString('base64');
    const req = http.request({
      host: u.hostname, port: u.port, path: u.pathname,
      headers: { Connection: 'Upgrade', Upgrade: 'websocket', 'Sec-WebSocket-Key': key, 'Sec-WebSocket-Version': 13 },
    });
    req.on('upgrade', (res, socket) => {
      let id = 0; const pend = new Map(); const handlers = new Map(); let buf = Buffer.alloc(0);
      socket.on('data', d => {
        buf = Buffer.concat([buf, d]);
        for (;;) {
          const f = decodeFrame(buf); if (!f) break;
          buf = buf.slice(f.consumed);
          if (f.opcode === 1) {
            const m = JSON.parse(f.payload);
            if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
            else if (m.method && handlers.has(m.method)) handlers.get(m.method)(m.params);
          }
        }
      });
      resolve({
        send: (method, params = {}) => new Promise(res2 => {
          const mid = ++id; pend.set(mid, res2);
          socket.write(encodeFrame(JSON.stringify({ id: mid, method, params })));
        }),
        onEvent: (method, fn) => handlers.set(method, fn),
        close: () => socket.end(),
      });
    });
    req.on('error', reject); req.end();
  });
}
function encodeFrame(str) {
  const payload = Buffer.from(str); const mask = crypto.randomBytes(4);
  let header;
  if (payload.length < 126) { header = Buffer.alloc(2); header[1] = 0x80 | payload.length; }
  else if (payload.length < 65536) { header = Buffer.alloc(4); header[1] = 0x80 | 126; header.writeUInt16BE(payload.length, 2); }
  else { header = Buffer.alloc(10); header[1] = 0x80 | 127; header.writeBigUInt64BE(BigInt(payload.length), 2); }
  header[0] = 0x81;
  const masked = Buffer.from(payload);
  for (let i = 0; i < masked.length; i++) masked[i] ^= mask[i % 4];
  return Buffer.concat([header, mask, masked]);
}
function decodeFrame(buf) {
  if (buf.length < 2) return null;
  const opcode = buf[0] & 0x0f; let len = buf[1] & 0x7f; let off = 2;
  if (len === 126) { if (buf.length < 4) return null; len = buf.readUInt16BE(2); off = 4; }
  else if (len === 127) { if (buf.length < 10) return null; len = Number(buf.readBigUInt64BE(2)); off = 10; }
  if (buf.length < off + len) return null;
  return { opcode, payload: buf.slice(off, off + len).toString(), consumed: off + len };
}

async function main() {
  const child = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${PORT}`, '--remote-allow-origins=*',
    '--no-sandbox', '--disable-gpu', '--window-size=1200,760',
    '--user-data-dir=/tmp/xray-spend-chrome-' + process.pid, 'about:blank',
  ], { stdio: 'ignore' });

  let version;
  for (let i = 0; i < 60; i++) {
    try { version = await httpJSON('GET', '/json/version'); if (version && version.webSocketDebuggerUrl) break; } catch {}
    await sleep(150);
  }
  if (!version) { console.error('devtools endpoint never came up'); child.kill('SIGKILL'); process.exit(2); }

  const tab = await httpJSON('PUT', '/json/new?' + encodeURIComponent(PAGE_URL));
  const cdp = await connectWS(tab.webSocketDebuggerUrl);
  const consoleErrors = [], externalReqs = [];
  await cdp.send('Runtime.enable'); await cdp.send('Page.enable'); await cdp.send('Network.enable');
  cdp.onEvent('Runtime.consoleAPICalled', p => { if (p.type === 'error') consoleErrors.push(JSON.stringify(p.args)); });
  cdp.onEvent('Network.requestWillBeSent', p => {
    const u = p.request.url;
    if (!u.startsWith(PAGE_URL) && !u.startsWith('data:') && !u.startsWith('about:')) externalReqs.push(u);
  });
  await cdp.send('Page.navigate', { url: PAGE_URL });
  await sleep(1200);

  async function ev(expr) {
    const r = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
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

  // ---------- 1. tab exists and is no longer a stub ----------
  ok('spend: tab present and clickable', (await ev('!!document.querySelector("#tabs .tab[data-lens=spend]")')) === true);
  ok('spend: stub class gone', (await ev('!!document.querySelector("#tabs .tab.stub")')) === false);

  // ---------- 2. lens switches ----------
  await ev('document.querySelector("#tabs .tab[data-lens=spend]").click()');
  ok('spend: lens switches (panel visible)',
    (await ev('document.body.classList.contains("lens-spend")')) === true
    && (await ev('getComputedStyle(document.getElementById("spMain")).display')) === 'grid');
  ok('spend: other panels hidden', (await ev('getComputedStyle(document.getElementById("main")).display')) === 'none');
  ok('spend: header names the lens', (await ev('document.getElementById("lensName").textContent')) === 'Spend lens');

  // ---------- 3. real rows through the proxy ----------
  await waitFor('document.querySelectorAll("#spLog .spReq").length >= 1', 12000, 'spend: request rows render');
  ok('spend: offline banner hidden', !(await ev('document.getElementById("spOffline").classList.contains("show")')));
  const reqs = await ev('parseInt(document.getElementById("spReqs").textContent)');
  ok('spend: totals count matches rows source', Number.isInteger(reqs) && reqs >= 1, String(reqs));
  ok('spend: total spend is a dollar figure', /^\$\d+\.\d{6}$/.test(await ev('document.getElementById("spTotal").textContent')));
  ok('spend: token total is numeric and > 0', (await ev('parseInt(document.getElementById("spToks").textContent)')) > 0);

  // ---------- 4. per-key aggregation ----------
  ok('spend: at least one key row', (await ev('document.querySelectorAll("#spKeys .spKeyRow").length')) >= 1);
  ok('spend: key row shows masked key + spend',
    /^…/.test(await ev('document.querySelector("#spKeys .spKeyRow .alias").textContent'))
    && /^\$\d/.test(await ev('document.querySelector("#spKeys .spKeyRow .amt").textContent')));

  // ---------- 5. cache-hit chips (needs one repeated request in the data) ----------
  ok('spend: MISS chips render', (await ev('document.querySelectorAll("#spLog .spReq .hit.no").length')) >= 1);
  ok('spend: CACHE chip renders for the repeat', (await ev('document.querySelectorAll("#spLog .spReq .hit.yes").length')) >= 1);
  ok('spend: cache-hit ratio shown', /\(\d+%\)/.test(await ev('document.getElementById("spHits").textContent')));

  // ---------- 6. hygiene ----------
  ok('spend: model named in rows', (await ev('document.querySelector("#spLog .spReq .m").textContent')).length > 1);
  ok('spend: zero external requests', externalReqs.length === 0, externalReqs.slice(0, 3).join(' '));
  ok('spend: no console errors', consoleErrors.length === 0, consoleErrors.join(' | ').slice(0, 200));
  await ev('document.querySelector("#tabs .tab[data-lens=tokens]").click()');
  ok('spend: switch back to Tokens works', (await ev('document.body.className')) === '');

  console.log(results.join('\n'));
  console.log(`\n${PASS}/${PASS + FAIL} assertions passed`);
  cdp.close(); child.kill('SIGKILL');
  process.exit(FAIL ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(2); });
