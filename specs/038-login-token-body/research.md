# Research: Token de Acesso no Corpo da Resposta de Login

Nenhum item da Technical Context ficou como NEEDS CLARIFICATION. As decisões abaixo foram verificadas no código atual e num protótipo descartável com FastAPI 0.141.1.

## 1. Formato da resposta e schema

- **Decision**: modelo Pydantic `LoginResponse` em `src/pivma/schemas.py` com `access_token: str`, `token_type: Literal['bearer']` e `expires_in: int`, os três sem valor padrão. A rota troca `response_class=Response` por `response_model=LoginResponse` e continua recebendo `response: Response` para gravar o cookie.
- **Rationale**: sem valor padrão, o OpenAPI marca os três campos como obrigatórios (`required`). Com `token_type = 'bearer'` como padrão, o protótipo mostrou `required: [access_token, expires_in]`, o que deixaria o contrato mais fraco do que a resposta real. `Literal` gera `const: "bearer"` no schema. O protótipo confirmou que cookie e cabeçalhos gravados no `Response` injetado chegam na resposta junto com o corpo do `response_model`.
- **Alternatives considered**: devolver `dict` sem modelo (não documenta o schema, viola FR-009); nomear `TokenResponse` (a issue aceita os dois nomes; `LoginResponse` segue o padrão `LoginCredentials` do mesmo fluxo).

## 2. Fonte única da validade

- **Decision**: calcular `expires_in = int(ACCESS_TOKEN_TTL.total_seconds())` uma vez na rota e usar o mesmo valor no `max_age` do cookie e no corpo. A expiração do token já vem de `ACCESS_TOKEN_TTL` em `create_access_token`.
- **Rationale**: atende FR-004 e o edge case "validade coerente" sem constante nova.
- **Alternatives considered**: constante `ACCESS_TOKEN_TTL_SECONDS` em `core/security.py` (duplicaria a fonte da verdade).

## 3. Leitura do Bearer e documentação no OpenAPI

- **Decision**: declarar `bearer_token = HTTPBearer(auto_error=False)` em `src/pivma/dependencies.py` e recebê-lo em `get_current_user` como `Security(bearer_token)`, substituindo a leitura manual de `request.headers['Authorization']`. A ordem fica como hoje: cookie, depois Bearer, depois o parâmetro `token`.
- **Rationale**: o OpenAPI passa a declarar `HTTPBearer` em todas as rotas que dependem de `get_current_user`, com `security: [{APIKeyCookie: []}, {HTTPBearer: []}]` (verificado no protótipo), o que habilita o "Authorize" de `/docs` (FR-010, SC-005). O código encolhe. Diferenças de comportamento: o esquema passa a aceitar `bearer` em qualquer caixa (RFC 7235); `Bearer ` sem credencial vira `None` em vez de string vazia, e nos dois casos o resultado é 401 `not_authenticated`.
- **Alternatives considered**: manter a leitura manual e só registrar o esquema no OpenAPI à mão (duas fontes da verdade que podem divergir).

## 4. Dispensa da checagem de origem com Bearer

- **Decision**: `require_trusted_origin` passa a receber `Security(access_token_cookie)` e `Security(bearer_token)`. Se não há cookie e há Bearer, a função retorna sem checar `Origin`. Nos demais casos, a checagem atual continua.
- **Rationale**: a checagem de `Origin` protege contra CSRF, ataque que depende de o navegador anexar credencial automaticamente, e só o cookie é anexado assim. Para mandar `Authorization` de outro site, o navegador exige preflight de CORS, e o `CORSMiddleware` (`src/pivma/__init__.py`) só aceita `AUTH_ALLOWED_ORIGINS` com `allow_headers=['Content-Type']`; nenhuma origem cruzada passa o preflight com `Authorization`. Essa configuração não muda: o frontend web continua com o cookie, e `/docs` roda na mesma origem da API, sem CORS. Exigir ausência de cookie fecha o caso em que o navegador anexaria o cookie junto com um Bearer qualquer, já que `get_current_user` dá precedência ao cookie. Reusar os mesmos objetos de segurança faz o FastAPI resolver cada um uma vez por requisição. Todas as rotas com `TrustedOrigin` também exigem autenticação (verificado nos 12 routers), então um Bearer inválido termina em 401.
- **Alternatives considered**: exigir que clientes de API mandem `Origin` manualmente (mantém exigência artificial; rejeitada pelo usuário); validar o token dentro de `require_trusted_origin` (duplicaria `get_current_user` sem ganho de segurança).

## 5. Cache da resposta

- **Decision**: `response.headers['Cache-Control'] = 'no-store'` no login bem-sucedido.
- **Rationale**: RFC 6749, seção 5.1, exige `no-store` em respostas que carregam token. O OAuth 2.1 e a RFC 9700 dispensam o `Pragma: no-cache`, cabeçalho de HTTP/1.0 que não vale a linha extra.
- **Alternatives considered**: middleware global de cache (fora do escopo).

## 6. Pontos fora do escopo, registrados

- Parâmetro de consulta `?token=` em `get_current_user` (anterior à feature, commit `76810fe`): mantido. Remover pode quebrar cliente e merece issue própria.
- Logout de cliente Bearer: o token continua válido até expirar, como qualquer token emitido hoje. Revogação exigiria estado no servidor.
