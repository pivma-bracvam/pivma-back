const pipelines = new Map(); // correlation_id -> group data

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
      const profiles =
        ((data.access && data.access.profiles) || []).map((p) => p.name).join(', ') || 'Sem perfil';
      const isAdmin = ((data.access && data.access.profiles) || []).some(
        (p) =>
          p.name.toLowerCase().includes('admin') || p.id === 'administrator'
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
  const res = await fetch('/auth/logout', {
    method: 'POST',
    credentials: 'include',
  });
  inspect('POST', '/auth/logout', res.status, {
    message: 'Sessão encerrada com sucesso.',
  });
  await checkSession();
}

async function loadInitialHistory() {
  const url = '/admin/logs/ai?limit=20';
  try {
    const res = await fetch(url, {
      credentials: 'include',
    });
    const groups = await res.json().catch(() => null);
    inspect('GET', url, res.status, groups);

    if (res.ok && Array.isArray(groups)) {
      pipelines.clear();
      groups.forEach((g) => {
        pipelines.set(g.correlation_id, g);
      });
      renderAllPipelines();
    } else if (res.status === 403) {
      alert('Acesso negado (403): é necessário o perfil Administrador.');
    } else if (res.status === 401) {
      alert('Não autenticado (401): faça login como Administrador.');
    }
  } catch (err) {
    console.warn('Erro ao carregar histórico de IA:', err);
  }
}

function renderAllPipelines() {
  const container = document.getElementById('pipelines-container');
  const countEl = document.getElementById('pipeline-count');
  if (!container) return;

  if (countEl) countEl.textContent = pipelines.size;

  if (pipelines.size === 0) {
    container.innerHTML = `
      <div id="empty-message" style="text-align: center; color: var(--text-muted); padding: 32px; border: 1px dashed var(--border); border-radius: 8px;">
        Nenhuma execução encontrada. Clique em "Consultar Histórico" para atualizar a lista.
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  const sorted = Array.from(pipelines.values()).reverse();

  sorted.forEach((group) => {
    const card = createPipelineCard(group);
    container.appendChild(card);
  });
}

function createPipelineCard(group) {
  const card = document.createElement('div');
  card.className = 'pipeline-card';

  const isCompleted = group.status === 'COMPLETED';
  const statusBadge = isCompleted
    ? '<span class="badge badge-success">COMPLETED</span>'
    : '<span class="badge badge-progress">IN_PROGRESS</span>';

  card.innerHTML = `
    <div class="pipeline-header">
      <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-weight: 700; font-size: 16px; color: #1e293b;">
          Pipeline :: <code style="background: #e2e8f0; padding: 2px 8px; border-radius: 4px;">${group.field_key || 'campo'}</code>
        </span>
        ${statusBadge}
      </div>
      <div style="display: flex; align-items: center; gap: 16px; font-size: 14px; font-family: monospace;">
        <span>Duração: <strong>${group.total_duration_ms.toFixed(1)} ms</strong></span>
        <span>Custo: <strong style="color: var(--warning);">$${group.total_cost.toFixed(6)}</strong></span>
        <span style="color: var(--text-muted);" title="${group.correlation_id}">ID: ${group.correlation_id.substring(0, 8)}...</span>
      </div>
    </div>
  `;

  const stepsBody = document.createElement('div');
  stepsBody.style.padding = '18px 20px';

  const steps = [...group.steps].sort((a, b) => a.step_order - b.step_order);
  if (steps.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'step-box';
    empty.style.color = 'var(--text-muted)';
    empty.textContent = 'Aguardando etapas da pré-avaliação...';
    stepsBody.appendChild(empty);
  }

  steps.forEach((s) => {
    const stepId = `step-${group.correlation_id}-${s.step_order}`;
    const stepBox = document.createElement('div');
    stepBox.className = 'step-box';
    const cost = (s.real_cost || s.simulated_cost || 0).toFixed(6);
    stepBox.innerHTML = `
      <div class="step-header">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="color: var(--success); font-weight: 700;">✔</span>
          <strong style="font-size: 14px; color: #1e293b;">${s.step_order}. ${s.step_name}</strong>
          <span style="font-size: 12px; color: var(--text-muted);">${s.field_key || ''}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 12px; font-size: 13px; font-family: monospace;">
          <span>${(s.step_duration_ms || 0).toFixed(1)} ms</span>
          <span style="color: var(--warning);">$${cost}</span>
          ${s.model_name ? `<span style="color: var(--text-muted);">${s.model_name}</span>` : ''}
          <button class="btn btn-sm btn-secondary" onclick="const e=document.getElementById('${stepId}');e.style.display=e.style.display==='none'?'grid':'none'">
            Ver Payloads
          </button>
        </div>
      </div>
      <div id="${stepId}" style="display: none; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);">
        <div>
          <span style="font-size: 12px; font-weight: 700; color: #475569;">Entrada (Input):</span>
          <pre class="payload-pre">${JSON.stringify(s.input_payload, null, 2)}</pre>
        </div>
        <div>
          <span style="font-size: 12px; font-weight: 700; color: #475569;">Saída (Output):</span>
          <pre class="payload-pre">${JSON.stringify(s.output_payload, null, 2)}</pre>
        </div>
      </div>
    `;
    stepsBody.appendChild(stepBox);
  });

  card.appendChild(stepsBody);
  return card;
}

function clearPipelines() {
  pipelines.clear();
  renderAllPipelines();
}

window.addEventListener('DOMContentLoaded', async () => {
  const user = await checkSession();
  if (user) {
    await loadInitialHistory();
  }
});
