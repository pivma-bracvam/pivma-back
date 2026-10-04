# Variáveis de ambiente

Lidas por `Settings` em `src/pivma/core/settings.py`, do ambiente ou do
arquivo `.env`. Modelo: `.env.example`.

## Obrigatórias

| Variável | Regra |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://usuario:senha@host:5432/banco`. No compose, o host é `db` |
| `JWT_SECRET_KEY` | Mínimo de 32 bytes |
| `AUTH_ALLOWED_ORIGINS` | Lista JSON de origens (`http(s)://host[:porta]`, sem caminho), ex.: `'["http://localhost:3000"]'` |

## IA

| Variável | Padrão | Uso |
|---|---|---|
| `AI_PROVIDER` | `openai` | `openai` ou `fake` (determinístico, sem rede) |
| `OPENAI_API_KEY` | — | Exigida com `openai` |
| `AI_MODEL_EXTRACTION` | `gpt-5.4-nano` | Reservada; nenhum passo do pipeline a usa hoje |
| `AI_MODEL_FAST` | `gpt-5.4-nano` | Critérios `presence` e `conformity` |
| `AI_MODEL_REASONING` | `gpt-5.4-mini` | Critérios `quality`, `comparison`, `cross_field_consistency` e sugestão de critérios |

## Anexos e amostras

| Variável | Padrão | Uso |
|---|---|---|
| `ATTACHMENTS_DIR` | `var/attachments` | Onde os arquivos ficam |
| `ATTACHMENT_MAX_SIZE_MB` | `25` | Limite por arquivo (anexos e SDS) |
| `ATTACHMENT_DEFAULT_EXTENSIONS` | `["pdf","docx","doc","png","jpg","jpeg"]` | Extensões quando o campo não declara as suas |
| `SAMPLE_QR_BASE_URL` | primeira origem de `AUTH_ALLOWED_ORIGINS` | Base da URL gravada no QR dos frascos |
| `PUBCHEM_BASE_URL` | `https://pubchem.ncbi.nlm.nih.gov` | Endereço do PubChem na consulta de sugestões por CAS |
| `PUBCHEM_TIMEOUT_SECONDS` | `10` | Tempo máximo de cada chamada ao PubChem (mínimo 1) |

## Convites e senha

| Variável | Padrão | Uso |
|---|---|---|
| `INVITE_EXPIRATION_HOURS` | `1` | Validade do convite |
| `INVITE_URL_TEMPLATE` | — | Página de aceite no frontend; deve conter `{token}` uma vez |
| `PASSWORD_RESET_URL_TEMPLATE` | — | Página de redefinição; deve conter `{token}` uma vez |

## Notificações

| Variável | Padrão | Uso |
|---|---|---|
| `NOTIFICATION_EMAIL_BACKEND` | vazio | `smtp`, `fake` (testes) ou vazio (sem e-mail) |
| `SMTP_HOST` | — | Servidor |
| `SMTP_PORT` | `587` | Porta |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` ou `none` |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | — | Credenciais |
| `SMTP_TIMEOUT_SECONDS` | `15` | Timeout |
| `NOTIFICATION_FROM_ADDRESS` | — | Remetente |
| `NOTIFICATION_FROM_NAME` | `pi*VMA` | Nome do remetente |
| `NOTIFICATION_ENCRYPTION_KEY` | — | Chave Fernet do conteúdo pendente |
| `NOTIFICATION_MAX_ATTEMPTS` | `5` | Tentativas por envio |
| `NOTIFICATION_RETRY_BASE_SECONDS` | `30` | Primeira espera; dobra a cada tentativa |
| `NOTIFICATION_RETRY_MAX_SECONDS` | `900` | Espera máxima |
| `NOTIFICATION_POLL_SECONDS` | `5` | Pausa do worker quando a fila esvazia |

## Provisionamento

Lidas só por `python -m pivma.bootstrap_system`:

| Variável | Padrão | Uso |
|---|---|---|
| `INITIAL_ADMIN_EMAIL` | — | Com a senha, cria o primeiro administrador |
| `INITIAL_ADMIN_PASSWORD` | — | Senha dele |
| `INITIAL_ADMIN_USERNAME` | `admin` | Username dele |

## Docker Compose

| Variável | Padrão | Uso |
|---|---|---|
| `DB_PORT` | `5432` | Porta do banco no host |
| `API_PORT` | `8000` | Porta da API no host |
