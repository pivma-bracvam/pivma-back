# Observações e pendências

## Escopo

Este documento reúne ambiguidades, inconsistências, informações ausentes e perguntas identificadas durante a conversão do Plano de Trabalho da Fase II e a análise dos materiais do protótipo.

Nenhum item abaixo altera o conteúdo das fontes. O PDF oficial permanece como fonte principal; roteiros e vídeos são fontes complementares e não constituem, isoladamente, especificação definitiva.

## Contrato de sessão e acesso

### DECISÃO REGISTRADA

- Por solicitação explícita da equipe, `GET /auth/me` retorna a identidade autenticada e um resumo do acesso efetivo para inicializar o frontend: permissões globais e escopos ativos por processo.
- O resumo não substitui as verificações de autorização do backend e não inclui capacidades derivadas, tarefas, justificativas de conflito ou dados de auditoria.
- A resposta mantém os campos legados `id`, `username` e `email` para reduzir impacto nos consumidores existentes.

## Acesso e limitações dos materiais

### CONFIRMADO

- O PDF oficial foi acessado integralmente, extraído e conferido visualmente nas 11 páginas.
- A página 11 do PDF contém apenas o cabeçalho, sem conteúdo adicional.
- A pasta do Google Drive foi percorrida, incluindo a subpasta `4.1 Preparando a validação - Grupo gestor`.
- O Google Docs `Roteiros` e o Markdown da subpasta foram lidos integralmente.
- Todos os 17 arquivos MP4 foram acessados e decodificados.
- Existem 16 vídeos únicos: a cópia de `Preparação - Grupo gestor.mp4` na subpasta é byte a byte idêntica ao arquivo `03 - Preparação - Grupo gestor.mp4` da raiz.
- Nenhum material listado na pasta ficou inacessível.

### LIMITAÇÕES

- A análise dos vídeos se concentrou nas telas, campos, estados e transições visíveis. A narração foi contextualizada pelo documento `Roteiros`, mas afirmações narradas e não visíveis não foram convertidas em comportamento visual confirmado.
- Os materiais são demonstrações de protótipo com dados simulados. Eles não comprovam persistência, segurança, autorização no backend, isolamento efetivo, concorrência, desempenho ou comportamento em casos de erro não demonstrados.
- Não foram fornecidos documentos DOC ou DOCX nesta etapa.

## Peculiaridades preservadas do PDF oficial

Os itens a seguir foram preservados na conversão, sem correção silenciosa:

- `National Council for the Control of Animal Experimentaion` no glossário de CONCEA.
- `FIOCRUZ- BraCVAM` na identificação do órgão responsável.
- RF011: `Gerar notificações assíncrona com retornos da IA e validação .`
- RF013 sem pontuação final.
- A expressão `eventuais problemas e ou perdas das amostras` na seção 2.
- A redação `Outra estratégia metodológica, são as reuniões semanais...` na seção 4.
- A nota `Cada sprint será planejada e executada em uma semana`.
- O cabeçalho `Atividade (Trimestre)` em uma tabela cujas colunas estão organizadas de `1M` a `8M`.

### Perguntas para a equipe

1. Essas grafias e construções devem permanecer como texto oficial ou haverá uma versão revisada do Plano de Trabalho?
2. O cabeçalho do cronograma deveria ser `Atividade (Mês)` em vez de `Atividade (Trimestre)`?
3. Existe uma versão assinada, aprovada ou com controle de revisão que deva substituir o PDF recebido?

## Terminologia e papéis

### Pontos observados

