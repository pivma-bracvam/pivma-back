/**
 * pi*VMA - Protótipo Interativo de Modelagem, Preenchimento e Triagem de Formulários
 */

// Estado global da aplicação
const state = {
  currentUser: {
    username: "admin",
    name: "Administrador Geral",
    email: "admin@bracvam.gov.br",
    role: "administrator",
    roleName: "Administrador"
  },
  users: [
    {
      username: "admin",
      name: "Administrador Geral",
      email: "admin@bracvam.gov.br",
      role: "administrator",
      roleName: "Administrador"
    },
    {
      username: "helena.souza",
      name: "Dra. Helena Souza",
      email: "helena.proponente@fiocruz.br",
      role: "proponent",
      roleName: "Proponente"
    },
    {
      username: "carlos.mendes",
      name: "Dr. Carlos Mendes",
      email: "carlos.gestor@bracvam.gov.br",
      role: "management_group",
      roleName: "Grupo Gestor / Triador BraCVAM"
    },
    {
      username: "roberto.silva",
      name: "Dr. Roberto Silva",
      email: "avaliador.adhoc@fiocruz.br",
      role: "ad_hoc_evaluator",
      roleName: "Avaliador Ad Hoc"
    }
  ],
  formSchema: JSON.parse(JSON.stringify(window.DEFAULT_FORM_TEMPLATE || {})),
  process: {
    id: "proc-" + Math.random().toString(36).substring(2, 9),
    code: "BRA-2026-001",
    title: "Validação do Método de Irritação Corneana HET-CAM",
    status: "DRAFT", // DRAFT, SUBMITTED, IN_DILIGENCE, APPROVED, REJECTED
    runNumber: 1,
    submittedAt: null,
    submittedBy: null
  },
  formData: {
    method_title: "Ensaio HET-CAM para Irritação / Corrosão Ocular",
    endpoint_target: "ocular_irritation",
    scientific_justification: "O método de ensaio da membrana corioalantoide do ovo embrionado de galinha (HET-CAM) é uma alternativa robusta e mecanicista ao ensaio de Draize em coelhos (OECD TG 405), reduzindo integralmente o uso de animais sencientes.",
    expected_laboratories_count: 4,
    study_protocol_file: "POP_HET_CAM_Protocolo_v2.1.pdf"
  },
  fieldReviews: {}, // key: { status: 'OK' | 'NEEDS_REVISION' | 'PROBLEM', comment: string }
  triageDecision: null, // { outcome: 'APPROVED' | 'DILIGENCE' | 'REJECTED', notes: string, score: string }
  timeline: [
    {
      timestamp: new Date().toLocaleTimeString(),
      event: "PROCESSO_INICIALIZADO",
      actor: "Sistema",
      description: "Processo instanciado a partir do template de Validação Completa (v1)."
    }
  ]
};

// =========================================================================
// Inicialização e Renderização
// =========================================================================

document.addEventListener("DOMContentLoaded", () => {
  initProfileSelector();
  renderFormBuilder();
  renderFormFilling();
  renderTriageReview();
  renderTimeline();
  updateProcessStatusBadge();
});

// =========================================================================
// Gestão de Perfis e Usuário
// =========================================================================

function initProfileSelector() {
  const select = document.getElementById("profileSelector");
  if (!select) return;
  select.innerHTML = "";
  state.users.forEach((user) => {
    const opt = document.createElement("option");
    opt.value = user.username;
    opt.textContent = `${user.name} (${user.roleName})`;
    if (user.username === state.currentUser.username) opt.selected = true;
    select.appendChild(opt);
  });

  select.addEventListener("change", (e) => {
    const found = state.users.find((u) => u.username === e.target.value);
    if (found) {
      state.currentUser = found;
      showToast(`Perfil alterado para: ${found.name} (${found.roleName})`, "info");
      updateUIForRole();
    }
  });

  updateUIForRole();
}

function updateUIForRole() {
  const roleBadge = document.getElementById("currentRoleBadge");
  if (roleBadge) {
    roleBadge.textContent = state.currentUser.roleName;
  }
}

// =========================================================================
// SESSÃO 1: Form Builder (Modelador de Formulário)
// =========================================================================

