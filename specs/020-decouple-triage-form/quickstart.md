# Quickstart & Validation Guide: 020 - Desacoplamento do Formulário da Atividade de Triagem

**Feature**: 020-decouple-triage-form  
**Date**: 2026-09-11  

---

## 1. Pré-requisitos e Sincronização

1. Sincronizar templates via bootstrap:
   ```bash
   poetry run python -m pivma.bootstrap_process_templates
   ```
2. Executar seeds de carga (incluindo formulários e processos de demonstração):
   ```bash
   poetry run python -m scripts.seeds.seed_forms
   ```

---

## 2. Validação Automatizada

Executar testes unitários e de integração relacionados:
```bash
poetry run pytest tests/unit/core/test_first_deploy_forms.py -v
poetry run pytest tests/ -k triage -v
```

Executar linters e formatadores:
```bash
poetry run ruff check .
poetry run ruff format --check .
```

---

## 3. Validação da Demonstração Ponta a Ponta

1. Iniciar a API:
   ```bash
   poetry run uvicorn pivma.app:app --port 8000
   ```
2. Acessar a demonstração de triagem em `http://localhost:8000/demos/triage/`:
   - Efetuar login com usuário com papel BraCVAM/Admin.
   - Selecionar um processo em triagem.
   - Avaliar os campos do formulário do proponente.
   - Emitir a decisão de triagem (Aprovar, Solicitar Diligência ou Rejeitar).
   - Verificar na linha do tempo que o processo avança corretamente e a decisão é persistida sem erros de integridade.
