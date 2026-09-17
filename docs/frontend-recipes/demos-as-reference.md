# Catálogo das Demos como Implementação de Referência

A pasta `demos/` na raiz do repositório contém telas HTML/JavaScript estáticas que operam diretamente contra a API real do backend. 

---

## 🎯 O Propósito das Demos

As demos **não são a interface final do usuário da PIVMA** (que é desenvolvida no repositório de frontend oficial). Elas desempenham dois papéis fundamentais:

1. **Implementações de Referência (Reference Implementations)**: Mostram exatamente quais endpoints chamar, em que ordem e com quais payloads para completar uma tarefa.
2. **Sandbox de Teste e Smoke Test**: Permitem que desenvolvedores e pesquisadores testem novos fluxos sem precisar abrir ferramentas de API como Postman ou Insomnia.

---

## 🧭 Catálogo de Demonstrações Disponíveis

Acesse o portal central em [http://localhost:8000/demos/](http://localhost:8000/demos/) após subir a API.

| # | Pasta | Módulo | Perfil Recomendado | O que demonstra |
| :- | :- | :- | :- | :- |
| 1 | `forms/` | Editor de Formulário | `admin` | Criação e versionamento de campos com IA. |
| 2 | `submission/` | Submissão de Método | `proponent_user` | Preenchimento, upload de anexos e envio formal. |
| 3 | `triage/` | Triagem Técnica | `triage_evaluator` | Comparação de dados da proposta com o parecer da IA. |
| 4 | `ai-pipeline/` | Observabilidade de IA | `admin` | Linha do tempo de execuções de IA e consumo de tokens. |
| 5 | `users/` | Usuários e RBAC | `admin` | Gestão de perfis e contas ativas. |
| 6 | `kanban/` | Painel de Pendências | `kanban_demo_padrao_a` / `admin` | Quadro com 4 colunas consumindo `GET /activities/kanban`. |
| 7 | `attachments/` | Anexos de Formulário | `proponent_user` | Upload, download e substituição de documentos POP. |
| 8 | `submission-update/` | Edição Parcial (PATCH) | `proponent_user` | Atualização de campos de rascunho sem perder o restante. |
| 9 | `process-retirement/` | Ciclo de Vida | `admin` / `proponent_user` | Exclusão suave (soft-delete) e arquivamento formal. |

---

## 💡 Como Usar o Código das Demos como Cookbook

Se você tiver dúvidas no frontend sobre como tratar um fluxo complexo:
1. Abra o arquivo `demos/<modulo>/index.html` ou `app.js`.
2. Busque pelas funções `fetch(...)`.
3. Veja o tratamento de respostas 200, 401, 403 e 422 pronto para copiar e adaptar em React/Vue.
