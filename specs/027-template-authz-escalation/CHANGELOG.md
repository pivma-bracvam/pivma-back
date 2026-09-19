# O que muda para quem já usa o PIVMA (Issue #39)

**Para quem é este documento**: equipe BraCVAM, administradores da
plataforma e suporte — qualquer pessoa que já opera o sistema hoje e pode
notar uma diferença de acesso depois deste deploy. Não é um changelog
técnico; não fala de código, arquivos ou nomes internos.

## Resumo em uma frase

Uma falha de segurança permitia que contas sem privilégio de administrador
editassem templates de processo/formulário e acessassem funções
administrativas (reprocessar avaliação por IA, ver logs internos) — isso
foi fechado, e a equipe BraCVAM ganhou uma permissão própria e legítima
para continuar editando formulários, no lugar do acesso indevido que usava
sem saber.

## O que muda, na prática

- **Uma permissão de "só consulta" deixa de abrir portas que não deveria.**
  Existia uma falha: qualquer conta com a permissão de *consultar* a
  configuração de acesso (perfis e permissões) conseguia, sem querer,
  editar a definição de formulários e acessar telas administrativas
  internas (reprocessamento de avaliação por IA, histórico de logs). Isso
  foi corrigido — essa permissão volta a servir só para consulta.
- **Um perfil batizado de "Administrador" deixa de valer como se fosse.**
  Existia uma segunda falha: bastava um perfil de acesso ter esse nome de
  exibição — não o cargo oficial — para editar formulários. Corrigido; só
  quem de fato tem o cargo de Administrador (ou a nova permissão abaixo)
  consegue.
- **A equipe BraCVAM ganha uma permissão própria para editar formulários.**
  Adicionar ou ajustar campos de um formulário de processo (o que a equipe
  já fazia no dia a dia) continua funcionando exatamente igual — agora por
  um caminho correto e específico para essa tarefa, em vez de depender da
  falha de segurança corrigida acima.
- **Reprocessar avaliação por IA e ver logs internos continua só para
  Administrador.** Essas duas funções não foram estendidas à equipe
  BraCVAM — ninguém pediu esse acesso, e ele não muda.

## O que **não** muda

- Nenhum botão, tela ou fluxo de trabalho muda. Editar um formulário
  continua sendo a mesma ação, no mesmo lugar.
- Quem já tem o cargo oficial de Administrador mantém acesso total a tudo,
  sem nenhuma mudança.
- Nenhum contrato de API muda — nenhum endpoint, nem formato de request ou
  resposta.

## Atenção ao aplicar esta correção em um ambiente já existente

Se este deploy for feito sobre um ambiente que **já está em uso** (não
recriado do zero), qualquer conta que hoje edita formulários ou acessa
funções administrativas **só por causa da falha de segurança** (por ter a
permissão de consulta ao RBAC, ou por um perfil chamado "Administrador" sem
ser o cargo oficial) perde esse acesso assim que a correção entrar no ar.
Antes de aplicar em um ambiente assim, vale conferir se alguém está nessa
situação e conceder a essa pessoa a nova permissão de edição de formulário,
para não interromper o trabalho dela sem aviso.

## Por que essa mudança

Duas falhas de autorização tratavam uma permissão de leitura, e o nome de
um perfil, como se fossem prova de privilégio administrativo. Na prática,
isso também era o único jeito de a equipe BraCVAM editar formulários hoje —
corrigir a falha sem dar a ela um caminho próprio quebraria esse trabalho.
Por isso a correção veio junto com a permissão nova, em vez de só fechar a
porta.
