# Implementation Readiness Checklist: Cadastro Seguro de Usuários

**Purpose**: Avaliar se a especificação e o plano estão completos, claros, consistentes e
mensuráveis antes da geração de tarefas
**Created**: 2026-08-11
**Feature**: [spec.md](../spec.md)

**Note**: Esta checklist avalia a qualidade dos requisitos. Ela não valida a implementação.

## Requirement Completeness

- [x] CHK001 Os requisitos enumeram todos os resultados possíveis do cadastro: criação, entrada
  inválida, senha bloqueada, conflito e falha interna? [Completeness, Spec §FR-001–FR-021]
- [x] CHK002 O status e a estrutura da resposta estão definidos para cada classe de rejeição de
  entrada, incluindo username, e-mail e senha? [Gap, Spec §FR-002, Contract §422]
- [x] CHK003 O requisito de blocklist define o resultado público quando a senha está bloqueada sem
  revelar se ela é comum ou comprometida? [Completeness, Spec §FR-008]
- [x] CHK004 Os requisitos de auditoria definem todos os campos pertinentes no cadastro público,
  incluindo o comportamento de `updated_at`, `updated_by`, `deleted_at` e `deleted_by`?
  [Completeness, Spec §FR-018–FR-019, Data Model §Usuário]
- [x] CHK005 As exclusões de login, JWT, cookies, perfis, permissões, vínculos, recuperação de senha
  e novos endpoints estão expressas de modo consistente em spec, plano e contrato?
  [Completeness, Spec §FR-021, Plan §Constraints]
- [x] CHK006 A transformação de credenciais legadas em texto simples está aprovada como parte do
  escopo, apesar de não aparecer como requisito funcional explícito da spec?
  [Gap, Plan §Migration Safety, Research §6]

## Requirement Clarity

- [x] CHK007 O conjunto de caracteres classificado como “espaço em branco” está definido sem
  depender de interpretação do implementador? [Clarity, Spec §FR-007]
- [x] CHK008 A contagem de 8 a 128 caracteres da senha especifica como caracteres Unicode são
  contabilizados? [Clarity, Spec §FR-007, Research §2]
- [x] CHK009 A ordem entre trim, validação, comparação, armazenamento e retorno de username e
  e-mail está declarada sem permitir resultados diferentes? [Clarity, Spec §FR-012]
- [x] CHK010 “Representação segura adequada à verificação futura” está ligada a uma decisão
  técnica única e versionada, sem deixar algoritmo ou parâmetros indefinidos?
  [Clarity, Spec §FR-006, Research §1]
- [x] CHK011 “Versão vigente” da blocklist identifica de forma inequívoca qual artefato rege cada
  versão da aplicação? [Clarity, Spec §FR-008, Data Model §metadata.json]
- [x] CHK012 A precedência de conflito de username está definida tanto para a verificação normal
  quanto para conflitos produzidos por pedidos concorrentes? [Clarity, Spec §FR-015–FR-016]

## Requirement Consistency

- [x] CHK013 A política aprovada de senha está consistente em spec, contrato e plano, inclusive nas
  divergências registradas em relação ao NIST? [Consistency, Spec §FR-007, Contract
  §UserRegistration, Plan §Divergências registradas]
- [x] CHK014 Os corpos e códigos de resposta definidos no contrato correspondem aos requisitos e
  cenários da spec, sem introduzir comportamento novo? [Consistency, Spec §FR-002–FR-005,
  Contract §/users/]
- [x] CHK015 A exclusão lógica está tratada de forma consistente entre a suposição de que
  reativação está fora do escopo e a decisão de ignorar usuários excluídos na unicidade?
  [Consistency, Spec §Assumptions, Data Model §Invariantes]
- [x] CHK016 A denominação `password_hash` e a proibição de exposição estão consistentes em
  modelo, contrato, plano e critérios de sucesso? [Consistency, Spec §FR-005–FR-006, Data Model
  §Usuário, Contract §UserPublic]
- [x] CHK017 A exigência de preservar a caixa de username e e-mail permanece compatível com a
  unicidade case-insensitive em todos os artefatos? [Consistency, Spec §FR-012–FR-014, Data Model
  §Invariantes]
- [x] CHK018 A estratégia de migração distingue de forma consistente valores Argon2id existentes
  de texto legado sem classificar dados arbitrários pelo prefixo apenas? [Ambiguity, Plan
  §Migration Safety, Data Model §Migração]

## Acceptance Criteria Quality

- [x] CHK019 O universo usado pelos critérios de “100%” está delimitado por conjuntos de dados e
  condições reproduzíveis? [Measurability, Spec §SC-001–SC-010]
