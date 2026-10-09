# Research: Template de coleta de dados

Cada item registra a decisão, o motivo e as alternativas descartadas. O
critério geral é o da decisão da equipe: a menor complexidade que cumpre os
critérios de aceite, sem deixar lacuna.

## R1. Onde fica o código

- **Decisão**: um serviço novo, `src/pivma/core/collection_template_service.py`,
  com as regras (validação, travamento, arquivo-modelo), e um router novo,
  `src/pivma/routers/collection_templates.py`, fino, no padrão do router
  institucional.
- **Motivo**: `sample_service.complete_sample_definition` precisa chamar o
  travamento da linha do template (R4). Uma regra chamada de dois lugares
  pede um módulo de serviço; o resto do CRUD cabe no mesmo módulo sem
  abstração extra.
- **Alternativas**: tudo no router, como `institutional.py`. Descartada
  porque o `sample_service` teria de importar um router.

## R2. Cálculo do travamento

- **Decisão**: uma função `locked_template_ids(session, template_ids) ->
  set[UUID]` faz uma consulta: processos com `collection_template_id` na
  lista, unidos à `ActivityInstance` de chave `sample_definition` com status
  `COMPLETED`. A consulta usa `skip_soft_delete_filter=True`. A consulta de
  um template e a listagem (uma consulta por página) usam a mesma função.
- **Motivo**: a decisão 6 manda calcular por consulta, sem marcador. Um
  processo excluído vira `CANCELLED` com `deleted_at` preenchido
  (`ensure_process_mutable`), e a exclusão é permitida a qualquer processo
  fora dos estados terminais, inclusive depois da definição das amostras.
  FR-017 diz que processo cancelado trava. Sem o `skip`, o filtro global de
  exclusão lógica (Spec 022) esconderia esse processo e o template
  destravaria, o que a Assumption "um template travado não volta a
  destravar" proíbe.
- **Alternativas**: coluna `locked_at` gravada na conclusão. Descartada pela
  decisão 6. Subconsulta `EXISTS` correlacionada dentro da listagem.
  Descartada porque `paginate_query` devolve só a entidade; a segunda
  consulta por página é mais simples.

## R3. Alteração estrutural e não estrutural

- **Decisão**: são estruturais a criação, a alteração e a exclusão de
  coluna, e a mudança de `min_experiments` ou `min_replicates`. No `PATCH`
  do template, um mínimo só conta como mudança quando o valor enviado
  difere do atual. Enviar o mesmo valor junto com o nome novo é aceito no
  template travado.
- **Motivo**: o frontend costuma reenviar o objeto inteiro. Recusar um
  `PATCH` que só troca o nome por carregar os mínimos iguais quebraria o
  cenário 4 da US3 sem proteger nada.
- **Alternativas**: recusar qualquer `PATCH` com mínimo presente. Descartada
  pelo motivo acima.

## R4. Concorrência entre alteração estrutural e conclusão das amostras (FR-019)

- **Decisão**: as duas operações travam a mesma linha de
  `collection_templates` com `SELECT ... FOR UPDATE`.
  - Toda alteração estrutural trava a linha do template antes de consultar o
    travamento (R2) e só grava se ele estiver livre.
  - `complete_sample_definition` trava a linha do template vinculado ao
    processo, quando houver, antes do `commit`. Processo sem vínculo não
    trava nada.
- **Motivo**: no `READ COMMITTED` do PostgreSQL, cada comando lê um retrato
  novo. Se a conclusão pega a trava antes, a alteração espera e, ao
  consultar o travamento depois do `commit` da conclusão, vê o `COMPLETED` e
  recusa. Se a alteração pega a trava antes, a conclusão espera, e a
  alteração entrou antes da conclusão. Não há ciclo de travas: a alteração
  não trava a `ActivityInstance`, que a conclusão já trava em
  `_mutable_activity`.
- **Alternativas**: nível `SERIALIZABLE` com nova tentativa. Descartada por
  exigir laço de repetição. Trava consultiva do PostgreSQL. Descartada:
  a trava de linha resolve sem chave extra.

## R5. Unicidade de chave e posição sob concorrência

- **Decisão**: a criação e a alteração de coluna já travam a linha do
  template (R4). Com a trava, o serviço confere chave e posição e calcula a
  posição automática sem corrida. Dois índices únicos parciais
  (`deleted_at IS NULL`) em `(collection_template_id, key)` e
  `(collection_template_id, position)` garantem a integridade no banco.
- **Motivo**: a trava serializa as operações de coluna de um mesmo template.
  O serviço devolve `duplicate_key` ou `position_taken` antes de tocar o
  banco, sem cair em erro genérico. Os índices só impedem dados inválidos
  fora da API.
- **Alternativas**: tratar `IntegrityError` e traduzir pelo nome do índice.
  Descartada: com a trava, esse caminho não ocorre, e tratá-lo seria código
  para cenário impossível.

## R6. Códigos de erro

- **Decisão**:

  | Situação | Status | `code` |
  | --- | --- | --- |
  | Template ou coluna inexistente, excluída ou de outro template | 404 | `not_found` |
  | Chave duplicada entre colunas ativas | 409 | `duplicate_key` |
  | Chave reservada (`codigo_amostra`, `experimento`, `replica`) | 409 | `reserved_key` |
  | Posição ocupada por coluna ativa | 409 | `position_taken` |
  | Posição automática acima de 2147483647 | 409 | `position_limit_reached` |
  | Template travado | 409 | `template_locked` |
  | `select` sem opções ou com lista vazia, outro tipo com opções, opção repetida | 422 | `invalid_options` |
  | Opção vazia ou com mais de 255 caracteres | 422 | `validation_error`, `fields[].code = string_too_short` ou `string_too_long` |
  | Chave fora do formato | 422 | `validation_error`, `fields[].code = string_pattern_mismatch` |
  | Tipo fora da lista | 422 | `validation_error`, `fields[].code = literal_error` |
  | Posição ou mínimo menor que 1 | 422 | `validation_error`, `fields[].code = greater_than_equal` |
  | Formato de download fora de `csv` e `xlsx` | 422 | `validation_error`, `fields[].code = literal_error` |
  | Sem a permissão | 403 | `forbidden` |
  | Sem sessão | 401 | `not_authenticated` |
  | Origem não confiável na escrita | 403 | `invalid_origin` |