function renderFormBuilder() {
  const container = document.getElementById("builderFieldsList");
  if (!container) return;
  container.innerHTML = "";

  const fields = state.formSchema.fields || [];

  if (fields.length === 0) {
    container.innerHTML = `
      <div class="p-8 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-dashed border-slate-700">
        <i class="fa-solid fa-folder-open text-3xl mb-2 text-slate-500"></i>
        <p>Nenhum campo adicionado a este formulário ainda.</p>
      </div>`;
    return;
  }

  fields.forEach((field, index) => {
    const typeLabels = {
      text: "Texto Curto",
      textarea: "Texto Longo / Parágrafo",
      select: "Seleção Única (Dropdown)",
      integer: "Número Inteiro",
      float: "Número Decimal",
      boolean: "Sim / Não (Booleano)",
      date: "Data",
      file_upload: "Upload de Arquivo (PDF/Docs)"
    };

    const typeIcons = {
      text: "fa-font",
      textarea: "fa-paragraph",
      select: "fa-list-ul",
      integer: "fa-hashtag",
      float: "fa-calculator",
      boolean: "fa-toggle-on",
      date: "fa-calendar",
      file_upload: "fa-file-arrow-up"
    };

    const card = document.createElement("div");
    card.className =
      "p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4";

    card.innerHTML = `
      <div class="flex items-start gap-3">
        <div class="w-8 h-8 rounded-lg bg-slate-800 text-teal-400 flex items-center justify-center text-sm mt-0.5">
          <i class="fa-solid ${typeIcons[field.field_type] || "fa-cube"}"></i>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-white">${field.label}</span>
            <span class="font-mono text-[11px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">${field.field_key}</span>
            ${
              field.is_required
                ? '<span class="text-[10px] uppercase font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">Obrigatório</span>'
                : '<span class="text-[10px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">Opcional</span>'
            }
          </div>
          <p class="text-xs text-slate-400 mt-1">${field.help_text || "Sem texto de orientação"}</p>
          <div class="text-[11px] text-teal-400/80 mt-1 flex items-center gap-2">
            <span>Tipo: <strong>${typeLabels[field.field_type] || field.field_type}</strong></span>
            ${field.options && field.options.length ? `<span>&bull; ${field.options.length} opções configuradas</span>` : ""}
          </div>
        </div>
      </div>
      <div class="flex items-center gap-1 self-end sm:self-center">
        <button onclick="moveField(${index}, -1)" ${index === 0 ? "disabled" : ""} class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed">
          <i class="fa-solid fa-arrow-up text-xs"></i>
        </button>
        <button onclick="moveField(${index}, 1)" ${index === fields.length - 1 ? "disabled" : ""} class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed">
          <i class="fa-solid fa-arrow-down text-xs"></i>
        </button>
        <button onclick="editField('${field.id}')" class="p-2 rounded-lg text-teal-400 hover:text-teal-300 hover:bg-teal-500/10">
          <i class="fa-solid fa-pen-to-square text-xs"></i>
        </button>
        <button onclick="deleteField('${field.id}')" class="p-2 rounded-lg text-rose-400 hover:text-rose-300 hover:bg-rose-500/10">
          <i class="fa-solid fa-trash text-xs"></i>
        </button>
      </div>
    `;

    container.appendChild(card);
  });
}

function moveField(index, direction) {
  const targetIndex = index + direction;
  if (targetIndex < 0 || targetIndex >= state.formSchema.fields.length) return;
  const temp = state.formSchema.fields[index];
  state.formSchema.fields[index] = state.formSchema.fields[targetIndex];
  state.formSchema.fields[targetIndex] = temp;
  renderFormBuilder();
  renderFormFilling();
  renderTriageReview();
}

function deleteField(fieldId) {
  if (confirm("Tem certeza que deseja remover este campo da estrutura do formulário?")) {
    state.formSchema.fields = state.formSchema.fields.filter((f) => f.id !== fieldId);
    renderFormBuilder();
    renderFormFilling();
    renderTriageReview();
    showToast("Campo removido com sucesso.", "info");
  }
}

