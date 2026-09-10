# Plano de Implementação IA PIVMA --- Sprint 02: Operação Humana, Relatórios e Auditoria

## Objetivo

Criar a camada operacional onde a IA auxilia, mas não substitui, a
decisão regulatória humana.

## Escopo

-   Apresentação do resultado da IA ao proponente.
-   Apresentação do histórico da IA ao BraCVAM.
-   Fluxo de contestação.
-   Preparação para revisão humana.

## Fluxo do proponente

Após submissão:

1.  Formulário é avaliado automaticamente.
2.  Resultado preliminar é apresentado.
3.  Caso existam inconformidades, o proponente pode:
    -   corrigir e reenviar;
    -   contestar a avaliação;
    -   solicitar análise humana.

A contestação deve preservar o resultado original da IA.

## Fluxo BraCVAM

O avaliador humano deve visualizar:

-   dados avaliados;
-   critérios utilizados;
-   resultado gerado;
-   justificativas;
-   recomendações;
-   versão da avaliação utilizada;
-   data da execução;
-   identificação da execução.

A IA deve funcionar como evidência auxiliar para decisão humana.

## Persistência e auditoria

Registrar:

-   configuração utilizada;
-   versão da configuração;
-   conteúdo avaliado;
-   resultado produzido;
-   alterações humanas posteriores;
-   decisão final.

Não permitir alteração retroativa de avaliações já utilizadas.

## Resultado esperado

O BraCVAM consegue responder:

"Qual avaliação automática foi realizada e qual informação sustentou
essa conclusão?"

## Critérios de conclusão

-   Proponente consegue contestar.
-   BraCVAM consegue consultar avaliações anteriores.
-   Histórico permanece auditável.
-   Decisão final continua pertencendo ao humano.
