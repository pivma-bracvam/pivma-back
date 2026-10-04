# Research: Spec 040

## R1. Onde vive o recebimento: rotas próprias, não formulário

- **Decision**: o recebimento usa rotas e tabelas próprias
  (`/processes/{id}/sample-receipt/...`), como a definição das amostras
  (Spec 031). A atividade `sample_receipt` não declara formulário.
- **Rationale**: o registro é por frasco, com regras de domínio (faixa
  térmica da substância, inconformidade, conclusão automática do lote) e
  isolamento por laboratório. As rotas de formulário recusam atividade por
  laboratório (Spec 036, FR-034) e não têm o conceito de frasco.
- **Alternatives considered**: estender as rotas de formulário para
  atividade por laboratório. Exigiria um formulário com um grupo repetido por
  frasco e regras que o motor de formulários não expressa.

## R2. Etapa 3 nos templates

- **Decision**: os cinco templates ganham `phase_3_validation_execution`
  ("Execução da Validação") com:
  - `sample_receipt` ("Confirmação de Recebimento de Amostras"),
    `activity_type: sample_receipt`, `execution_scope: per_laboratory`,
    `assigned_role` e `edit` = `participating_laboratory`, dependente de
    `sample_definition`;
  - `sample_receipt_resolution` ("Resolver problemas no recebimento de
    amostras"), `activity_type: sample_receipt_resolution`, `edit` =
    `sample_selection_group`, sem dependências.
- **Rationale**: a conclusão de `sample_definition` já ativa dependentes por
  laboratório (Spec 036). A resolução é aberta por evento, como
  `submission_return_review`.
- **Consequência no motor**: hoje a instanciação inicia toda atividade sem
  dependências, salvo `return_review`. O conjunto passa a ser
  `EVENT_OPENED_ACTIVITY_TYPES = {return_review, sample_receipt_resolution}`.

## R3. Conclusão do lote e o motor

- **Decision**: extrair de `complete_laboratory_run` a parte que conclui a
  execução (status, tarefas, evento, desbloqueio, agregado) para
  `_finish_laboratory_run`. `complete_laboratory_run` continua com as mesmas
  checagens e passa a chamá-la. O recebimento chama `_finish_laboratory_run`
  quando o lote fecha: no registro (ator: laboratório) e no aceite com
  ressalva (ator: Grupo de Seleção, que não edita `sample_receipt`).
- **Rationale**: mudança cirúrgica; sem ela o Grupo de Seleção receberia
  `403` ao concluir o lote de outro cargo.

## R4. Situação do frasco: derivada, não gravada

- **Decision**: a situação (`pending`, `received`, `awaiting_decision`,
  `accepted_with_caveat`, `replaced`, `disqualified`) é calculada do código,
  do registro e da inconformidade.
- **Rationale**: uma só fonte de verdade; nada a sincronizar.

## R5. Reenvio

- **Decision**: o reenvio, sob o lock do processo, debita
  `reserve_vials_count`, exclui logicamente o código anterior, cria o código
  novo com `replaces_code_id` e grava o código novo na inconformidade. A
  execução do laboratório continua em andamento (ela não podia ter
  concluído).
- **Rationale**: os índices únicos de código ativo (por processo e por
  substância × laboratório) continuam valendo. O registro do frasco anterior
  aponta para o código excluído e fica preservado. A lista de etiquetas, que
  lê códigos ativos, passa a trazer a etiqueta nova sem mudança.
- **Alternatives considered**: abrir execução nova do laboratório
  (`reopen_laboratory_run`). Só reabre execução concluída e reabriria em
  cadeia o que depende dela; aqui a execução nunca concluiu.

## R6. Desclassificação

- **Decision**: chamar `waive_laboratory` com a fase de `sample_receipt` e a
  justificativa como motivo. Se o laboratório já estiver dispensado
  (`already_waived`), só encerrar as inconformidades.
- **Rationale**: reusa a dispensa da Spec 036, com custódia preservada e
  evento `LABORATORY_WAIVED` visível só à gestão.

## R7. Aviso ao Grupo de Seleção

- **Decision**: tarefa na execução aberta de `sample_receipt_resolution`
  (abre uma se não houver) e um e-mail por pessoa com designação ativa de
  `sample_selection_group` no processo, `kind =
  sample_receipt_nonconformity_email`, assunto
  `('sample_receipt_nonconformity', id)`. Sem canal de e-mail configurado
  (`email_channel_available` falso), nenhum e-mail é pedido e o registro
  segue.
- **Rationale**: não existe central de notificações; a tarefa é o aviso
  dentro da plataforma. O e-mail não pode travar o registro do laboratório.
- **Alternatives considered**: recusar o registro sem e-mail configurado
  (como o convite). Puniria o laboratório por configuração da implantação.

## R8. PubChem

- **Decision**: cliente `httpx.AsyncClient` (já instalado pelo pacote
  `httpx2`), três chamadas PUG-REST/PUG-View:
  1. `GET {base}/rest/pug/compound/name/{cas}/cids/JSON` → primeiro CID; `404`
     → "composto não encontrado";
  2. `GET {base}/rest/pug/compound/cid/{cid}/property/Title,IUPACName/JSON`;
  3. `GET {base}/rest/pug_view/data/compound/{cid}/JSON?heading=GHS+Classification`
     → códigos `GHS01`…`GHS09` das URLs de ícone do **primeiro** bloco
     "Pictogram(s)" (o que o PubChem exibe: `ShowAtMost: 1`); `404` → lista
     vazia.
  Qualquer outra falha, resposta fora do formato ou tempo esgotado →
  "consulta indisponível" (`503 lookup_unavailable`).
  Configuração: `PUBCHEM_BASE_URL` (padrão
  `https://pubchem.ncbi.nlm.nih.gov`) e `PUBCHEM_TIMEOUT_SECONDS` (padrão 10).
  O transporte vem de uma dependência FastAPI, sobrescrita nos testes por
  `httpx.MockTransport`.
- **Rationale**: formato conferido em 2026-10-04 contra o serviço real
  (formaldeído, CID 712: GHS05, GHS06, GHS08 no primeiro bloco). A união de
  todos os blocos mistura notificações de fornecedores diferentes e
  superestima o perigo.
- **Alternatives considered**: EPA CompTox (exige chave de API); gravar a
  sugestão no servidor e pedir "aplicar" (dois passos sem ganho: o cadastro já
  é a confirmação).

## R9. Fotos

- **Decision**: `Artifact` com `key = sample_receipt_photo`, ligado à
  execução do laboratório, `metadata_payload.receipt_id`. Extensões `png`,
  `jpg`, `jpeg`; teto `ATTACHMENT_MAX_SIZE_MB`; gravação por
  `attachment_service.store_upload`.
- **Rationale**: mesmo padrão da SDS (Spec 031) e dos anexos (Spec 016), sem
  tabela nova.

## R10. Faixa térmica

- **Decision**: colunas `Float` em °C. Regime `ambient` preenche 15–25 e
  `refrigerated` 2–8 quando a faixa não vem; `frozen`, `deep_frozen` e
  `custom` exigem os dois limites. Na alteração, a regra roda sobre o estado
  resultante (valores gravados + enviados).
- **Rationale**: a #72 dá faixas só para ambiente e refrigerado; para
  congelado e ultracongelado dá um valor nominal, que não define a tolerância.

## R11. Concorrência

- **Decision**: registro, foto, decisão e reenvio travam o processo
  (`_lock_process`, como a Spec 036). Índice único parcial em
  `sample_receipts(blind_sample_code_id)` garante um registro por frasco
  mesmo sem lock.

## R12. Eventos

| Evento | Execução | Contexto |
| --- | --- | --- |
| `SAMPLE_RECEIPT_REGISTERED` | do laboratório | `laboratory_id`, `blind_sample_code_id`, `receipt_id`, `conforming`, `deviations` |
| `SAMPLE_RECEIPT_PHOTO_ATTACHED` | do laboratório | `laboratory_id`, `receipt_id`, `artifact_id` |
| `SAMPLE_NONCONFORMITY_OPENED` | da resolução | `nonconformity_id`, `laboratory_id`, `deviations` |
| `SAMPLE_NONCONFORMITY_RESOLVED` | da resolução | `nonconformity_id`, `laboratory_id`, `decision` |
| `SAMPLE_VIAL_RESENT` | da resolução | `nonconformity_id`, `laboratory_id`, `replacement_code_id`, `reserve_vials_count` |
| `SAMPLE_RECEIPT_RESOLUTION_OPENED` | da resolução | `run_number` |

Nenhum evento traz nome, CAS, lote, código cego ou justificativa. Eventos da
execução do laboratório seguem o filtro da Spec 037; os da resolução, a
concessão de visão da atividade (Grupo de Seleção, admin, BraCVAM).
