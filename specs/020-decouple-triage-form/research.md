# Research & Architecture Decisions: 020 - Desacoplamento do Formulário da Atividade de Triagem

**Feature**: 020-decouple-triage-form  
**Date**: 2026-09-11  
**Status**: Concluded  

---

## 1. Contexto e Diagnóstico

A atividade `triage_evaluation` (Triagem e Decisão BraCVAM) foi historicamente concebida na Spec 004 associada a um `FormTemplate` (`triage_review_v1`). No entanto:
1. O domínio real opera via avaliação pericial campo a campo sobre a submissão do proponente ([`FieldReview`](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/src/pivma/core/database/models.py#L854)) e deliberação formal ([`Decision`](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/src/pivma/core/database/models.py#L950)).
2. Os campos de `triage_review_v1` (`regulatory_adherence_score` e `triage_summary_notes`) nunca são preenchidos ou utilizados pela API de triagem nem pela interface da demonstração.
3. Desde a Spec 017, o motor de processos já oferece suporte pleno a atividades sem formulário associado (`form_template_key` ausente).

---

## 2. Decisões Técnicas

### Decisão 1: Representação Declarativa nos Arquivos YAML
- **Decisão**: Remover a propriedade `form_template_key: "triage_review_v1"` da atividade `triage_evaluation` em todos os 5 arquivos YAML em `src/pivma/templates_data/` e remover a entrada `triage_review_v1` da lista `forms:`.
- **Racional**: Cada arquivo YAML passará a conter exatamente 1 formulário declarado (o respectivo formulário de submissão da proposta), eliminando redundâncias e alinhando os arquivos à realidade do domínio.
- **Alternativas consideradas**: Manter o formulário vazio ou com flag inativo. Rejeitado: manteria dívida técnica e confusão sobre a finalidade do formulário.

### Decisão 2: Desbloqueio e Inicialização da Atividade de Triagem
- **Decisão**: Em [`_unblock_triage_activity`](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/src/pivma/core/process_engine.py#L819), remover a busca por `FormTemplate.key == 'triage_review_v1'` e a criação de `FormInstance`. A função cria apenas a `ActivityRun` e a `Task` atribuída ao cargo global `bracvam`.
- **Racional**: A atividade não requer formulário; a criação de `FormInstance` órfã consumia recursos e induzia a chamadas de API inválidas.

### Decisão 3: Resolução de Execução em `execute_triage_decision`
- **Decisão**: Substituir a chamada `get_current_form_instance(session, process_id, 'triage_evaluation')` por uma função que obtenha diretamente a `ActivityInstance` e seu `ActivityRun` ativo (`_get_current_activity_run` ou query direta de atividade/execução).
- **Racional**: `get_current_form_instance` exige obrigatoriamente a presença de `FormInstance` ativa. Ao desacoplar o formulário da triagem, essa chamada falharia com `NotFoundError`.

### Decisão 4: Sincronização e Ciclo de Vida no Bootstrap
- **Decisão**: Em [`bootstrap_all_templates`](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/src/pivma/bootstrap_process_templates.py), coletar todas as chaves de formulários ativas presentes nos arquivos YAML e aplicar soft-delete / inativação (`deleted_at = datetime.now(UTC)`) em instâncias de `FormTemplate` que não façam mais parte do catálogo ativo (como `triage_review_v1`), exatamente como já é feito para `ProcessTemplate`.
- **Racional**: Preserva a integridade relacional do banco de dados (chaves estrangeiras existentes não sofrem deleção física) enquanto limpa o catálogo para novas operações.

### Decisão 5: Validação e Testes de Regressão
- **Decisão**: Atualizar o teste unitário [`tests/unit/core/test_first_deploy_forms.py`](file:///home/jaspion/Fiocruz/BraCVAM/pivma-back/tests/unit/core/test_first_deploy_forms.py) para validar que os formulários ativos são estritamente os 5 formulários de submissão e que `triage_review_v1` não existe mais como formulário ativo. Criar testes adicionais para certificar o fluxo completo de triagem sem formulário próprio.