- O Plano de Trabalho lista: Proponente, Grupo Gestor, Gerente do Estudo, Laboratório Participante, Avaliador Ad Hoc, Revisor, Especialista, Analista Estatístico e Administrador.
- O protótipo também usa: BraCVAM, Grupo de Seleção de Amostras, Laboratório Líder, Laboratórios Participantes e Especialistas Temáticos do Comitê ADHOC.
- O PDF usa `Peer Review Committee`, `Avaliador Ad Hoc`, `Revisor` e `Especialista`, mas não define se são papéis distintos ou sobrepostos.
- O roteiro de avaliação usa a expressão `junta médica`, que não aparece no Plano de Trabalho e parece destoar do domínio descrito.
- O roteiro de planejamento menciona `HET-CAM (Redcam)`; a grafia e a relação entre esses termos não são explicadas.

### Perguntas para a equipe

1. Qual é a lista canônica de papéis da plataforma?
2. `BraCVAM`, `Grupo Gestor` e `Gerente do Estudo` são papéis distintos? Quais permissões e responsabilidades pertencem a cada um?
3. `Avaliador Ad Hoc`, `Revisor`, `Especialista` e membro do `Peer Review Committee` representam funções diferentes?
4. `Grupo de Seleção de Amostras` e `Laboratório Líder` devem ser incluídos formalmente entre os perfis ou são atribuições dentro de um processo?
5. A expressão `junta médica` deve ser substituída por `Comitê ADHOC`, `Peer Review Committee` ou outro termo oficial?
6. Qual grafia deve ser adotada como padrão: `Ad Hoc`, `ad hoc` ou `ADHOC`?

## Identificação de métodos e processos

### Pontos observados

- O documento oficial define `crCode` como identificador único de cada método submetido.
- O protótipo exibe identificadores como `BRA-2026-1`, `BRA-2026-2` e `BRA-2026-3`.
- Os materiais não afirmam que esses identificadores são equivalentes.
- O protótipo mostra quatro etapas de fluxo, enquanto o Plano de Trabalho organiza o produto em seis módulos.

### Perguntas para a equipe

1. O código `BRA-2026-*` é o `crCode`, um código de processo, um identificador de demonstração ou outro conceito?
2. Um método pode ter mais de um processo de validação e, portanto, mais de um identificador?
3. Qual é a relação oficial entre módulo, modelo de processo, instância de processo, etapa, tarefa e tipo de tarefa?
4. Quais estados e transições são válidos para método, processo, etapa e tarefa?

## Diferenças entre documento oficial, roteiro e vídeos

### Submissão e monitoramento

- O roteiro descreve criação de conta, criação do método pelo proponente, seleção de maturidade e ciclo de correção após retorno da IA.
- O vídeo `01.2 - Submissão e Triagem.mp4` mostra principalmente a revisão pelo perfil BraCVAM.
- Não foi encontrado um vídeo `01.1` ou equivalente para confirmar a criação e a submissão inicial.
- O roteiro descreve monitoramento em Kanban, mas nenhum vídeo específico de monitoramento está presente.

### Aprovação formal da estrutura

- O roteiro registra que não haveria vídeo porque a interação seria apenas abrir e clicar em um botão.
- Não há material visual para confirmar o portão de decisão, suas pré-condições, responsável ou efeitos.

### Planejamento estatístico

- O roteiro afirma que quatro documentos são enviados à análise automática de IA; o vídeo mostra upload e revisão, mas não a análise da IA.
- O roteiro apresenta HET-CAM como exemplo; o exemplo não aparece no vídeo.

### Seleção de amostras

- O roteiro afirma geração automática de códigos cegos para cada laboratório. O protótipo mostra um código e uma etiqueta para um laboratório, sem comparação entre laboratórios.
- O roteiro afirma registro na trilha de auditoria; a auditoria não é aberta.

### Recebimento

- O roteiro menciona `Log de Entrega`, inventário de amostras liberadas e protocolo eletrônico.
- Os vídeos mostram formulário, validação do código, confirmação e mensagem de sucesso, mas não mostram esses artefatos.

### Upload de resultados

