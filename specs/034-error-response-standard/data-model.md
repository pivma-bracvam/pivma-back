# Data Model: Formato único das respostas de erro

**Feature**: [spec.md](spec.md) · **Research**: [research.md](research.md)

Sem tabela nova e sem migração.

## Schemas

### ErrorResponse

| Campo | Tipo | Regra |
|---|---|---|
| `detail` | `ErrorDetail` | sempre presente |

### ErrorDetail

| Campo | Tipo | Regra |
|---|---|---|
| `code` | texto | identificador estável, inglês, `snake_case` |
| `message` | texto | português, para o usuário final; sem valores enviados nem detalhes internos |
| `fields` | lista de `FieldError` | só em erros de validação (`validation_error`, `invalid_form_values`) |
| *(contexto)* | variável | só em códigos específicos que já trazem contexto hoje (ex.: `missing_sds` → `substance_ids`) |

### FieldError

| Campo | Tipo | Regra |
|---|---|---|
| `location` | `body` \| `query` \| `path` \| `header` \| `cookie` | origem do campo |
| `field` | texto | caminho do campo separado por `.` (ex.: `values.method_title`, `per_page`); vazio para o corpo inteiro |
| `code` | texto | tipo do erro (ex.: `missing`, `string_too_short`, `less_than_equal`); `invalid` para senha |
| `message` | texto | português; nunca repete o valor enviado |

## Códigos genéricos por status

| Status | Código | Mensagem padrão |
|---|---|---|
| 400 | `bad_request` | "Requisição inválida." |
| 401 | `not_authenticated` | "Sessão ausente ou expirada." |
| 403 | `forbidden` | "Sem permissão para esta ação." |
| 404 | `not_found` | "Recurso não encontrado." |
| 405 | `method_not_allowed` | "Método não permitido." |
| 409 | `conflict` | "A operação conflita com o estado atual." |
| 413 | `payload_too_large` | "Conteúdo grande demais." |
| 422 | `validation_error` | "Dados inválidos." |
| 500 | `internal_error` | "Erro interno do servidor." |
| 503 | `service_unavailable` | "Serviço indisponível no momento." |

## Códigos específicos

**Existentes (FR-005, nomes mantidos)**: `invalid_transition`, `forbidden`, `not_found`, `form_submitted`, `invalid_form_values`, `not_a_file_field`, `empty_file`, `file_too_large`, `extension_not_allowed`, `invalid_cas`, `duplicate_cas`, `no_substances`, `missing_sds`, `no_laboratories`.

**Novos (FR-007)**:

| Código | Status | Situação |
|---|---|---|
| `invalid_credentials` | 401 | login com credenciais inválidas |
| `invalid_origin` | 403 | mutação de origem não confiável |
| `admin_only` | 403 | rota restrita a administradores |
| `invite_email_mismatch` | 403 | aceite com e-mail diferente do convite |
| `invite_expired` | 409 | convite expirado |
| `invite_not_pending` | 409 | convite já aceito ou revogado |
| `self_deactivation` | 409 | desativar a própria conta |
| `last_administrator` | 409 | remover o último administrador ativo |
| `inactive_entity` | 409 | usuário, perfil, instituição, laboratório ou afiliação inativos |
| `process_closed` | 409 | processo encerrado não aceita a alteração |
| `duplicate` | 409 | violação de unicidade (cadastro, designação, convite pendente) |
| `ai_unavailable` | 503 | serviço de IA indisponível |

A lista de códigos específicos pode crescer; cada novo código é mudança de contrato e entra no changelog.