function openFieldModal(fieldToEdit = null) {
  const modal = document.getElementById("fieldModal");
  const form = document.getElementById("fieldEditForm");
  if (!modal || !form) return;

  form.reset();
  document.getElementById("optionsContainer").classList.add("hidden");

  if (fieldToEdit) {
    document.getElementById("modalTitle").textContent = "Editar Campo do Formulário";
    document.getElementById("modalFieldId").value = fieldToEdit.id;
    document.getElementById("fldKey").value = fieldToEdit.field_key;
    document.getElementById("fldLabel").value = fieldToEdit.label;
    document.getElementById("fldType").value = fieldToEdit.field_type;
    document.getElementById("fldHelp").value = fieldToEdit.help_text || "";
    document.getElementById("fldRequired").checked = !!fieldToEdit.is_required;

    if (fieldToEdit.field_type === "select" && fieldToEdit.options) {
      document.getElementById("optionsContainer").classList.remove("hidden");
      document.getElementById("fldOptions").value = fieldToEdit.options
        .map((o) => `${o.value}:${o.label}`)
        .join("\n");
    }
  } else {
    document.getElementById("modalTitle").textContent = "Adicionar Novo Campo";
    document.getElementById("modalFieldId").value = "";
    document.getElementById("fldRequired").checked = true;
  }

  modal.classList.remove("hidden");
}

function closeFieldModal() {
  const modal = document.getElementById("fieldModal");
  if (modal) modal.classList.add("hidden");
}

function handleFieldTypeChange(type) {
  const optContainer = document.getElementById("optionsContainer");
  if (type === "select") {
    optContainer.classList.remove("hidden");
  } else {
    optContainer.classList.add("hidden");
  }
}

function saveFieldModal(event) {
  event.preventDefault();
  const id = document.getElementById("modalFieldId").value;
  const key = document.getElementById("fldKey").value.trim().toLowerCase().replace(/\s+/g, "_");
  const label = document.getElementById("fldLabel").value.trim();
  const type = document.getElementById("fldType").value;
  const help = document.getElementById("fldHelp").value.trim();
  const required = document.getElementById("fldRequired").checked;
  const optionsRaw = document.getElementById("fldOptions").value.trim();

  let options = [];
  if (type === "select" && optionsRaw) {
    options = optionsRaw
      .split("\n")
      .map((line) => {
        const parts = line.split(":");
        return {
          value: (parts[0] || "").trim(),
          label: (parts[1] || parts[0] || "").trim()
        };
      })
      .filter((o) => o.value);
  }

  if (id) {
    // Edit existing
    const fld = state.formSchema.fields.find((f) => f.id === id);
    if (fld) {
      fld.field_key = key;
      fld.label = label;
      fld.field_type = type;
      fld.help_text = help;
      fld.is_required = required;
      fld.options = options;
    }
  } else {
    // Add new
    const newField = {
      id: "fld_" + Date.now(),
      field_key: key,
      label: label,
      field_type: type,
      help_text: help,
      is_required: required,
      order_index: state.formSchema.fields.length + 1,
      options: options,
      validation_rules: {}
    };
    state.formSchema.fields.push(newField);
  }

  closeFieldModal();
  renderFormBuilder();
  renderFormFilling();
  renderTriageReview();
  showToast("Estrutura do formulário atualizada e sincronizada!", "success");
}

function editField(fieldId) {
  const fld = state.formSchema.fields.find((f) => f.id === fieldId);
  if (fld) openFieldModal(fld);
}

function saveSchemaChanges() {
  showToast("Estrutura do formulário persistida com sucesso na versão local.", "success");
  addTimelineEvent("TEMPLATE_MODIFIED", "Administrador", "Esquema e campos do formulário atualizados.");
}

// =========================================================================
// SESSÃO 2: Preenchimento Dinâmico (Proponente)
// =========================================================================

