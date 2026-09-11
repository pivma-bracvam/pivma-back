# Implementation Plan: 020 - Desacoplamento do Formulário da Atividade de Triagem

**Branch**: `020-decouple-triage-form` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

---

## Summary

Desacoplar formalmente a atividade de triagem (`triage_evaluation`) do modelo de formulários (`FormTemplate`), removendo o template fantasma `triage_review_v1` de todos os arquivos YAML em `src/pivma/templates_data/`, ajustando o ciclo de vida da atividade no motor de processos (`src/pivma/core/process_engine.py`) para operar sem `FormInstance` e aplicando soft-delete em `FormTemplate` obsoletos no bootstrap (`src/pivma/bootstrap_process_templates.py`).

---

## Technical Context

**Language/Version**: Python 3.14  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, PyYAML  
**Storage**: PostgreSQL com extensões existentes (sem alterações de esquema DDL, apenas dados de template)  
**Testing**: Pytest com Testcontainers e SQLite/PostgreSQL in-memory conforme suite  
**Target Platform**: Linux / Docker  
**Project Type**: Web API (REST)  
**Performance Goals**: Sincronização e resolução de atividade instantâneas (< 50ms)  
**Constraints**: Não quebrar histórico de processos pré-existentes; manter conformidade com Constituição e `AGENTS.md`  
**Scale/Scope**: 5 arquivos YAML de templates de processo, 2 módulos Python centrais (`bootstrap_process_templates.py` e `process_engine.py`), suites de testes unitários/integração.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Princípio I (Spec Kit)**: Em conformidade; seguindo rigorosamente a cadeia spec → plan → tasks → implement.
- **Princípio II (Domínio Puro na API)**: Em conformidade; a mudança remove um resíduo artificial e alinha o domínio estritamente às necessidades reais de negócio.
- **Princípio III (Demonstração como Critério de Conclusão)**: Em conformidade; a demo existente de triagem (`demos/triage/`) continua sendo o critério de validação ponta a ponta.
- **Princípio IV (Qualidade Verificável)**: Em conformidade; ruff e pytest com 100% de sucesso.
- **Princípio V (Auditabilidade e Rastreabilidade)**: Em conformidade; soft-delete para desativação de templates legados, preservando integridade referencial.
- **Princípio VI (Segurança por Padrão)**: Em conformidade; permissões e RBAC inalterados.

---

## Project Structure

### Documentation (this feature)

```text
specs/020-decouple-triage-form/
├── plan.md              # Este arquivo
├── research.md          # Decisões arquiteturais da fase 0
├── data-model.md        # Modelo relacional e diagramas
├── quickstart.md        # Guia de validação rápida
├── contracts/           # Contratos das APIs de triagem
│   └── triage_contract.md
└── tasks.md             # Tarefas de implementação (fase 2)
```

### Source Code Impacted

```text
src/pivma/
├── templates_data/
│   ├── 01_pre_validated_method.yaml         # Remover form_template_key e triage_review_v1
│   ├── 02_scope_extension.yaml              # Remover form_template_key e triage_review_v1
│   ├── 03_me_too_validation.yaml            # Remover form_template_key e triage_review_v1
│   ├── 04_validated_method_dossier.yaml     # Remover form_template_key e triage_review_v1
│   └── 05_proof_of_concept.yaml             # Remover form_template_key e triage_review_v1
├── bootstrap_process_templates.py           # Soft-delete em FormTemplate ausente dos YAMLs
└── core/
    └── process_engine.py                    # Ajustar _unblock_triage_activity e execute_triage_decision

tests/
└── unit/
    └── core/
        └── test_first_deploy_forms.py       # Atualizar asserções sobre templates ativos
```
