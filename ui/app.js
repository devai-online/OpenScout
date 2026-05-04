// LeadFinder UI — vanilla JS, no build step.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  tab: 'search',
  running: false,
  sessionId: null,
  liveLeads: [],
  source: null,
};

// ----- Tabs -----
function setTab(name) {
  state.tab = name;
  $$('.tab').forEach(b => {
    const active = b.dataset.tab === name;
    b.classList.toggle('pill-active', active);
    b.classList.toggle('pill', !active);
  });
  $$('.tab-pane').forEach(p => p.classList.add('hidden'));
  $('#tab-' + name).classList.remove('hidden');
  if (name === 'history') loadHistory();
}
$$('.tab').forEach(b => b.addEventListener('click', () => setTab(b.dataset.tab)));

// ----- Status indicator -----
function setStatus(running, label) {
  state.running = running;
  $('#status-dot').classList.toggle('bg-accent', running);
  $('#status-dot').classList.toggle('bg-zinc-600', !running);
  if (running) $('#status-dot').classList.add('animate-pulse');
  else $('#status-dot').classList.remove('animate-pulse');
  $('#status-text').textContent = label || (running ? 'running' : 'idle');
  $('#run-btn').disabled = running;
  $('#cancel-btn').classList.toggle('hidden', !running);
}

// ----- Helpers -----
function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function badge(status) {
  const cls = `badge badge-${status || 'pending'}`;
  return `<span class="${cls}">${escapeHtml(status || 'pending')}</span>`;
}

function leadCard(l) {
  const score = Math.round(l.relevance_score || 0);
  const meta = [
    l.contact_person && `${escapeHtml(l.contact_person)}${l.contact_title ? ' · ' + escapeHtml(l.contact_title) : ''}`,
    l.employee_count && escapeHtml(l.employee_count) + ' emp',
    l.country && escapeHtml(l.country),
  ].filter(Boolean).join(' · ');
  return `
    <div class="card rounded-xl p-4 lead-row fade-in">
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 mb-1">
            <a href="${escapeHtml(l.website)}" target="_blank" rel="noopener" class="font-medium text-zinc-100 hover:text-accent truncate">${escapeHtml(l.company)}</a>
            <span class="text-xs text-zinc-500 truncate">${escapeHtml((l.website || '').replace(/^https?:\/\//, ''))}</span>
          </div>
          ${meta ? `<div class="text-xs text-zinc-500 mb-2">${meta}</div>` : ''}
          ${l.description ? `<p class="text-sm text-zinc-400 line-clamp-2 mb-2">${escapeHtml(l.description)}</p>` : ''}
          <div class="flex items-center flex-wrap gap-3 text-xs text-zinc-300">
            ${l.email ? `<span class="font-mono"><span class="text-zinc-500">@</span> ${escapeHtml(l.email)}</span>` : ''}
            ${l.phone ? `<span class="font-mono"><span class="text-zinc-500">☎</span> ${escapeHtml(l.phone)}</span>` : ''}
          </div>
        </div>
        <div class="text-right shrink-0 w-24">
          <div class="text-2xl font-semibold text-accent-400">${score}</div>
          <div class="score-bar mt-1"><div class="score-fill" style="width:${score}%"></div></div>
          <div class="text-[10px] text-zinc-500 mt-1 leading-tight">${escapeHtml(l.relevance_reason || '')}</div>
        </div>
      </div>
    </div>
  `;
}

// ----- Search form -----
$('#search-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('#form-error').classList.add('hidden');
  const data = Object.fromEntries(new FormData(e.target).entries());
  const body = {
    domain: data.domain.trim(),
    country: (data.country || '').trim(),
    min_emp: parseInt(data.min_emp) || 0,
    max_emp: parseInt(data.max_emp) || 0,
    limit: parseInt(data.limit) || 20,
    notes: (data.notes || '').trim(),
  };
  try {
    const res = await fetch('/api/search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const j = await res.json();
    state.sessionId = j.session_id;
    state.liveLeads = [];
    $('#live-leads').innerHTML = '';
    $('#live-log').innerHTML = '';
    $('#live-count').textContent = '0';
    $('#live-empty').classList.add('hidden');
    $('#live-actions').classList.remove('hidden');
    $('#export-link').href = `/api/sessions/${j.session_id}/export.csv`;
    setStatus(true, 'searching');
    setTab('live');
    connectStream();
  } catch (err) {
    $('#form-error').textContent = err.message;
    $('#form-error').classList.remove('hidden');
  }
});

$('#cancel-btn').addEventListener('click', async () => {
  await fetch('/api/cancel', { method: 'POST' });
});

