# Erros

Todo erro responde no mesmo formato:

```json
{"detail": {"code": "duplicate_cas", "message": "CAS já cadastrado neste processo."}}
```

- `code`: estável, em inglês. O cliente decide o comportamento por ele.
- `message`: em português, para exibir. Pode mudar.
- Nenhuma resposta repete os valores enviados nem detalhes internos.
- Alguns erros trazem contexto extra (ex.: `substance_ids` em `missing_sds`).

## Validação (`422`)

Erros de entrada trazem `fields`, um item por campo:

```json
{"detail": {"code": "validation_error", "message": "Dados inválidos.",
  "fields": [{"location": "body", "field": "email", "code": "value_error",
              "message": "E-mail inválido."}]}}
```

| Campo | Valores |
|---|---|
| `location` | `body`, `query`, `path`, `header`, `cookie` |
| `field` | Caminho separado por ponto (`values.method_title`) |
| `code` | Tipo do erro (`missing`, `string_too_short`, `extra_forbidden`…) |

Em campos de senha, o item vem com `code: invalid` e `message: Senha
inválida.`, sem expor a regra nem o valor.

## Códigos

Quando não há código específico, vale o genérico do status (primeira linha de
cada grupo).

| Status | `code` | Quando |
|---|---|---|
| 400 | `bad_request` | Requisição inválida |
| 400 | `empty_file` | Anexo vazio |
| 400 | `invalid_current_password` | `PATCH /auth/me` com senha atual errada |
| 400 | `invalid_reset_token` | Token de redefinição desconhecido, expirado, usado, substituído ou de conta inativa |
| 401 | `not_authenticated` | Sessão ausente, expirada ou de conta inativa |
| 401 | `invalid_credentials` | Login com usuário ou senha errados |
| 403 | `forbidden` | Sem permissão global; ver sem editar a atividade; conflito de interesse vigente |
| 403 | `invalid_origin` | Mutação com cookie vinda de origem fora de `AUTH_ALLOWED_ORIGINS` |
| 403 | `admin_only` | Rota exclusiva do perfil Administrador |
| 403 | `invite_email_mismatch` | Aceite de convite por conta com outro e-mail |
| 404 | `not_found` | Recurso inexistente **ou** sem concessão de ver. A resposta é igual nos dois casos |
| 404 | `compound_not_found` | O PubChem não conhece o CAS consultado |
| 405 | `method_not_allowed` | Método não suportado na rota |
| 409 | `conflict` | Regra de negócio sem código próprio |
| 409 | `duplicate` | Nome, designação ou vínculo repetido; nome reservado de perfil oficial |
| 409 | `duplicate_cas` | CAS repetido entre substâncias ativas do processo |
| 409 | `inactive_entity` | Usuário, perfil, laboratório ou instituição inativos |
| 409 | `process_closed` | Processo encerrado ou excluído |
| 409 | `invalid_transition` | Ação fora do estado permitido (formulário enviado, atividade concluída, processo terminal) |
| 409 | `form_submitted` | Anexo em formulário já enviado |
| 409 | `invite_expired` | Convite vencido |
| 409 | `invite_not_pending` | Convite já aceito ou revogado |
| 409 | `self_deactivation` | Usuário tentando desativar a própria conta |
| 409 | `last_administrator` | Remover a última conta administradora ativa |
| 409 | `channel_unavailable` | Convite por e-mail sem e-mail ou sem `INVITE_URL_TEMPLATE` configurados |
| 409 | `sample_definition_not_frozen` | Dispensa de laboratório antes de concluir as amostras |
| 409 | `already_waived` | Segunda dispensa do mesmo laboratório na fase |
| 409 | `no_frozen_laboratories` | Ativar atividade por laboratório sem laboratórios congelados |
| 409 | `vial_already_registered` | Segundo registro de recebimento do mesmo frasco |
| 409 | `already_decided` | Decisão sobre inconformidade já decidida |
| 409 | `no_reserve_vials` | Reenvio de frasco com a reserva da substância em zero |
| 409 | `duplicate_key` | Chave repetida entre as colunas ativas do template de coleta |
| 409 | `reserved_key` | Coluna com `codigo_amostra`, `experimento` ou `replica` como chave |
| 409 | `position_taken` | Posição ocupada por outra coluna ativa do template de coleta |
| 409 | `position_limit_reached` | Coluna sem posição quando a última coluna ativa já está em 2147483647 |
| 409 | `template_locked` | Mudança estrutural em template de coleta travado (colunas ou mínimos) |
| 413 | `payload_too_large` | Corpo grande demais |
| 413 | `file_too_large` | Anexo acima de `ATTACHMENT_MAX_SIZE_MB` |
| 422 | `validation_error` | Entrada inválida (com `fields`) |
| 422 | `invalid_form_values` | Valores do formulário dinâmico inválidos (com `fields`, `field: values.<chave>`) |
| 422 | `invalid_submission_values` | Valores inválidos em `PUT`/`PATCH /processes/{id}` (com `fields`) |
| 422 | `extension_not_allowed` | Extensão fora da lista do campo |
| 422 | `not_a_file_field` | Anexo em campo que não é de arquivo |
| 422 | `invalid_cas` | CAS com formato ou dígito verificador inválido |
| 422 | `invalid_temperature_range` | Faixa térmica sem regime, regime sem a faixa que exige ou mínima acima da máxima (com `fields`) |
| 422 | `no_substances` | Concluir amostras sem substância |
| 422 | `missing_sds` | Concluir amostras com substância sem SDS (com `substance_ids`) |
| 422 | `no_laboratories` | Concluir amostras sem laboratório participante |
| 422 | `laboratory_not_frozen` | Dispensar laboratório fora do conjunto congelado |
| 422 | `invalid_options` | Coluna `select` sem opções ou com opção repetida; outro tipo com opções |
| 500 | `internal_error` | Erro inesperado. O detalhe vai só para o log |
| 503 | `service_unavailable` | Dependência indisponível |
| 503 | `ai_unavailable` | Provedor de IA falhou ao sugerir critérios ou testar uma versão |
| 503 | `lookup_unavailable` | PubChem fora do ar, com erro, lento ou em formato inesperado |

## `404` e não `403`

Quando revelar a existência de um recurso já seria um vazamento, a API
responde `404`:

- processo em que o usuário não tem atribuição (fora Admin e BraCVAM);
- atividade sem concessão de ver;
- execução de outro laboratório;
- amostras cegas para laboratórios e Grupo Gestor;
- frasco, registro de recebimento ou foto de outro laboratório.

Veja [Autorização](../explicacao/autorizacao.md).
