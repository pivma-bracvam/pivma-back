# Research: 011 - Processos Padrão do Sistema e Fase 1 (Submissão, IA e Deliberação BraCVAM)

**Feature**: `011-standard-process-templates`
**Date**: 2026-09-09

---

## 1. Descontinuação de `full_validation_v1.yaml` e Carga Declarativa dos 5 Processos

### Contexto
Atualmente, o sistema possui apenas `src/pivma/templates_data/full_validation_v1.yaml`, criado na Feature 004 como prova de conceito com duas fases (`phase_1_submission_triage` e `phase_2_planning_governance`). O carregador `bootstrap_all_templates` em `src/pivma/bootstrap_process_templates.py` itera sobre `templates_dir.glob('*.yaml')` e sincroniza formulários, templates de processo e versões no PostgreSQL.

### Decisão
1. Excluir fisicamente o arquivo mock `src/pivma/templates_data/full_validation_v1.yaml`.
2. Criar 5 arquivos declarativos padronizados sob `src/pivma/templates_data/`:
   - `01_pre_validated_method.yaml`
   - `02_scope_extension.yaml`
   - `03_me_too_validation.yaml`
   - `04_validated_method_dossier.yaml`
   - `05_proof_of_concept.yaml`
3. Prefixar os nomes de arquivo com dígitos (`01_`, `02_`, etc.) para assegurar ordem de descoberta determinística no filesystem e no banco de dados.
4. Manter estritamente a **Fase 1 (Submissão e Triagem)** em todos os 5 arquivos. A fase 2 (`phase_2_planning_governance`) é removida da definição dos templates, alinhando-se à diretriz explícita do usuário.

### Alternativas Consideradas
- *Manter `full_validation` como arquivo inativo ou oculto*: Rejeitado. O usuário determinou expressamente que o arquivo deixe de existir e que apenas os 5 reais sejam mantidos no sistema.
- *Agrupar todos os 5 processos em um único arquivo YAML gigante*: Rejeitado. Dificulta manutenção, versionamento e viola a modularidade declarativa já adotada.

---

## 2. Padrão de Chaves e Compatibilidade com o Motor de Processos (`process_engine.py`)

### Contexto
O motor de processos (`src/pivma/core/process_engine.py`) gerencia o ciclo de vida através de funções como `submit_proposal_form`, `_unblock_triage_activity`, `save_field_reviews` e `execute_triage_decision`. Algumas dessas funções utilizam chaves canônicas de atividade:
- `proposal_submission` para a atividade de envio da proposta;
- `triage_evaluation` para a atividade de triagem e parecer técnico;
- `triage_review_v1` para o formulário de deliberação do BraCVAM.

### Decisão
1. Adotar padronização de chaves de atividade em todos os 5 processos:
   - Atividade de Submissão: `proposal_submission` (atribuída ao papel `PROPONENT`);
   - Atividade de Triagem BraCVAM: `triage_evaluation` (atribuída ao papel `TRIAGE_LEAD`), com dependência explícita de `proposal_submission` em estado `COMPLETED`.
2. As chaves dos processos seguem a convenção semântica aprovada:
   - `pre_validated_method`
   - `scope_extension`
   - `me_too_validation`
   - `validated_method_dossier`
   - `proof_of_concept`
3. Esta decisão garante que nenhum endpoint existente (`/processes/{id}/activities/proposal_submission/form`, `/processes/{id}/triage/decision`, etc.) seja quebrado, mantendo 100% de estabilidade retroativa.

### Alternativas Consideradas
- *Renomear chaves de atividade para incluir o slug do processo (ex.: `pre_validated_submission`)*: Rejeitado. Quebraria os contratos REST de formulários e tarefas existentes na API, exigindo roteamento dinâmico sem ganho técnico.

---

## 3. Orquestração da Avaliação por IA com a Arquitetura da Spec 010

### Contexto
Na Spec 010, implementou-se o motor `FormAIPipelineEngine` (`src/pivma/ai/pipeline.py`), que avalia campos com `ai_evaluation_enabled = True` em 3 passos simulados (*ContextExtractionStep*, *MockEvaluationStep*, *VerdictSynthesisStep*), emitindo logs especializados em `logs/ai/ai_steps.jsonl`, eventos no índice operacional em `logs/application/events.jsonl` e eventos em tempo real via SSE. O usuário solicitou reutilizar essa estrutura mantendo resultado negativo simulado por padrão nesta fase.

