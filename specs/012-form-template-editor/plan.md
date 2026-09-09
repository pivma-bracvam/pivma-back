# Implementation Plan: 012 - Editor e Customização de Templates de Formulários de Processo (Versão 1.1)

**Branch**: `012-form-template-editor` | **Date**: 2026-09-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-form-template-editor/spec.md`

---

## Summary

Implementar a capacidade de edição e customização de templates de formulários associados a processos de validação (Versão 1.1). A solução disponibiliza endpoints REST para consulta e atualização de definições de formulários e campos (`PUT /processes/templates/{key}/forms/{form_key}`), suportando agrupamento em seções, controle de obrigatoriedade, tipos fundamentais de dados e configuração simplificada de IA (Spec 010). Ao instanciar um novo processo como proponente (`POST /processes`), a nova instância herda a definição atualizada do template. A entrega inclui a validação operacional através da demonstração em `demos/forms/index.html` em estrita conformidade com `AGENTS.md`.

---

## Technical Context

**Language/Version**: Python 3.14 (compatível com Poetry e tipagem moderna)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.0 (AsyncSession), Uvicorn

**Storage**: PostgreSQL (asyncpg), tabelas `process_templates`, `process_template_versions`, `form_templates`, `form_fields`, `process_instances`, `form_instances`

**Testing**: Pytest, pytest-asyncio, HTTPX AsyncClient

**Target Platform**: Linux / Docker / Web Application (FastAPI backend + páginas HTML nativas em `demos/`)

**Project Type**: Web Service / API REST + Demos interativas desacopladas

**Performance Goals**: Tempo de resposta de atualização e instanciação inferior a 300ms

**Constraints**:
- Não criar dependências de pacotes externos pesados para o frontend;
- Manter total desacoplamento entre `demos/` e `src/` (conforme `AGENTS.md`);
- Preservar imutabilidade histórica de processos e instâncias já criados no passado.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Library-First / Domain-First)**: Os contratos de endpoints atendem diretamente às regras de negócio de templates e formulários do PIVMA, sem endpoints facilitadores exclusivos para demos. -> **PASS**
- **Princípio II (Desacoplamento de Demos)**: Toda interface de teste e validação reside em `demos/` consumindo a API pública real. -> **PASS**
- **Princípio III (Test-First & Regressão)**: Acompanhado de testes unitários e de integração com cobertura de autorização (BraCVAM vs Proponente) e persistência de dados. -> **PASS**
- **Princípio IV (Compatibilidade com Specs Anteriores)**: Mantém compatibilidade com a esteira simplificada de IA da Spec 010 e com a governança da Spec 004/011. -> **PASS**

---

## Project Structure

### Documentation (this feature)

```text
specs/012-form-template-editor/
├── plan.md              # Este arquivo (plano técnico de implementação)
├── research.md          # Decisões arquiteturais e resolução de dúvidas
├── data-model.md        # Entidades, esquemas Pydantic e relacionamentos
├── quickstart.md        # Roteiro de validação operacional ponta a ponta
├── contracts/           # Contrato OpenAPI (form-template-editor-api.yaml)
└── checklists/
    └── requirements.md  # Checklist de qualidade de requisitos
```

### Source Code (repository root)

```text
src/pivma/
├── schemas.py                          # Schemas Pydantic para atualização de templates de formulários
├── routers/
│   └── processes.py                    # Endpoint PUT /processes/templates/{key}/forms/{form_key}
└── core/
    ├── process_engine.py               # Lógica de atualização e sincronização atômica de templates
    └── authorization.py                # Verificação de permissões da equipe BraCVAM

demos/
├── forms/
│   └── index.html                      # Interface completa de edição de template e validação com proponente
└── index.html                          # Catálogo de demonstrações com Módulo 2 ativo

tests/
├── api/routers/
│   └── test_process_template_editor.py # Testes de integração dos novos endpoints
└── unit/core/
    └── test_form_template_sync.py      # Testes unitários de sincronização e versionamento de templates
```

---

## Proposed Changes by Component

### 1. `src/pivma/schemas.py`
- Adicionar `FormFieldUpdateDefinition`: modelo para cada campo com `field_key`, `label`, `help_text`, `field_type`, `is_required`, `order_index`, `section`, `options`, `validation_rules`, `ai_evaluation_enabled`, `ai_context_instructions`, `ai_validation_rules`.
- Adicionar `UpdateFormTemplateRequest`: contendo lista de `fields`, `name` e `description`.
- Adicionar `FormTemplateDetailResponse`: retorno estruturado da definição do template e campos.

### 2. `src/pivma/routers/processes.py`
- Criar endpoint `GET /processes/templates/{key}/forms/{form_key}` retornando a definição estruturada do formulário.
- Criar endpoint `PUT /processes/templates/{key}/forms/{form_key}`:
  - Protegido por autenticação e verificação de perfil administrativo/BraCVAM.
  - Atualiza o `FormTemplate` e a coleção de `FormField`.
  - Atualiza o `definition_payload` da versão mais recente do `ProcessTemplateVersion`.
  - Retorna o formulário salvo.

### 3. `demos/forms/index.html`
- Ajustar para que a seleção do processo oficial carregue seus templates de formulário.
- Permitir ao usuário BraCVAM editar os campos (seções, labels, tipos, obrigatoriedade, IA), adicionar novos campos e remover campos.
- Botão "Salvar Template no Backend" disparando `PUT /processes/templates/{key}/forms/{form_key}`.
- Painel para o Proponente: alternar para sessão de proponente, instanciar novo processo via `POST /processes` e verificar imediatamente o formulário customizado renderizado.

---

## Complexity Tracking

| Item | Necessidade | Alternativa Mais Simples Rejeitada |
|---|---|---|
| Atualização Atômica de Formulário (`PUT .../forms/{form_key}`) | Garante que campos, ordenação e seções sejam salvos de forma consistente em uma única transação | Atualizações granulares campo a campo via múltiplos requests HTTP gerariam inconsistências durante edição incompleta |
