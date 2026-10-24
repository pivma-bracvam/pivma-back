# Research: Terminologia dos tipos e código da submissão

## R1. Como a lista de tipos passa a seguir a ordem do BraCVAM

- **Decisão**: coluna `display_order` (inteiro, anulável) em
  `process_templates`, preenchida pelo campo `process_template.display_order`
  do YAML. `GET /processes/templates` ordena por
  `display_order ASC NULLS LAST, key ASC` e informa
  `sort: {by: "display_order", order: "asc"}`.
- **Motivo**: nenhum dado existente reproduz a ordem pedida. O nome em ordem
  alfabética põe a Extensão em primeiro, e as chaves, que não mudam, também
  não seguem a ordem. A coluna anulável deixa funcionar os templates criados
  direto no banco pelos testes; eles vão para o fim e o desempate pela chave
  mantém a paginação estável.
- **Alternativas descartadas**:
  - Ordenar pelo nome do arquivo YAML: o banco não guarda o arquivo, e os
    prefixos atuais (01 a 04) não seguem a ordem nova.
  - Deixar a ordem para o frontend: fora do escopo, e cada cliente teria de
    repetir a regra.
  - Coluna obrigatória com valor padrão: o padrão esconderia o YAML que
    esqueceu a ordem, o caso que a decisão 3 quer recusar.

## R2. Onde a ordem obrigatória é validada

- **Decisão**: em `bootstrap_all_templates`, numa primeira passada que lê
  todos os YAMLs e confere a ordem antes de qualquer
  `sync_template_from_dict`. Um YAML sem `display_order` inteiro maior ou
  igual a 1 levanta `ValidationError` com a chave do tipo, no padrão de
  `_validate_activity_access`, e nenhum template é gravado. `_sync_process_template_and_version` grava o
  valor (ou `None`) na criação e na atualização.
- **Motivo**: a decisão vale para o YAML. Dez arquivos de teste chamam
  `sync_template_from_dict` com dicionários sem ordem; validar ali obrigaria
  a mudar todos sem ganho.
- **Alternativa descartada**: validar em `sync_template_from_dict`, pelo
  custo acima.

## R3. Como gerar o sequencial anual sem repetir nem pular número

- **Decisão**: tabela `process_code_sequences` (`year` como chave primária,
  `last_value`), com `AuditMixin`. `generate_process_code` faz um upsert
  `INSERT … ON CONFLICT (year) DO UPDATE SET last_value = last_value + 1
  RETURNING last_value` na mesma sessão de `instantiate_process`.
- **Motivo**: o upsert trava a linha do ano até o commit. Uma criação
  simultânea espera e recebe o número seguinte (FR-008). Como
  `instantiate_process` faz commit no fim e rollback em qualquer falha, o
  incremento só vale se o processo for gravado (FR-009). Na primeira
  criação do ano, duas inserções simultâneas esbarram no índice único e a
  segunda vira atualização depois do commit da primeira.
- **Alternativas descartadas**:
  - `SEQUENCE` do PostgreSQL: não volta no rollback, deixando buracos, e não
    recomeça por ano sem rotina extra.
  - `MAX(code)` + 1: duas criações simultâneas leem o mesmo máximo; exigiria
    lock consultivo e parsing do código.
  - Contar processos do ano: mesmo problema de concorrência.
- **Constituição II**: a tabela herda `AuditMixin`; `created_by` recebe
  quem criou o primeiro processo do ano; cada incremento grava `updated_at`
  e, em `updated_by`, quem criou o processo.

## R4. Ano no horário de Brasília

- **Decisão**: `utc_now().astimezone(ZoneInfo('America/Sao_Paulo')).year`,
  usando o `utc_now` de `process_engine`. Adicionar a dependência `tzdata`.
- **Motivo**: o fuso nomeado acompanha mudanças de horário de verão, que o
  Brasil discute retomar; um deslocamento fixo de −3 h erraria nesse caso.
  A imagem `python:3.14-slim` não garante a base de fusos do sistema, e o
  `zoneinfo` usa o pacote `tzdata` quando ela falta. Testes controlam o
  relógio com `monkeypatch` em `pivma.core.process_engine.utc_now`.
- **Alternativa descartada**: `timezone(timedelta(hours=-3))`, pelo motivo
  acima.

## R5. Formato do número

- **Decisão**: `f'VAL-{year}-{n:04d}'`. Acima de 9999 o formato só cresce.
  A coluna `process_instances.code` tem 32 caracteres e comporta qualquer
  número realista.

## R6. Remoção da Prova de Conceito

- **Decisão**: apagar `05_proof_of_concept.yaml`. O bootstrap já desativa e
  aplica soft delete em templates de processo e formulários ausentes dos
  YAMLs (`bootstrap_all_templates`, precedente `full_validation`). Nenhum
  código de produção cita a Prova de Conceito.
- **Testes afetados** (13 referências em 9 arquivos):
  - Listas de chaves: `test_process_router.py`, `test_sample_activity_unlock.py`,
    `test_activity_type_extension.py`, `test_activity_access_columns.py`,
    `test_template_phase_2.py`, `test_template_phase_3.py`: retirar a chave.
  - `test_template_loader.py`: retirar a tupla e atualizar os nomes.
  - `test_form_submission.py`: retirar o caso parametrizado da Prova de
    Conceito.
  - `test_first_deploy_forms.py`: apagar
    `test_preliminary_form_covers_all_nine_sections` e retirar o formulário
    de `test_triage_form_deactivated_and_submission_forms_active`.
- **Documentação**: `templates_data/README.md` (exemplo do formulário
  completo), `manual/referencia/templates.md` e
  `manual/guias/enviar-uma-proposta.md` (exemplo com `proof_of_concept`).

## R7. Nomes dos formulários de submissão

- **Decisão**: os formulários de submissão dos quatro tipos levam o nome do
  tipo ("Formulário de Submissão - Validação Me-Too", por exemplo). Eles
  passam a "Formulário de Submissão - <nome novo do tipo>". Chaves,
  descrições e campos não mudam.
- **Motivo**: o nome do formulário aparece ao proponente; manter o termo
  antigo contradiz a terminologia que o BraCVAM pediu.

## R8. Versão dos templates

- **Decisão**: não subir `version` nos YAMLs. Nome, descrição e ordem ficam
  em `process_templates`, que o bootstrap atualiza sempre. A versão existente
  recebe o payload novo no mesmo número, como já acontece hoje.
- **Motivo**: o fluxo (fases, atividades, dependências) não muda.

## R9. Nomes dos arquivos YAML

- **Decisão**: manter os nomes `01_` a `04_`. Renomear para seguir a ordem
  nova mexeria em três testes que mapeiam chave para arquivo, sem efeito no
  sistema, porque a ordem vem de `display_order`.
