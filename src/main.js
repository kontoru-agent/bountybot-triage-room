// Bountybot Triage Room — frontend.
//
// LIVE mode: real Nexconn Chat SDK (@nexconn/chat). The engine's bot user
// broadcasts candidate cards / verdicts / approvals into the group via the
// backend's signed Server API calls; humans discuss and approve in the
// same group. Custom message types are registered before connect.
//
// DEMO mode (server has no App Key configured): the identical UI and
// engine events are rendered from the backend's local responses, under a
// permanent banner stating that transport is a local preview — never
// presented as Nexconn traffic.

const $ = (s) => document.querySelector(s);
const messagesEl = $('#messages');

let cfg = null;          // /api/config
let me = null;           // current user id
let channel = null;      // live GroupChannel
let sdk = null;          // @nexconn/chat module (live only)
let bootstrapped = false;
const seen = new Set();  // dedupe live broadcasts vs API responses

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function scrollDown() { messagesEl.scrollTop = messagesEl.scrollHeight; }

function bubble({ from, text, mine = false, system = false }) {
  const div = document.createElement('div');
  div.className = 'msg' + (mine ? ' mine' : '') + (system ? ' system' : '');
  div.innerHTML = `<div class="from">${esc(from)}</div>${esc(text)}`;
  messagesEl.appendChild(div); scrollDown();
  return div;
}

// ---------------------------------------------------------------- events
function eventKey(ev) {
  return JSON.stringify([ev.type, ev.candidate_id || ev.candidate?.id,
    ev.decision || ev.verdict, ev.reason || '']);
}

function renderEvent(ev, force = false) {
  const key = eventKey(ev);
  if (!force && seen.has(key)) return;
  seen.add(key);
  if (ev.type === 'candidate_card') return renderCard(ev.candidate);
  if (ev.type === 'verdict') return renderVerdict(ev);
  if (ev.type === 'approval') return renderVerdict({
    candidate_id: ev.candidate_id, decision: ev.verdict,
    gate: 'gated_signer (chat approval)', reason: ev.reason,
    actor: ev.actor, meaning: ev.meaning });
}

function renderCard(c) {
  const div = document.createElement('div');
  div.className = 'card';
  div.innerHTML = `
    <h3>🗂️ Candidate ${esc(c.id)} — ${esc(c.function || '')}</h3>
    <div class="meta">${esc(c.contract || '')}</div>
    <div class="meta">impact class: ${esc(c.impact_class || '—')} ·
      pattern: ${esc(c.pattern || '—')}</div>
    <div class="desc">${esc(c.description || '')}</div>
    <div class="meta">${(c.locations || []).map(esc).join(' · ')}</div>`;
  messagesEl.appendChild(div); scrollDown();
}

function renderVerdict(ev) {
  const d = ev.decision || ev.verdict;
  const div = document.createElement('div');
  div.className = `verdict ${d}`;
  const extra = [
    ev.gate ? `gate: ${esc(ev.gate)}` : '',
    ev.rank_score != null ? `rank ${esc(ev.rank_score)}` : '',
    ev.actor ? `by ${esc(ev.actor)}` : '',
  ].filter(Boolean).join(' · ');
  div.innerHTML = `
    <span class="tag">${d === 'block' ? '🔴 block' : d === 'warn' ? '🟡 warn' : '🟢 allow'}</span>
    <b>${esc(ev.candidate_id)}</b> — ${esc(ev.reason || '')}
    ${extra ? `<div class="meta" style="color:var(--muted);font-size:12px">${extra}</div>` : ''}
    ${ev.meaning ? `<div style="font-size:12.5px;margin-top:4px">${esc(ev.meaning)}</div>` : ''}`;
  if (d === 'warn' && ev.candidate_id && !String(ev.candidate_id).startsWith('INJ')) {
    const actions = document.createElement('div');
    actions.className = 'actions';
    actions.style.marginTop = '8px';
    const ap = document.createElement('button');
    ap.textContent = 'Approve (lead only)';
    ap.onclick = () => decide('/api/approve', ev.candidate_id, actions);
    const rj = document.createElement('button');
    rj.textContent = 'Reject (lead only)';
    rj.onclick = () => decide('/api/reject', ev.candidate_id, actions);
    actions.append(ap, rj);
    div.appendChild(actions);
  }
  messagesEl.appendChild(div); scrollDown();
}

