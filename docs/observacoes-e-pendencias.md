# Observações e pendências

Este documento reúne divergências entre fontes, ambiguidades e perguntas para a equipe, como pedem a constituição do Spec Kit e o [índice da documentação](README.md). Nenhum item altera as fontes oficiais.

## Recuperação de senha (issue #45, Spec 039)

### DIVERGÊNCIA REGISTRADA

- **Fonte**: a issue #45 admite "imprimir o token em logs em ambiente local/desenvolvimento".
- **Conflito**: a Spec 036 proíbe o link bruto em logs. O backend de e-mail falso e o Mailpit do compose, ambos da Spec 036, já entregam o link em testes e em desenvolvimento.
- **Decisão**: o token nunca vai para log, em nenhum ambiente. Em desenvolvimento, o link é lido no Mailpit (`http://localhost:8025`).
- **Validação**: confirmada pelo usuário em 2026-10-02. Registrada em `specs/039-password-reset/spec.md` (Clarifications, FR-004 e Assumptions) e citada na descrição da PR.
