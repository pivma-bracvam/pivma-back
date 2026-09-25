"""Seed de setup inicial do banco (o que deve existir após o deploy).

Delega para `pivma.bootstrap_system`, o mesmo provisionamento idempotente
que o `entrypoint.sh` executa a cada deploy: perfis, permissões, templates
canônicos de processo e o administrador inicial (`INITIAL_ADMIN_*`, opcional).
Não cria usuários de exemplo nem processos.
"""

from pivma.bootstrap_system import main

if __name__ == '__main__':
    main()