async function decide(path, candidateId, actionsEl) {
  if (!me) return;
  actionsEl.querySelectorAll('button').forEach((b) => (b.disabled = true));
  try {
    const result = await api(path, { actor: me, candidate_id: candidateId });
    renderEvent({ type: 'approval', ...result });
    refreshLog();
  } catch (e) {
    bubble({ from: 'system', text: `Decision failed: ${e.message}`, system: true });
    actionsEl.querySelectorAll('button').forEach((b) => (b.disabled = false));
  }
}

// ------------------------------------------------------------------- log
async function refreshLog() {
  try {
    const { entries } = await api('/api/log');
    $('#log').innerHTML = entries.slice(-30).reverse().map((e) => `
      <div class="entry"><span class="v-${esc(e.verdict)}">${esc(e.verdict).toUpperCase()}</span>
      <b>${esc(e.candidate)}</b> · ${esc(e.reason || '')}<br>
      <span style="color:var(--muted)">${esc(e.ts || '')}</span></div>`).join('')
      || '<span class="hint">No decisions yet.</span>';
  } catch { /* log panel is best-effort */ }
}

// -------------------------------------------------------------- identity
async function setIdentity(user) {
  me = user;
  document.querySelectorAll('#identity button').forEach((b) =>
    b.classList.toggle('active', b.dataset.user === user));
  $('#btn-run').disabled = false;
  $('#btn-inject').disabled = false;
  $('#composer-input').disabled = false;
  $('#composer-send').disabled = false;

  if (cfg.mode === 'demo') {
    $('#conn').textContent = `local demo — joined as ${user} (${cfg.users[user].role})`;
    return;
  }
  // live
  if (!bootstrapped) { await api('/api/bootstrap', {}); bootstrapped = true; }
  const { token } = await api('/api/token', { user });
  await connectLive(token);
  $('#conn').textContent = `connected to Nexconn as ${user} (${cfg.users[user].role})`;
}

async function connectLive(token) {
  if (!sdk) {
    sdk = await import('@nexconn/chat');
    sdk.NCEngine.initialize({ appKey: cfg.appKey });
    sdk.NCEngine.registerCustomMessages([
      { messageType: 'BB:CandidateCard', isPersited: true, isPersisted: true, isCounted: true },
      { messageType: 'BB:Verdict', isPersited: true, isPersisted: true, isCounted: true },
      { messageType: 'BB:Approval', isPersited: true, isPersisted: true, isCounted: true },
      { messageType: 'BB:SystemNote', isPersited: true, isPersisted: true, isCounted: false },
    ]);
    sdk.NCEngine.addConnectionStatusHandler('bb-conn',
      new sdk.ConnectionStatusHandler({
        onConnectionStatusChanged({ status, code }) {
          $('#conn').textContent = `Nexconn: ${status} (code ${code}) — ${me}`;
        },
      }));
    sdk.NCEngine.addMessageHandler('bb-msg', new sdk.MessageHandler({
      onMessageReceived({ messages }) {
        for (const m of messages || []) onSdkMessage(m);
      },
    }));
  }
  try { await sdk.NCEngine.disconnect(); } catch { /* not connected yet */ }
  const res = await sdk.NCEngine.connect({ token });
  if (res.code !== 0) throw new Error(`connect failed, code ${res.code}`);
  channel = new sdk.GroupChannel(cfg.group.id);
  await loadHistory();
}

