# Modelo de dados: Autenticação de Usuários

## Conta de usuário existente

**Fonte confirmada**: `src/pivma/core/database/models.py`.

| Campo | Uso na autenticação | Regra |
|---|---|---|
| `id` | Identifica a conta no claim `sub` | UUID imutável; não expor como credencial. |
| `username` | Identificador aceito no login | Comparar sem distinção de caixa entre contas ativas. |
| `email` | Identificador alternativo aceito no login | Comparar sem distinção de caixa entre contas ativas. |
| `password_hash` | Verifica a senha | Usar a verificação Argon2id existente; nunca retornar ou registrar senha. |
| `deleted_at` | Define conta ativa | Valor nulo permite autenticação e reconhecimento. Valor preenchido causa recusa. |

Nenhuma coluna, índice ou migração será criada.

## Perfis globais na identidade

`GET /auth/me` apresenta, em `access.profiles`, os perfis globais ativos já atribuídos à conta.
Cada resumo contém `id`, `name` e `active=true`. A lista é informativa e não concede acesso nem
substitui a verificação de permissões feita pelo backend.

## JWT de autenticação

O JWT não é persistido. Ele contém apenas os dados abaixo.

| Claim | Valor | Validação |
|---|---|---|
| `sub` | UUID da conta como texto | Deve existir e referir-se a conta ativa. |
| `iat` | Instante UTC de emissão | Obrigatório. |
| `exp` | Instante UTC até 8 horas após `iat` | Obrigatório; token vencido é recusado. |

### Transições

1. Credenciais válidas de conta ativa criam um JWT e um cookie.
2. JWT íntegro, não vencido e ligado a conta ativa fornece identidade à requisição.
3. JWT ausente, inválido, vencido ou ligado a conta excluída não fornece identidade.
4. Logout com origem confiável remove o cookie no navegador. O token continua criptograficamente válido até expirar, pois a especificação exclui revogação antecipada no servidor.
