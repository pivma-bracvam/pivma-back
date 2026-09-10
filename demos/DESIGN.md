# Diretrizes de Design para Demonstrações (DESIGN.md)

Este documento estabelece os padrões visuais, de usabilidade e arquiteturais obrigatórios para todas as páginas de demonstração interativa localizadas em `demos/`.

---

## 1. Princípios Fundamentais

1. **Foco Estritamente Funcional e Validação Operacional:**
   - As demonstrações existem para comprovar que os endpoints desenvolvidos no backend operam de ponta a ponta com a API real.
   - Não devem tentar simular um sistema ERP completo ou complexo: cada página é um painel direto de teste e validação para o avaliador.

2. **Tipografia Ampla e Alta Legibilidade:**
   - **Títulos de Página:** `26px` a `32px`, peso `700` (`font-weight: bold`).
   - **Títulos de Seção:** `20px` a `24px`, peso `600`.
   - **Rótulos (Labels), Botões e Ações:** `16px` a `18px`, peso `600`.
   - **Corpo e Dados em Tabelas:** `16px`, contraste mínimo WCAG AA sobre fundo claro.

3. **Pouco Texto e Operações Rápidas:**
   - Evitar blocos longos de documentação na interface.
   - Usar botões de ação descritivos e autoexplicativos (ex: "Criar Usuário", "Salvar Rascunho", "Submeter Proposta", "Aprovar").
   - Fornecer atalhos de autenticação de 1 clique (ex: "Entrar como Admin", "Entrar como Proponente").

4. **Total Desacoplamento e Autocontenção:**
   - Cada página de demonstração deve ser **100% autocontida** e independente.
   - Não utilizar mini-frameworks complexos, empacotadores (webpack, vite) ou bibliotecas externas pesadas.
   - Um novo módulo deve ser adicionado apenas criando `demos/<modulo>/index.html` e inserindo o link correspondente em `demos/index.html`.

5. **Transparência Técnica e Resposta da API:**
   - Toda página deve exibir uma caixa de inspeção técnica (`#api-inspector` ou similar) mostrando o método HTTP, rota chamada, status de resposta (ex: `200 OK`, `201 Created`, `422 Unprocessable Entity`) e o payload JSON retornado pela API.

---

## 2. Paleta de Cores e Estilos Recomendados

Para manter harmonia visual entre as demonstrações, adote as seguintes variáveis CSS:

```css
:root {
  --font-main: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --bg-color: #f8fafc;
  --card-bg: #ffffff;
  --text-main: #0f172a;
  --text-muted: #475569;
  --primary: #1d4ed8;
  --primary-hover: #1e40af;
  --success: #15803d;
  --warning: #b45309;
  --danger: #b91c1c;
  --border: #cbd5e1;
}
```

---

## 3. Padrão de Integração com a API

Como as demos são servidas pelo próprio backend sob `/demos/`, as requisições para a API ocorrem na mesma origem (`http://localhost:8000`), garantindo envio e recebimento automático do cookie `access_token`:

```javascript
async function apiCall(endpoint, options = {}) {
  options.credentials = 'include';
  options.headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };
  const res = await fetch(endpoint, options);
  const data = await res.json().catch(() => null);
  renderInspector(options.method || 'GET', endpoint, res.status, data);
  return { status: res.status, ok: res.ok, data };
}
```

---

## 4. Estrutura Padrão de uma Página de Demonstração

Toda página em `demos/<modulo>/index.html` deve conter:
1. **Cabeçalho:** Título grande do módulo, link de volta para `/demos/` e barra de status do usuário atual (`GET /auth/me`).
2. **Painel de Ações Rápidas:** Botões para disparar o caso de uso prioritário do módulo.
3. **Área Interativa de Trabalho:** Tabelas com busca, formulários orientados a esquema ou painéis de decisão.
4. **Inspetor de Requisição / Resposta da API:** Exibição clara e legível do JSON retornado.

---

## 5. Ciclo Básico (4 Módulos) e Avaliação por IA (Spec 013)

O hub (`demos/index.html`) expõe **4 módulos** que juntos cobrem o ciclo Fase 1
(submissão → pré-avaliação → triagem → decisão). Contas semeadas por
`scripts/seeds/seed_all.py`, autenticação via `POST /auth/login`
(`{identifier, password}`):

| Conta | Senha | Papel na demo |
|---|---|---|
| `admin` | `Admin@123456` | BraCVAM: edita formulário e configura avaliações por IA |
| `proponent_user` | `Proponent@123456` | Proponente: submete e acompanha a pré-avaliação |
| `triage_evaluator` | `Triage@123456` | Avaliador: triagem, decisão e feedback por critério da IA |

| # | Página | Endpoints principais |
|---|---|---|
| 1 | `demos/forms/` — Editor + Configuração de IA | `GET/PUT /processes/templates/...`, `GET /form-templates/{k}/evaluable-fields` |
| 2 | `demos/submission/` — Submissão + Pré-avaliação | `POST /processes/{id}/activities/{k}/form`, `GET /processes/{id}/pre-evaluation`, `POST /processes/{id}/submission/direct-review` |
| 3 | `demos/triage/` — Triagem & Decisão | `POST /processes/{id}/triage/reviews` e `/decision`, `GET /processes/{id}/pre-evaluation`, `POST /processes/{id}/pre-evaluation/{run}/feedback` |
| 4 | `demos/ai-pipeline/` — Observabilidade de IA | painel de execuções de pipeline |

**Configuração de IA por campo** — `demos/forms/ai-config.html?template=<k>&field=<f>`:
página dedicada aberta pelo botão *Configurar Avaliação por IA →* de cada campo do
editor. Fluxo com endpoints existentes apenas: reaproveitar da biblioteca
(`GET /ai-evaluations`) ou criar (`POST /ai-evaluations`) → sugerir critérios
(`POST /ai-evaluations/suggest-criteria`) → editar
(`PATCH /ai-evaluations/{id:uuid}/versions/{n:int}`) → testar (`.../test`) →
publicar (`.../publish`) → associar ao campo. A associação faz
`GET` das associações atuais, **acrescenta** a nova e envia o conjunto completo
via `PUT /form-templates/{k}/evaluation-assignments` (o `PUT` substitui a lista
inteira).

**Restrição de acesso conhecida:** `GET .../pre-evaluation` e
`POST .../feedback` exigem proponente do processo, gestor do processo
(`group_manager`) **ou** perfil Administrador (permissão `ai_evaluations.read`).
O perfil *Revisor* não basta. O seed de Spec 013 designa `triage_evaluator`
como `group_manager` do processo `[DEMO IA] Extensão de Escopo` para a demo de
Triagem funcionar de ponta a ponta.
