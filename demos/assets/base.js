/* Componente compartilhado de status da API para as demonstrações do PIVMA.
   Uso: <span class="api-status" data-api-status><span class="dot"></span>
        <span data-api-status-text>Verificando API...</span></span>
   Contrato: specs/015-first-deploy-baseline/contracts/demo-standard.md */

(function () {
  var SEED_CMD = 'uv run python -m scripts.seeds.seed_all';

  async function checkApiStatus() {
    var boxes = document.querySelectorAll('[data-api-status]');
    if (!boxes.length) return;
    var online = false;
    try {
      var res = await fetch('/', { credentials: 'include' });
      online = res.ok;
    } catch (e) {
      online = false;
    }
    boxes.forEach(function (box) {
      var dot = box.querySelector('.dot');
      var text = box.querySelector('[data-api-status-text]');
      if (dot) dot.className = 'dot ' + (online ? 'online' : 'offline');
      if (text) text.textContent = online ? 'API conectada' : 'API inacessível';
    });
  }

  // Exibe um aviso único e orientador quando faltam dados de demonstração.
  window.showNeedsSeed = function (container, detail) {
    var el = document.createElement('div');
    el.className = 'needs-seed';
    el.innerHTML =
      '<strong>Dados de demonstração ausentes.</strong> ' +
      (detail ? detail + ' ' : '') +
      'Carregue a massa com <code>' + SEED_CMD + '</code> e recarregue a página.';
    if (container) container.prepend(el);
    return el;
  };
  window.PIVMA_SEED_CMD = SEED_CMD;

  document.addEventListener('DOMContentLoaded', checkApiStatus);
})();