### Decisão
1. No fluxo de envio da submissão (`submit_proposal_form`), acionar o pipeline de avaliação de IA de forma integrada e não bloqueante para a integridade dos dados:
   - Identificar campos preenchidos do formulário daquela execução que possuem `ai_evaluation_enabled == True`.
   - Executar o `FormAIPipelineEngine.run_field_pipeline(...)` para cada campo.
   - O resultado simulado consolida um veredito padrão (`NEEDS_ADJUSTMENT` ou `REPROVED`) com pontuação de confiança e recomendações simuladas.
2. Armazenar a avaliação de IA gerada como um artefato do processo (`Artifact` com chave `ai_evaluation_report`) vinculado àquela `ActivityRun`.
3. Na visualização de triagem do BraCVAM (`triage_evaluation`), a interface e os endpoints disponibilizam o relatório de IA para subsidiar a análise dos membros avaliadores.
4. Quando a IA real for conectada no futuro, apenas o conector do passo de inferência será modificado, preservando toda a esteira de processos.

### Alternativas Consideradas
- *Criar uma atividade manual separada de IA no grafo*: Rejeitado. Como a IA é automatizada e utiliza mocks sem intervenção humana, inseri-la como trigger na conclusão da submissão é mais limpo e não gera tarefas órfãs para usuários humanos.

---

## 4. Estrutura dos 5 Formulários Declarativos Dedicados

### Decisão
Cada template declara seu próprio formulário de submissão versionado:
1. `submission_pre_validated_v1`:
   - `method_title` (text, required)
   - `endpoint_target` (select, required)
   - `biological_mechanism` (textarea, required, `ai_evaluation_enabled: true`)
   - `pre_validation_history` (textarea, required, `ai_evaluation_enabled: true`)
   - `study_protocol_file` (file_upload, required)
   - `participating_laboratories_count` (integer, optional)

2. `submission_scope_extension_v1`:
   - `method_title` (text, required)
   - `base_method_reference` (text, required)
   - `new_intended_endpoint` (select, required)
   - `scope_extension_justification` (textarea, required, `ai_evaluation_enabled: true`)
   - `applicability_domain_data` (textarea, required, `ai_evaluation_enabled: true`)
   - `adapted_protocol_file` (file_upload, required)

3. `submission_me_too_v1`:
   - `method_title` (text, required)
   - `reference_validated_method` (text, required)
   - `target_test_system` (text, required)
   - `mechanistic_similarity_rationale` (textarea, required, `ai_evaluation_enabled: true`)
   - `functional_equivalence_evidence` (textarea, required, `ai_evaluation_enabled: true`)
   - `comparative_protocol_file` (file_upload, required)

4. `submission_validated_dossier_v1`:
   - `method_title` (text, required)
   - `validated_endpoint` (select, required)
   - `executive_validation_summary` (textarea, required, `ai_evaluation_enabled: true`)
   - `complete_dossier_file` (file_upload, required)
   - `oecd_guideline_alignment` (textarea, required, `ai_evaluation_enabled: true`)
   - `supporting_publications` (textarea, optional)

5. `submission_proof_of_concept_v1`:
   - `method_title` (text, required)
   - `intended_endpoint` (select, required)
   - `conceptual_hypothesis_and_3r` (textarea, required, `ai_evaluation_enabled: true`)
   - `current_readiness_and_plan` (textarea, required, `ai_evaluation_enabled: true`)
   - `estimated_timeline_months` (integer, optional)
   - `concept_note_file` (file_upload, optional)

---

## 5. Estratégia de Migração de Testes e Demos

### Decisão
1. **Testes**:
   - `tests/api/routers/test_process_router.py`: Atualizar para testar `GET /processes/templates` retornando 5 itens e validar detalhes de `pre_validated_method`.
   - `tests/api/routers/test_form_submission.py` e testes de triagem: Usar `pre_validated_method` como template canônico nos testes de integração de processo.
   - `tests/unit/core/test_template_loader.py`: Validar que todos os 5 templates e formulários são carregados corretamente.
2. **Seeds**:
   - `scripts/seeds/seed_all.py`, `seed_forms.py`, `seed_triage.py`, `seed_form_ai_demo.py`: Sincronizar dados utilizando as novas chaves canônicas.
3. **Demos**:
   - `demos/index.html`: Atualizar a listagem e os fluxos de demonstração para referenciar os 5 novos processos oficiais do BraCVAM.
