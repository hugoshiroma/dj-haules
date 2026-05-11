#!/bin/bash
# Executa git pull antes de desligar/reiniciar, apenas se houver internet.
# Roda como serviço systemd no shutdown — veja djhaules-update.service.

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_TAG="djhaules-update"

if ! ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1; then
    logger -t "$LOG_TAG" "Sem internet — atualização ignorada."
    exit 0
fi

logger -t "$LOG_TAG" "Internet disponível — iniciando git pull em $REPO_DIR"
cd "$REPO_DIR" || exit 1

OUTPUT=$(git pull origin main --ff-only 2>&1)
STATUS=$?

logger -t "$LOG_TAG" "$OUTPUT"

if [ $STATUS -eq 0 ]; then
    logger -t "$LOG_TAG" "Atualização concluída com sucesso."
else
    logger -t "$LOG_TAG" "git pull falhou (código $STATUS). Continuando desligamento normalmente."
fi

exit 0