function renderFormFilling() {
  const container = document.getElementById("fillingFieldsContainer");
  if (!container) return;
  container.innerHTML = "";

  const isReadOnly = state.process.status === "SUBMITTED" || state.process.status === "APPROVED" || state.process.status === "REJECTED";

  const fields = state.formSchema.fields || [];

  fields.forEach((field) => {
    const val = state.formData[field.field_key] !== undefined ? state.formData[field.field_key] : "";
    const review = state.fieldReviews[field.field_key];

    const wrapper = document.createElement("div");
    wrapper.className = "p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 transition-all";

    // Se houver parecer/diligência sobre este campo
    let reviewAlert = "";
    if (review && review.status === "NEEDS_REVISION") {
      wrapper.classList.add("border-amber-500/50", "bg-amber-950/10");
      reviewAlert = `
        <div class="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-2">
          <i class="fa-solid fa-triangle-exclamation text-amber-400 mt-0.5"></i>
          <div>
            <strong>Apontamento do Triador:</strong> ${review.comment}
          </div>
        </div>
      `;
    }

    let inputHtml = "";
    const disabledAttr = isReadOnly ? "disabled" : "";

    switch (field.field_type) {
      case "textarea":
        inputHtml = `
          <textarea
            id="input_${field.field_key}"
            rows="3"
            ${disabledAttr}
            onchange="handleInputChange('${field.field_key}', this.value)"
            class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white text-sm focus:border-teal-500 focus:outline-none disabled:opacity-60 disabled:bg-slate-900"
            placeholder="Digite aqui..."
          >${val}</textarea>
        `;
        break;

      case "select":
        const opts = (field.options || [])
          .map((o) => `<option value="${o.value}" ${val === o.value ? "selected" : ""}>${o.label}</option>`)
          .join("");
        inputHtml = `
          <select
            id="input_${field.field_key}"
            ${disabledAttr}
            onchange="handleInputChange('${field.field_key}', this.value)"
            class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white text-sm focus:border-teal-500 focus:outline-none disabled:opacity-60 disabled:bg-slate-900"
          >
            <option value="">Selecione uma opção...</option>
            ${opts}
          </select>
        `;
        break;

      case "integer":
      case "float":
        inputHtml = `
          <input
            type="number"
            id="input_${field.field_key}"
            value="${val}"
            ${disabledAttr}
            step="${field.field_type === "float" ? "0.01" : "1"}"
            onchange="handleInputChange('${field.field_key}', this.value)"
            class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white text-sm focus:border-teal-500 focus:outline-none disabled:opacity-60 disabled:bg-slate-900"
          />
        `;
        break;

      case "boolean":
        inputHtml = `
          <div class="flex items-center gap-3">
            <input
              type="checkbox"
              id="input_${field.field_key}"
              ${val ? "checked" : ""}
              ${disabledAttr}
              onchange="handleInputChange('${field.field_key}', this.checked)"
              class="w-5 h-5 rounded bg-slate-950 border-slate-700 text-teal-500 focus:ring-teal-500"
            />
            <label for="input_${field.field_key}" class="text-xs text-slate-300">Sim / Confirmado</label>
          </div>
        `;
        break;

      case "date":
        inputHtml = `
          <input
            type="date"
            id="input_${field.field_key}"
            value="${val}"
            ${disabledAttr}
            onchange="handleInputChange('${field.field_key}', this.value)"
            class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white text-sm focus:border-teal-500 focus:outline-none disabled:opacity-60 disabled:bg-slate-900"
          />
        `;
        break;

      case "file_upload":
        inputHtml = `
          <div class="flex items-center gap-3">
            <div class="flex-1 px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-300 flex items-center justify-between">
              <span class="truncate"><i class="fa-solid fa-file-pdf text-rose-400 mr-2"></i>${val || "Nenhum arquivo anexado"}</span>
              ${val ? '<span class="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded">Válido</span>' : ""}
            </div>
            ${
              !isReadOnly
                ? `
              <label class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold cursor-pointer border border-slate-700">
                <i class="fa-solid fa-upload mr-1"></i> Anexar
                <input type="file" class="hidden" onchange="handleFileUpload('${field.field_key}', this)" />
              </label>`
                : ""
            }
          </div>
        `;
        break;

      default: // text
        inputHtml = `
          <input
            type="text"
            id="input_${field.field_key}"
            value="${val}"
            ${disabledAttr}
            onchange="handleInputChange('${field.field_key}', this.value)"
            class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-700 text-white text-sm focus:border-teal-500 focus:outline-none disabled:opacity-60 disabled:bg-slate-900"
            placeholder="Digite aqui..."
          />
        `;
    }

    wrapper.innerHTML = `
      <div class="flex items-center justify-between">
        <label class="text-xs font-semibold text-white">
          ${field.label} ${field.is_required ? '<span class="text-amber-400">*</span>' : ""}
        </label>
        <span class="text-[10px] text-slate-400 font-mono">${field.field_key}</span>
      </div>
      ${field.help_text ? `<p class="text-[11px] text-slate-400">${field.help_text}</p>` : ""}
      ${reviewAlert}
      ${inputHtml}
    `;

    container.appendChild(wrapper);
  });

  const submitBtn = document.getElementById("btnSubmitProposal");
  const draftBtn = document.getElementById("btnSaveDraft");
  if (submitBtn) {
    if (isReadOnly) {
      submitBtn.disabled = true;
      submitBtn.classList.add("opacity-50", "cursor-not-allowed");
      submitBtn.innerHTML = '<i class="fa-solid fa-check mr-2"></i> Submetido para Triagem';
    } else {
      submitBtn.disabled = false;
      submitBtn.classList.remove("opacity-50", "cursor-not-allowed");
      submitBtn.innerHTML = '<i class="fa-solid fa-paper-plane mr-2"></i> Submeter Proposta (Dar OK)';
    }
  }
}

