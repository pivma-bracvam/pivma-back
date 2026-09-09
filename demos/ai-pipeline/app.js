let eventSource = null;
const pipelines = new Map(); // correlation_id -> group data

const tokenInput = document.getElementById('adminToken');
const formInstanceInput = document.getElementById('formInstanceId');
const btnConnect = document.getElementById('btnConnect');
const btnClear = document.getElementById('btnClear');
const btnTriggerEval = document.getElementById('btnTriggerEval');
const triggerFeedback = document.getElementById('triggerFeedback');
const statusBadge = document.getElementById('connectionStatus');
const container = document.getElementById('pipelinesContainer');
const pipelineCount = document.getElementById('pipelineCount');
const emptyMessage = document.getElementById('emptyMessage');

// Carregar valores salvos do localStorage
if (localStorage.getItem('pivma_admin_token')) {
  tokenInput.value = localStorage.getItem('pivma_admin_token');
}
if (localStorage.getItem('pivma_demo_form_instance_id')) {
  formInstanceInput.value = localStorage.getItem('pivma_demo_form_instance_id');
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
    btnConnect.className = 'bg-indigo-500 hover:bg-indigo-600 text-white font-semibold px-4 py-1.5 rounded text-sm transition';
  }
}

async function loadInitialHistory(token) {
  try {
    const res = await fetch('/admin/logs/ai?limit=20', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) {
      const groups = await res.json();
      groups.forEach(g => {
        pipelines.set(g.correlation_id, g);
      });
      renderAllPipelines();
    }
  } catch (err) {
    console.warn('Erro ao carregar histórico inicial:', err);
  }
}

function handleIncomingStep(step) {
  if (emptyMessage && emptyMessage.parentNode) {
    emptyMessage.remove();
  }

  const cid = step.correlation_id;
  if (!pipelines.has(cid)) {
    pipelines.set(cid, {
      correlation_id: cid,
      field_key: step.field_key,
      pipeline_name: step.pipeline_name,
      status: 'IN_PROGRESS',
      total_duration_ms: 0,
      total_cost: 0,
      steps: [],
      verdict: null
    });
  }

  const group = pipelines.get(cid);
  // Evitar duplicatas da mesma etapa
  const existingIndex = group.steps.findIndex(s => s.step_order === step.step_order);
  if (existingIndex >= 0) {
    group.steps[existingIndex] = step;
  } else {
    group.steps.push(step);
  }

  group.steps.sort((a, b) => a.step_order - b.step_order);
  group.total_duration_ms = group.steps.reduce((acc, s) => acc + (s.step_duration_ms || 0), 0);
  group.total_cost = group.steps.reduce((acc, s) => acc + (s.simulated_cost || 0), 0);

  // Se a etapa 3 tiver o veredito, extrair
  if (step.step_name === 'verdict_synthesis' && step.output_payload && step.output_payload.verdict) {
    group.verdict = step.output_payload.verdict;
    group.status = 'COMPLETED';
  }

  renderAllPipelines();
}

function renderAllPipelines() {
  pipelineCount.textContent = pipelines.size;
  container.innerHTML = '';

  if (pipelines.size === 0) {
    container.appendChild(emptyMessage);
    return;
  }

  // Converter para array e ordenar pelos mais recentes
  const sorted = Array.from(pipelines.values()).reverse();

  sorted.forEach(group => {
    const card = createPipelineCard(group);
    container.appendChild(card);
  });
}