- [x] CHK020 O critério de concorrência define quantidade mínima de pedidos, identificadores
  equivalentes e resultado esperado para cada pedido? [Measurability, Spec §SC-004]
- [x] CHK021 O plano define um limiar de aceitação para latência e memória do Argon2id, ou declara
  quem aprovará os resultados medidos antes da implementação? [Gap, Plan §Performance Goals,
  Quickstart §6]
- [x] CHK022 A falha fechada da blocklist possui critério observável para recurso ausente,
  corrompido, incompleto ou com metadados divergentes? [Measurability, Research §3, Data Model
  §Lista de senhas bloqueadas]
- [x] CHK023 O critério de preservação dos contratos identifica quais testes atuais mudam por causa
  da nova senha mínima de oito caracteres? [Traceability, Spec §FR-020, Spec §SC-006]

## Scenario Coverage

- [x] CHK024 Os requisitos do fluxo principal cobrem validação, blocklist, proteção da senha,
  persistência, auditoria e resposta sem omitir a ordem necessária? [Coverage, Spec §User Story 1]
- [x] CHK025 Os fluxos alternativos cobrem valores válidos nos limites de username e senha e
  preservação de caixa após trim? [Coverage, Spec §Edge Cases, Spec §SC-007–SC-009]
- [x] CHK026 Os fluxos de exceção cobrem conflito apenas de username, apenas de e-mail, de ambos e
  concorrente? [Coverage, Spec §User Story 2]
- [x] CHK027 O comportamento de recuperação está definido quando o carregamento da blocklist falha
  fechado, incluindo condição para voltar a aceitar cadastros? [Gap, Recovery, Research §3]
- [x] CHK028 O comportamento atômico está especificado quando proteção da senha, flush ou commit
  falha depois que o pedido foi validado? [Coverage, Exception Flow, Spec §FR-017]
- [x] CHK029 O fluxo operacional após aborto da migração por colisões define responsável,
  evidência necessária e condição para nova execução? [Gap, Recovery, Plan §Migration Safety]

## Edge Case Coverage

- [x] CHK030 O resultado está definido quando o trim transforma username ou e-mail em valor vazio?
  [Coverage, Edge Case, Spec §FR-002, Spec §FR-012]
- [x] CHK031 Os requisitos esclarecem se pontos, hífens e sublinhados podem aparecer no início,
  fim ou em sequência no username? [Ambiguity, Spec §FR-009]
- [x] CHK032 A equivalência case-insensitive de username e e-mail está definida para todo o
  alfabeto aceito, inclusive a parte local e o domínio do e-mail? [Clarity, Spec §FR-013–FR-014]
- [x] CHK033 O requisito de senha distingue code points Unicode, sequências canonicamente
  equivalentes e caracteres invisíveis que não são whitespace? [Coverage, Edge Case, Spec
  §FR-007, Plan §Divergências registradas]
- [x] CHK034 A migração define o tratamento de usuários ativos, excluídos e parcialmente migrados
  em caso de falha? [Coverage, Recovery, Data Model §Migração]

## Non-Functional Requirements

- [x] CHK035 Os requisitos de confidencialidade proíbem senha, SHA-1 de consulta e hash Argon2id em
  respostas, logs, erros e diagnósticos de migração? [Security, Gap, Spec §FR-005, Data Model
  §Invariantes]
- [x] CHK036 Os requisitos de integridade da blocklist definem origem, checksum, versionamento,
  empacotamento e política de atualização? [Security, Completeness, Research §3, Data Model
  §metadata.json]
- [x] CHK037 A ausência de rate limiting nesta feature está documentada como exclusão aprovada ou
  permanece uma lacuna de segurança do cadastro público? [Security, Gap, Spec §FR-021]
- [x] CHK038 Os requisitos operacionais definem limites aceitáveis de memória e concorrência para
  o perfil Argon2id escolhido? [Performance, Gap, Plan §Performance Goals]
- [x] CHK039 Os requisitos definem se a migração precisa preservar disponibilidade ou pode exigir
  janela de manutenção? [Reliability, Gap, Plan §Migration Safety]

## Dependencies & Assumptions

- [x] CHK040 A compatibilidade, a faixa de versão e a responsabilidade de atualização do
  `argon2-cffi` estão documentadas? [Dependency, Plan §Technical Context, Research §1]
- [x] CHK041 A fonte, os termos de redistribuição, a data e o processo reproduzível para derivar a
  blocklist aprovada estão documentados antes de incorporar o artefato? [Dependency, Gap, Research
  §3]
- [x] CHK042 A inclusão dos recursos da blocklist em wheel, sdist e imagem está expressa como
  requisito de distribuição, não apenas como procedimento de validação? [Dependency,
  Completeness, Plan §Implementation Strategy, Quickstart §5]
