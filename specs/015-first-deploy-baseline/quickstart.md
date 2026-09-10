# Quickstart — Validação do Baseline do Primeiro Deploy

Roteiro executável que prova a feature ponta a ponta contra a API real. Reflete o
cenário de primeiro deploy: banco migrado e **vazio**.

## Pré-requisitos

- Docker (para o PostgreSQL `pgvector`) ou um Postgres local com `DATABASE_URL` válido.
- `uv` (ou Poetry — paridade mantida).
- Provedor de IA: os seeds usam `AI_PROVIDER=fake` automaticamente.

## 1. Banco limpo + migração

```bash
docker compose down -v && docker compose up db -d
uv run alembic upgrade head
```

**Esperado**: migração conclui em `head` sem erro; nenhuma tabela de domínio populada.

## 2. Carga única

```bash
uv run python -m scripts.seeds.seed_all
```

**Esperado**:
- Conclui sem erro (`❌` ausente).
- Imprime as 3 contas de teste com perfil e os links das 4 demos do ciclo + apoio.
- Idempotência: rodar de novo **não** duplica usuários/processos/avaliações e termina
  no mesmo estado (SC‑003).

## 3. Subir a API

```bash
uv run fastapi dev src/pivma/__init__.py
```

Catálogo em `http://localhost:8000/demos/`.

## 4. Percorrer as demos (SC‑001, SC‑004)

Para cada página, conferir o [contrato de UI](./contracts/demo-standard.md) (C1–C9).

| # | Demo | Ação | Esperado |
| :-- | :-- | :-- | :-- |
| 4.1 | `/demos/` (catálogo) | abrir, clicar todos os links | 6 páginas listadas, 1 linha cada, **zero** link quebrado, **zero** menção a `DESIGN.md` (C6, C7) |
| 4.2 | `/demos/forms/` | login `admin`; abrir formulário de um processo padrão; marcar um campo como avaliável; abrir "Configurar Avaliação por IA" | fluxo do editor + configuração de IA funciona contra a API |
| 4.3 | `/demos/submission/` | login `proponent_user`; instanciar `[DEMO 5]` (Prova de Conceito); abrir o formulário | o formulário exibe as **9 seções** do FP; campos agrupados por `section` |
| 4.4 | `/demos/submission/` | instanciar `[DEMO 4]` (Dossiê); preencher `terminology_notes`; submeter | submissão dispara pré-avaliação (status `AI_PRE_EVALUATION` → roteamento) |
| 4.5 | `/demos/triage/` | login `triage_evaluator`; selecionar `[DEMO 4]` | painel de pré-avaliação por IA populado; parecer por campo e decisão disponíveis |
| 4.6 | `/demos/triage/` | selecionar `[DEMO 1]` | processo em `TRIAGE` (sem painel de IA — não tem campo avaliável); decisão disponível |
| 4.7 | `/demos/ai-pipeline/` | login `admin` | linha do tempo da esteira de IA com ao menos 1 execução (provedor `fake`), modelo e custo |
| 4.8 | `/demos/users/` | login `admin` | lista de usuários e perfis RBAC |
| 4.9 | `/demos/operational-index/` | login `admin` | logs operacionais (SSE) |
| 4.10 | qualquer demo com banco vazio (repetir passo 1 sem passo 2) | abrir | mensagem única orientando `uv run python -m scripts.seeds.seed_all` (C4, C5) |

## 5. Formulários de submissão (SC‑007, SC‑008)

```bash
uv run python -m pivma.bootstrap_process_templates
```

Depois, via API (`GET /processes/{id}/activities/proposal_submission/form`) ou pelo
teste novo `tests/unit/core/test_first_deploy_forms.py`:

- `submission_pre_validated_v1`, `submission_scope_extension_v1`,
  `submission_me_too_v1` → **exatamente 1 campo** (`method_title`, `text`, obrigatório).
- `submission_validated_dossier_v1` → campos mínimos da narrativa de IA, com
  `terminology_notes` tendo `ai_evaluation_enabled = true`.
- `submission_proof_of_concept_v1` → todas as 9 seções presentes (valores distintos de
  `validation_rules.section`); nenhum elemento do FP ausente.
- Todas as aproximações do FP constam de `data-model.md` e da seção "Pendências" do
  `spec.md`.

## 6. Portões de qualidade (SC‑009, SC‑010)

```bash
uv run poe format
uv run poe lint
uv run poe test
```

**Esperado**: tudo verde. `git status` não mostra `scripts/seeds/seed_form_ai_demo.py`
(removido) nem `demos/DESIGN.md` (permanece removido).

## 7. Critério de aceite consolidado

- [ ] `seed_all` em banco vazio → 100% das demos operáveis sem passo manual (SC‑001).
- [ ] Do banco vazio à 1ª demo funcional em < 5 min (SC‑002).
- [ ] Re-seed sem duplicação (SC‑003).
- [ ] 6 páginas conformes ao contrato de UI (SC‑004).
- [ ] Zero link quebrado / zero `DESIGN.md` em `demos/` (SC‑005).
- [ ] Comando de carga idêntico em toda demo (SC‑006).
- [ ] Formas dos 5 formulários conforme `data-model.md` (SC‑007).
- [ ] 100% das aproximações do FP listadas (SC‑008).
- [ ] `format` + `lint` + `test` verdes (SC‑009).
- [ ] Nenhum seed órfão remanescente (SC‑010).