// ----- SSE -----
function connectStream() {
  if (state.source) state.source.close();
  const es = new EventSource('/api/stream');
  state.source = es;

  es.addEventListener('start', (ev) => {
    const d = JSON.parse(ev.data);
    appendLog(`▶ session #${d.session_id} started`);
  });
  es.addEventListener('log', (ev) => {
    const d = JSON.parse(ev.data);
    appendLog(d.msg);
  });
  es.addEventListener('lead', (ev) => {
    const d = JSON.parse(ev.data);
    state.liveLeads.unshift(d.lead);
    $('#live-count').textContent = state.liveLeads.length;
    const wrap = document.createElement('div');
    wrap.innerHTML = leadCard(d.lead);
    $('#live-leads').prepend(wrap.firstElementChild);
  });
  es.addEventListener('done', (ev) => {
    const d = JSON.parse(ev.data);
    appendLog(`✓ ${d.status} — ${d.lead_count} leads`);
    setStatus(false, d.status);
    es.close();
    state.source = null;
  });
  es.addEventListener('ping', () => {});
  es.onerror = () => {
    appendLog('stream error');
  };
}

function appendLog(msg) {
  const line = document.createElement('div');
  line.className = 'log-line';
  const ts = new Date().toLocaleTimeString();
  line.innerHTML = `<span class="text-zinc-600">${ts}</span>  ${escapeHtml(msg)}`;
  $('#live-log').appendChild(line);
  $('#live-log').scrollTop = $('#live-log').scrollHeight;
}

// ----- History -----
async function loadHistory() {
  const res = await fetch('/api/sessions');
  const rows = await res.json();
  const list = $('#history-list');
  if (!rows.length) {
    list.innerHTML = `<div class="text-sm text-zinc-500 px-2">No searches yet.</div>`;
    return;
  }
  list.innerHTML = rows.map(r => `
    <button class="hist-item w-full text-left card rounded-lg p-3 hover:border-ink-500" data-id="${r.id}">
      <div class="flex items-center justify-between gap-2 mb-1">
        <div class="font-medium text-sm truncate">${escapeHtml(r.domain)}</div>
        ${badge(r.status)}
      </div>
      <div class="text-[11px] text-zinc-500 flex items-center justify-between">
        <span>${escapeHtml(r.country || 'any')} · ${r.lead_count || 0} leads</span>
        <span>${fmtDate(r.started_at)}</span>
      </div>
    </button>
  `).join('');
  $$('.hist-item').forEach(b => b.addEventListener('click', () => showSession(b.dataset.id)));
}

async function showSession(id) {
  const res = await fetch('/api/sessions/' + id);
  if (!res.ok) return;
  const { session, leads } = await res.json();
  const detail = $('#history-detail');
  detail.classList.remove('p-12', 'text-center');
  detail.innerHTML = `
    <div class="card rounded-xl p-5 mb-4">
      <div class="flex items-start justify-between gap-4 mb-3">
        <div>
          <div class="text-xs uppercase tracking-wider text-zinc-500 mb-1">Domain</div>
          <h2 class="text-xl font-semibold">${escapeHtml(session.domain)}</h2>
          <div class="text-xs text-zinc-500 mt-1">
            ${escapeHtml(session.country || 'any')} ·
            ${session.min_emp || 0}-${session.max_emp || '∞'} emp ·
            limit ${session.limit} ·
            ${fmtDate(session.started_at)}
          </div>
        </div>
        <div class="flex items-center gap-2">
          ${badge(session.status)}
          <a href="/api/sessions/${session.id}/export.csv" class="btn-secondary px-3 py-1.5 rounded-md text-xs">Export CSV</a>
          <button data-del="${session.id}" class="btn-secondary px-3 py-1.5 rounded-md text-xs">Delete</button>
        </div>
      </div>
      <div class="text-sm text-zinc-400">${leads.length} leads</div>
    </div>
    <div class="space-y-2">
      ${leads.map(leadCard).join('') || '<div class="card rounded-xl p-8 text-center text-zinc-500 text-sm">No leads.</div>'}
    </div>
  `;
  $$('button[data-del]', detail).forEach(b => b.addEventListener('click', async () => {
    if (!confirm('Delete this search and its leads?')) return;
    await fetch('/api/sessions/' + b.dataset.del, { method: 'DELETE' });
    detail.classList.add('p-12', 'text-center');
    detail.innerHTML = `Select a search to see leads.`;
    loadHistory();
  }));
}

// ----- Init -----
async function init() {
  setTab('search');
  try {
    const res = await fetch('/api/status');
    const j = await res.json();
    if (j.running) {
      state.sessionId = j.session_id;
      $('#live-empty').classList.add('hidden');
      $('#live-actions').classList.remove('hidden');
      $('#export-link').href = `/api/sessions/${j.session_id}/export.csv`;
      setStatus(true, 'running');
      setTab('live');
      connectStream();
    }
  } catch (_) {}
}
init();
