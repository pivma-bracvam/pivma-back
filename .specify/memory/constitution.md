<!--
Sync Impact Report
- Versão: template sem preencher → 1.0.0
- Princípios definidos:
  - I. Requisitos e evidência
  - II. Rastreabilidade e auditoria
  - III. Segurança, autorização e sigilo
  - IV. IA como apoio, decisão humana
  - V. Testes orientados a jornadas
  - VI. Mudanças simples, cirúrgicas e verificáveis
  - VII. Documentação do estado atual
- Seções adicionadas: Restrições técnicas; Fluxo de desenvolvimento; Governança
- Seções removidas: nenhuma
- Templates: plan-template.md lê a constituição no "Constitution Check"; nenhum
  template precisou de alteração. spec-template.md e tasks-template.md seguem
  compatíveis.
- Observações:
  - O docs/README.md citava uma constituição 1.0.0 ratificada em 2026-08-11. Ela nunca
    foi versionada e se perdeu. Esta versão a substitui; planos antigos que citam
    princípios numerados se referem àquela redação.
- TODOs: nenhum.
-->

# Constituição do backend pi*VMA

## Princípios

### I. Requisitos e evidência

- Toda mudança de comportamento DEVE apontar sua fonte: instrução do usuário,
  Plano de Trabalho da Fase II (`docs/plano-de-trabalho-fase-ii.md`), spec aprovada
  ou comportamento já entregue e testado.
- A spec DEVE classificar cada afirmação como confirmada, inferência ou ponto a
  validar. Material do protótipo só conta como evidência quando o guia o marca
  como `CONFIRMADO NO MATERIAL`.
- Quando um requisito tiver validade, interpretação ou prioridade incerta, o agente
  DEVE registrar o conflito e perguntar antes de implementar. Suposição não
  preenche lacuna de requisito.

Motivo: parte do Plano de Trabalho está desatualizada, e uma suposição errada vira
código, migração e contrato que o frontend passa a usar.

### II. Rastreabilidade e auditoria

- Todo modelo novo DEVE herdar `AuditMixin` e preencher quem criou, alterou ou
  excluiu.
- Toda ação de negócio sobre um processo DEVE gravar um evento na linha do tempo
  (`AuditEvent`). Mudanças de perfis e do catálogo institucional DEVEM gravar nos
  históricos próprios.
- Exclusão de dados de negócio DEVE ser lógica. Documentos enviados NÃO DEVEM ser
  apagados.
- A cadeia requisito → `spec.md` → `plan.md` → `tasks.md` → código → teste DEVE
  permitir achar, a partir de um teste, o requisito que ele prova.

Motivo: a validação de métodos alternativos é um processo regulatório. O BraCVAM
precisa reconstruir quem decidiu o quê, quando e com base em qual versão.

### III. Segurança, autorização e sigilo

- Toda checagem de acesso DEVE acontecer no backend, a cada requisição, a partir do
  banco. O token carrega só a identidade.
- Quando revelar a existência de um recurso já vazar informação, a API DEVE
  responder `404`, igual a um recurso inexistente.
- Rotas de escrita DEVEM exigir sessão (`CurrentUser`) e origem confiável
  (`TrustedOrigin`).
- O cegamento e o isolamento por laboratório NÃO DEVEM ser contornados por nenhuma
  rota, listagem, evento ou log: nome químico, CAS e SDS ficam restritos ao Grupo
  de Seleção de Amostras; cada laboratório vê só a própria execução.
- Respostas de erro NÃO DEVEM repetir valores enviados nem detalhes internos.
  Senhas, tokens e conteúdo de notificações NÃO DEVEM aparecer em resposta, log ou
  auditoria.
- Conflito de interesse vigente DEVE bloquear decisões do declarante no processo.

Motivo: o sistema guarda propostas confidenciais e identidades de substâncias de
ensaios cegos. Um vazamento invalida o estudo.

### IV. IA como apoio, decisão humana

- A IA PODE pré-avaliar, sugerir e apontar problemas. Ela NÃO DEVE aprovar,
  rejeitar ou encerrar um processo.
- Todo resultado de IA DEVE ser contestável pelo proponente e revisável por uma
  pessoa com o perfil BraCVAM, e o retorno dessa pessoa DEVE ficar registrado.
- Toda pré-avaliação DEVE registrar a versão da avaliação que usou. Versões
  publicadas NÃO DEVEM mudar.
- Testes NÃO DEVEM chamar provedores reais de IA. A suíte padrão usa o provedor
  fake determinístico.

