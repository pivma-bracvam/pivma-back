# Contrato de Estrutura da Documentação: MkDocs

A documentação estática é configurada em `mkdocs.yml` na raiz do repositório e servida a partir de arquivos Markdown na pasta `docs/`.

## Estrutura de Navegação (`nav`)

```yaml
nav:
  - Início: index.md
  - Onboarding & Configuração:
      - Ambiente Local & Docker: onboarding/local-setup.md
      - Arquitetura de Seeds & Reset: onboarding/seed-architecture.md
  - Domínio & Regras de Negócio:
      - Ciclo de Vida do Processo: domain/process-lifecycle.md
      - Matriz de Governança RBAC: domain/rbac.md
  - Funcionalidades & Endpoints:
      - Painel de Pendências (Kanban): features/kanban.md
      - Triagem Técnica & IA Assistiva: features/triage-and-ai.md
      - Formulários Dinâmicos & Versionamento: features/dynamic-forms.md
  - Guia de Integração (Frontend):
      - Autenticação e Sessão: frontend-recipes/auth-session.md
      - Demos como Implementação de Referência: frontend-recipes/demos-as-reference.md
```

## Padrões Exigidos nas Páginas
1. **Diagramas Mermaid**: Diagramas de fluxo e sequência em blocos ` ```mermaid ` para ilustrar máquinas de estado e interações entre frontend e backend.
2. **Admonitions**: Uso de notas (`!!! note`), avisos (`!!! warning`) e dicas (`!!! tip`).
3. **Links Ativos**: Nenhuma rota ou link quebrado (`mkdocs build --strict` obrigatório).
