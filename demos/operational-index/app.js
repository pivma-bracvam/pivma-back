let refreshInterval = null;
let refreshStarting = false;
let eventsList = [];

function inspect(method, url, status, data) {
  const infoEl = document.getElementById('inspector-info');
  const inspEl = document.getElementById('api-inspector');
  if (infoEl) {
    infoEl.textContent = `${method} ${url} -> HTTP ${status}`;
  }
  if (inspEl) {
    inspEl.textContent = JSON.stringify(data, null, 2);
  }
}

async function checkSession() {
  const displayEl = document.getElementById('user-display');
  const btnLogin = document.getElementById('btn-quick-login');
  const btnLogout = document.getElementById('btn-logout');

  try {
    const res = await fetch('/auth/me', { credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      const user = data.user;
      const profiles = ((data.access && data.access.profiles) || []).map(p => p.name).join(', ') || 'Sem perfil';
      const isAdmin = ((data.access && data.access.profiles) || []).some(
        p => p.name.toLowerCase().includes('admin') || p.id === 'administrator'
      );

      if (displayEl) {
        displayEl.textContent = `${user.full_name || user.username} (${profiles})`;
        displayEl.style.color = isAdmin ? 'var(--success)' : 'var(--warning)';
      }
      if (btnLogin) btnLogin.style.display = 'none';
      if (btnLogout) btnLogout.style.display = 'inline-flex';
      return data;
    } else {
      if (displayEl) {
        displayEl.textContent = 'Não autenticado';
        displayEl.style.color = 'var(--danger)';
      }
      if (btnLogin) btnLogin.style.display = 'inline-flex';
      if (btnLogout) btnLogout.style.display = 'none';
      return null;
    }
  } catch (err) {
    if (displayEl) {
      displayEl.textContent = 'API Inacessível';
      displayEl.style.color = 'var(--danger)';
    }
    return null;
  }
}

async function quickLoginAdmin() {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ identifier: 'admin', password: 'Password123!' }),
  });
  const data = res.ok
    ? { message: 'Autenticado com sucesso como Administrador!' }
    : await res.json().catch(() => ({ detail: 'Falha no login' }));
  inspect('POST', '/auth/login', res.status, data);

  if (res.ok) {
    await checkSession();
    await loadInitialHistory();
  } else {
    alert(
      'Falha ao autenticar como admin. Execute a carga: uv run python -m scripts.seeds.seed_all'
    );
  }
}

async function testForbiddenUser() {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      identifier: 'proponent_user',
      password: 'Password123!',
    }),
  });
  const data = res.ok
    ? { message: 'Autenticado como proponente (usuário comum sem privilégio admin)' }
    : await res.json().catch(() => ({ detail: 'Falha no login' }));
  inspect('POST', '/auth/login', res.status, data);

  if (res.ok) {
    await checkSession();
    await loadInitialHistory();
  }
}

async function logout() {
  stopAutoRefresh();
  const res = await fetch('/auth/logout', {
    method: 'POST',
    credentials: 'include',
  });
  inspect('POST', '/auth/logout', res.status, {
    message: 'Sessão encerrada com sucesso.',
  });
  await checkSession();
}

function updateRefreshBadge(state, text) {
  const dot = document.getElementById('refresh-status-dot');
  const label = document.getElementById('refresh-status-text');
  const btn = document.getElementById('btn-toggle-refresh');

  if (dot) dot.className = 'status-dot ' + state;
  if (label) label.textContent = text;

  if (btn) {
    btn.disabled = state === 'connecting';
    if (refreshInterval !== null) {
      btn.className = 'btn btn-danger';
      btn.innerHTML = '<span>⏹ Parar atualização automática</span>';
    } else {
      btn.className = 'btn btn-primary';
      btn.innerHTML = '<span>▶ Atualizar a cada 5 segundos</span>';
    }
  }
}

function toggleAutoRefresh() {
  if (refreshStarting) return;
  if (refreshInterval !== null) {
    stopAutoRefresh();
  } else {
    startAutoRefresh();
  }
}

async function startAutoRefresh() {
  if (refreshStarting || refreshInterval !== null) return;
  refreshStarting = true;
  updateRefreshBadge('connecting', 'Consultando histórico...');
  const loaded = await loadInitialHistory(false);
  if (!refreshStarting) return;
  refreshStarting = false;
  if (!loaded) return;

  refreshInterval = window.setInterval(() => loadInitialHistory(false), 5000);
  updateRefreshBadge('connected', 'Atualização automática ativa (5 s)');
}