function parseContent(content) {
  if (content == null) return null;
  if (typeof content === 'object') {
    if (typeof content.content === 'string') return parseContent(content.content);
    return content;
  }
  try { return JSON.parse(content); } catch { return null; }
}

function onSdkMessage(m) {
  const type = m.messageType || '';
  const from = m.senderUserId || m.fromUserId || 'unknown';
  if (type.startsWith('BB:')) {
    const ev = parseContent(m.content);
    if (ev) renderEvent(ev);
    return;
  }
  // plain text (RC:TxtMsg and friends)
  const raw = typeof m.content === 'string' ? m.content
    : (m.content?.content ?? '');
  if (from === me) return; // own messages render on send
  if (raw) bubble({ from, text: raw });
}

async function loadHistory() {
  try {
    const query = sdk.BaseChannel.createMessagesQuery({
      channelIdentifier: channel.identifier,
      startTime: Date.now(), pageSize: 50, isAscending: false,
    });
    const { code, data } = await query.loadNextPage();
    if (code === 0 && Array.isArray(data)) {
      [...data].reverse().forEach(onSdkMessage);
    }
  } catch { /* history is best-effort; live messages still flow */ }
}

// ---------------------------------------------------------------- actions
$('#btn-run').addEventListener('click', async () => {
  const btn = $('#btn-run'); btn.disabled = true;
  try {
    const { events } = await api('/api/run', {});
    if (cfg.mode === 'demo') {
      for (const ev of events) {
        renderEvent(ev);
        await new Promise((r) => setTimeout(r, 130)); // readable pacing
      }
    } else {
      events.forEach((ev) => renderEvent(ev)); // broadcasts dedupe against this
    }
    refreshLog();
  } catch (e) {
    bubble({ from: 'system', text: `Pipeline run failed: ${e.message}`, system: true });
  }
  btn.disabled = false;
});

$('#btn-inject').addEventListener('click', async () => {
  try {
    const r = await api('/api/inject', {});
    bubble({ from: 'chat note (untrusted text)',
      text: `“${r.injected_text}”`, system: true });
    renderEvent({ type: 'verdict', candidate_id: 'INJ-1',
      decision: r.verdict, gate: 'gated_signer', reason: r.reason }, true);
    refreshLog();
  } catch (e) {
    bubble({ from: 'system', text: `Injection demo failed: ${e.message}`, system: true });
  }
});

$('#composer').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = $('#composer-input');
  const text = input.value.trim();
  if (!text || !me) return;
  input.value = '';
  if (cfg.mode === 'demo') {
    bubble({ from: `${me} · local only (demo mode)`, text, mine: true });
    return;
  }
  try {
    const params = new sdk.SendTextMessageParams({ text });
    const { code } = await channel.sendMessage(params);
    if (code !== 0) throw new Error(`send failed, code ${code}`);
    bubble({ from: me, text, mine: true });
  } catch (err) {
    bubble({ from: 'system', text: `Send failed: ${err.message}`, system: true });
  }
});

// ------------------------------------------------------------------ init
(async function init() {
  cfg = await api('/api/config');
  const badge = $('#mode-badge');
  if (cfg.mode === 'live') {
    badge.textContent = '● LIVE — Nexconn connected app';
    badge.classList.add('live');
  } else {
    badge.textContent = 'LOCAL DEMO MODE';
    badge.classList.add('demo');
    $('#demo-banner').classList.remove('hidden');
  }
  $('#room-name').textContent = cfg.group.name;
  const box = $('#identity');
  for (const [id, u] of Object.entries(cfg.users)) {
    if (u.role === 'bot') continue;
    const b = document.createElement('button');
    b.dataset.user = id;
    b.innerHTML = `${esc(u.name)} <span class="role">${esc(u.role)}</span>`;
    b.onclick = () => setIdentity(id).catch((err) =>
      bubble({ from: 'system', text: `Join failed: ${err.message}`, system: true }));
    box.appendChild(b);
  }
  refreshLog();
})();