- O roteiro diz que a validação ocorre instantaneamente no navegador e apresenta erros por linha.
- O vídeo confirma um erro de cabeçalho e uma prévia de arquivo válido, mas não comprova execução exclusivamente no navegador nem erros detalhados por linha.
- A confirmação visual usa a expressão `resultados estatísticos submetidos com sucesso`, embora o fluxo seja executado pelo laboratório participante.

### Devolução

- O roteiro menciona baixa automática de estoque, ficha de logística reversa, recibo de descarte e certificado digital.
- Os vídeos não mostram esses artefatos nem a atualização do estoque.

### Avaliação ADHOC

- O roteiro afirma geração de alerta ao Grupo Gestor e relatório técnico unificado.
- Os vídeos não mostram o alerta nem o relatório.

### Consolidação técnica

- O roteiro pressupõe pareceres individuais previamente submetidos.
- No vídeo de consolidação, a interface informa que nenhum parecer foi submetido.
- O roteiro descreve a conclusão e geração de relatório técnico.
- O vídeo termina após criar uma solicitação de ajuste pendente para um laboratório; não demonstra a conclusão.
- O roteiro usa `Concluir Consolidação e Gerar Relatório Técnico`; o vídeo mostra `Salvar e Concluir Consolidação Técnica`.

### Deliberação final

- O roteiro afirma que a publicação é confirmada em modal e o processo é concluído.
- O vídeo mostra o formulário preenchido, PDF aceito, confirmação institucional ativada e botão de publicação habilitado, mas não mostra o clique final ou o estado publicado.
- O cenário de deliberação mostra ausência de parecer e consolidação técnica pendente, embora a deliberação seja apresentada como etapa final.
- As opções de decisão têm redações parcialmente diferentes no roteiro e no vídeo.

### Perguntas para a equipe

1. Qual fonte complementar representa a versão mais recente do protótipo: vídeos `Final`, variantes sem `Final` ou o documento `Roteiros`?
2. Os comportamentos citados apenas nos roteiros fazem parte do escopo aprovado ou são ideias de demonstração ainda não validadas?
3. A deliberação pode ser iniciada sem parecer ADHOC e sem consolidação concluída?
4. Solicitar ajuste a um laboratório reabre a execução, cria uma nova rodada ou mantém a consolidação aberta?
5. Quais textos de botões, decisões e estados devem ser considerados canônicos?

## IA e base de conhecimento

### Pontos confirmados no Plano de Trabalho

- A IA deve apoiar verificação de completude, identificação de inconsistências e análise de conformidade.
- A base de conhecimento deve permitir gestão de conhecimentos, taxonomia, critérios, fontes documentais e versionamento.
- As análises de IA devem registrar a base e os critérios utilizados.
- Recomendações de IA devem ser submetidas a validação humana.
- O apoio de IA não substitui o parecer do especialista.

### Pontos observados somente no protótipo ou roteiro

- O protótipo permite configurar prompt, variáveis, modelo e temperatura por campo de formulário.
- O modelo visível é `Gemini 1.5 Flash (Rápido & Eficiente)`.
- O Plano de Trabalho menciona o planejamento da integração do `IA-OIACTEST`, mas não define sua relação com o Gemini ou com a base de conhecimento.

### Perguntas para a equipe

1. Qual é a relação entre IA-OIACTEST, o modelo Gemini exibido no protótipo e a base de conhecimento do pi\*VMA?
2. Quem pode cadastrar fontes, alterar critérios, configurar prompts e aprovar versões?
3. Como a análise registra versão da base, fontes, critérios, modelo e configuração utilizados?
4. Quais respostas da IA são apenas orientativas e quais estados do fluxo podem ser afetados por elas?
5. Como o especialista revisa, aceita, ajusta ou rejeita uma recomendação de IA?
6. Quais informações devem acompanhar uma recomendação para permitir rastreabilidade e revisão humana?

## Isolamento de dados, cegamento e autorização

### Pontos observados

