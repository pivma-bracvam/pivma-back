# O que muda para quem já usa o PIVMA (Issue #22)

**Para quem é este documento**: equipe BraCVAM/triadores, gestores de
processo e suporte — qualquer pessoa que já opera processos no sistema hoje
e pode notar uma diferença depois deste deploy. Não é um changelog técnico;
não fala de código, arquivos ou nomes internos.

## Resumo em uma frase

Depois de uma **diligência de triagem** (quando a triagem pede ajustes e o
proponente reenvia a proposta), o sistema agora trata essa nova rodada de
triagem como um trabalho novo e independente — com sua própria pendência,
seu próprio prazo e seu próprio registro no histórico. Antes, a segunda
rodada em diante "desaparecia" silenciosamente.

## O que muda, na prática

- **Você vai ver uma pendência nova depois de cada diligência.** Antes,
  quando o proponente reenviava uma proposta depois de uma diligência de
  triagem, nenhuma tarefa nova aparecia na sua lista de pendências — a
  triagem ficava, na prática, sem um "aviso" de que havia algo para fazer de
  novo. Agora, cada reenvio gera uma pendência própria, visível normalmente
  na sua lista de tarefas.
- **O prazo da triagem passa a contar certo a cada rodada.** Antes, o prazo
  (SLA) da triagem ficava travado na data da primeira vez que ela foi aberta,
  mesmo depois de uma diligência e reenvio — o que podia fazer uma rodada
  nova parecer "atrasada" mesmo tendo acabado de começar, ou nunca acusar
  atraso de verdade. Agora, o prazo recomeça a contar a partir do momento em
  que cada nova rodada começa.
- **O histórico do processo passa a registrar quando a triagem é liberada.**
  Isso já acontecia para outras etapas do processo; a triagem era a única
  exceção. Se você acompanha a linha do tempo de um processo de perto, vai
  notar esse novo registro.
- **O número da rodada da triagem passa a aumentar.** Assim como já acontece
  na submissão da proposta (rodada 1, 2, 3...), a triagem também passa a
  numerar suas rodadas em vez de ficar sempre na "rodada 1".

## O que **não** muda

- Nenhum botão, tela ou fluxo de trabalho muda. Você continua submetendo,
  solicitando diligência, aprovando ou rejeitando exatamente do jeito que já
  faz hoje.
- Nenhuma informação sobre processos já concluídos ou já em andamento hoje é
  alterada retroativamente. A mudança vale a partir da próxima vez que uma
  triagem passar por diligência depois do deploy.
- O resultado final de um processo (aprovado, rejeitado, em ajuste) continua
  decidido do mesmo jeito, pelas mesmas pessoas, com a mesma autorização.

## Por que essa mudança

Era um comportamento que passava despercebido: internamente, a segunda
rodada de triagem reaproveitava os registros da primeira em vez de criar os
seus próprios — o que fazia a pendência "sumir" e o prazo "travar". Foi
tratado como uma correção, não como um ajuste de comportamento em aberto.
