#!/bin/bash
# =============================================================================
# DJ Haules - Wi-Fi Monitor & Hotspot Fallback
# =============================================================================
#
# Este script roda como um serviço systemd e monitora a conectividade Wi-Fi
# do Raspberry Pi. Se o Pi não conseguir se conectar à internet (ex: senha
# da rede foi alterada), ele ativa automaticamente um hotspot de configuração.
#
# Hotspot: "DJHaules-Config"   Senha: "djhaules"
# Acesse: http://192.168.4.1:8080/wifi para configurar a nova rede.
# =============================================================================

HOTSPOT_CON="DJHaules-Hotspot"
HOTSPOT_SSID="DJHaules-Config"
HOTSPOT_PASS="djhaules"
HOTSPOT_IP="192.168.4.1/24"

# Tempo de espera no boot para o NetworkManager tentar conectar normalmente
BOOT_WAIT=60

# Intervalo entre verificações após o boot
CHECK_INTERVAL=30

log() {
    echo "[$(date '+%H:%M:%S')] [wifi-monitor] $1"
}

has_internet() {
    # Verifica conectividade real com a internet via NetworkManager
    nmcli -t -f CONNECTIVITY general status 2>/dev/null | grep -q "full"
}

hotspot_active() {
    nmcli -t -f NAME,STATE con show --active 2>/dev/null \
        | grep -q "^${HOTSPOT_CON}:activated"
}

ensure_hotspot_profile_exists() {
    # Cria o perfil do hotspot se ainda não existir
    if ! nmcli con show "$HOTSPOT_CON" &>/dev/null; then
        log "Criando perfil de hotspot '${HOTSPOT_SSID}'..."
        nmcli con add \
            type wifi \
            ifname wlan0 \
            con-name "$HOTSPOT_CON" \
            ssid "$HOTSPOT_SSID" \
            mode ap \
            ipv4.method shared \
            ipv4.addresses "$HOTSPOT_IP" \
            wifi-sec.key-mgmt wpa-psk \
            wifi-sec.psk "$HOTSPOT_PASS" \
            connection.autoconnect no \
            &>/dev/null
        log "Perfil de hotspot criado."
    fi
}

activate_hotspot() {
    if hotspot_active; then
        return 0
    fi
    log "Sem internet. Ativando hotspot '${HOTSPOT_SSID}'..."
    ensure_hotspot_profile_exists
    nmcli con up "$HOTSPOT_CON" &>/dev/null
    if hotspot_active; then
        log "Hotspot ativo em ${HOTSPOT_IP%/*}."
        log "Conecte-se ao Wi-Fi '${HOTSPOT_SSID}' (senha: ${HOTSPOT_PASS}) e acesse:"
        log "  http://${HOTSPOT_IP%/*}:8080/wifi"
    else
        log "ERRO: Falha ao ativar hotspot."
    fi
}

deactivate_hotspot() {
    if ! hotspot_active; then
        return 0
    fi
    log "Internet restaurada! Desativando hotspot..."
    nmcli con down "$HOTSPOT_CON" &>/dev/null
    log "Hotspot desativado. Sistema operando normalmente."
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

log "Serviço iniciado. Aguardando ${BOOT_WAIT}s para conexão Wi-Fi inicial..."
sleep "$BOOT_WAIT"

while true; do
    if has_internet; then
        deactivate_hotspot
    else
        activate_hotspot
    fi
    sleep "$CHECK_INTERVAL"
done