- **Motivo**: o formato da chave, o tipo e os limites numéricos são
  validação de entrada e seguem o padrão da Spec 034, com o código estável
  no campo. Chave reservada sai como 409, igual à chave duplicada, como
  pede a decisão 3. `invalid_options` fica no serviço porque, no `PATCH`,
  depende do estado resultante (tipo atual mais o enviado).
- **Alternativas**: validar a chave reservada com o Pydantic. Descartada: a
  decisão 3 a trata como a duplicada.

## R7. Arquivo-modelo

- **Decisão**:
  - Rota `GET /collection-templates/{id}/file?format=csv|xlsx`.
  - O cabeçalho é `codigo_amostra`, `experimento`, `replica` e as chaves das
    colunas ativas por `position` crescente.
  - CSV: módulo `csv` da biblioteca padrão, `delimiter=';'`, codificado em
    `utf-8-sig` (BOM), `text/csv; charset=utf-8`.
  - Excel: `openpyxl`, planilha única com o título `resultados`, cabeçalho na
    linha 1, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
  - Os bytes saem num `Response` com `Content-Disposition: attachment;
    filename="template-coleta-<id>.<ext>"`.
- **Motivo**: o arquivo tem uma linha e se gera em memória. O nome pelo
  identificador evita codificar acentos e `;` do nome do template no
  cabeçalho HTTP.
- **Alternativas**: o nome do template no arquivo. Descartada pelo motivo
  acima. `StreamingResponse`. Descartada: não há volume que justifique.

## R8. Dependência `openpyxl`

- **Decisão**: `openpyxl (>=3.1.5,<4.0.0)` nas dependências de produção, com
  `poetry.lock` e `uv.lock` atualizados.
- **Motivo**: decisão 8. É Python puro e lê e escreve `.xlsx`, o que a #30
  precisa.
- **Alternativas**: `xlsxwriter`. Descartada pela decisão 8, porque não lê.

## R9. Permissão

- **Decisão**: código `collection_templates.manage`, UUID fixo
  `00000000-0000-0000-0000-00000000010e`, constante
  `COLLECTION_TEMPLATES_MANAGE` em `core/authorization.py`. A migração só
  insere a permissão, como a `fa506675d3f9`. O `bootstrap_system` a acrescenta
  ao `CANONICAL_PERMISSIONS` e à lista explícita da BraCVAM, como
  `form_templates.manage`.
- **Motivo**: `effective_permission_codes` (Spec 023) já concede toda
  permissão ativa ao Admin e à BraCVAM, então nenhuma composição na migração
  é necessária. O teste `test_bracvam_rbac_migration` trava o conjunto de
  composições explícitas da migração e continua válido.
- **Alternativas**: reaproveitar `form_templates.manage`. Descartada pela
  decisão 6.

## R10. Vínculo na criação do processo

- **Decisão**:
  - `CreateProcessRequest` ganha `collection_template_id: UUID | None = None`.
  - A rota checa, nesta ordem:
    1. com o campo e sem a permissão: 403 `forbidden`;
    2. `template_key`: o 404 atual;
    3. template de coleta inexistente: 404 `not_found`, com a mensagem
       "Template de coleta não encontrado.".
  - `instantiate_process` ganha o parâmetro opcional
    `collection_template_id`. Ele grava o vínculo no processo e o acrescenta
    ao `context_data` do `PROCESS_CREATED` só quando houver.
  - `ProcessInstanceDetail` ganha `collection_template_id: UUID | None`,
    preenchido nos três pontos que montam a resposta (criar, consultar,
    listar).
- **Motivo**: a permissão vem primeiro para não revelar quais identificadores
  existem (constituição III). O parâmetro opcional mantém os chamadores
  atuais e os testes sem mudança (SC-004).
- **Alternativas**: 422 para template inexistente. Descartada: a mesma rota
  já responde 404 para `template_key` inexistente.

## R11. Proteção de origem

- **Decisão**: as rotas de escrita do catálogo recebem `TrustedOrigin`, como
  as do router institucional. As seis rotas de escrita de
  `routers/processes.py` também passam a recebê-la.
- **Motivo**: FR-029 cobre o catálogo. A constituição (III) exige origem
  confiável em toda escrita, e `POST /processes` passou a fazer o vínculo
  privilegiado com o template. A revisão da entrega apontou a falta, e o
  usuário escolheu corrigir o router inteiro (2026-10-09).
- **Alternativas**: proteger só `POST /processes`. Descartada pelo usuário.
  As duas rotas de formulário de atividade sem a checagem (`PUT` e `POST
  /processes/{id}/activities/{activity_key}/form`) também a recebem, a
  pedido do usuário.

## R12. Trilha de mudanças do catálogo

- **Decisão**: só o `AuditMixin` (quem e quando criou, alterou e excluiu).
  Sem tabela de histórico.
- **Motivo**: decisão 1 e Assumption da spec. A regra da constituição sobre
  históricos próprios cita os perfis e o catálogo institucional. O
  `AuditEvent` exige um processo.
- **Alternativas**: tabela de histórico nos moldes de `InstitutionalChange`.
  Descartada: nenhuma fonte pede, e seria recurso fora da lista da decisão
  geral.
