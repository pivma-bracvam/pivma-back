# Pesquisa técnica: Autenticação de Usuários

## JWT

**Decisão**: adicionar `PyJWT >=2.13,<3.0` e usar somente HS256 com chave aleatória de pelo menos 32 bytes fornecida por variável de ambiente.

**Justificativa**: a documentação do FastAPI apresenta PyJWT para JWT, e PyJWT 2.11 ou superior declara suporte a Python 3.14. A API assina e valida no mesmo serviço, portanto uma chave simétrica atende ao escopo sem material de chaves assimétricas. Na leitura, o código fixará `algorithms=['HS256']` e exigirá `sub`, `iat` e `exp`. O token usará `sub` com o UUID da conta, sem `iss`, `aud`, `jti`, escopos ou perfis. `iss` e `aud` seriam hardening opcional para ambientes com múltiplos emissores ou destinatários, cenário que esta feature não atende.

**Alternativas consideradas**:

- `PyJWT[crypto]` com RSA ou ECDSA: exige material criptográfico extra sem requisito de múltiplos emissores ou verificadores.
- Authlib e bibliotecas OAuth: incluem fluxos e conceitos fora da feature.
- `python-jose`: não foi escolhido porque a pesquisa não confirmou suporte a Python 3.14 com a mesma clareza.

Fontes: [FastAPI JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html), [PyJWT changelog](https://github.com/jpadilla/pyjwt/blob/master/CHANGELOG.rst), [RFC 8725, seção 3.1](https://datatracker.ietf.org/doc/html/rfc8725#section-3.1).

## Cookie e proteção contra requisições forjadas

**Decisão**: emitir o cookie `access_token` com `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/` e expiração alinhada ao JWT de oito horas. Para o único endpoint autenticado que altera estado, logout, exigir `Origin` igual a uma origem confiável configurada. Origem ausente, inválida ou fora da lista retorna 403 antes de remover o cookie.

**Justificativa**: `HttpOnly` bloqueia acesso por scripts, `Secure` restringe o envio a HTTPS e `SameSite=Strict` cumpre a decisão aprovada. CORS não autoriza uma operação no backend; a rota deve validar `Origin`. A aplicação só configura CORS se houver origens confiáveis, usando a mesma lista com credenciais e sem curingas.

**Alternativas consideradas**:

- `SameSite=Lax`: não cumpre a decisão da especificação.
- Double-submit ou token CSRF: acrescenta um token legível e não foi escolhido pela equipe.
- Inferir uma origem a partir de `Host`: cria uma política implícita e insegura.
- Curinga CORS: incompatível com cookies e credenciais.

Fontes: [Starlette Responses](https://www.starlette.io/responses/), [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/), [Starlette CORSMiddleware](https://www.starlette.io/middleware/).

## Rotas e falhas públicas

**Decisão**: expor `POST /auth/login`, `GET /auth/me` e `POST /auth/logout`. Login inválido retorna 401 com `Invalid credentials`; token ausente, inválido, vencido ou associado a conta excluída retorna 401 com `Not authenticated`; origem recusada no logout retorna 403 com `Invalid origin`.

**Justificativa**: as três rotas demonstram autenticação, reconhecimento posterior e encerramento de sessão sem criar um recurso de domínio. A mensagem única de login impede enumeração por identificador ou estado de exclusão.

**Alternativas consideradas**:

- Acrescentar endpoints protegidos de domínio: antecipa RF002 a RF006.
- Persistir sessões ou `jti`: seria necessário apenas para revogação, que a especificação exclui.
