#!/bin/bash
# =============================================================================
# DJ Haules — Setup / Reconcile
# =============================================================================
#
# Script idempotente que garante que o Pi está com toda a configuração
# esperada: service files, captive portal DNS, grupos, permissões, venv.
#
# Roda em dois cenários:
#   1. Manualmente, uma vez por Pi novo:   sudo ./scripts/setup.sh
#   2. Automaticamente em todo boot via    djhaules-reconcile.service
#
# Detecta o usuário-alvo (dono do djhaules) e substitui o placeholder
# "seu_usuario" nos service files. Só copia arquivos que mudaram, só
# reinicia serviços que foram alterados.
# =============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# -----------------------------------------------------------------------------
# Detecção do usuário-alvo
# -----------------------------------------------------------------------------
# Precedência:
#   1. $TARGET_USER (passado pelo systemd ou explicitamente)
#   2. $SUDO_USER (quando rodado via `sudo ./setup.sh`)
#   3. dono do diretório do repo (fallback robusto)
if [ -n "${TARGET_USER:-}" ]; then
    USER_NAME="$TARGET_USER"
elif [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != "root" ]; then
    USER_NAME="$SUDO_USER"
else
    USER_NAME="$(stat -c '%U' "$REPO_DIR")"
fi

if [ "$USER_NAME" = "root" ]; then
    echo "[setup] ERRO: não foi possível detectar usuário não-root."
    echo "[setup] Rode como: sudo ./scripts/setup.sh"
    exit 1
fi

HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
EXPECTED_REPO="$HOME_DIR/dj-haules"

log() {
    echo "[setup] $*"
}

log "Usuário-alvo: $USER_NAME (home: $HOME_DIR)"
log "Repositório:  $REPO_DIR"

if [ "$REPO_DIR" != "$EXPECTED_REPO" ]; then
    log "AVISO: repo está em $REPO_DIR, mas o esperado pelos service files é $EXPECTED_REPO."
    log "Os paths hardcoded nos service files podem não funcionar."
fi

# Variáveis de estado
SYSTEMD_RELOAD_NEEDED=0
CHANGED_UNITS=()
USER_SYSTEMD_RELOAD_NEEDED=0
CHANGED_USER_UNITS=()

# UID do user-alvo — usado pra falar com o systemd de usuário
USER_UID="$(id -u "$USER_NAME")"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

# Renderiza um service file: substitui "seu_usuario" pelo usuário-alvo
render_unit() {
    local src="$1"
    local out="$2"
    sed "s/seu_usuario/$USER_NAME/g" "$src" > "$out"
}

# Instala uma systemd unit se mudou. Marca pra reload + restart.
install_unit() {
    local src="$1"
    local dest="$2"
    local tmp
    tmp="$(mktemp)"
    render_unit "$src" "$tmp"

    if [ -f "$dest" ] && cmp -s "$tmp" "$dest"; then
        rm -f "$tmp"
        return 0
    fi

    log "Instalando/atualizando $(basename "$dest")"
    install -m 0644 "$tmp" "$dest"
    rm -f "$tmp"
    SYSTEMD_RELOAD_NEEDED=1
    CHANGED_UNITS+=("$(basename "$dest")")
}

# Copia um arquivo se mudou
install_file() {
    local src="$1"
    local dest="$2"
    local mode="${3:-0644}"
    if [ -f "$dest" ] && cmp -s "$src" "$dest"; then
        return 0
    fi
    log "Instalando $dest"
    mkdir -p "$(dirname "$dest")"
    install -m "$mode" "$src" "$dest"
}

# Roda systemctl --user como o USER_NAME — precisa de XDG_RUNTIME_DIR
# e DBUS_SESSION_BUS_ADDRESS apontados pra sessão do user (existe porque
# habilitamos linger acima)
user_systemctl() {
    sudo -u "$USER_NAME" \
        XDG_RUNTIME_DIR="/run/user/$USER_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$USER_UID/bus" \
        systemctl --user "$@"
}

