# Quickstart: Validação do Editor de Templates de Formulários (Versão 1.1)

Este guia apresenta o roteiro prático e reprodutível para validar o ciclo completo da **Feature 012**: customização de templates pela equipe BraCVAM e instanciação subsequente pelo Proponente.

---

## 1. Pré-Requisitos e Preparação

1. Certificar-se de que o banco de dados está atualizado e com os seeds executados:
   ```bash
   poetry run python -m scripts.seeds.seed_all
   ```

2. Iniciar o servidor de aplicação:
   ```bash
   poetry run uvicorn pivma:app --reload --port 8000
   ```

---

## 2. Cenário de Validação Ponta a Ponta

### Passo 1: Autenticar como BraCVAM e Consultar Template
- Acessar `http://localhost:8000/demos/forms/`
- Clicar em **"Entrar como BraCVAM (Admin)"**
- Selecionar o processo **"Método Pré-Validado"** (`pre_validated_method`)
- O sistema carrega os formulários vinculados, por padrão `submission_pre_validated_v1`.

### Passo 2: Customizar Campos e Seções do Template
- Adicionar um novo campo customizado:
  - **Chave (`field_key`)**: `glp_audit_dossier`
  - **Rótulo (`label`)**: `Dossiê de Auditoria de Boas Práticas (BPL)`
  - **Seção**: `Conformidade e Qualidade`
  - **Tipo**: `file_upload`
  - **Obrigatório**: `Sim (true)`
  - **Avaliação por IA**: `Habilitada (true)`
  - **Instruções IA**: `"Verificar se o relatório de auditoria possui carimbo de auditor líder credenciado."`
- Clicar em **"Salvar Template de Formulário"** (`PUT /processes/templates/pre_validated_method/forms/submission_pre_validated_v1`).
- Validar que o Inspetor da API exibe `HTTP 200 OK` e o JSON com a versão atualizada e o novo campo persistido.

### Passo 3: Alternar para Proponente e Instanciar Novo Processo
- Na barra superior da demo, clicar em **"Entrar como Proponente"** (`proponent_user`).
- No painel de instanciação, criar um novo processo utilizando o template **"Método Pré-Validado"**:
  - Título: `Validação In Vitro Especial - Teste 1.1`
- Clicar em **"Instanciar Processo"** (`POST /processes`).

### Passo 4: Verificar que o Proponente Recebe o Formulário Customizado
- Com o processo recém-criado selecionado, inspecionar os campos renderizados na atividade de submissão:
  - Constatar a presença visual do campo `Dossiê de Auditoria de Boas Práticas (BPL)`;
  - Verificar que o campo está marcado como obrigatório (`*`) e com a tag `🤖 IA Ativada`;
  - Preencher os dados e salvar/submeter, comprovando que o motor valida e aceita os novos campos.

---

## 3. Testes Automatizados de Regressão

Executar a suíte de testes unitários e de integração:
```bash
poetry run pytest tests/api/routers/test_process_router.py tests/unit/core/test_process_engine.py
```
