/* ── MyCode Dashboard JS ── */
const B = window.BASE_PATH || '';
const TOOLS = [
  { kind: 'claude',   label: 'Claude Code', icon: `<img src="${B}/static/img/icon_claude.png" width="48" height="48" style="border-radius:10px;object-fit:cover;">`,   cardClass: 'tool-card-claude' },
  { kind: 'codex',    label: 'Codex',       icon: `<img src="${B}/static/img/icon_codex.png" width="48" height="48" style="border-radius:10px;object-fit:cover;">`,    cardClass: 'tool-card-codex' },
  { kind: 'opencode', label: 'OpenCode',    icon: `<img src="${B}/static/img/icon_opencode.png" width="48" height="48" style="border-radius:10px;object-fit:cover;">`, cardClass: 'tool-card-opencode' },
  { kind: 'bash',     label: 'Terminal',    icon: `<img src="${B}/static/img/icon_terminal.png" width="48" height="48" style="border-radius:10px;object-fit:cover;">`,  cardClass: 'tool-card-bash' },
];
const KIND_LABEL = { claude: 'Claude Code', codex: 'Codex', opencode: 'OpenCode', bash: 'Terminal' };

let sessions       = [];
let suggestTimer   = null;
let refreshTimer   = null;
let refreshInterval = 30000; // default 30s

// ── Toast ──
function toast(msg, dur) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), dur || 2000);
}

// ── Time ──
function timeAgo(ts) {
  if (!ts) return '—';
  const d = typeof ts === 'number' ? ts * 1000 : Date.parse(ts);
  const s = Math.floor((Date.now() - d) / 1000);
  if (s < 60)   return s + 's ago';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}

// ── Render Tool Grid (once) ──
function renderTools() {
  document.getElementById('toolGrid').innerHTML = TOOLS.map(t => `
    <div class="tool-card ${t.cardClass}" onclick="launchTool('${t.kind}')" id="tool-${t.kind}">
      <div class="tool-icon">${t.icon}</div>
      <div class="tool-label">${t.label}</div>
    </div>
  `).join('');
}

// ── Smart session update (no full replace → no flicker) ──
function reconcileSessionList(newSessions) {
  const list = document.getElementById('sessionList');

  // Remove cards whose sessions are gone
  const existingCards = list.querySelectorAll('.session-card[data-name]');
  const newNames = new Set(newSessions.map(s => s.name));
  existingCards.forEach(card => {
    if (!newNames.has(card.dataset.name)) card.remove();
  });

  // Empty state
  if (!newSessions.length) {
    if (!list.querySelector('.empty-state')) {
      list.innerHTML = '<div class="empty-state"><div class="icon">📡</div>No active sessions. Launch one above!</div>';
    }
    return;
  }
  // Remove empty state if present
  const empty = list.querySelector('.empty-state');
  if (empty) empty.remove();

  // Update or insert each session card
  newSessions.forEach((s, idx) => {
    const existing = list.querySelector(`.session-card[data-name="${s.name}"]`);
    const html = buildCardHTML(s);

    if (existing) {
      // Only replace innerHTML if something actually changed
      const newHash = hashCard(s);
      if (existing.dataset.hash !== newHash) {
        existing.outerHTML = html; // replace
      }
    } else {
      // Insert at correct position
      const cards = list.querySelectorAll('.session-card[data-name]');
      if (idx < cards.length) {
        cards[idx].insertAdjacentHTML('beforebegin', html);
      } else {
        list.insertAdjacentHTML('beforeend', html);
      }
    }
  });
}

function hashCard(s) {
  return `${s.is_running}|${s.auto_approve}|${s.kind}`;
}

function buildCardHTML(s) {
  const isRunning = s.is_running !== false;
  const badgeClass = isRunning ? 'badge-running' : 'badge-stopped';
  const badgeText  = isRunning ? 'Running' : 'Stopped';
  const kindLabel  = KIND_LABEL[s.kind] || s.kind;
  const autoLabel  = s.auto_approve ? '<span style="font-size:11px;color:var(--green)">🟢 Auto</span>' : '';

  return `<div class="session-card" data-name="${s.name}" data-hash="${hashCard(s)}">
    <div class="session-top">
      <div class="session-name">
        <span>${kindLabel}</span>
        <span class="badge ${badgeClass}">${badgeText}</span>
        ${autoLabel}
      </div>
    </div>
    <div class="session-meta">
      <span><span class="label">tmux</span> <span class="value">${s.name || '—'}</span></span>
      <span><span class="label">Port</span> <span class="value">${s.ttyd_port || '—'}</span></span>
      <span><span class="label">Created</span> <span class="value">${timeAgo(s.created_at)}</span></span>
    </div>
    <div class="session-actions">
      <a href="${B}/viewer?s=${encodeURIComponent(s.name)}&t=${encodeURIComponent(s.token)}" class="btn btn-primary">▶ Open</a>
      <button class="btn" onclick="toggleAutoApprove('${s.name}', ${!s.auto_approve})">${s.auto_approve ? '⏸ Auto Off' : '⚡ Auto On'}</button>
      <button class="btn btn-danger" onclick="killSession('${s.name}')">✕ Kill</button>
    </div>
  </div>`;
}

