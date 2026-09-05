/**
 * pi*VMA - Protótipos Spec 004: Submissão e Triagem
 * Integração com API Real FastAPI, Autenticação e Dev Inspector de JSONs
 */

// Histórico em memória de chamadas HTTP para desenvolvedores inspecionarem
window.apiInspectionLogs = [];

/**
 * Cliente HTTP para a API Real do PIVMA
 */
async function apiRequest(method, url, body = null) {
  const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const options = {
    method: method,
    headers: {
      "Content-Type": "application/json"
    },
    credentials: "include" // Importante: envia e recebe o cookie HttpOnly access_token
  };

  if (body !== null) {
    options.body = JSON.stringify(body);
  }

  const logEntry = {
    id: "log_" + Date.now() + "_" + Math.random().toString(36).substring(2, 6),
    timestamp,
    method,
    url,
    requestBody: body,
    status: null,
    statusText: null,
    responseBody: null,
    error: null
  };

  try {
    const response = await fetch(url, options);
    logEntry.status = response.status;
    logEntry.statusText = response.statusText;

    let responseData = null;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      responseData = await response.json();
    } else {
      const text = await response.text();
      responseData = text ? { raw: text } : null;
    }

    logEntry.responseBody = responseData;
    window.apiInspectionLogs.unshift(logEntry);
    updateDevInspectorUI();

    if (!response.ok) {
      const errMsg = (responseData && (responseData.detail || responseData.message)) || `HTTP ${response.status} ${response.statusText}`;
      return { ok: false, status: response.status, data: responseData, error: errMsg };
    }

    return { ok: true, status: response.status, data: responseData, error: null };
  } catch (err) {
    logEntry.status = 0;
    logEntry.statusText = "Network Error";
    logEntry.error = err.message;
    window.apiInspectionLogs.unshift(logEntry);
    updateDevInspectorUI();
    return { ok: false, status: 0, data: null, error: err.message };
  }
}

/**
 * Autenticação Real
 */
async function getCurrentUser() {
  const res = await apiRequest("GET", "/auth/me");
  if (res.ok) {
    window.currentUser = res.data;
    return res.data;
  }
  window.currentUser = null;
  return null;
}

async function performLogin(identifier, password) {
  const res = await apiRequest("POST", "/auth/login", {
    identifier: identifier.trim(),
    password: password
  });

  if (res.ok) {
    showToast("Autenticado com sucesso!", "success");
    await getCurrentUser();
    return { success: true };
  } else {
    showToast(`Falha no login: ${res.error}`, "error");
    return { success: false, error: res.error };
  }
}

async function performLogout() {
  await apiRequest("POST", "/auth/logout");
  window.currentUser = null;
  showToast("Sessão encerrada.", "info");
  window.location.reload();
}

/**
 * Gestão do Processo Selecionado
 */
function getSelectedProcessId() {
  const params = new URLSearchParams(window.location.search);
  const urlId = params.get("process_id");
  if (urlId) return urlId;
  return localStorage.getItem("pivma_004_selected_process_id") || null;
}

function setSelectedProcessId(id) {
  if (id) {
    localStorage.setItem("pivma_004_selected_process_id", id);
    const url = new URL(window.location);
    url.searchParams.set("process_id", id);
    window.history.replaceState({}, "", url);
  } else {
    localStorage.removeItem("pivma_004_selected_process_id");
    const url = new URL(window.location);
    url.searchParams.delete("process_id");
    window.history.replaceState({}, "", url);
  }
}

/**
 * Barra Superior Compartilhada
 */
async function setupSharedHeader(pageName) {
  const topNav = document.getElementById("sharedTopNav");
  const breadcrumb = document.getElementById("sharedBreadcrumb");

  // Breadcrumbs
  if (breadcrumb) {
    breadcrumb.innerHTML = `
      <a href="/demos/004/">Spec 004: Submissão e Triagem</a>
      ${pageName ? `<span>&rsaquo;</span> <strong>${pageName}</strong>` : ""}
    `;
  }

  if (!topNav) return;

  // Carrega usuário atual
  const userResp = await getCurrentUser();

  let userMetaHtml = "";
  if (userResp && userResp.user) {
    const roleName = (userResp.profiles && userResp.profiles[0]) ? userResp.profiles[0].name : "Autenticado";
    userMetaHtml = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-weight: 600;">${escapeHtml(userResp.user.full_name || userResp.user.username)}</span>
        <span class="badge" style="background-color: #ede9fe; color: #6d28d9; border-color: #ddd6fe;">${escapeHtml(roleName)}</span>
        <button onclick="performLogout()" class="btn btn-sm" title="Encerrar sessão na API">Sair</button>
      </div>
    `;
  } else {
    userMetaHtml = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="color: var(--color-danger); font-weight: 600;">Não autenticado</span>
        <button onclick="openLoginModal()" class="btn btn-sm btn-primary">Entrar (Login)</button>
      </div>
    `;
  }

  // Seletor de processos reais
  topNav.innerHTML = `
    <div class="top-nav-brand">
      <a href="/demos/004/">pi*VMA Demos</a>
      <span style="color: #94a3b8;">/</span>
      <span style="font-weight: 500;">Spec 004</span>
    </div>
    <div class="top-nav-meta">
      <div style="display: flex; align-items: center; gap: 6px;">
        <label style="font-weight: 600;">Processo Real:</label>
        <select id="headerProcessSelect" style="padding: 3px 6px; font-size: 12px; border: 1px solid #cbd5e1; border-radius: 3px; max-width: 240px;">
          <option value="">Carregando processos...</option>
        </select>
        <button onclick="openCreateProcessModal()" class="btn btn-sm" title="Criar nova instância de processo no banco">+ Novo</button>
      </div>
      ${userMetaHtml}
    </div>
  `;

  // Carrega os processos reais da API
  loadProcessListToHeader();

  // Injeta Modal de Login e Modal de Novo Processo se não existirem
  injectGlobalModals();

  // Injeta o Dev Inspector no final da página
  injectDevInspector();
}

