# Montar a equipe e preparar as amostras

Depois da triagem, o estudo precisa de gente: um patrocinador, um Grupo
Gestor para coordenar, um grupo que escolhe as substâncias, os laboratórios
que vão testá-las e os especialistas que acompanham o estudo. Neste tutorial
a equipe é montada e as amostras são preparadas de forma cega: os
laboratórios recebem frascos com códigos, sem saber o que há dentro.

```mermaid
sequenceDiagram
    actor A as Administrador
    actor P as Proponente
    actor G as Grupo Gestor
    actor E as Estatístico
    actor S as Seleção de Amostras
    actor L as Laboratório
    participant API
    A->>API: cadastra o laboratório e vincula sua equipe
    P->>API: indica o patrocinador e o Grupo Gestor
    G->>API: indica a seleção de amostras, os laboratórios e os especialistas
    E->>API: envia o plano estatístico
    API-->>S: abre a definição das amostras
    S->>API: cadastra substâncias e fichas de segurança
    S->>API: conclui e gera os códigos cegos
    L->>API: tenta ver as substâncias
    API-->>L: não encontrado
```

## Os personagens

- **Administrador**: mantém o cadastro de instituições e laboratórios.
- **Proponente**: indica o patrocinador e quem vai gerir o estudo.
- **Grupo Gestor**: monta o restante da equipe.
- **Estatístico**: envia o plano estatístico do estudo.
- **Grupo de Seleção de Amostras**: único que conhece as substâncias.
- **Laboratório participante**: vai testar as amostras sem saber o que são.

## Antes de começar

Faça o tutorial [Do cadastro à triagem](primeiro-processo.md) inteiro. Este
tutorial continua aquele processo, que já está na Fase 2. Recupere o processo:

??? example "Como fazer pela API"
    ```bash
    PROP=$(login proponente senha-segura-123)
    PID=$(curl -s "$API/processes" -H "Authorization: Bearer $PROP" \
      | jq -r '.data[] | select(.title=="Método 3T3 NRU") | .id')
    echo $PID
    ```

## 1. As novas pessoas criam suas contas

A gestora do estudo, a responsável pela seleção de amostras, o técnico do
laboratório, o patrocinador, o estatístico, a colaboradora e o avaliador ad
hoc se cadastram.

??? example "Como fazer pela API"
    ```bash
    signup() {
      curl -s -X POST $API/users -H 'Content-Type: application/json' \
        -d "{\"username\":\"$1\",\"email\":\"$1@example.com\",\"full_name\":\"Usuário $1\",\"password\":\"senha-segura-123\"}" \
        | jq -r .id
    }
    GESTORA_ID=$(signup gestora)
    SELECAO_ID=$(signup selecao)
    TECNICO_ID=$(signup tecnico)
    PATROCINIO_ID=$(signup patrocinio)
    ESTATISTICO_ID=$(signup estatistico)
    COLABORADORA_ID=$(signup colaboradora)
    AVALIADOR_ID=$(signup avaliador)
    ```

## 2. O administrador cadastra o laboratório

Um laboratório só participa do estudo se estiver no cadastro da plataforma e
se quem trabalha nele estiver vinculado a ele. O administrador cria a
instituição, o laboratório e vincula o técnico.

??? example "Como fazer pela API"
    ```bash
    ADMIN=$(login admin@example.com admin-senha-123)
    INST=$(curl -s -X POST $API/institutional/institutions -H "Authorization: Bearer $ADMIN" \
      -H 'Content-Type: application/json' -d '{"name":"Instituto Exemplo"}' | jq -r .id)
    LAB=$(curl -s -X POST $API/institutional/laboratories -H "Authorization: Bearer $ADMIN" \
      -H 'Content-Type: application/json' \
      -d "{\"institution_id\":\"$INST\",\"name\":\"Laboratório de Toxicologia\"}" | jq -r .id)
    curl -s -X POST $API/institutional/users/$TECNICO_ID/affiliations -H "Authorization: Bearer $ADMIN" \
      -H 'Content-Type: application/json' \
      -d "{\"institution_id\":\"$INST\",\"laboratory_id\":\"$LAB\"}" -o /dev/null -w '%{http_code}\n'
    ```

    O vínculo responde `201`.

## 3. O proponente indica o patrocinador e o Grupo Gestor

O proponente tem duas tarefas abertas desde a triagem. Ele indica o
patrocinador e a gestora para o Grupo Gestor. Cada tarefa se fecha sozinha,
e a gestora passa a ver o processo.

??? example "Como fazer pela API"
    ```bash
    designar() {  # token, usuário, cargo e, para laboratório, o laboratório
      LAB_JSON=${4:+,\"laboratory_id\":\"$4\"}
      curl -s -X POST $API/processes/$PID/participants -H "Authorization: Bearer $1" \
        -H 'Content-Type: application/json' \
        -d "{\"user_id\":\"$2\",\"role_key\":\"$3\"$LAB_JSON}" -o /dev/null -w '%{http_code}\n'
    }
    designar $PROP $PATROCINIO_ID sponsor
    designar $PROP $GESTORA_ID group_manager
    ```

## 4. A gestora monta a equipe

A gestora recebe as tarefas de indicar o restante da equipe. Ela indica a
responsável pela seleção de amostras, o técnico como laboratório
participante e como laboratório líder, apontando o laboratório dele, o
estatístico, a colaboradora e o avaliador ad hoc. O BraCVAM só homologa a
estrutura com os oito cargos preenchidos.