// ── Load Sessions ──
async function loadSessions(isManual) {
  if (isManual) {
    const btn = document.getElementById('refreshNowBtn');
    btn.classList.add('spinning');
    setTimeout(() => btn.classList.remove('spinning'), 600);
  }
  try {
    const r = await fetch(`${B}/api/sessions`);
    const data = await r.json();
    sessions = data.sessions || [];
    const running = sessions.filter(s => s.is_running !== false).length;
    document.getElementById('stats').textContent = `${running} running · ${sessions.length} total`;
    document.getElementById('sessionCount').textContent =
      sessions.length ? `${sessions.length} session${sessions.length !== 1 ? 's' : ''}` : '';
    reconcileSessionList(sessions);
  } catch (e) {
    if (isManual) toast('Load failed: ' + e.message);
  } finally {
    scheduleNextRefresh();
  }
}

// ── Refresh scheduling ──
function scheduleNextRefresh() {
  clearTimeout(refreshTimer);
  if (refreshInterval > 0) {
    refreshTimer = setTimeout(() => loadSessions(false), refreshInterval);
  }
}

document.getElementById('refreshSelect').addEventListener('change', function () {
  refreshInterval = parseInt(this.value, 10);
  clearTimeout(refreshTimer);
  if (refreshInterval > 0) scheduleNextRefresh();
  toast(refreshInterval ? `Auto-refresh: every ${this.options[this.selectedIndex].text}` : 'Auto-refresh: OFF');
});

document.getElementById('refreshNowBtn').addEventListener('click', () => loadSessions(true));

// ── Launch ──
async function launchTool(kind) {
  const workdir = document.getElementById('workdirInput').value.trim() || '/root';
  const card = document.getElementById(`tool-${kind}`);
  if (card) card.style.opacity = '0.5';
  toast(`Launching ${KIND_LABEL[kind] || kind}…`);
  try {
    const r = await fetch(`${B}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, workdir })
    });
    const data = await r.json();
    if (data.error) { toast('Error: ' + data.error); return; }
    location.href = `${B}/viewer?s=${encodeURIComponent(data.name)}&t=${encodeURIComponent(data.token)}`;
  } catch (e) {
    toast('Launch failed: ' + e.message);
  } finally {
    if (card) card.style.opacity = '';
  }
}

// ── Kill ──
async function killSession(name) {
  if (!confirm('Kill this session?')) return;
  try {
    await fetch(`${B}/api/sessions/${encodeURIComponent(name)}`, { method: 'DELETE' });
    toast('Session killed');
    await loadSessions(false);
  } catch (e) { toast('Error: ' + e.message); }
}

// ── Auto-approve toggle ──
async function toggleAutoApprove(name, enabled) {
  try {
    await fetch(`${B}/api/sessions/${encodeURIComponent(name)}/auto-approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    });
    toast(`Auto-approve: ${enabled ? 'ON 🟢' : 'OFF'}`);
    await loadSessions(false);
  } catch (e) { toast('Error: ' + e.message); }
}

// ── Path Suggestions ──
async function querySuggestions() {
  const inp = document.getElementById('workdirInput');
  const box = document.getElementById('suggestions');
  const raw = inp.value.trim();
  if (!raw) { box.hidden = true; return; }
  try {
    const r = await fetch(`${B}/api/path/suggest?prefix=${encodeURIComponent(raw)}`);
    const data = await r.json();
    const items = data.suggestions || [];
    if (!items.length) { box.hidden = true; return; }
    box.hidden = false;
    box.innerHTML = items.map(it =>
      `<button type="button" onclick="useSuggestion('${CSS.escape(it.path)}')">${it.path}</button>`
    ).join('');
  } catch (_) { box.hidden = true; }
}

function useSuggestion(path) {
  document.getElementById('workdirInput').value = path;
  document.getElementById('suggestions').hidden = true;
}

document.getElementById('workdirInput').addEventListener('input', () => {
  clearTimeout(suggestTimer);
  suggestTimer = setTimeout(querySuggestions, 180);
});
document.addEventListener('click', e => {
  if (!e.target.closest('.workdir-wrap')) document.getElementById('suggestions').hidden = true;
});

// ── Init ──
renderTools();
loadSessions(false); // first load