- [x] CHK043 A suposição sobre existência e volume de usuários persistidos está validada antes de
  aprovar hashing legado dentro da migração? [Assumption, Plan §Migration Safety]
- [x] CHK044 A decisão de trabalhar na branch `main` foi validada diante da orientação de usar
  uma branch própria para features? [Assumption, Plan §Branch, AGENTS §Git e branches]

## Traceability & Gate Decision

- [x] CHK045 Cada requisito funcional possui vínculo com ao menos um cenário de aceitação e um
  critério mensurável? [Traceability, Spec §FR-001–FR-021, Spec §SC-001–SC-010]
- [x] CHK046 Cada decisão técnica do plano aponta para o requisito que a torna necessária, sem
  ampliar o escopo aprovado? [Traceability, Plan §Implementation Strategy, Spec §FR-001–FR-021]
- [x] CHK047 As afirmações estão classificadas como CONFIRMADO, INFERÊNCIA ou PROPOSTA sempre que
  sua natureza afeta aprovação ou implementação? [Governance, Constitution §I, Spec §Scope and
  Traceability]
- [x] CHK048 As divergências entre fontes e recomendações externas estão registradas sem substituir
  as decisões aprovadas da spec? [Consistency, Constitution §I, Plan §Divergências registradas]
- [x] CHK049 Todos os gaps, ambiguidades e suposições encontrados nesta checklist foram resolvidos
  nos artefatos ou aceitos por responsável identificado antes de `$speckit-tasks`?
  [Gate, Gap]

## Notes

- Marque um item como concluído somente quando os artefatos contiverem evidência suficiente.
- Registre achados e decisões junto ao item correspondente.
- Esta checklist é um gate de requisitos para autor e revisor; ela não substitui testes.

## Resultado da revisão de 2026-08-11

**Estado do gate**: GERAÇÃO DE TAREFAS AUTORIZADA, IMPLEMENTAÇÃO BLOQUEADA. Em 2026-08-11, o
responsável autorizou gerar `tasks.md` com as pendências rastreadas. A revisão encontrou evidência
suficiente para 20 de 49 itens. Os 29 itens desmarcados foram revisados e continuam pendentes; eles
não representam itens ainda não lidos nem decisões aprovadas para implementação.

### Itens atendidos

| Itens | Evidência principal |
|---|---|
| CHK005 | A spec, o plano e o contrato mantêm login, JWT, cookies, perfis, permissões, vínculos, recuperação de senha e novos endpoints fora do escopo. |
| CHK007–CHK012 | `research.md` define `str.isspace()`, contagem por code points Python, ordem das transformações, Argon2id, identificação da blocklist e precedência de conflitos. |
| CHK013–CHK014 | A política de senha e os códigos 201, 409 e 422 coincidem entre spec, plano e contrato. |
| CHK016–CHK017 | Spec, plano, modelo de dados e contrato preservam a caixa dos identificadores e não expõem `password_hash`. |
| CHK022 | O modelo de dados e a pesquisa exigem falha fechada para ausência, formato, quantidade, ordenação, unicidade ou checksum inválido da blocklist. |
| CHK024–CHK026 | As três histórias e o quickstart cobrem fluxo principal, limites e conflitos simples, duplos e concorrentes. |
| CHK030–CHK033 | A spec, o contrato e a pesquisa definem trim para valores vazios, regex do username, `lower()` para os identificadores e tratamento exato de Unicode na senha. |
| CHK048 | O plano registra as divergências com o NIST sem substituir a política aprovada. |

### Pendências que exigem decisão ou validação

| Itens | Pendência |
|---|---|
| CHK001–CHK004 | Falta definir resposta para falha interna, nível de detalhe do erro de senha bloqueada e estado dos campos de auditoria não relacionados à criação. |
| CHK006, CHK018, CHK034, CHK043 | A equipe ainda não aprovou o tratamento de credenciais legadas, não validou a existência e o volume desses dados e não definiu identificação segura de registros já migrados nem recuperação de migração parcial. |
| CHK015 | A spec exclui reutilização e reativação de contas apagadas, enquanto o desenho dos índices permite reutilizar identificadores de contas com `deleted_at`. |
| CHK020–CHK021, CHK038 | Faltam quantidade mínima para o teste concorrente, limites aceitáveis de latência e memória e responsável por aprovar o benchmark do Argon2id. |
| CHK027 | Falta definir quando o serviço volta a aceitar cadastros após falha fechada no carregamento da blocklist. |
| CHK029, CHK039 | Faltam responsável, evidência para nova execução e decisão sobre janela de manutenção após aborto da migração. |
| CHK037 | A feature não registra se rate limiting fica fora do escopo ou se constitui requisito do cadastro público. |
| CHK040–CHK041 | Faltam faixa de versão e responsável por atualizar `argon2-cffi`, além de licença, data comprovada e processo reproduzível de derivação da blocklist. |
| CHK044 | O trabalho continua em `main`; a equipe ainda não confirmou a branch própria nem alinhou `dev` e `develop`. |