async function loadProcessListToHeader() {
  const select = document.getElementById("headerProcessSelect");
  if (!select) return;

  const currentId = getSelectedProcessId();
  const res = await apiRequest("GET", "/processes?size=50");

  if (!res.ok) {
    select.innerHTML = `<option value="">Erro ao carregar processos (${res.status})</option>`;
    return;
  }

  const items = res.data.items || [];
  if (items.length === 0) {
    select.innerHTML = `<option value="">Nenhum processo no banco (clique em + Novo)</option>`;
    setSelectedProcessId(null);
    return;
  }

  select.innerHTML = items.map(p => `
    <option value="${p.id}" ${p.id === currentId ? "selected" : ""}>
      ${escapeHtml(p.code)} - ${escapeHtml(p.title)} (${p.status})
    </option>
  `).join("");

  // Se não havia selecionado ou o selecionado não existe na lista, seleciona o primeiro
  if (!currentId || !items.some(p => p.id === currentId)) {
    setSelectedProcessId(items[0].id);
    select.value = items[0].id;
  }

  select.addEventListener("change", (e) => {
    setSelectedProcessId(e.target.value);
    window.location.reload();
  });
}

/**
 * Modais Globais: Login e Novo Processo
 */
function injectGlobalModals() {
  if (document.getElementById("globalLoginModal")) return;

  const modalHtml = `
    <!-- Modal de Login -->
    <div id="globalLoginModal" class="modal-backdrop">
      <div class="modal">
        <div class="modal-header">
          <h3>Autenticar na API (POST /auth/login)</h3>
          <button onclick="closeLoginModal()" class="modal-close">&times;</button>
        </div>
        <form id="globalLoginForm" onsubmit="handleLoginFormSubmit(event)">
          <div class="form-group">
            <label class="form-label">E-mail ou Usuário:</label>
            <input type="text" id="loginEmailInput" class="form-control" required placeholder="ex.: helena.proponente@fiocruz.br" />
          </div>
          <div class="form-group">
            <label class="form-label">Senha:</label>
            <input type="password" id="loginPasswordInput" class="form-control" required value="Password123!" />
          </div>

          <div style="background-color: #f1f5f9; padding: 8px 10px; border-radius: 4px; font-size: 11px; margin-bottom: 12px;">
            <strong>Usuários de Teste do Banco:</strong>
            <div style="display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap;">
              <button type="button" onclick="fillLoginDemo('helena.proponente@fiocruz.br')" class="btn btn-sm">Helena (Proponente)</button>
              <button type="button" onclick="fillLoginDemo('carlos.gestor@bracvam.gov.br')" class="btn btn-sm">Carlos (Triador)</button>
              <button type="button" onclick="fillLoginDemo('admin@bracvam.gov.br')" class="btn btn-sm">Admin</button>
            </div>
          </div>

          <div class="modal-footer">
            <button type="button" onclick="closeLoginModal()" class="btn">Cancelar</button>
            <button type="submit" class="btn btn-primary">Entrar</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Modal de Criação de Processo -->
    <div id="globalCreateProcessModal" class="modal-backdrop">
      <div class="modal">
        <div class="modal-header">
          <h3>Instanciar Novo Processo (POST /processes)</h3>
          <button onclick="closeCreateProcessModal()" class="modal-close">&times;</button>
        </div>
        <form id="globalCreateProcessForm" onsubmit="handleCreateProcessSubmit(event)">
          <div class="form-group">
            <label class="form-label">Template de Processo:</label>
            <input type="text" id="newProcTemplateKey" class="form-control" readonly value="full_validation" style="font-family: var(--font-mono); background-color: #f1f5f9;" />
          </div>
          <div class="form-group">
            <label class="form-label">Título da Proposta de Validação <span class="req">*</span>:</label>
            <input type="text" id="newProcTitle" class="form-control" required placeholder="Ex.: Método HET-CAM de Irritação Corneana" />
          </div>
          <div class="modal-footer">
            <button type="button" onclick="closeCreateProcessModal()" class="btn">Cancelar</button>
            <button type="submit" class="btn btn-primary">Criar Processo no Banco</button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHtml);
}

function openLoginModal() {
  document.getElementById("globalLoginModal").classList.add("active");
}
function closeLoginModal() {
  document.getElementById("globalLoginModal").classList.remove("active");
}
function fillLoginDemo(email) {
  document.getElementById("loginEmailInput").value = email;
  document.getElementById("loginPasswordInput").value = "Password123!";
}
async function handleLoginFormSubmit(e) {
  e.preventDefault();
  const id = document.getElementById("loginEmailInput").value;
  const pw = document.getElementById("loginPasswordInput").value;
  const res = await performLogin(id, pw);
  if (res.success) {
    closeLoginModal();
    window.location.reload();
  }
}

function openCreateProcessModal() {
  document.getElementById("globalCreateProcessModal").classList.add("active");
}
function closeCreateProcessModal() {
  document.getElementById("globalCreateProcessModal").classList.remove("active");
}
async function handleCreateProcessSubmit(e) {
  e.preventDefault();
  const title = document.getElementById("newProcTitle").value.trim();
  const res = await apiRequest("POST", "/processes", {
    template_key: "full_validation",
    title: title
  });

  if (res.ok) {
    showToast(`Processo ${res.data.code} criado com sucesso!`, "success");
    setSelectedProcessId(res.data.id);
    closeCreateProcessModal();
    window.location.reload();
  } else {
    showToast(`Erro ao criar processo: ${res.error}`, "error");
  }
}

/**
 * Dev Inspector: Visualizador de Requisições e Respostas JSON
 */
function injectDevInspector() {
  if (document.getElementById("devInspectorContainer")) return;

  const inspectorHtml = `
    <div class="container" style="margin-top: 40px;">
      <div id="devInspectorContainer" class="dev-inspector">
        <div class="dev-inspector-header" onclick="toggleDevInspector()">
          <h4>
            <span>&bull;&bull;&bull;</span> Dev Inspector: Requisições & Respostas da API Real
          </h4>
          <span id="devInspectorCountBadge" class="badge" style="background-color: #334155; color: #94a3b8; font-size: 11px;">
            0 chamadas
          </span>
        </div>
        <div id="devInspectorBody" class="dev-inspector-body" style="display: block;">
          <div id="devInspectorContent">
            <p style="color: #64748b; font-style: italic;">Nenhuma requisição realizada ainda nesta tela.</p>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", inspectorHtml);
  updateDevInspectorUI();
}

