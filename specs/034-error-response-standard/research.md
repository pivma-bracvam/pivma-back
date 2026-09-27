# Research: Formato único das respostas de erro

**Feature**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

As duas dúvidas da spec (forma do corpo e idioma) foram resolvidas em Clarifications. As decisões abaixo tratam de como chegar ao formato único sem mudar status HTTP nem regras de acesso.

## Levantamento

- 99 `HTTPException` em 16 arquivos, mais 4 em `dependencies.py` (sessão, origem, permissão, admin).
- `detail` como texto: cerca de 60 pontos. Mensagens em inglês nos roteadores de usuários, RBAC e catálogo institucional (`'User not found'`, `'Forbidden'`, `'Profile is inactive'`...) e em mensagens de domínio (`'At least one administrator must remain'`, `'Invalid password'`...). Cerca de 30 pontos repetem `str(e)` de exceções de domínio.
- `detail` como objeto: 19 pontos, em `forms`, `processes`, `return_review`, `samples` e `triage`. `invalid_form_values` usa `errors` (lista `{field_key, code, message}`) em vez de `message`.
- Exceções de domínio: `ValidationError`, `ConflictError`, `NotFoundError` e `AuthorizationError` (`process_engine`); `SampleValidationError`/`SampleConflictError` (com `code`); `AttachmentError` (com `code`); `AIProviderError`.
- Validação de entrada: um handler de `RequestValidationError` em `pivma/__init__.py` que troca a resposta inteira por `{'detail': 'Invalid password'}` quando algum erro toca `password`; os demais saem no formato do FastAPI (`loc`, `msg`, `type`, `input`).
- 404 de rota, 405 e 500 não tratados saem no formato do Starlette.
- 17 arquivos de teste comparam `detail` (70 asserções).

## R1. Handlers globais como garantia do formato

**Decision**: Três handlers registrados no app, em `src/pivma/errors.py`:

1. **`StarletteHTTPException`** (inclui 404 de rota e 405):
   - `detail` já no formato (`dict` com `code`) passa adiante, garantindo `message`;
   - `detail` texto vira `{code: <genérico do status>, message: <texto>}`.

   Os cabeçalhos da exceção (ex.: `WWW-Authenticate`) são preservados.
2. **`RequestValidationError`**: `{code: 'validation_error', message: 'Dados inválidos.', fields: [...]}` (R3).
3. **`Exception`** (não tratada): `500` com `{code: 'internal_error', message: 'Erro interno do servidor.'}`, sem detalhes. A exceção continua indo para o log.

**Rationale**: o handler de `HTTPException` é a rede de segurança (SC-001): mesmo um ponto esquecido sai no formato, com código genérico. Os pontos conhecidos são migrados para códigos explícitos (R2), porque o código genérico não distingue casos no mesmo status (FR-007).

**Alternatives considered**: middleware reescrevendo corpos de resposta. É frágil (precisa ler e reescrever o JSON) e não alcança o 500.

## R2. Códigos explícitos nos pontos de erro

**Decision**:
- Novo módulo `src/pivma/core/errors.py` com `api_error(status, code, message, **context) -> HTTPException`, que monta `detail={'code', 'message', **context}`.
- As exceções de domínio (`ProcessEngineError` e subclasses, `AttachmentError`) ganham um atributo opcional `code` (padrão `None`), preenchido onde o caso precisa de código próprio. Os roteadores convertem com o código da exceção ou com o genérico do status.
- Os helpers locais (`not_found`, `conflict`, `forbidden` em `institutional`, `rbac`, `process_participants`; `_not_found` em `invites`; `not_authenticated` em `dependencies`) passam a usar `api_error`, com mensagens em português.

**Rationale**: FR-007 pede códigos que distingam casos no mesmo status. Os helpers já centralizam a maior parte dos pontos, o que reduz o número de edições.

**Catálogo** (genéricos por status e específicos novos) em [data-model.md](data-model.md).

## R3. Erros de validação por campo

**Decision**: Cada erro do Pydantic vira `{location, field, code, message}`:
- `location`: primeiro elemento de `loc`: `body`, `query`, `path`, `header` ou `cookie`.
- `field`: os demais elementos de `loc`, unidos por `.` (índices de lista como número). Vazio quando o erro é do corpo inteiro.
- `code`: o `type` do Pydantic (`missing`, `string_too_short`, `value_error`, `less_than_equal`, `enum`, `literal_error`...).
- `message`: tradução em português por `type` (tabela em `core/errors.py`); tipos sem tradução usam "Valor inválido.".

Nunca inclui `input`, `ctx` nem `url` (FR-004). Campos cujo `loc` contém `password` recebem `code: 'invalid'` e `message: 'Senha inválida.'` (FR-010), preservando o que o handler atual faz.

`invalid_form_values` (validação de formulário dinâmico feita no domínio) passa a usar o mesmo `fields`, com `location: 'body'` e `field: 'values.<field_key>'`.

**Rationale**: FR-003, FR-004 e FR-012. O `type` do Pydantic já é um identificador estável e em inglês. As mensagens com parâmetros (limites, tamanhos) são traduzidas sem repetir o valor enviado. Os limites vêm do `ctx` do erro, que é regra da API, não dado do usuário. Na senha, nem isso.

**Alternatives considered**: repassar `msg` do Pydantic, que fica em inglês e contraria a Q2.

## R4. Mensagens de domínio

**Decision**: As mensagens de exceção de domínio em inglês são traduzidas no ponto em que são levantadas. Os pontos que repetem `str(e)` continuam repetindo, porque as mensagens de domínio passam a ser escritas para o usuário, em português. Mensagens com detalhes internos (ex.: `f'Erro ao instanciar processo: {e!s}'`) são trocadas por mensagens fixas, e o detalhe vai para o log.

**Rationale**: FR-004 e FR-012 com o menor número de mudanças. As exceções de domínio já são a fonte da mensagem na maior parte da API.

## R5. OpenAPI

**Decision**:
- Schemas `ErrorResponse` (`detail: ErrorDetail`), `ErrorDetail` (`code`, `message`, `fields?`) e `FieldError` (`location`, `field`, `code`, `message`), todos com descrição em `schemas.py`.
- Uma função `custom_openapi` troca as referências a `HTTPValidationError` por `ErrorResponse` nas respostas `422` geradas automaticamente e remove `HTTPValidationError`/`ValidationError` dos componentes.

**Rationale**: FR-011. O FastAPI sempre injeta `HTTPValidationError` na resposta `422` das rotas com parâmetros; sem o pós-processamento, a documentação mostraria o formato antigo.

**Alternatives considered**: declarar `responses={422: ...}` em cada rota. São dezenas de rotas, e é fácil esquecer uma.

## R6. Status preservados

**Decision**: Nenhum status muda (FR-008). Os casos que hoje respondem `404` para esconder a existência de um recurso continuam com `not_found` e a mesma mensagem genérica do recurso (FR-009). Os `400`/`413` de anexos continuam com `empty_file`/`file_too_large`.

## R7. Testes existentes

**Decision**: Os 17 arquivos que comparam `detail` passam a comparar `detail.code` (preferencialmente) ou `detail.message`. Onde o teste só confere o status, nada muda. Um teste de contrato parametrizado passa por cada status usado e confere o formato (SC-001).
