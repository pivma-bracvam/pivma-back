# Diretrizes para Agentes de Desenvolvimento (AGENTS.md)

Este documento estabelece padrões normativos, requisitos de entrega e diretrizes de desenvolvimento para agentes e desenvolvedores no projeto.

---

## 1. Padrão para Novos Módulos e Demonstrações

> **Nota de Conceito:** **Módulo não é o mesmo que Spec**. Um módulo representa uma fronteira funcional/arquitetural de domínio no sistema, enquanto uma spec descreve um incremento ou especificação de entrega.

Todo novo módulo desenvolvido no projeto deve conter **uma ou mais páginas interativas de demonstração** que evidenciem suas capacidades e funcionamento prático.

---

## 2. Estrutura e Organização das Demos

Para garantir consistência e fácil avaliação:

- **Diretório de Demos (`demos/`):** Todas as páginas e interfaces de demonstração devem residir na pasta `demos/` na raiz do projeto.
- **Catálogo Central (`demos/index.html` ou índice correspondente):** A raiz de `demos/` deve conter um `index` listando todas as demonstrações existentes de maneira estruturada, permitindo que o usuário navegue e avalie cada funcionalidade sob demanda.
- **Seeds de Carga (`scripts/seeds/`):** O agente responsável por demonstrar uma funcionalidade deve criar/atualizar um script de seed correspondente em `scripts/seeds/` com a massa de dados estritamente necessária para viabilizar a execução daquela demonstração.

---

## 3. Critérios de Aceite e Conclusão de Specs

- **Demonstração como Critério de Conclusão:** A entrega de uma spec só é considerada concluída quando a respectiva demonstração (interface e script de seed) estiver funcional e validando o comportamento desenvolvido.
- **Validação com a API Real:** As páginas de demonstração devem obrigatoriamente interagir com a API real do backend, comprovando que os fluxos implementados operam corretamente de ponta a ponta.

---

## 4. Regras Arquiteturais e Desacoplamento

- **Proibição de Endpoints Facilitadores:** Nenhum endpoint deve ser adicionado à API exclusivamente para viabilizar, mascarar ou simplificar o desenvolvimento das páginas de demonstração. Os contratos de API devem atender unicamente ao domínio da aplicação.
- **Total Desacoplamento:** O código localizado em `demos/` deve ser completamente desacoplado do núcleo da aplicação (`src/`). As demonstrações devem ser descartáveis a qualquer tempo sem provocar qualquer degradação ou perda funcional para o backend.