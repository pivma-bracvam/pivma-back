let eventSource = null;
let events = [];

const tokenInput = document.getElementById('adminToken');
const btnConnect = document.getElementById('btnConnect');
const btnClear = document.getElementById('btnClear');
const filterStatus = document.getElementById('filterStatus');
const statusBadge = document.getElementById('connectionStatus');
const tableBody = document.getElementById('eventsTableBody');
const eventCount = document.getElementById('eventCount');
const emptyRow = document.getElementById('emptyRow');

// Recuperar token prévio se salvo
if (localStorage.getItem('pivma_admin_token')) {
  tokenInput.value = localStorage.getItem('pivma_admin_token');
}

function updateConnectionStatus(connected, message) {
  if (connected) {
    statusBadge.className = 'flex items-center space-x-2 text-sm text-emerald-400';
    statusBadge.innerHTML = `<span class="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></span><span>Conectado</span>`;
    btnConnect.textContent = 'Desconectar';
    btnConnect.className = 'bg-rose-500 hover:bg-rose-600 text-white font-semibold px-4 py-1.5 rounded text-sm transition';
  } else {
    statusBadge.className = 'flex items-center space-x-2 text-sm text-yellow-400';
    statusBadge.innerHTML = `<span class="w-3 h-3 rounded-full bg-yellow-400"></span><span>${message || 'Desconectado'}</span>`;
    btnConnect.textContent = 'Conectar Stream';
    btnConnect.className = 'bg-teal-500 hover:bg-teal-600 text-slate-950 font-semibold px-4 py-1.5 rounded text-sm transition';
  }
}

async function loadInitialHistory(token) {
  try {
    const res = await fetch('/admin/logs/operational?limit=50', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    if (res.ok) {
      const data = await res.json();
      data.reverse().forEach(ev => appendEvent(ev));
    }
  } catch (err) {
    console.warn('Não foi possível carregar histórico inicial:', err);
  }
}

function appendEvent(ev) {
  if (emptyRow && emptyRow.parentNode) {
    emptyRow.remove();
  }

  events.unshift(ev);
  eventCount.textContent = events.length;

  renderRows();
}

function renderRows() {
  const currentFilter = filterStatus.value;
  const filtered = events.filter(e => !currentFilter || e.status === currentFilter);

  tableBody.innerHTML = '';
  if (filtered.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="6" class="p-6 text-center text-slate-500">Nenhum evento correspondente ao filtro.</td></tr>`;
    return;
  }

  filtered.forEach((ev, idx) => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-750 transition border-b border-slate-700/50';

    const isSuccess = ev.status === 'SUCCESS';
    const statusBg = isSuccess ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' : 'bg-rose-500/20 text-rose-400 border-rose-500/40';

    const formattedTime = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString('pt-BR') : '-';
    const duration = ev.total_duration_ms ? `${ev.total_duration_ms.toFixed(1)} ms` : '-';

    tr.innerHTML = `
      <td class="p-3 text-slate-300 font-mono text-xs">${formattedTime}</td>
      <td class="p-3 font-semibold text-teal-300">${ev.operation_type || 'N/A'}</td>
      <td class="p-3">
        <span class="px-2 py-0.5 rounded text-xs font-medium border ${statusBg}">
          ${ev.status}
        </span>
      </td>
      <td class="p-3 text-slate-300 font-mono text-xs">${duration}</td>
      <td class="p-3 font-mono text-xs text-slate-400" title="${ev.correlation_id}">
        ${ev.correlation_id ? ev.correlation_id.substring(0, 8) + '...' : '-'}
      </td>
      <td class="p-3">
        <button onclick="toggleDetails(${idx})" class="text-xs text-teal-400 hover:underline">Ver JSON</button>
      </td>
    `;

    const detailTr = document.createElement('tr');
    detailTr.id = `detail-${idx}`;
    detailTr.className = 'hidden bg-slate-950/80';
    detailTr.innerHTML = `
      <td colspan="6" class="p-4 font-mono text-xs text-slate-300">
        <pre class="bg-slate-900 p-3 rounded border border-slate-700 overflow-x-auto">${JSON.stringify(ev, null, 2)}</pre>
      </td>
    `;

    tableBody.appendChild(tr);
    tableBody.appendChild(detailTr);
  });
}

window.toggleDetails = function(idx) {
  const el = document.getElementById(`detail-${idx}`);
  if (el) {
    el.classList.toggle('hidden');
  }
};

function connectStream() {
  const token = tokenInput.value.trim();
  if (!token) {
    alert('Por favor, informe o Token de Administrador.');
    return;
  }

  localStorage.setItem('pivma_admin_token', token);

  if (eventSource) {
    eventSource.close();
    eventSource = null;
    updateConnectionStatus(false, 'Desconectado');
    return;
  }

  loadInitialHistory(token);

  // Conectar SSE via endpoint administrativo passando token como query param
  const sseUrl = `/admin/logs/operational/stream?token=${encodeURIComponent(token)}`;
  eventSource = new EventSource(sseUrl);

  eventSource.onopen = () => {
    updateConnectionStatus(true);
  };

  eventSource.onmessage = (e) => {
    if (!e.data || e.data.startsWith(':')) return;
    try {
      const data = JSON.parse(e.data);
      appendEvent(data);
    } catch (err) {
      console.error('Erro ao processar mensagem SSE:', err);
    }
  };

  eventSource.onerror = () => {
    updateConnectionStatus(false, 'Erro de Conexão');
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };
}

btnConnect.addEventListener('click', connectStream);
btnClear.addEventListener('click', () => {
  events = [];
  eventCount.textContent = '0';
  renderRows();
});
filterStatus.addEventListener('change', renderRows);