function stopAutoRefresh(errorMessage = null) {
  refreshStarting = false;
  if (refreshInterval !== null) {
    window.clearInterval(refreshInterval);
    refreshInterval = null;
  }
  updateRefreshBadge(
    errorMessage ? 'error' : 'disconnected',
    errorMessage || 'Atualização automática pausada'
  );
}

async function loadInitialHistory(showAlerts = true) {
  const limit = document.getElementById('query-limit')?.value || 50;
  const status = document.getElementById('filter-status')?.value;
  const op = document.getElementById('filter-op')?.value.trim();

  let url = `/admin/logs/operational?limit=${limit}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  if (op) url += `&operation_type=${encodeURIComponent(op)}`;

  try {
    const res = await fetch(url, { credentials: 'include' });
    const data = await res.json().catch(() => null);
    inspect('GET', url, res.status, data);

    if (res.ok && Array.isArray(data)) {
      eventsList = data;
      renderEventsTable();
      if (refreshInterval === null && !refreshStarting) {
        updateRefreshBadge('disconnected', 'Atualização automática pausada');
      }
      return true;
    } else if (res.status === 403) {
      if (showAlerts) alert('Acesso negado (403): é necessário o perfil Administrador.');
      stopAutoRefresh('Acesso negado (403)');
    } else if (res.status === 401) {
      if (showAlerts) alert('Não autenticado (401): faça login como Administrador.');
      stopAutoRefresh('Sessão não autenticada (401)');
    } else {
      stopAutoRefresh(`Falha ao consultar histórico (HTTP ${res.status})`);
    }
  } catch (err) {
    inspect('GET', url, 0, { error: err.message });
    stopAutoRefresh('Falha ao consultar histórico');
  }
  return false;
}

function clearEvents() {
  eventsList = [];
  renderEventsTable();
}

function renderEventsTable() {
  const tbody = document.getElementById('events-table-body');
  const counter = document.getElementById('event-count');
  if (!tbody) return;

  const statusFilter = document.getElementById('filter-status')?.value || '';
  const opFilter = (
    document.getElementById('filter-op')?.value.trim() || ''
  ).toLowerCase();

  const filtered = eventsList.filter((ev) => {
    if (statusFilter && ev.status !== statusFilter) return false;
    if (opFilter && !(ev.operation_type || '').toLowerCase().includes(opFilter))
      return false;
    return true;
  });

  if (counter) counter.textContent = filtered.length;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">
          Nenhum evento correspondente aos filtros atuais.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = '';
  filtered.forEach((ev, idx) => {
    const tr = document.createElement('tr');
    const isSuccess = ev.status === 'SUCCESS';
    const statusBadge = isSuccess
      ? '<span class="badge badge-success">SUCCESS</span>'
      : '<span class="badge badge-failed">FAILED</span>';

    const timeStr = ev.timestamp
      ? new Date(ev.timestamp).toLocaleTimeString('pt-BR')
      : '-';
    const durationStr =
      ev.total_duration_ms !== null && ev.total_duration_ms !== undefined
        ? `${ev.total_duration_ms.toFixed(1)} ms`
        : '-';

    const correlationShort = ev.correlation_id
      ? ev.correlation_id.substring(0, 8) + '...'
      : '-';

    tr.innerHTML = `
      <td style="font-family: monospace; font-size: 13px;">${timeStr}</td>
      <td><span class="badge badge-op">${ev.operation_type || 'N/A'}</span></td>
      <td>${statusBadge}</td>
      <td style="font-family: monospace; font-size: 13px;">${durationStr}</td>
      <td style="font-family: monospace; font-size: 13px;" title="${ev.correlation_id || ''}">${correlationShort}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="toggleDetails(${idx})">Ver JSON</button>
      </td>
    `;

    const detailTr = document.createElement('tr');
    detailTr.id = `detail-row-${idx}`;
    detailTr.style.display = 'none';
    detailTr.innerHTML = `
      <td colspan="6" style="background: #f8fafc; padding: 12px 16px;">
        <strong style="font-size: 13px; color: #334155;">Payload Completo do Evento:</strong>
        <pre class="payload-detail">${JSON.stringify(ev, null, 2)}</pre>
      </td>
    `;

    tbody.appendChild(tr);
    tbody.appendChild(detailTr);
  });
}

function toggleDetails(idx) {
  const row = document.getElementById(`detail-row-${idx}`);
  if (row) {
    row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  const user = await checkSession();
  if (user) {
    await loadInitialHistory();
  }
});
