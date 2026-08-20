# Contrato operacional: bootstrap do Administrador

## Comando

```bash
poetry run python -m pivma.bootstrap_rbac --user-id <UUID>
```

O comando deve ser executado depois da migração RBAC e da criação da conta escolhida.

## Resultados

| Condição | Resultado |
|---|---|
| Conta ativa e sem atribuição Administrador | Cria a atribuição e `bootstrap.admin_assigned`; encerra com código 0. |
| Conta ativa com a atribuição Administrador | Não duplica registros; encerra com código 0. |
| Outra conta já possui atribuição Administrador | Não concede o perfil à conta indicada e encerra com código diferente de 0. Novas concessões usam a API protegida. |
| Conta ausente | Reverte a transação, não promove outra conta e encerra com código diferente de 0. |
| Conta excluída logicamente | Reverte a transação, não promove outra conta e encerra com código diferente de 0. |
| Catálogo RBAC ausente ou incompleto | Reverte a transação e encerra com código diferente de 0. |

## Garantias

- O argumento aceita somente UUID de uma conta existente.
- O comando bloqueia o perfil Administrador durante a atribuição.
- A atribuição e a mudança persistente usam a mesma transação.
- A primeira atribuição usa autoria nula porque ainda não existe uma identidade autorizada.
- O comando não cria conta, perfil ou permissão e não roda durante cada inicialização da aplicação.