# Instala uma unit de USUÁRIO (~/.config/systemd/user/) se mudou.
install_user_unit() {
    local src="$1"
    local dest="$2"
    if [ -f "$dest" ] && cmp -s "$src" "$dest"; then
        return 0
    fi
    log "Instalando/atualizando $(basename "$dest") (user service)"
    sudo -u "$USER_NAME" mkdir -p "$(dirname "$dest")"
    install -m 0644 -o "$USER_NAME" -g "$USER_NAME" "$src" "$dest"
    USER_SYSTEMD_RELOAD_NEEDED=1
    CHANGED_USER_UNITS+=("$(basename "$dest")")
}

# -----------------------------------------------------------------------------
# 1. Permissões executáveis nos scripts
# -----------------------------------------------------------------------------
log "Garantindo permissão de execução em scripts/*.sh"
chmod +x "$REPO_DIR/scripts/"*.sh

# -----------------------------------------------------------------------------
# 2. Bluetooth: desbloqueio + grupo do usuário
# -----------------------------------------------------------------------------
if rfkill list bluetooth 2>/dev/null | grep -q "Soft blocked: yes"; then
    log "Desbloqueando Bluetooth (rfkill)"
    rfkill unblock bluetooth
fi

if ! id -nG "$USER_NAME" 2>/dev/null | tr ' ' '\n' | grep -qx bluetooth; then
    log "Adicionando $USER_NAME ao grupo 'bluetooth'"
    usermod -aG bluetooth "$USER_NAME"
fi

# -----------------------------------------------------------------------------
# 3. Linger pro raspotify (serviço de usuário) iniciar no boot sem login
# -----------------------------------------------------------------------------
if ! loginctl show-user "$USER_NAME" 2>/dev/null | grep -q "^Linger=yes"; then
    log "Habilitando linger para $USER_NAME"
    loginctl enable-linger "$USER_NAME"
fi

# -----------------------------------------------------------------------------
# 4. Captive portal DNS (NetworkManager dnsmasq)
# -----------------------------------------------------------------------------
install_file \
    "$REPO_DIR/scripts/captive-portal-dns.conf" \
    "/etc/NetworkManager/dnsmasq-shared.d/djhaules-captive.conf"

# -----------------------------------------------------------------------------
# 5. Systemd units
# -----------------------------------------------------------------------------
install_unit "$REPO_DIR/scripts/djhaules.service"           "/etc/systemd/system/djhaules.service"
install_unit "$REPO_DIR/scripts/djhaules-wifi.service"      "/etc/systemd/system/djhaules-wifi.service"
install_unit "$REPO_DIR/scripts/djhaules-update.service"    "/etc/systemd/system/djhaules-update.service"
install_unit "$REPO_DIR/scripts/djhaules-reconcile.service" "/etc/systemd/system/djhaules-reconcile.service"

# -----------------------------------------------------------------------------
# 5b. Raspotify (USER service — PipeWire vive na sessão do user, não no root)
# -----------------------------------------------------------------------------
USER_SYSTEMD_DIR="$HOME_DIR/.config/systemd/user"
install_user_unit "$REPO_DIR/scripts/raspotify.service" "$USER_SYSTEMD_DIR/raspotify.service"

# -----------------------------------------------------------------------------
# 6. Venv Python + dependências (reinstala só se requirements.txt mudou)
# -----------------------------------------------------------------------------
VENV="$REPO_DIR/.venv"
REQ_FILE="$REPO_DIR/requirements.txt"
REQ_HASH_FILE="$VENV/.requirements.sha256"

if [ ! -x "$VENV/bin/python" ]; then
    log "Criando virtualenv em $VENV"
    sudo -u "$USER_NAME" python3 -m venv "$VENV"
fi

CURRENT_HASH="$(sha256sum "$REQ_FILE" | cut -d' ' -f1)"
INSTALLED_HASH=""
[ -f "$REQ_HASH_FILE" ] && INSTALLED_HASH="$(cat "$REQ_HASH_FILE")"

if [ "$CURRENT_HASH" != "$INSTALLED_HASH" ]; then
    log "requirements.txt mudou — instalando dependências"
    sudo -u "$USER_NAME" "$VENV/bin/pip" install -q -r "$REQ_FILE"
    echo "$CURRENT_HASH" | sudo -u "$USER_NAME" tee "$REQ_HASH_FILE" > /dev/null
    # Se o djhaules.service não estiver na lista de mudados, força restart
    # — deps novas só entram em vigor com restart do processo
    if [[ ! " ${CHANGED_UNITS[*]:-} " =~ " djhaules.service " ]]; then
        CHANGED_UNITS+=("djhaules.service")
    fi