Motivo: a decisão sobre um método é científica e regulatória, e a responsabilidade
é de quem assina a triagem.

### V. Testes orientados a jornadas

- Toda história de usuário DEVE ter um teste de jornada: a descrição do que cada
  ator faz e espera ver, e um teste que percorre esse caminho pela API pública, a
  partir de um ambiente recém-provisionado.
- Erros, perfis negados, isolamento, concorrência, paginação e ordenação DEVEM
  ter testes focados e separados, escolhidos pela matriz de risco.
- Todo defeito corrigido DEVE ganhar um teste de regressão.
- A skill `testing-methodology` define o método e os critérios de parada.
  Resultados de teste só DEVEM ser relatados quando a suíte de fato rodou.

Motivo: o produto é um fluxo entre vários atores. Um teste que só confere uma rota
isolada deixa passar o defeito que aparece quando o processo muda de mãos.

### VI. Mudanças simples, cirúrgicas e verificáveis

- Cada tarefa DEVE definir antes um critério de aceitação verificável.
- A solução DEVE ser a mais simples que atende ao pedido: sem abstração para uso
  único, sem configuração não pedida, sem tratamento de cenário impossível.
- Cada linha alterada DEVE se ligar ao pedido. Refatorações e limpezas fora do
  escopo DEVEM ser apontadas, não feitas.
- Contratos públicos (rotas, formatos, códigos de erro) só DEVEM mudar quando a spec
  aprovar a mudança.
- A skill `karpathy-guidelines` detalha esta disciplina.

Motivo: o backend atende um frontend em desenvolvimento paralelo. Mudança fora do
escopo quebra contratos que ninguém pediu para mudar.

### VII. Documentação do estado atual

- Toda entrega que mude comportamento DEVE atualizar o `manual/` no mesmo PR, e
  `poe docs-build` DEVE passar.
- O manual DEVE descrever só o estado atual. O histórico fica em `specs/`; os
  requisitos de origem ficam em `docs/`.
- Cada fato DEVE ter um único lugar no repositório. O README aponta para o manual
  em vez de repetir contratos.
- Texto em prosa DEVE passar pela skill `stop-slop`.

Motivo: documentação que diverge do código é pior que nenhuma, porque o frontend e
os agentes passam a confiar nela.

## Restrições técnicas

- Stack: Python 3.14, FastAPI, SQLAlchemy 2 assíncrono, Pydantic v2, Alembic,
  PostgreSQL 17 com pgvector.
- Toda mudança de modelo DEVE vir com migração Alembic revisada. O catálogo de
  permissões só muda por migração.
- Erros DEVEM seguir o formato único `{"detail": {"code", "message"}}`, com
  `fields` nos de validação. Listagens DEVEM seguir o envelope paginado único.
- Envios assíncronos DEVEM ser gravados na mesma transação da operação de negócio.
- Dependências: `pyproject.toml` é a fonte única; `poetry.lock` e `uv.lock` DEVEM
  estar atualizados.

## Fluxo de desenvolvimento

- Features e mudanças de comportamento relevantes DEVEM seguir o Spec Kit:
  `speckit-specify` → `speckit-plan` → `speckit-tasks` → `speckit-implement`.
  Mudança pequena e mecânica dispensa spec.
- O `plan.md` DEVE ter a seção "Constitution Check", avaliando cada princípio com
  PASS ou com a justificativa da exceção, antes da pesquisa e de novo após o
  desenho.
- O `tasks.md` DEVE trazer, por história, a tarefa de jornada e as tarefas de teste
  focado antes das tarefas de implementação.
- A ordem das fontes de requisito, as skills obrigatórias e o fluxo de git estão
  no `AGENTS.md`.
- Toda entrega passa por PR para `develop`, com `poe lint`, `poe test` e
  `poe docs-build` verdes.

## Governança

- Esta constituição prevalece sobre specs, planos e tarefas. Uma exceção DEVE
  aparecer justificada no "Constitution Check" do plano e aprovada no PR.
- Emendas DEVEM ser feitas com `speckit-constitution`, em PR próprio, com o
  relatório de impacto no topo do arquivo e revisão de quem mantém o projeto.
- Versionamento semântico:
  - MAJOR: princípio removido ou redefinido de forma incompatível.
  - MINOR: princípio ou seção nova, ou regra ampliada.
  - PATCH: redação e correções sem efeito nas regras.
- A revisão de cada PR DEVE checar o cumprimento desta constituição.

**Version**: 1.0.0 | **Ratified**: 2026-10-03 | **Last Amended**: 2026-10-03
