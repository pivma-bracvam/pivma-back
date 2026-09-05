# Plano de Implementação: Submissão de Método Alternativo

**Branch**: `feat/009-alternative-method-submission` | **Data**: 2026-09-04 | **Spec**: [spec.md](spec.md)

## Resumo

Implementar o RF007 sobre os artefatos da Feature 004: criar a instância de processo, atribuir o criador como proponente, apresentar o formulário persistido e salvar seus valores parciais. A implementação corrige três lacunas: validação estrita antes da gravação, escopo exclusivo do proponente ativo e geração segura do `crCode` em criações concorrentes.

O frontend continua a usar os endpoints de processo e formulário já publicados. O contrato documenta uma sequência de três chamadas e erros por campo; não será criada uma entidade, router ou formulário paralelo para “submissão”.

## Contexto Técnico

**Linguagem/versão**: Python 3.14.

**Dependências principais**: FastAPI, Pydantic v2, SQLAlchemy 2.0 assíncrono, Psycopg, Alembic.

**Armazenamento**: PostgreSQL com `process_instances`, `assignments`, `activity_instances`, `activity_runs`, `form_instances`, `form_fields`, `form_values` e `audit_events` já existentes.

**Testes**: Pytest, TestClient, Testcontainers PostgreSQL e Factory Boy.

**Plataforma-alvo**: serviço HTTP FastAPI em Linux e PostgreSQL.

**Tipo de projeto**: API web.

**Metas de desempenho**: nenhuma meta numérica foi definida para RF007. A listagem preserva paginação e a consulta deve filtrar no banco antes de contar e paginar.

**Restrições**: reutilizar o motor e os modelos existentes; não anexar, simular ou persistir documentos; não concluir a atividade nem liberar triagem; não criar identificador paralelo ao `ProcessInstance.code`; negar acesso fora da participação contextual sem expor dados.

**Escopo**: criação, leitura e rascunho de submissões em elaboração para o proponente ativo. Exclui RF008 a RF014, salvo a preservação explícita do endpoint formal já existente sem ampliá-lo.

## Evidências e Decisões de Planejamento

- **CONFIRMADO**: `instantiate_process` já cria `ProcessInstance`, `Assignment` de papel `proponent`, execução inicial, `FormInstance` e eventos de auditoria em uma transação ([process_engine.py](../../src/pivma/core/process_engine.py)).
- **CONFIRMADO**: `ProcessInstance.code` tem restrição única no modelo e na migração `1bd1b3d5ddad` ([models.py](../../src/pivma/core/database/models.py), [migração](../../migrations/versions/1bd1b3d5ddad_process_submission_triage_core.py)).
- **CONFIRMADO**: o contador atual em `generate_process_code` pode repetir sob concorrência. A restrição do banco impede a duplicação, mas a criação concorrente pode falhar.
- **DECISÃO TÉCNICA REGISTRADA**: manter `ProcessInstance.code` como `crCode`, conforme a clarificação da spec. Trocar a geração por `VAL-{ano}-{token aleatório de 16 hexadecimais}`. O token cabe no limite atual de 32 caracteres; a restrição única existente é a garantia final. Não há migração nem nova tabela.
- **DECISÃO TÉCNICA REGISTRADA**: acrescentar uma verificação estreita de “proponente ativo e eficaz” em `authorization.py`, filtrando `role_key="proponent"`, `revoked_at IS NULL`, exclusão lógica da designação e usuário ativo. Essa regra não reutiliza `participant_read_scope`, pois ela aceita participantes comuns e gestores, o que conflita com RF007.
- **DECISÃO TÉCNICA REGISTRADA**: validar todo o payload antes de criar ou atualizar `FormValue`. Para os tipos hoje persistidos: texto/textarea exigem string ou `null`; integer exige inteiro sem booleano; float exige número sem booleano; boolean exige booleano; date exige data ISO `YYYY-MM-DD`; select exige uma opção configurada. Regras `min` e `max` aplicam-se a números. `null` limpa o valor parcial quando o tipo aceitar ausência. Campos obrigatórios continuam verificáveis apenas no envio formal de RF014.
- **DECISÃO TÉCNICA REGISTRADA**: `file_upload` não aceita valor em RF007. O campo pode aparecer na definição persistida, mas o frontend não deve enviar valor para ele; uma tentativa recebe erro de validação, sem criar `Artifact` ou gravar texto que simule um anexo. Isso preserva RF008 fora do escopo sem bloquear os demais campos parciais.
- **DECISÃO TÉCNICA REGISTRADA**: usar `404` uniforme para processo, formulário ou mutação sem proponente ativo, igual ao recurso ausente. A resposta não informa se o identificador existia nem expõe definição, valores ou eventos.