function handleInputChange(key, value) {
  state.formData[key] = value;
}

function handleFileUpload(key, input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    state.formData[key] = file.name;
    renderFormFilling();
    renderTriageReview();
    showToast(`Arquivo "${file.name}" anexado com sucesso!`, "success");
  }
}

function saveDraft() {
  showToast("Rascunho do formulário salvo com sucesso.", "info");
  addTimelineEvent("DRAFT_SAVED", state.currentUser.name, "Rascunho de preenchimento salvo.");
}

function submitProposal() {
  // Validar campos obrigatórios
  const missing = [];
  state.formSchema.fields.forEach((field) => {
    if (field.is_required) {
      const val = state.formData[field.field_key];
      if (val === undefined || val === null || val === "" || (typeof val === "string" && val.trim() === "")) {
        missing.push(field.label);
      }
    }
  });

  if (missing.length > 0) {
    showToast(`Preencha todos os campos obrigatórios: ${missing.join(", ")}`, "error");
    return;
  }

  state.process.status = "SUBMITTED";
  state.process.submittedAt = new Date().toLocaleString();
  state.process.submittedBy = state.currentUser.name;

  addTimelineEvent(
    "PROPOSAL_SUBMITTED",
    state.currentUser.name,
    `Proposta submetida formalmente (Execução #${state.process.runNumber}). Triagem desbloqueada.`
  );

  updateProcessStatusBadge();
  renderFormFilling();
  renderTriageReview();
  showToast("Proposta submetida com sucesso! A tarefa de Triagem foi liberada.", "success");

  // Rolar até a sessão 3 suavemente
  const triageSec = document.getElementById("sectionTriage");
  if (triageSec) triageSec.scrollIntoView({ behavior: "smooth" });
}

// =========================================================================
// SESSÃO 3: Avaliação & Triagem (Triador / BraCVAM)
// =========================================================================