- O Plano de Trabalho exige acesso individualizado e impede troca de informações entre laboratórios durante etapas restritas.
- O protótipo mostra resultados com laboratórios cegos para o Comitê ADHOC e identificados para o Grupo Gestor na consolidação.
- Os vídeos utilizam um seletor de perfil de demonstração; isso não comprova autorização real.

### Perguntas para a equipe

1. Em quais etapas ocorre cegamento de amostras, laboratórios, operadores, proponentes e demais participantes?
2. Qual evento autoriza a revelação das identidades e quem pode executá-lo?
3. Quais dados cada papel pode visualizar antes e depois da revelação?
4. O Laboratório Líder pode visualizar dados dos laboratórios participantes durante a execução?
5. Como serão tratados usuários vinculados a mais de uma instituição ou laboratório?
6. Como conflitos de interesse afetam designação e acesso?
7. Quais ações exigem nova verificação de autorização no backend, mesmo quando o botão está oculto na interface?

## Auditoria e rastreabilidade

### Informações ausentes nos materiais visuais

- Conteúdo detalhado da tela `Auditoria`.
- Eventos obrigatórios e granularidade dos logs.
- Preservação de valores anteriores e posteriores.
- Identificação do autor, data, justificativa e origem da ação.
- Versionamento de submissões, documentos, formulários, templates, critérios, prompts, pareceres e relatórios.
- Tratamento de correções, reaberturas, cancelamentos, revogações e republicações.

### Perguntas para a equipe

1. Quais eventos devem obrigatoriamente integrar a trilha de auditoria?
2. Quais artefatos precisam de versionamento e qual versão deve ser associada a cada decisão?
3. Como comentários, devoluções e justificativas se relacionam às versões dos documentos avaliados?
4. Como deve ser registrada a revelação de dados cegos?
5. Quais registros devem ser imutáveis e quais podem receber retificação com histórico?

## Amostras e logística

### Informações ausentes

- Regras para geração e colisão de códigos cegos.
- Relação entre amostra, lote, frasco, insumo e laboratório.
- Estados de despacho, recebimento, avaria, perda, consumo, devolução e descarte.
- Tratamento de substituição e reposição.
- Regras de quantidade e volume.
- Destino e autorização do QR Code do SDS.

### Perguntas para a equipe

1. O código cego é gerado por amostra, frasco, lote, laboratório, rodada ou combinação desses elementos?
2. Como perdas, avarias e reposições preservam o cegamento e a rastreabilidade?
3. Quem confirma despacho, recebimento, devolução e descarte?
4. Quais comprovantes são obrigatórios e quais exigem assinatura ou certificado digital?

## Dados experimentais e análise estatística

### Informações ausentes

- Regras completas dos tipos e das colunas derivadas.
- Semântica de experimento independente, réplica técnica, corrida inválida e ensaio fracassado.
- Reenvio e versionamento de CSV.
- Tratamento de duplicidades, valores ausentes e correções.
- Métodos estatísticos, parâmetros, critérios de aceitação e responsabilidade pela execução.

### Perguntas para a equipe

1. Quem define e aprova o template de coleta antes da execução?
2. O template fica imutável após o primeiro download ou envio de resultados?
3. Como são representadas e avaliadas corridas inválidas ou com falha?
4. Quem pode corrigir dados e como a correção é auditada?
5. Quais análises são realizadas na plataforma e quais são apenas importadas como resultados externos?

## Planejamento e cronograma

### Pontos a validar

- O planejamento totaliza 20 sprints de uma semana, enquanto o cronograma está organizado em oito meses.
- O cronograma inclui períodos de implantação e treinamento sobrepostos ao desenvolvimento de módulos.
- Não estão definidos critérios de aceite por sprint ou por módulo no PDF recebido.

### Perguntas para a equipe

1. As 20 sprints são sequenciais, paralelas entre frentes ou distribuídas ao longo dos oito meses?
2. Quais entregáveis e critérios de aceite encerram cada módulo?
3. O cronograma do PDF é indicativo ou contratualmente vinculante?