## Verificação da Constituição

### Antes da pesquisa

| Princípio | Resultado | Evidência no plano |
|---|---|---|
| Requisitos e evidência classificada | Aprovado | As fontes e decisões estão classificadas nesta seção; RF007 e RF004 permanecem rastreáveis. |
| Rastreabilidade e auditoria | Aprovado | Reutiliza `AuditMixin` e preserva `PROCESS_CREATED`, `PARTICIPANT_ASSIGNED` e `FORM_DRAFT_SAVED`. |
| Segurança e autorização | Aprovado | Filtro de proponente ativo em lista, detalhe, timeline, leitura e rascunho. |
| Autoridade humana e IA | Não aplicável | RF013 está fora do escopo. |
| Mudança pequena e verificável | Aprovado | Não há novo modelo, dependência, endpoint, tabela ou migração. Testes isolam cada contrato observável. |

### Após o desenho

O desenho preserva os mesmos resultados. Não requer exceção de complexidade.

## Desenho de Implementação

1. Em `authorization.py`, criar um predicado/consulta reutilizável para a participação local de proponente ativa e eficaz. Ele será a única regra nova de acesso desta feature.
2. Em `routers/processes.py`, aplicar esse predicado à lista antes do `count`, ao detalhe e à timeline. `POST /processes` preserva a criação existente e passa a obter um `crCode` seguro do motor.
3. Em `process_engine.py`, substituir o gerador baseado em `COUNT(*)` por token aleatório compatível com `String(32)`. Manter a restrição única já existente como proteção de integridade.
4. Centralizar em uma função pequena a validação e a normalização de valores de campos persistidos. A função primeiro identifica chaves desconhecidas, tipos, opções e regras; só depois a gravação cria/altera `FormValue`. O pedido inteiro falha antes de `commit` se houver qualquer erro.
5. Proteger a leitura, o rascunho e o endpoint formal já existente de formulário com o predicado de proponente. Mapear a negação ao mesmo `404` usado para recurso ausente. A feature só acrescenta a proteção contextual ao endpoint formal; não altera seu fluxo, artefatos ou triagem.
6. Expor ao frontend os erros de validação como lista estável por `field_key`, com `code` e `message`; o contrato está em [contracts/submission-api.md](contracts/submission-api.md).

## Ordem de Implementação e Verificação

1. Adicionar a policy de proponente ativo e filtros de router. Verificar com testes de lista, detalhe, timeline e cada operação de formulário para proponente, terceiro, designação revogada e participante em outro papel.
2. Trocar a geração do `crCode`. Verificar geração distinta em criações concorrentes e a preservação do formato `VAL-` esperado pelos contratos existentes.
3. Implementar validação prévia e gravação atômica de rascunho. Verificar cada tipo/opção/regra, chave desconhecida, `false` e zero, payload misto e preservação do estado anterior.
4. Ajustar contratos/schemas apenas para a resposta estruturada de erro necessária ao frontend. Verificar a sequência criar → ler formulário → salvar → reler e a ausência de transição para triagem.

## Estrutura do Projeto

```text
src/pivma/
├── core/
│   ├── authorization.py          # policy estreita de proponente ativo
│   └── process_engine.py         # crCode e validação/gravação de rascunho
├── routers/
│   ├── processes.py              # listagem, detalhe e timeline no escopo RF007
│   └── forms.py                  # leitura e gravação do formulário no escopo RF007
└── schemas.py                    # contrato de erro estruturado, se necessário

tests/
├── api/routers/
│   ├── test_process_router.py    # criação, lista/detalhe/timeline autorizados
│   └── test_form_submission.py   # contrato HTTP de formulário e erros
└── integration/database/
    ├── test_participant_authorization.py # predicado ativo/eficaz
    └── test_process_code_generation.py   # concorrência e atomicidade do motor

specs/009-alternative-method-submission/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/submission-api.md
```

**Decisão de estrutura**: alterar somente módulos existentes e acrescentar o teste de integração isolado de geração de código. O novo arquivo evita misturar concorrência e atomicidade do motor aos contratos HTTP de router. O frontend consome os contratos HTTP; este repositório não contém aplicação frontend.