Se ela tentasse indicar alguém sem vínculo com o laboratório, a plataforma
recusaria.

??? example "Como fazer pela API"
    ```bash
    GM=$(login gestora senha-segura-123)
    curl -s "$API/tasks?process_id=$PID&status=READY" -H "Authorization: Bearer $GM" \
      | jq '.data[] | .activity_key'
    designar $GM $SELECAO_ID sample_selection_group
    designar $GM $TECNICO_ID participating_laboratory $LAB
    designar $GM $TECNICO_ID lead_laboratory $LAB
    designar $GM $ESTATISTICO_ID statistician
    designar $GM $COLABORADORA_ID collaborator
    designar $GM $AVALIADOR_ID adhoc_evaluator
    ```

    Cada designação responde `201`.

## 5. O estatístico envia o plano estatístico

Quando a gestora indica o estatístico, ele recebe a tarefa do plano
estatístico. Ele anexa o plano em PDF ou DOCX, escreve um resumo curto e
envia. Sem o anexo, a plataforma recusa o envio. O BraCVAM confere o plano
na homologação, junto com a equipe e as amostras.

??? example "Como fazer pela API"
    ```bash
    EST=$(login estatistico senha-segura-123)
    FORM=$API/processes/$PID/activities/statistical_plan/form
    printf '%%PDF-1.4\n%%%%EOF\n' > plano.pdf
    curl -s -X POST $FORM/fields/plan_file/attachment -H "Authorization: Bearer $EST" \
      -F file=@plano.pdf -o /dev/null -w '%{http_code}\n'
    curl -s -X POST $FORM -H "Authorization: Bearer $EST" -H 'Content-Type: application/json' \
      -d '{"values":{"summary":"Análise de concordância entre laboratórios."}}' | jq .status
    ```

    O anexo responde `200`, e o envio, `"COMPLETED"`.

## 6. A seleção de amostras cadastra as substâncias

Com a equipe formada, a responsável pela seleção recebe a tarefa de definir
as amostras. Ela cadastra cada substância com nome, número CAS, lote,
instruções de manuseio e a classificação de referência, o resultado já
conhecido da substância no ensaio. Informa também como conservar o frasco
(refrigerado) e quantos frascos guarda de reserva. Depois anexa a ficha de
segurança (SDS) em PDF.

A cada cadastro, a plataforma já gera um código cego para cada laboratório
participante.

??? example "Como fazer pela API"
    ```bash
    SEL=$(login selecao senha-segura-123)
    curl -s "$API/tasks?process_id=$PID&status=READY" -H "Authorization: Bearer $SEL" \
      | jq '.data[] | .activity_key'
    SUB=$(curl -s -X POST $API/processes/$PID/samples -H "Authorization: Bearer $SEL" \
      -H 'Content-Type: application/json' \
      -d '{"chemical_name":"Formaldeído","cas_number":"50-00-0","lot":"L-2026-04",
           "safe_handling_instructions":"Tóxico por inalação. Usar luvas e capela.",
           "reference_classification":"Severamente irritante / Categoria 1",
           "storage_temperature_regime":"refrigerated","reserve_vials_count":1,
           "ghs_hazard_pictograms":["GHS05","GHS06","GHS08"]}' \
      | jq -r .id)
    printf '%%PDF-1.4\n%%%%EOF\n' > sds.pdf
    curl -s -X PUT $API/processes/$PID/samples/$SUB/sds -H "Authorization: Bearer $SEL" \
      -F file=@sds.pdf -o /dev/null -w '%{http_code}\n'
    ```

    A tarefa é `sample_definition`.

## 7. A seleção conclui e imprime as etiquetas

Quando todas as substâncias têm ficha, a seleção conclui a etapa. A lista de
laboratórios fica congelada e as amostras só mudam se o BraCVAM reprovar
esse ponto na homologação. As etiquetas trazem só o código, o lote e um QR.
Nenhuma delas mostra o nome da substância.

??? example "Como fazer pela API"
    ```bash
    curl -s -X POST $API/processes/$PID/samples/complete -H "Authorization: Bearer $SEL" \
      -o /dev/null -w '%{http_code}\n'
    curl -s $API/processes/$PID/samples/labels -H "Authorization: Bearer $SEL" \
      | jq '.data[] | {code, lot, laboratory: .laboratory.name}'
    ```

## 8. O laboratório não vê o que há nos frascos

O técnico do laboratório participa do processo, mas não consegue ver as
substâncias. Para ele, a lista de substâncias não existe. Ele só vê os
frascos do próprio laboratório, pelo código, quando eles chegam. Antes, o
BraCVAM confere a equipe e as amostras:
[Quando o BraCVAM reprova a estrutura](homologacao-da-estrutura.md).

??? example "Como fazer pela API"
    ```bash
    TEC=$(login tecnico senha-segura-123)
    curl -s $API/processes/$PID/samples -H "Authorization: Bearer $TEC" -o /dev/null -w '%{http_code}\n'
    ```

    Resposta: `404`.

## O que você viu

- O proponente indica o patrocinador e o gestor; o gestor monta o resto da
  equipe.
- Laboratórios precisam estar cadastrados e ter pessoas vinculadas.
- O estatístico envia o plano pelo formulário da tarefa dele.
- Só o Grupo de Seleção conhece as substâncias.
- Cada laboratório recebe códigos próprios, sem nada que identifique o
  conteúdo.

Mais detalhes: [Amostras cegas](../explicacao/amostras-cegas.md) e
[Designar participantes](../guias/designar-participantes.md).
