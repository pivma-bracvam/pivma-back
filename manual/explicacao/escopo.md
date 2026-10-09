# Escopo atual

O que o backend resolve hoje, comparado aos requisitos RF001–RF062 do
[Plano de Trabalho da Fase II](https://github.com/pivma-bracvam/pivma-back/blob/develop/docs/plano-de-trabalho-fase-ii.md).
O plano é a fonte de requisitos; esta página só descreve o estado do código.

Legenda: **Sim** atende; **Parcial** atende parte, com o limite descrito;
**Não** não existe no backend.

```mermaid
flowchart LR
    E1[Etapa 1<br/>Submissão e triagem]:::sim --> E2[Etapa 2<br/>Governança e amostras]:::sim
    E2 --> E3[Etapa 3<br/>Ensaio interlaboratorial]:::parcial
    E3 --> E4[Etapa 4<br/>Avaliação, estatística e conclusão]:::nao
    classDef sim fill:#2e7d32,color:#fff
    classDef parcial fill:#f9a825,color:#000
    classDef nao fill:#9e9e9e,color:#fff
```

## Gestão de usuários (RF001–RF006)

| RF | Requisito | Estado | Como |
|---|---|---|---|
| RF001 | Cadastro e autenticação | Sim | Cadastro público, login por cookie ou Bearer, recuperação de senha |
| RF002 | Perfis de acesso | Sim | Perfis globais com permissões; Administrador e BraCVAM oficiais |
| RF003 | Vinculação institucional | Sim | Instituições, laboratórios e vínculos de usuários |
| RF004 | Controle de acesso | Sim | Permissão global, cargo no processo, concessão por atividade, isolamento por laboratório |
| RF005 | Designação de participantes | Sim | Designação direta e convite por link ou e-mail |
| RF006 | Conflito de interesse | Sim | Declaração por designação; bloqueia decisões no processo |

## Submissão de métodos (RF007–RF014)

| RF | Requisito | Estado | Como |
|---|---|---|---|
| RF007 | Submissão estruturada | Sim | Formulários dinâmicos por template |
| RF008 | Anexos | Sim | Campos de arquivo, com tipo e tamanho validados |
| RF009 | Edição durante a elaboração | Sim | Rascunho; reabertura pela revisão do retorno |
| RF010 | Versionamento | Sim | Cada reenvio é uma nova execução; as versões devolvidas ficam guardadas com a justificativa (`submission-versions`) |
| RF011 | Notificação dos retornos | Parcial | O retorno vira tarefa para o proponente; não há e-mail |
| RF012 | Gestão eletrônica de documentos | Parcial | Anexos guardados por campo; sem classificação ou busca de documentos |
| RF013 | Verificação por IA | Sim | Pré-avaliação por critérios |
| RF014 | Envio para análise | Sim | O envio abre a pré-avaliação ou a triagem |

## Base de conhecimento da IA (RF015–RF023)

| RF | Requisito | Estado | Como |
|---|---|---|---|
| RF015 | Base de conhecimento | Parcial | Avaliações e critérios configuráveis; não há documentos indexados nem busca semântica (o pgvector está instalado, mas sem uso) |
| RF016 | Taxonomia de validação | Parcial | Tipos de verificação e severidade fixos; sem taxonomia própria |
| RF017 | Critérios de análise | Sim | Critérios em linguagem natural por avaliação |
| RF018 | Fontes documentais | Parcial | Referências normativas como metadados (identificador, versão), sem o arquivo |
| RF019 | Versionamento da configuração | Sim | Versões publicadas imutáveis |
| RF020 | Checklist de completude | Parcial | Critérios do tipo `presence` |
| RF021 | Inconsistências | Parcial | Critérios `conformity` e `cross_field_consistency` |
| RF022 | Registro das análises | Sim | Resultado por critério guardado em cada execução |
| RF023 | Validação humana | Sim | Retorno do triador por item e contestação pelo proponente |

## Aprovação e gestão do processo (RF024–RF034)

| RF | Requisito | Estado | Como |
|---|---|---|---|
| RF024 | Configuração do fluxo | Parcial | Fases e atividades em YAML no repositório; pela API, só os campos dos formulários |
| RF025 | Análise inicial | Sim | Triagem |
| RF026 | Aprovar, devolver, rejeitar | Sim | `APPROVED`, `NEEDS_REVISION`, `REJECTED` |
| RF027 | Registro de deliberações | Parcial | Decisão de triagem com justificativa; sem deliberações colegiadas |
| RF028 | Reuniões e atas | Não | |
| RF029 | Prazos | Parcial | Prazo por atividade no template; não há prazo por participante nem ajuste manual |
| RF030 | Visualização do fluxo | Parcial | Estados de fases e atividades, tarefas e linha do tempo; sem rota de visão consolidada das fases |
| RF031 | Painel de monitoramento | Parcial | Contagens e resumo em `GET /tasks` |
| RF032 | Comentários | Não | Só comentários nos pareceres de campo da triagem |
| RF033 | Notificações | Parcial | Base de envio pronta; usada em convites, recuperação de senha e problemas no recebimento de amostras e na decisão sobre eles; sem central de notificações |
| RF034 | Logs e auditoria | Sim | Linha do tempo por processo, históricos de RBAC e catálogo, logs estruturados |

## Ensaio interlaboratorial (RF035–RF047)

| RF | Requisito | Estado | Como |
|---|---|---|---|
| RF035 | Configuração do ensaio | Não | |
| RF036 | Formulários dinâmicos | Sim | Mesmo motor de formulários e editor de campos; templates de coleta definem as colunas do arquivo de resultados e o arquivo-modelo em CSV e Excel |
| RF037 | Gestão dos laboratórios | Sim | Catálogo, vínculos e designação de laboratórios |
| RF038 | Codificação de amostras | Sim | Substâncias com gabarito, faixa térmica, frasco, reserva e GHS; SDS; sugestões pelo PubChem; códigos cegos por laboratório; etiquetas com QR |
| RF039 | Despacho | Não | |
| RF040 | Check-in das amostras | Sim | Registro por frasco (data e hora, temperatura, embalagem, observação, fotos); inconformidade decidida pelo Grupo de Seleção: aceitar com ressalva, reenviar com código novo ou desclassificar |
| RF041 | Registro da execução | Parcial | Motor de execução por laboratório pronto; nos templates, só o recebimento |
| RF042 | Ingestão de resultados | Não | Formulários em atividade por laboratório respondem `409` |
| RF043 | Dados brutos | Não | |
| RF044 | Acesso por laboratório | Sim | Cada laboratório vê só a própria execução |
| RF045 | Submissão dos resultados | Não | |
| RF046 | Monitoramento interlaboratorial | Parcial | Gestor vê as tarefas de todos os laboratórios; o Grupo de Seleção vê as inconformidades do recebimento; sem painel de recebimento ou resultados |
| RF047 | Reprodutibilidade | Não | |

O template de coleta não tem colunas calculadas, registro de ensaio
fracassado, reordenação em lote nem exclusão do template. Só quem tem
`collection_templates.manage` baixa o arquivo-modelo; o laboratório não o
baixa nem envia resultados (RF042).

## Avaliação ad hoc, estatística e conclusão (RF048–RF062)

| RF | Requisito | Estado | Como |
|---|---|---|---|
| RF048 | Designação de avaliadores ad hoc | Parcial | Cargo `adhoc_evaluator` designável; nenhuma atividade de avaliação |
| RF049 | Distribuição dos materiais | Não | |
| RF050 | Revisão cega | Parcial | Só o cegamento das amostras; o gabarito das substâncias fica restrito ao Grupo de Seleção |
| RF051–RF054 | Pareceres e consolidação | Não | |
| RF055–RF059 | Análise estatística | Não | |
| RF060 | Validação final | Não | |
| RF061 | Relatório final | Não | |
| RF062 | Exportação | Não | |

## Fora do backend

- Telas, layout e impressão de etiquetas: frontend.
- Hospedagem de arquivos em serviço externo: os anexos ficam no disco da API.