fi

# -----------------------------------------------------------------------------
# 6b. Código Python (main.py, shared.py, webapp/) — restart se mudou
# -----------------------------------------------------------------------------
# Templates HTML e static/* são lidos a cada request pelo Flask, então mudanças
# entram em vigor sem restart. Já o código Python é carregado em memória no
# import — precisa restart pro djhaules pegar a versão nova.
CODE_HASH_FILE="$VENV/.code.sha256"
CODE_CURRENT_HASH="$(
    find \
        "$REPO_DIR/main.py" \
        "$REPO_DIR/shared.py" \
        "$REPO_DIR/webapp" \
        -name '*.py' -type f -print0 2>/dev/null \
    | sort -z \
    | xargs -0 sha256sum \
    | sha256sum \
    | cut -d' ' -f1
)"
CODE_INSTALLED_HASH=""
[ -f "$CODE_HASH_FILE" ] && CODE_INSTALLED_HASH="$(cat "$CODE_HASH_FILE")"

if [ "$CODE_CURRENT_HASH" != "$CODE_INSTALLED_HASH" ]; then
    log "Código Python mudou — djhaules.service será reiniciado"
    echo "$CODE_CURRENT_HASH" | sudo -u "$USER_NAME" tee "$CODE_HASH_FILE" > /dev/null
    if [[ ! " ${CHANGED_UNITS[*]:-} " =~ " djhaules.service " ]]; then
        CHANGED_UNITS+=("djhaules.service")
    fi
fi

# -----------------------------------------------------------------------------
# 7. systemctl daemon-reload + enable + restart do que mudou
# -----------------------------------------------------------------------------
if [ "$SYSTEMD_RELOAD_NEEDED" -eq 1 ]; then
    log "systemctl daemon-reload"
    systemctl daemon-reload
fi

for unit in djhaules-update.service djhaules-reconcile.service djhaules-wifi.service djhaules.service; do
    if ! systemctl is-enabled --quiet "$unit"; then
        log "Habilitando $unit"
        systemctl enable "$unit" > /dev/null
    fi
done

# Restart das units alteradas — pula a si mesmo e units oneshot
SELF_UNIT="djhaules-reconcile.service"
for unit in "${CHANGED_UNITS[@]:-}"; do
    [ -z "$unit" ] && continue
    if [ "$unit" = "$SELF_UNIT" ]; then
        log "Pulando restart de $unit (estamos rodando dentro dele)"
        continue
    fi
    unit_type="$(systemctl show "$unit" --property=Type --value 2>/dev/null || echo simple)"
    if [ "$unit_type" = "oneshot" ]; then
        log "Pulando restart de $unit (oneshot)"
        continue
    fi
    # Só reinicia se já estava ativo — se ainda não iniciou (caso do boot),
    # systemd vai subir com a unit nova naturalmente
    if systemctl is-active --quiet "$unit"; then
        log "Reiniciando $unit (config mudou)"
        systemctl restart "$unit" || log "AVISO: restart de $unit falhou"
    fi
done

# -----------------------------------------------------------------------------
# 8. systemctl --user daemon-reload + enable + restart das user units alteradas
# -----------------------------------------------------------------------------
if [ "$USER_SYSTEMD_RELOAD_NEEDED" -eq 1 ]; then
    log "user systemctl daemon-reload ($USER_NAME)"
    user_systemctl daemon-reload || log "AVISO: user daemon-reload falhou — sessão sem linger?"
fi

for unit in "${CHANGED_USER_UNITS[@]:-}"; do
    [ -z "$unit" ] && continue
    if ! user_systemctl is-enabled --quiet "$unit" 2>/dev/null; then
        log "Habilitando $unit (user)"
        user_systemctl enable "$unit" > /dev/null 2>&1 || log "AVISO: enable de $unit (user) falhou"
    fi
    if user_systemctl is-active --quiet "$unit" 2>/dev/null; then
        log "Reiniciando $unit (user, config mudou)"
        user_systemctl restart "$unit" || log "AVISO: restart de $unit (user) falhou"
    fi
done

log "Reconcile concluído."
