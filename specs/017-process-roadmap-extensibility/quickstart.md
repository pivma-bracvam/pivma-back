# Quickstart: Validar o Roteiro de Duas Fases

**Feature**: 017-process-roadmap-extensibility

## Pré-requisitos

- API rodando localmente (`poe dev` ou equivalente) com a migração desta feature
  aplicada (`alembic upgrade head`).
- Seed desta demo executado: `python -m scripts.seeds.seed_roadmap_demo` (cria um usuário
  proponente, um triador BraCVAM e reaplica o bootstrap de templates para publicar a
  versão 2 de `validated_method_dossier`).
- Navegador para abrir `demos/roadmap/index.html` (servido pelo mesmo mecanismo estático
  já usado pelas demais páginas em `demos/`).

## Passos

1. Abrir `demos/roadmap/index.html`.
2. Clicar em "Consultar roteiro declarado" → confirma visualmente as duas fases e os
   três tipos de atividade (`form`, `form`, `placeholder`) vindos de
   `GET /processes/templates/validated_method_dossier`.
3. Clicar em "Iniciar submissão de exemplo" → `POST /processes`; a página mostra a Fase 2
   como bloqueada, com o motivo de bloqueio.
4. Preencher e enviar o formulário de submissão (usando o usuário proponente do seed).
5. Autenticar como o usuário triador do seed e emitir decisão de triagem `APPROVED`.
6. Voltar à página do roteiro: a Fase 2 (`planning_preview`) aparece `READY`, com seu
   `activity_type = "placeholder"` visível — prova de que o frontend pode renderizar uma
   atividade além do formulário sem nenhuma mudança de contrato adicional.

## Verificação de não regressão

- Uma instância criada **antes** da publicação da versão 2 (ou criada explicitamente a
  partir da versão 1, se ainda selecionável em ambiente de teste) continua exibindo
  apenas a Fase 1 ao repetir o passo 2/6 — confirma SC-004 da spec (imutabilidade de
  versão).
- A suíte automatizada completa (`poe test`) permanece verde, cobrindo em particular
  `tests/api/routers/test_process_router.py`, `test_form_submission.py` e
  `test_triage_review.py` (Specs 004/009/011), que exercitam o template
  `validated_method_dossier` sem depender da Fase 2.

## Critério de conclusão

Este quickstart só é considerado cumprido quando os 6 passos acima forem executados
manualmente contra a API real (não mocada) e a verificação de não regressão passar —
consistente com a Constituição do projeto (demonstração como critério de conclusão).