function createPipelineCard(group) {
  const card = document.createElement('div');
  card.className = 'bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-lg transition';

  const isCompleted = group.status === 'COMPLETED';
  const statusColor = isCompleted ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40' : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40';

  // Cabeçalho do Card
  card.innerHTML = `
    <div class="bg-slate-850 p-4 border-b border-slate-700 flex flex-wrap justify-between items-center gap-3">
      <div class="flex items-center space-x-3">
        <span class="w-3 h-3 rounded-full ${isCompleted ? 'bg-emerald-400' : 'bg-yellow-400 animate-pulse'}"></span>
        <h3 class="font-bold text-white font-mono text-sm">Pipeline :: ${group.field_key || 'campo'}</h3>
        <span class="text-xs px-2.5 py-0.5 rounded border ${statusColor} font-medium">${group.status}</span>
      </div>
      <div class="flex items-center space-x-4 text-xs font-mono text-slate-300">
        <span>Duração: <strong class="text-teal-300">${group.total_duration_ms.toFixed(1)} ms</strong></span>
        <span>Custo: <strong class="text-amber-300">$${group.total_cost.toFixed(6)}</strong></span>
        <span class="text-slate-500">ID: ${group.correlation_id.substring(0, 8)}...</span>
      </div>
    </div>
  `;

  // Corpo das 3 Etapas Sequenciais
  const stepsBody = document.createElement('div');
  stepsBody.className = 'p-5 space-y-4';

  const stepNames = [
    { order: 1, name: 'context_extraction', label: '1. Extração de Contexto' },
    { order: 2, name: 'mock_evaluation', label: '2. Avaliação de Conformidade (Mock)' },
    { order: 3, name: 'verdict_synthesis', label: '3. Síntese do Veredito' }
  ];

  stepNames.forEach(def => {
    const executedStep = group.steps.find(s => s.step_order === def.order);
    const stepCard = document.createElement('div');
    stepCard.className = 'bg-slate-900/90 rounded-lg p-3.5 border border-slate-700/80';

    if (executedStep) {
      const stepId = `step-${group.correlation_id}-${def.order}`;
      stepCard.innerHTML = `
        <div class="flex justify-between items-center">
          <div class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full bg-teal-400"></span>
            <span class="font-semibold text-xs text-slate-200">${def.label}</span>
          </div>
          <div class="flex items-center space-x-3 text-xs font-mono">
            <span class="text-slate-400">${executedStep.step_duration_ms.toFixed(1)} ms</span>
            <span class="text-amber-400/90">$${executedStep.simulated_cost.toFixed(6)}</span>
            <button onclick="document.getElementById('${stepId}').classList.toggle('hidden')" 
                    class="text-xs text-indigo-400 hover:text-indigo-300 underline">
              Payloads
            </button>
          </div>
        </div>
        <div id="${stepId}" class="hidden mt-3 pt-3 border-t border-slate-800 text-xs font-mono grid md:grid-cols-2 gap-3">
          <div>
            <span class="text-slate-400 font-bold block mb-1">Entrada (Input):</span>
            <pre class="bg-slate-950 p-2 rounded text-slate-300 overflow-x-auto max-h-40 border border-slate-800">${JSON.stringify(executedStep.input_payload, null, 2)}</pre>
          </div>
          <div>
            <span class="text-slate-400 font-bold block mb-1">Saída (Output):</span>
            <pre class="bg-slate-950 p-2 rounded text-teal-300 overflow-x-auto max-h-40 border border-slate-800">${JSON.stringify(executedStep.output_payload, null, 2)}</pre>
          </div>
        </div>
      `;
    } else {
      stepCard.innerHTML = `
        <div class="flex justify-between items-center text-slate-500">
          <div class="flex items-center space-x-2">
            <span class="w-2 h-2 rounded-full bg-slate-600"></span>
            <span class="text-xs">${def.label}</span>
          </div>
          <span class="text-xs italic">Aguardando execução...</span>
        </div>
      `;
    }
    stepsBody.appendChild(stepCard);
  });

  // Veredito Canônico Final (se houver)
  if (group.verdict) {
    const v = group.verdict;
    const verdictDiv = document.createElement('div');
    verdictDiv.className = 'mt-4 p-4 rounded-lg bg-rose-950/30 border border-rose-800/40 text-sm space-y-2';
    verdictDiv.innerHTML = `
      <div class="flex justify-between items-center">
        <span class="font-bold text-rose-300 flex items-center space-x-1.5">
          <span>❌ Veredito Canônico:</span>
          <span class="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs">${v.status}</span>
        </span>
        <span class="text-xs font-mono text-slate-400">Score de Confiança: ${(v.confidence_score * 100).toFixed(0)}%</span>
      </div>
      <div>
        <span class="text-xs font-semibold text-rose-300 block">Inconformidades Simuladas:</span>
        <ul class="list-disc list-inside text-xs text-slate-300 space-y-0.5 pl-1">
          ${v.issues.map(iss => `<li>${iss}</li>`).join('')}
        </ul>
      </div>
      <div class="pt-2 border-t border-rose-900/40">
        <span class="text-xs font-semibold text-emerald-300 block">Recomendações:</span>
        <ul class="list-disc list-inside text-xs text-slate-300 space-y-0.5 pl-1">
          ${v.recommendations.map(rec => `<li>${rec}</li>`).join('')}
        </ul>
      </div>
    `;
    stepsBody.appendChild(verdictDiv);
  }

  card.appendChild(stepsBody);
  return card;
}

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

  const sseUrl = `/admin/logs/ai/stream?token=${encodeURIComponent(token)}`;
  eventSource = new EventSource(sseUrl);

  eventSource.onopen = () => {
    updateConnectionStatus(true);
  };

  eventSource.onmessage = (e) => {
    if (!e.data || e.data.startsWith(':')) return;
    try {
      const step = JSON.parse(e.data);
      handleIncomingStep(step);
    } catch (err) {
      console.error('Erro ao processar etapa SSE:', err);
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

async function triggerEvaluation() {
  const token = tokenInput.value.trim();
  const formInstId = formInstanceInput.value.trim();

  if (!token) {
    alert('Por favor, informe o Token de Administrador.');
    return;
  }
  if (!formInstId) {
    alert('Por favor, informe o Form Instance ID.');
    return;
  }

  localStorage.setItem('pivma_demo_form_instance_id', formInstId);
  triggerFeedback.textContent = 'Disparando avaliação...';
  triggerFeedback.className = 'text-xs text-yellow-400 ml-2';

  try {
    const res = await fetch(`/forms/instances/${formInstId}/evaluate-ai`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (res.ok) {
      const data = await res.json();
      triggerFeedback.textContent = `Avaliação concluída! ${data.evaluations.length} campo(s) avaliados.`;
      triggerFeedback.className = 'text-xs text-emerald-400 ml-2';
    } else {
      const err = await res.json();
      triggerFeedback.textContent = `Erro: ${err.detail || res.statusText}`;
      triggerFeedback.className = 'text-xs text-rose-400 ml-2';
    }
  } catch (err) {
    triggerFeedback.textContent = `Falha na requisição: ${err.message}`;
    triggerFeedback.className = 'text-xs text-rose-400 ml-2';
  }
}

btnConnect.addEventListener('click', connectStream);
btnTriggerEval.addEventListener('click', triggerEvaluation);
btnClear.addEventListener('click', () => {
  pipelines.clear();
  renderAllPipelines();
});