function renderTriageReview() {
  const container = document.getElementById("triageFieldsList");
  if (!container) return;
  container.innerHTML = "";

  const isSubmitted = state.process.status === "SUBMITTED" || state.process.status === "APPROVED" || state.process.status === "REJECTED";

  if (!isSubmitted) {
    container.innerHTML = `
      <div class="p-8 text-center text-slate-400 bg-slate-900/40 rounded-xl border border-dashed border-slate-700">
        <i class="fa-solid fa-lock text-3xl mb-2 text-amber-500/80"></i>
        <h4 class="text-sm font-semibold text-slate-200">Aguardando Submissão do Proponente</h4>
        <p class="text-xs text-slate-400 mt-1 max-w-md mx-auto">
          A triagem técnica e a avaliação de conformidade serão liberadas assim que o formulário for preenchido e submetido na Sessão 2.
        </p>
      </div>`;
    const decisionCard = document.getElementById("triageDecisionPanel");
    if (decisionCard) decisionCard.classList.add("opacity-50", "pointer-events-none");
    return;
  }

  const decisionCard = document.getElementById("triageDecisionPanel");
  if (decisionCard) decisionCard.classList.remove("opacity-50", "pointer-events-none");

  const fields = state.formSchema.fields || [];

  fields.forEach((field) => {
    const val = state.formData[field.field_key];
    const review = state.fieldReviews[field.field_key] || { status: "OK", comment: "" };

    const card = document.createElement("div");
    card.className =
      "p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-all space-y-3";

    let displayVal = val || "<em class='text-slate-500'>Não informado</em>";
    if (field.field_type === "select") {
      const opt = (field.options || []).find((o) => o.value === val);
      if (opt) displayVal = opt.label;
    } else if (field.field_type === "boolean") {
      displayVal = val ? "Sim" : "Não";
    } else if (field.field_type === "file_upload" && val) {
      displayVal = `<span class="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800 text-teal-300 font-mono text-xs"><i class="fa-solid fa-file-pdf text-rose-400"></i> ${val}</span>`;
    }

    card.innerHTML = `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-800">
        <div>
          <span class="text-xs font-semibold text-white">${field.label}</span>
          <span class="text-[10px] text-slate-400 font-mono ml-2">(${field.field_key})</span>
        </div>
        <div class="flex items-center gap-1">
          <button onclick="setFieldStatus('${field.field_key}', 'OK')" class="px-2.5 py-1 rounded text-xs font-semibold ${review.status === "OK" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" : "text-slate-400 bg-slate-800 hover:bg-slate-700"}">
            <i class="fa-solid fa-check mr-1"></i> Conforme
          </button>
          <button onclick="setFieldStatus('${field.field_key}', 'NEEDS_REVISION')" class="px-2.5 py-1 rounded text-xs font-semibold ${review.status === "NEEDS_REVISION" ? "bg-amber-500/20 text-amber-300 border border-amber-500/40" : "text-slate-400 bg-slate-800 hover:bg-slate-700"}">
            <i class="fa-solid fa-triangle-exclamation mr-1"></i> Apontar Problema
          </button>
        </div>
      </div>
      <div class="text-xs text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800">
        ${displayVal}
      </div>
      ${
        review.status === "NEEDS_REVISION"
          ? `
        <div class="pt-1">
          <label class="text-[11px] font-semibold text-amber-300 block mb-1">
            <i class="fa-solid fa-comment-dots mr-1"></i> Parecer / Justificativa da Inconsistência:
          </label>
          <input
            type="text"
            value="${review.comment || ""}"
            placeholder="Descreva o ajuste necessário para o proponente..."
            onchange="setFieldComment('${field.field_key}', this.value)"
            class="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-amber-500/40 text-amber-100 text-xs focus:border-amber-400 focus:outline-none"
          />
        </div>`
          : ""
      }
    `;

    container.appendChild(card);
  });
}

function setFieldStatus(key, status) {
  if (!state.fieldReviews[key]) state.fieldReviews[key] = { status: "OK", comment: "" };
  state.fieldReviews[key].status = status;
  renderTriageReview();
}

function setFieldComment(key, comment) {
  if (!state.fieldReviews[key]) state.fieldReviews[key] = { status: "NEEDS_REVISION", comment: "" };
  state.fieldReviews[key].comment = comment;
}