### Pendências de especificação e rastreabilidade

| Itens | Pendência |
|---|---|
| CHK019 | Os critérios que usam “100%” não delimitam conjuntos de teste reproduzíveis. |
| CHK023 | Os artefatos não identificam que os três testes atuais usam a senha `secret`, incompatível com o novo mínimo. |
| CHK028 | A atomicidade está declarada de forma geral, mas não cobre separadamente falha no hashing, `flush` e `commit`. |
| CHK035 | A proibição de segredos não cobre de forma explícita respostas, logs, erros e diagnósticos de migração. |
| CHK036, CHK042 | Origem, integridade e empacotamento aparecem no desenho técnico, mas faltam política de atualização e requisito explícito de distribuição. |
| CHK045–CHK046 | Falta uma matriz que relacione cada FR a cenário, critério de sucesso, decisão técnica e teste previsto. |
| CHK047 | Spec e plano classificam parte das afirmações, mas `research.md` registra decisões futuras sem identificá-las como PROPOSTA. |
| CHK049 | O gate permanece aberto enquanto qualquer pendência acima não for resolvida ou aceita por responsável identificado. |

## Reavaliação de 2026-08-12

**Estado do gate**: IMPLEMENTAÇÃO AUTORIZADA. Em 2026-08-12, a pessoa solicitante aprovou a spec,
o plano e as decisões operacionais registradas. A checklist contém evidência suficiente para os 49
itens; os metadados concretos da aquisição da blocklist serão registrados antes de incorporar o
artefato, conforme T005.

| Itens | Estado atual |
|---|---|
| CHK041 | SecLists Top 100k aprovado; T005 registra commit, data, checksums e termos antes de incorporar o artefato. |
| CHK049 | Spec, plano e decisões operacionais aprovados pela pessoa solicitante em 2026-08-12. |

Os itens marcados nesta reavaliação agora têm evidência em `spec.md`, `plan.md`, `research.md`,
`data-model.md`, `contracts/users.openapi.yaml`, `quickstart.md` e `tasks.md`.

## Encerramento do relatório de implementação em 2026-08-12

**Estado do relatório**: CONCLUÍDO. A pessoa solicitante aprovou o registro do benchmark como
evidência do ambiente atual. A validação final registrou 59 testes aprovados, `ruff check` sem
violação, migração coberta por upgrade, abortos e downgrade, e recursos presentes em wheel e sdist.

**Pendência operacional**: a feature não possui limite de latência ou memória para produção. O
responsável técnico deve definir e aprovar esses limites em trabalho separado antes que a equipe
use o benchmark como critério operacional de produção. Esta pendência não autoriza mudar o perfil
Argon2id, ampliar escopo ou executar otimizações nesta feature.

## Redução de escopo de 2026-08-12

**Estado do gate**: MANTIDO, sob escopo reduzido. A pessoa solicitante, única aprovadora desta
spec, identificou que a Session 2026-08-11 produziu um conjunto de decisões desproporcional a uma
primeira feature em um projeto novo sem usuários reais, e removeu: blocklist de senhas (FR-008,
FR-024), inspeção de formato de credencial na migração (parte de FR-022), reserva de identificador
após exclusão lógica (FR-023) e o gate formal de benchmark (SC-011). Ver `spec.md`, Clarifications,
Session 2026-08-12.

Os itens desta checklist que dependiam exclusivamente dos pontos removidos deixam de se aplicar:

| Itens | Situação |
|---|---|
| CHK003, CHK011, CHK022, CHK027, CHK036, CHK041 | N/A — dependiam da blocklist local, removida nesta versão |
| CHK018, CHK034 (parte), CHK043 | N/A — a migração não inspeciona mais o formato da credencial existente |
| CHK015 | Resolvido no sentido oposto ao registrado em 2026-08-11: a spec agora confirma que a exclusão lógica libera identificadores, eliminando a inconsistência apontada |
| CHK021, CHK038 | N/A — o benchmark deixou de ser gate de aceite formal |
| CHK029, CHK039 | N/A — sem inspeção de credencial legada, não há mais cenário de aborto por credencial não Argon2id exigindo janela de manutenção; o aborto por colisão de identificador continua coberto por `tests/migrations/test_secure_user_registration.py` |

Os demais itens continuam válidos e evidenciados pelos artefatos atualizados em 2026-08-12.