function toggleDevInspector() {
  const body = document.getElementById("devInspectorBody");
  if (body) {
    body.style.display = (body.style.display === "none") ? "block" : "none";
  }
}

function updateDevInspectorUI() {
  const container = document.getElementById("devInspectorContent");
  const countBadge = document.getElementById("devInspectorCountBadge");
  if (!container) return;

  const logs = window.apiInspectionLogs || [];
  if (countBadge) {
    countBadge.textContent = `${logs.length} chamada${logs.length === 1 ? '' : 's'}`;
  }

  if (logs.length === 0) {
    container.innerHTML = `<p style="color: #64748b; font-style: italic;">Nenhuma requisição realizada ainda nesta tela.</p>`;
    return;
  }

  container.innerHTML = logs.map(log => {
    const statusClass = log.status >= 200 && log.status < 300 ? 'status-2xx' : 'status-4xx';
    const reqJson = log.requestBody !== null ? JSON.stringify(log.requestBody, null, 2) : "Sem corpo (Payload vazio)";
    const resJson = log.responseBody !== null ? JSON.stringify(log.responseBody, null, 2) : "Sem corpo na resposta";

    return `
      <div class="dev-call-item">
        <div class="dev-call-summary" onclick="toggleCallDetails('${log.id}')">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="method method-${log.method}">${log.method}</span>
            <code style="font-family: var(--font-mono); color: #e2e8f0; font-size: 11px;">${escapeHtml(log.url)}</code>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="${statusClass}">${log.status} ${log.statusText || ''}</span>
            <span style="color: #64748b; font-size: 11px;">${log.timestamp}</span>
          </div>
        </div>
        <div id="details_${log.id}" class="dev-call-details" style="display: block;">
          <div>
            <div class="dev-json-title">
              <span>Request Payload (Enviado):</span>
              <button onclick="copyToClipboard('${log.id}_req')" class="btn btn-sm" style="padding: 1px 5px; font-size: 10px;">Copiar</button>
            </div>
            <pre id="${log.id}_req" class="dev-json-box">${escapeHtml(reqJson)}</pre>
          </div>
          <div>
            <div class="dev-json-title">
              <span>Response Payload (Recebido):</span>
              <button onclick="copyToClipboard('${log.id}_res')" class="btn btn-sm" style="padding: 1px 5px; font-size: 10px;">Copiar</button>
            </div>
            <pre id="${log.id}_res" class="dev-json-box">${escapeHtml(resJson)}</pre>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

function toggleCallDetails(id) {
  const el = document.getElementById("details_" + id);
  if (el) {
    el.style.display = (el.style.display === "none") ? "grid" : "none";
  }
}

function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (el) {
    navigator.clipboard.writeText(el.textContent);
    showToast("JSON copiado para a área de transferência!", "info");
  }
}

function showToast(message, type = "info") {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[m]);
}