function emitTriageDecision(outcome) {
  const notesInput = document.getElementById("triageGeneralNotes");
  const scoreInput = document.getElementById("triageScore");
  const notes = notesInput ? notesInput.value.trim() : "";
  const score = scoreInput ? scoreInput.value : "high";

  if (outcome === "DILIGENCE") {
    // Checar se há apontamentos
    const flagged = Object.entries(state.fieldReviews).filter(([k, v]) => v.status === "NEEDS_REVISION");
    if (flagged.length === 0 && !notes) {
      showToast("Aponte os problemas nos campos ou registre notas antes de solicitar diligência.", "error");
      return;
    }

    state.process.status = "IN_DILIGENCE";
    state.process.runNumber += 1;

    addTimelineEvent(
      "DILIGENCE_REQUESTED",
      state.currentUser.name,
      `Diligência solicitada. Formulário reaberto para correções pelo Proponente (Execução #${state.process.runNumber}).`
    );

    updateProcessStatusBadge();
    renderFormFilling();
    renderTriageReview();
    showToast("Diligência solicitada com sucesso! O Proponente já pode revisar os campos na Sessão 2.", "info");

    const fillSec = document.getElementById("sectionFilling");
    if (fillSec) fillSec.scrollIntoView({ behavior: "smooth" });
  } else if (outcome === "APPROVED") {
    state.process.status = "APPROVED";
    addTimelineEvent(
      "TRIAGE_APPROVED",
      state.currentUser.name,
      `Proposta aprovada na triagem inicial. Processo apto para a Fase 2 (Planejamento e Governança).`
    );
    updateProcessStatusBadge();
    renderFormFilling();
    renderTriageReview();
    showToast("Proposta Aprovada na Triagem! Avançando para a Fase 2.", "success");
  } else if (outcome === "REJECTED") {
    state.process.status = "REJECTED";
    addTimelineEvent(
      "TRIAGE_REJECTED",
      state.currentUser.name,
      `Proposta rejeitada na triagem inicial. Processo encerrado.`
    );
    updateProcessStatusBadge();
    renderFormFilling();
    renderTriageReview();
    showToast("Proposta Rejeitada e arquivada.", "error");
  }
}

// =========================================================================
// Linha do Tempo e Notificações (Toasts)
// =========================================================================

function addTimelineEvent(event, actor, description) {
  state.timeline.unshift({
    timestamp: new Date().toLocaleTimeString(),
    event,
    actor,
    description
  });
  renderTimeline();
}

function renderTimeline() {
  const container = document.getElementById("timelineEventsList");
  if (!container) return;
  container.innerHTML = "";

  state.timeline.forEach((item) => {
    const el = document.createElement("div");
    el.className = "flex items-start gap-3 text-xs border-l-2 border-slate-700 pl-4 py-1.5 relative";
    el.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-teal-400 absolute -left-[5px] top-2.5"></span>
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-white">${item.actor}</span>
          <span class="text-[10px] text-slate-400 font-mono">${item.timestamp}</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-teal-300 font-mono">${item.event}</span>
        </div>
        <p class="text-slate-300 mt-0.5">${item.description}</p>
      </div>
    `;
    container.appendChild(el);
  });
}

function updateProcessStatusBadge() {
  const badge = document.getElementById("processStatusBadge");
  if (!badge) return;

  const map = {
    DRAFT: { text: "Rascunho (Sessão 2)", class: "bg-slate-700 text-slate-300" },
    SUBMITTED: { text: "Submetido - Aguardando Triagem", class: "bg-blue-500/20 text-blue-300 border border-blue-500/30" },
    IN_DILIGENCE: { text: `Em Diligência (Revisão #${state.process.runNumber})`, class: "bg-amber-500/20 text-amber-300 border border-amber-500/30" },
    APPROVED: { text: "Aprovado na Triagem (Fase 1 Concluída)", class: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30" },
    REJECTED: { text: "Rejeitado na Triagem (Arquivado)", class: "bg-rose-500/20 text-rose-300 border border-rose-500/30" }
  };

  const current = map[state.process.status] || map.DRAFT;
  badge.className = `inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${current.class}`;
  badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-current"></span> ${current.text}`;
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  const colors = {
    info: "bg-slate-800 border-teal-500 text-teal-300",
    success: "bg-slate-800 border-emerald-500 text-emerald-300",
    error: "bg-slate-800 border-rose-500 text-rose-300"
  };

  toast.className = `fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl border shadow-2xl text-xs font-medium flex items-center gap-2 transition-all transform translate-y-2 opacity-0 ${colors[type] || colors.info}`;
  toast.innerHTML = `<i class="fa-solid ${type === "success" ? "fa-circle-check" : type === "error" ? "fa-circle-xmark" : "fa-circle-info"}"></i> ${message}`;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  }, 10);

  setTimeout(() => {
    toast.classList.add("translate-y-2", "opacity-0");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
