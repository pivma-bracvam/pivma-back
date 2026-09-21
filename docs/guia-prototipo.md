# Guia inicial do protótipo

## Escopo e natureza deste documento

Este guia descreve o que foi observado nos vídeos do protótipo e o que está registrado nos respectivos roteiros. Ele não transforma o protótipo em especificação definitiva e não substitui o Plano de Trabalho da Fase II.

Fonte complementar: [pasta de materiais do protótipo no Google Drive](https://drive.google.com/drive/folders/1qgCSayKFCUDk6TAG4G5cSwziQfilxJpc?usp=share_link).

As informações estão classificadas como:

- **CONFIRMADO NO MATERIAL:** comportamento, tela, campo, fluxo ou regra diretamente observado em vídeo ou explicitamente registrado em roteiro. Quando a confirmação provém somente do roteiro, isso é indicado.
- **INFERÊNCIA:** interpretação provável a partir da sequência ou da interface, sem confirmação explícita.
- **DÚVIDA / PONTO A VALIDAR:** lacuna, divergência ou decisão que exige confirmação da equipe.

## Materiais complementares analisados

### Documentos de roteiro

| Material | Situação da leitura | Uso neste guia |
|---|---|---|
| `Roteiros` (Google Docs) | Acessível e legível integralmente | Fonte textual complementar para objetivos, papéis e sequências narradas |
| `4.1 Preparando a validação - Grupo gestor.md` | Acessível e legível integralmente | Roteiro específico da preparação da validação |

### Vídeos principais

| Vídeo | Duração aproximada | Situação da leitura |
|---|---:|---|
| `01.2 - Submissão e Triagem.mp4` | 1min08s | Decodificado e inspecionado visualmente |
| `02 - Modelagem e customização (Final).mp4` | 1min20s | Decodificado e inspecionado visualmente |
| `03 - Preparação - Grupo gestor.mp4` | 1min23s | Decodificado e inspecionado visualmente |
| `04.2 - Seleção das amostras (Final).mp4` | 1min39s | Decodificado e inspecionado visualmente |
| `04.3.1 - Planejamento Estatístico (Final).mp4` | 3min06s | Decodificado e inspecionado visualmente |
| `05.1 - Confirmação de recebimento de amostras (Final).mp4` | 50s | Decodificado e inspecionado visualmente |
| `05.2 - Upload e validação (Final).mp4` | 1min25s | Decodificado e inspecionado visualmente |
| `05.3 - Confirmação de Devolução de Amostras (Final).mp4` | 1min10s | Decodificado e inspecionado visualmente |
| `06.1 - Avaliação Independente do Comitê ADHOC (Final).mp4` | 1min12s | Decodificado e inspecionado visualmente |
| `06.2 - Consolidação técnica (Final).mp4` | 1min18s | Decodificado e inspecionado visualmente |
| `06.3 - Deliberação final (Final).mp4` | 1min04s | Decodificado e inspecionado visualmente |

### Variantes anteriores e duplicidades

Também foram decodificadas e inspecionadas as variantes sem a marca “(Final)” de seleção de amostras, planejamento estatístico, recebimento, devolução e avaliação ADHOC.

A cópia `Preparação - Grupo gestor.mp4` da subpasta é byte a byte idêntica ao arquivo `03 - Preparação - Grupo gestor.mp4` da raiz. As demais variantes são arquivos diferentes e foram tratadas como versões distintas, sem pressupor formalmente qual substitui qual.

## Elementos gerais observados

### CONFIRMADO NO MATERIAL

- A interface exibe as marcas pi\*VMA, BraCVAM e Fiocruz.
- Usuários acessam uma lista de métodos vinculados ao seu perfil.
- Os cartões de método mostram um código no padrão `BRA-2026-*`, nome do método, tipo do processo, criador e data de criação.
- A área de um método apresenta tarefas, acesso a `Auditoria`, progresso geral e um fluxo dividido visualmente em quatro etapas:
  1. `SUBMISSÃO E TRIAGEM`;
  2. `PLANEJAMENTO E PREPARAÇÃO`;
  3. `EXECUÇÃO DA VALIDAÇÃO`;
  4. `REVISÃO E DECISÃO`.
- Há filtros de tarefas, incluindo `Todas as Tarefas`, `Minhas Tarefas` e status.
- As tarefas podem aparecer como pendentes, concluídas ou bloqueadas por dependências.
- Os vídeos utilizam perfis simulados para demonstrar diferentes visões de acesso.
- Foram observados os seguintes papéis ou rótulos de perfil no protótipo:
  - BraCVAM;
  - Administrador;
  - Grupo Gestor;
  - Grupo de Seleção de Amostras;
  - Laboratório Líder;
  - Laboratórios Participantes;
  - Estatístico;
  - Especialistas Temáticos do Comitê ADHOC.

### INFERÊNCIA

- A lista de métodos e as tarefas são filtradas conforme o perfil simulado e o vínculo do usuário com cada método.
- O progresso geral parece estar associado à conclusão das etapas ou tarefas, mas a fórmula de cálculo não é demonstrada.

### DÚVIDA / PONTO A VALIDAR

- Os quatro estágios exibidos no protótipo não correspondem diretamente aos seis módulos do Plano de Trabalho. É necessário confirmar a relação entre “módulo”, “etapa”, “tarefa” e “tipo de tarefa”.
- O protótipo alterna termos como `BraCVAM`, `Grupo Gestor`, `Gestor`, `Comitê ADHOC` e `Especialistas Temáticos`; a nomenclatura canônica e as responsabilidades de cada papel precisam ser confirmadas.
- O padrão visual `BRA-2026-*` deve ser comparado ao identificador oficial `crCode`; os materiais não afirmam que são o mesmo identificador.

## 1. Submissão e triagem

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `01.2 - Submissão e Triagem.mp4`

- O vídeo demonstra uma conta associada ao perfil BraCVAM.
- A conta visualiza métodos vinculados e abre a tarefa `Submissão e Triagem de Métodos`.
- O formulário de triagem aparece dividido em três partes: `Identificação`, `Parâmetros do Ensaio` e `Anexos e Protocolos`.
- O material submetido inclui, entre outros itens visíveis, nome do método, princípio de redução ou substituição, número de replicatas, concentração máxima de teste e documento `Procedimento Operacional Padrão (POP)`.
- O revisor pode usar `Apontar Problema` e registrar um comentário sobre um campo.
- O painel de revisão oferece as ações `Recusar e Devolver` e `Aprovar e Avançar`.
- Após a aprovação, a etapa `SUBMISSÃO E TRIAGEM` aparece concluída e o processo avança para `PLANEJAMENTO E PREPARAÇÃO`.
- Novas tarefas de atribuição e aprovação passam a aparecer; uma delas é mostrada como bloqueada por dependências anteriores.

#### Registrado somente no documento `Roteiros`

- Há um roteiro chamado `Criação - Submissão e triagem` no qual uma conta nova cria um método, é registrada automaticamente como proponente, seleciona o nível de maturidade, preenche o formulário e o submete à análise da IA.
- Nesse roteiro, a IA aponta uma inconsistência; o proponente corrige o ponto e envia novamente, após o que o processo é submetido à triagem do BraCVAM.
- Há um roteiro separado de `Monitoramento`, segundo o qual a equipe do BraCVAM usa um quadro Kanban para visualizar tarefas pendentes, processos não iniciados, atrasos e demandas concluídas.
- O roteiro `Triagem de um método` descreve a análise de todos os pontos do formulário e as opções de recusa/devolução ou aprovação/avanço.

### INFERÊNCIA

- A numeração `01.2` e o conteúdo observado indicam que o vídeo representa principalmente a parte de triagem pelo BraCVAM, e não a criação inicial pelo proponente.
- A criação/submissão narrada no roteiro pode corresponder a um vídeo `01.1` que não está presente na pasta analisada.

### DÚVIDA / PONTO A VALIDAR

- Não foi encontrado vídeo que confirme visualmente o cadastro de nova conta, a criação de método pelo proponente e o ciclo de correção após retorno da IA.
- O vídeo `01.2` não demonstra o Kanban descrito no roteiro de monitoramento.
- Não está definido nos materiais se a IA bloqueia o envio, apenas recomenda correções ou muda o estado da tarefa.
- O conteúdo, a origem e o versionamento dos critérios usados pela IA nessa triagem não são mostrados.

## 2. Modelagem e customização de processos e formulários

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `02 - Modelagem e customização (Final).mp4`

- O perfil Administrador possui acesso a `Configurações`.
- A tela `Configurações do Sistema` apresenta `Configurar Processos` como ativo; `Gerenciar Usuários` e `Gerenciar Plataforma` aparecem como `Em breve`.
- A configuração de processos lista modelos e instâncias de processos.
- O editor de modelo exibe etapas e atividades da etapa selecionada.
- As etapas podem ser reordenadas, com uma confirmação explícita da mudança de posição.
- É possível adicionar uma etapa com nome e ícone.
- Ao adicionar uma tarefa, a interface apresenta tipos de tarefa, incluindo formulário, aprovação formal, atribuição de cargo, aprovação formal, definição de amostras, template de coleta, revisão e decisão, recebimento de amostras, upload de resultados, devolução de amostras, avaliação ADHOC, consolidação técnica e deliberação final.
- O construtor de formulário permite criar etapas/seções e adicionar campos de tipos como texto, inteiro, decimal, upload, opção, data e checkbox.
- Um campo pode ter validação por IA habilitada.
- A configuração visível da IA inclui:
  - regra ou prompt de validação;
  - variáveis do campo para uso no prompt;
  - seleção de `Gemini 1.5 Flash (Rápido & Eficiente)`;
  - ajuste de temperatura;
  - teste do prompt;
  - resultado do teste;
  - histórico recente identificado como `Mock`.

#### Registrado no documento `Roteiros`

- O objetivo declarado é permitir que o administrador modele e personalize fluxos, reorganize etapas, crie tarefas e configure regras de validação por IA.

### INFERÊNCIA

- As configurações de IA parecem pertencer a cada campo do formulário, mas os materiais não demonstram se também há configurações por formulário, tarefa, etapa ou processo.
- O histórico marcado como `Mock` parece ser dado demonstrativo, não uma trilha de auditoria funcional comprovada.

### DÚVIDA / PONTO A VALIDAR

- O Plano de Trabalho prevê um `Módulo Configurador da Base de Conhecimento da IA`, enquanto o vídeo mostra configuração de prompt, modelo e temperatura por campo. A relação entre essas duas configurações não está definida.
- O uso explícito do Gemini no protótipo não deve ser tratado como decisão arquitetural definitiva.
- Não está demonstrado quem pode publicar alterações de um modelo nem como instâncias já iniciadas são afetadas por mudanças.
- O versionamento de modelos, formulários, prompts e critérios não aparece no vídeo.

## 3. Preparação da validação pelo Grupo Gestor

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `03 - Preparação - Grupo gestor.mp4`

- O Grupo Gestor recebe tarefas para definir:
  - o grupo de seleção de amostras;
  - o Laboratório Líder;
  - os laboratórios participantes;
  - o estatístico.
- A interface permite selecionar usuário cadastrado ou convidar por e-mail.
- A atribuição de laboratórios participantes admite mais de uma pessoa.
- A tarefa de revisão do planejamento estatístico informa que a revisão será iniciada após o envio pelo perfil Estatístico.
- Depois do envio, o Grupo Gestor visualiza quatro documentos: `Desenho do Estudo`, `Critérios de Aceitação`, `Plano Estatístico` e `Possibilidade de Erros`.
- Cada documento pode receber um apontamento de problema.
- O painel de revisão oferece `Recusar e Devolver` ou `Aprovar e Avançar`.
- Após aprovação, uma notificação visual indica que a revisão final foi aprovada e o formulário foi concluído.

#### Registrado nos roteiros

- O arquivo Markdown da subpasta descreve a atribuição dos mesmos papéis e a dependência do envio do plano pelo estatístico.
- O documento `Roteiros` contém uma seção `Aprovação Formal da Estrutura (Portão de Decisão)` com a observação: “Não existe interação, apenas abrir e clicar em um botão, vou manter sem video”.

### INFERÊNCIA

- As tarefas de atribuição parecem anteceder a aprovação formal da estrutura e a liberação da execução laboratorial.

### DÚVIDA / PONTO A VALIDAR

- Não há vídeo da aprovação formal da estrutura.
- O papel `Laboratório Líder` aparece no protótipo, mas não está listado nominalmente nos perfis do RF001–RF006.
- É necessário confirmar se convites por e-mail criam um usuário, criam apenas um vínculo pendente ou exigem cadastro prévio.
- Não são mostradas regras para substituição, remoção ou conflito de interesse dos participantes designados.

## 4. Planejamento estatístico e template de coleta

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `04.3.1 - Planejamento Estatístico (Final).mp4`

- O perfil Estatístico envia quatro documentos: `Desenho do Estudo`, `Critérios de Aceitação`, `Plano Estatístico` e `Possibilidade de Erros`.
- A tarefa fica aguardando revisão pelo Grupo Gestor.
- O estatístico também configura um template de coleta de dados.
- O template inclui nome, descrição/finalidade e opção de permitir ensaios fracassados.
- A configuração de réplicas inclui número de experimentos por laboratório e número de réplicas por experimento.
- A estrutura do template é formada por colunas configuráveis.
- A criação de coluna apresenta rótulo de exibição, identificador do campo, tipo de dado, obrigatoriedade, posição/ordem e distinção entre dados brutos e derivados.
- Entre os tipos visíveis estão texto simples, texto longo, inteiro, decimal, booleano, data, data e hora e seleção única.
- A prévia tabular mostra colunas reservadas ou autocompletadas, incluindo identificação do laboratório, nome do operador, digitador dos dados, data do experimento, data da digitação e status de execução.
- O template pode ser salvo e sua prévia visualizada.

#### Registrado somente no documento `Roteiros`

- Os quatro documentos seriam enviados a um `Validador de Inteligência Artificial` logo após a submissão.
- O roteiro usa o HET-CAM (Redcam) como exemplo de template específico para recebimento de ovos embrionados.
- O roteiro afirma que colunas derivadas podem realizar cálculos automatizados entre colunas.

### INFERÊNCIA

- A prévia indica que alguns campos de auditoria e operação são acrescentados pelo sistema, além das colunas definidas pelo estatístico.

### DÚVIDA / PONTO A VALIDAR

- A execução da validação por IA dos quatro documentos não é mostrada no vídeo.
- A fórmula, linguagem ou mecanismo de cálculo das colunas derivadas não é demonstrado.
- A semântica de “permitir ensaios fracassados” e do `Status de Execução` precisa ser especificada.
- Não está demonstrado como alterações em um template afetam resultados já coletados.

## 5. Seleção e codificação de amostras

### CONFIRMADO NO MATERIAL

#### Observado nos vídeos de seleção de amostras

- O perfil `Grupo de Seleção de Amostras` acessa a tarefa `Definição e Preparação das Amostras`.
- O cadastro lateral de amostra contém seções para:
  - identificação básica, incluindo nome químico ou comercial e CASRN;
  - classificação;
  - características visuais e físicas;
  - dados físico-químicos;
  - especificações do teste;
  - qualidade e origem;
  - estabilidade e segurança;
  - composição de mistura;
  - documento SDS em PDF.
- Após o salvamento, a amostra aparece em uma tabela com substância/CASRN, características físicas, classes, documento SDS, códigos cegos e ações.
- A interface exibe um código cego para a amostra.
- A visualização de etiquetas mostra:
  - o estudo;
  - o laboratório participante destinatário;
  - o código cego;
  - um QR Code;
  - a indicação de acesso ao SDS;
  - a ação `Imprimir Etiquetas`.
- A tarefa possui a ação `Confirmar e Concluir Cadastro de Amostras`.

#### Registrado no documento `Roteiros`

- O sistema geraria automaticamente os códigos cegos para cada laboratório participante.
- A conclusão seria registrada na trilha de auditoria e a etapa seguiria para aprovações institucionais.

### INFERÊNCIA

- A presença do laboratório destinatário na etiqueta sugere que a codificação pode variar por laboratório, mas isso não é demonstrado comparando duas etiquetas da mesma amostra.

### DÚVIDA / PONTO A VALIDAR

- Não foi demonstrado o algoritmo de geração, embaralhamento ou unicidade dos códigos cegos.
- O QR Code é visível, mas seu destino, expiração, autorização e comportamento sem autenticação não foram verificados.
- O registro na auditoria não foi aberto no vídeo.
- Não foram demonstrados despacho, acompanhamento de remessa, perda ou substituição de amostra.

## 6. Recebimento de amostras

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `05.1 - Confirmação de recebimento de amostras (Final).mp4`

- O perfil de laboratório participante acessa a etapa `EXECUÇÃO DA VALIDAÇÃO`.
- A tarefa `Confirmação de Recebimento de Amostras` apresenta dados descritivos da amostra sem revelar sua identidade química completa além das informações exibidas para manuseio.
- O laboratório informa o código cego, e a interface mostra uma confirmação de correspondência.
- O formulário inclui quantidade recebida, data de recebimento, condições de chegada do material e observações gerais opcionais.
- As condições de chegada incluem opções como adequado, avariado, temperatura incorreta e vazamento ou quebra.
- A ação `Confirmar Recebimento de Amostras` registra a tarefa e exibe confirmação visual de sucesso.

#### Registrado somente no documento `Roteiros`

- O sistema armazenaria um `Log de Entrega`.
- Haveria checagem automática da correspondência do código cego e consolidação de um inventário de amostras liberadas.
- O portal geraria um protocolo eletrônico de recebimento de material biológico.

### INFERÊNCIA

- A confirmação exibida abaixo do código sugere validação imediata do código cego.

### DÚVIDA / PONTO A VALIDAR

- Não foram exibidos o `Log de Entrega`, o inventário ou o protocolo eletrônico mencionados no roteiro.
- Não está demonstrado o fluxo para código inválido, quantidade divergente, temperatura incorreta, avaria, vazamento ou quebra.
- Não é mostrado quem recebe alertas nem se uma condição inadequada bloqueia a execução.

## 7. Upload e validação de resultados

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `05.2 - Upload e validação (Final).mp4`

- A tarefa `Upload de Resultados Obtidos` apresenta um modelo principal de coleta.
- A tela informa três experimentos independentes por laboratório, cinco réplicas por experimento e permissão para corridas inválidas ou com falha.
- O laboratório pode baixar uma planilha modelo em CSV.
- O envio aceita CSV por clique ou arrastar e soltar.
- Um primeiro arquivo é rejeitado com a mensagem `Falha na Validação da Planilha` e a indicação de coluna obrigatória ausente no cabeçalho: `Status de Execução`.
- Um segundo arquivo passa pela validação e exibe `Validação Concluída com Sucesso`.
- A prévia dos dados validados mostra, entre outros campos, código da amostra, ID do laboratório, nome do operador, digitador dos dados, data do experimento, data da digitação e status de execução.
- A interface oferece `Submeter Planilha de Resultados`.
- Após a submissão, há confirmação visual de que os resultados estatísticos foram submetidos com sucesso e a tarefa deixa de aparecer entre as pendentes do perfil.

#### Registrado no documento `Roteiros`

- A validação seria executada instantaneamente no navegador.
- Erros de tipo e códigos incorretos seriam apresentados com as linhas exatas.

### INFERÊNCIA

- O esquema do template configurado pelo estatístico parece ser usado para validar o cabeçalho e os valores do CSV.

### DÚVIDA / PONTO A VALIDAR

- O vídeo confirma um erro de coluna ausente, mas não demonstra erros de tipo, códigos incorretos ou localização por linha.
- Não está definido se a validação ocorre exclusivamente no navegador, no backend ou em ambos. A autorização e a validação definitiva precisam permanecer no backend.
- Não são mostrados limites de arquivo, tratamento de duplicidade, reenvio, versionamento ou atomicidade da submissão.
- O texto de confirmação usa “resultados estatísticos”, embora a tarefa seja de resultados obtidos pelo laboratório; a terminologia precisa ser validada.

## 8. Devolução de amostras

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `05.3 - Confirmação de Devolução de Amostras (Final).mp4`

- O laboratório acessa a tarefa `Confirmação de Devolução de Amostras`.
- O código cego é usado para identificar e desbloquear a amostra.
- O formulário exibe instrução de descarte ou retorno e solicita:
  - quantidade de frascos vazios retornados;
  - volume não consumido;
  - descrição dos itens físicos devolvidos e detalhes.
- A ação `Confirmar Devolução de Amostras` registra a devolução e exibe confirmação visual de sucesso.
- Após a confirmação, a tarefa deixa de aparecer e o upload de resultados permanece visível como pendência.

#### Registrado somente no documento `Roteiros`

- O sistema faria baixa automática no volume total do lote original.
- Haveria uma `Ficha de Logística Reversa`, um `Recibo de Descarte` e um comprovante com certificado digital de conformidade.

### INFERÊNCIA

- O código cego parece ser usado como chave de acesso aos campos de devolução da amostra correspondente.

### DÚVIDA / PONTO A VALIDAR

- A baixa de estoque, a ficha, o recibo e o certificado digital não aparecem nos vídeos.
- Não estão demonstradas validações de volume, quantidades maiores que as enviadas, devolução parcial, múltiplas devoluções ou correção posterior.
- A relação entre devolução, descarte e encerramento da fase experimental precisa ser confirmada.

## 9. Avaliação independente do Comitê ADHOC

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `06.1 - Avaliação Independente do Comitê ADHOC (Final).mp4`

- O perfil `Especialistas Temáticos (Comitê ADHOC)` acessa a etapa `REVISÃO E DECISÃO`.
- A tarefa apresenta um `Dossiê Completo de Validação (Cego)`.
- A tela informa que as identidades dos laboratórios foram ofuscadas.
- Os resultados são exibidos com identificadores como `Laboratório Cego #1`, código cego da amostra, réplica, média, desvio padrão e status do ensaio.
- O avaliador pode exportar resultados em CSV.
- A emissão de parecer contém observações técnicas e justificativas.
- As decisões preliminares visíveis são:
  - `APROVADO`;
  - `APROVADO COM RESTRIÇÕES`;
  - `REJEITADO`;
  - `SOLICITAR NOVA RODADA DE DADOS`.
- O avaliador submete o parecer técnico, após o que a tarefa deixa de aparecer entre suas pendências.

#### Registrado somente no documento `Roteiros`

- Um novo parecer geraria alerta aos representantes do Grupo Gestor.
- O portal consolidaria pareceres e geraria um relatório técnico unificado para comparação de divergências.

### INFERÊNCIA

- O cegamento observado protege os nomes dos laboratórios durante a avaliação, mas não prova quais outras identidades ou metadados são ocultados.

### DÚVIDA / PONTO A VALIDAR

- O alerta automático e o relatório unificado não aparecem no vídeo.
- O roteiro usa o termo “junta médica”, que parece destoar do contexto de métodos alternativos e deve ser confirmado antes de adoção terminológica.
- Não é mostrado se avaliadores veem os pareceres uns dos outros antes de submeter o próprio parecer.
- Não são demonstrados conflito de interesse, prazo, edição posterior ou anexação de evidências ao parecer.

## 10. Consolidação técnica

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `06.2 - Consolidação técnica (Final).mp4`

- O Grupo Gestor acessa a tarefa `Consolidação Técnica entre Comitê ADHOC e Grupo Gestor`.
- O dossiê é identificado: os nomes dos laboratórios e as substâncias químicas aparecem revelados.
- A tabela relaciona laboratório participante, substância química, código cego, média, desvio padrão e status.
- A tela inclui seções para pareceres do Comitê ADHOC e para registros da reunião técnica.
- No cenário demonstrado, a seção de pareceres informa que nenhum parecer técnico foi submetido até o momento.
- O formulário de consolidação inclui:
  - discussões técnicas da reunião de avaliação;
  - divergências entre pareceres;
  - limitações metodológicas;
  - necessidades de complementação documental.
- O Grupo Gestor pode solicitar ajuste a um laboratório, selecionando o laboratório e descrevendo a ação.
- O vídeo registra uma solicitação a `Laboratório Beta` com estado `PENDENTE DE ENVIO`.
- A interface apresenta o botão `Salvar e Concluir Consolidação Técnica`.

#### Registrado no documento `Roteiros`

- O Grupo Gestor teria acesso aos pareceres individuais e notas previamente submetidos.
- Ao final, clicaria em `Concluir Consolidação e Gerar Relatório Técnico`, registrando o parecer técnico consolidado.

### INFERÊNCIA

- A consolidação parece ser o ponto em que o cegamento dos laboratórios e das amostras é removido para o Grupo Gestor.

### DÚVIDA / PONTO A VALIDAR

- O vídeo mostra ausência de pareceres, embora o roteiro pressuponha pareceres previamente submetidos.
- O vídeo termina com uma solicitação de ajuste pendente e não demonstra a conclusão da consolidação nem a geração de relatório técnico.
- O texto do botão no vídeo difere do texto citado no roteiro.
- É necessário definir se uma solicitação de ajuste impede a conclusão, reabre tarefas laboratoriais ou inicia uma nova rodada formal.

## 11. Deliberação final e publicação

### CONFIRMADO NO MATERIAL

#### Observado no vídeo `06.3 - Deliberação final (Final).mp4`

- O Grupo Gestor acessa a tarefa `Deliberação Final e Publicação`.
- A tela apresenta um resumo técnico de pareceres e consolidação.
- No cenário demonstrado, o resumo contém ausência de parecer emitido, ata de consolidação, consolidação técnica pendente, divergências registradas e nenhuma limitação relatada.
- As opções visíveis de decisão final são:
  - `Aprovado (Homologado)`;
  - `Aprovado com Restrições`;
  - `Rejeitado (Não Validado)`;
  - `Solicitar nova rodada de dados estatísticos`.
- O formulário inclui parecer institucional consolidado e recomendação regulatória.
- Entre as recomendações visíveis estão substituição plena do ensaio in-vivo correspondente, uso integrado em estratégias IATA, uso restrito para triagem inicial ou controle interno e método não recomendado para fins regulatórios.
- É exigido upload de documentação oficial ou portaria em PDF.
- Arquivos não PDF são recusados visualmente; um PDF é aceito e exibido no formulário.
- Há uma chave `Aprovação e Assinatura Institucional`.
- Com o PDF carregado e a chave ativada, o botão `Publicar Deliberação Final e Concluir Processo` fica habilitado.

#### Registrado somente no documento `Roteiros`

- O roteiro afirma que o usuário confirma a publicação em um modal, o parecer é publicado e o processo é concluído.

### INFERÊNCIA

- O PDF oficial e a confirmação institucional parecem ser pré-condições de interface para habilitar a publicação.

### DÚVIDA / PONTO A VALIDAR

- O vídeo não demonstra o clique final, o modal de confirmação, o estado publicado nem a conclusão efetiva do processo.
- A terminologia das decisões no vídeo difere parcialmente do roteiro, que usa `Aprovado`, `Aprovado com Restrições`, `Rejeitado` e `Solicitar Nova Rodada de Dados`.
- Não está definido quem possui autoridade para ativar a aprovação institucional nem como a assinatura do PDF é validada.
- Não são demonstrados versionamento, republicação, revogação, publicidade, visibilidade externa ou preservação do documento oficial.

## 12. Auditoria, rastreabilidade e controle de acesso observáveis

### CONFIRMADO NO MATERIAL

- A navegação de cada método inclui uma opção `Auditoria`.
- A interface mostra tarefas atribuídas conforme o perfil simulado.
- O dossiê do Comitê ADHOC oculta os nomes dos laboratórios, enquanto a consolidação do Grupo Gestor exibe nomes e substâncias.
- Códigos cegos são usados na seleção, recebimento, devolução, upload e avaliação.
- Diversas ações exibem mensagens de atualização ou conclusão de tarefa.

### INFERÊNCIA

- As diferenças de visualização entre perfis sugerem controle de acesso por papel e por participação no método.
- A mudança de dossiê cego para identificado sugere um ponto de revelação controlada entre avaliação independente e consolidação.

### DÚVIDA / PONTO A VALIDAR

- Os vídeos não abrem a trilha de auditoria nem permitem confirmar quais eventos, valores anteriores, autores, datas ou justificativas são preservados.
- O seletor `Simular Perfil` é próprio da demonstração; ele não comprova o mecanismo real de autenticação ou autorização.
- O isolamento entre laboratórios não foi testado comparando contas de laboratórios diferentes.
- Nenhum material demonstra tentativa de acesso indevido, autorização no backend ou proteção contra alteração de identificadores no cliente.
