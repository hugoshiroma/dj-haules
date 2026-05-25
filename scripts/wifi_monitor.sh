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

# Tempo de espera no boot para o NetworkManager tentar conectar normalmente.
# Mantido alto (10 min) para tolerar cenários de blackout no bar, em que o
# Pi religa junto com roteador/repetidor e o ecossistema Wi-Fi leva minutos
# pra estabilizar. Durante essa janela o NM tenta autoconnect sozinho.
BOOT_WAIT=600

# Intervalo entre verificações após o boot
CHECK_INTERVAL=30

# Tempo em modo hotspot antes de tentar voltar para o Wi-Fi cliente.
# Evita a armadilha de ficar preso no AP quando a rede do bar só voltou
# alguns minutos depois do hotspot ter sido ativado.
HOTSPOT_ESCAPE_INTERVAL=300

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

enable_captive_portal() {
    # Redireciona porta 80 para o Flask (8080) — ativa o captive portal
    iptables -t nat -C PREROUTING -i wlan0 -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null \
        || iptables -t nat -A PREROUTING -i wlan0 -p tcp --dport 80 -j REDIRECT --to-port 8080
}

disable_captive_portal() {
    iptables -t nat -D PREROUTING -i wlan0 -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null || true
}

activate_hotspot() {
    ensure_hotspot_profile_exists
    if hotspot_active; then
        # Garante a regra de captive portal mesmo se o hotspot já estava ativo
        enable_captive_portal
        return 0
    fi
    log "Sem internet. Ativando hotspot '${HOTSPOT_SSID}'..."
    nmcli con up "$HOTSPOT_CON" &>/dev/null
    if hotspot_active; then
        enable_captive_portal
        log "Hotspot ativo em ${HOTSPOT_IP%/*}. Captive portal habilitado."
        log "Conecte-se ao Wi-Fi '${HOTSPOT_SSID}' (senha: ${HOTSPOT_PASS})"
        log "O celular vai abrir a página de configuração automaticamente."
    else
        log "ERRO: Falha ao ativar hotspot."
    fi
}

deactivate_hotspot() {
    if ! hotspot_active; then
        return 0
    fi
    log "Desativando hotspot..."
    disable_captive_portal
    nmcli con down "$HOTSPOT_CON" &>/dev/null
}

# Lista perfis Wi-Fi cliente salvos (exclui o próprio hotspot)
list_client_profiles() {
    nmcli -t -f NAME,TYPE con show 2>/dev/null \
        | awk -F: '$2 == "802-11-wireless" {print $1}' \
        | grep -v "^${HOTSPOT_CON}$" || true
}

# Tenta subir cada perfil Wi-Fi cliente salvo até um conectar com internet.
# Retorna 0 se conectou com internet, 1 caso contrário.
try_reconnect_client() {
    local profiles
    profiles=$(list_client_profiles)

    if [ -z "$profiles" ]; then
        log "Nenhum perfil Wi-Fi cliente salvo."
        return 1
    fi

    while IFS= read -r profile; do
        [ -z "$profile" ] && continue
        log "Tentando conectar em '${profile}'..."
        if nmcli con up "$profile" &>/dev/null; then
            # NM precisa de alguns segundos pro connectivity check
            sleep 5
            if has_internet; then
                log "Conectado em '${profile}' com internet."
                return 0
            fi
            log "Conexão com '${profile}' subiu mas sem internet."
        else
            log "Falha ao conectar em '${profile}'."
        fi
    done <<< "$profiles"

    return 1
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

log "Serviço iniciado. Aguardando ${BOOT_WAIT}s para conexão Wi-Fi inicial..."
sleep "$BOOT_WAIT"

hotspot_uptime=0

while true; do
    if has_internet; then
        if hotspot_active; then
            log "Internet restaurada!"
            deactivate_hotspot
        fi
        hotspot_uptime=0
    elif hotspot_active; then
        hotspot_uptime=$((hotspot_uptime + CHECK_INTERVAL))
        if [ "$hotspot_uptime" -ge "$HOTSPOT_ESCAPE_INTERVAL" ]; then
            log "Em hotspot há ${hotspot_uptime}s. Tentando reconectar no Wi-Fi salvo..."
            deactivate_hotspot
            if try_reconnect_client; then
                log "Saiu do hotspot."
                hotspot_uptime=0
            else
                log "Reconexão falhou. Voltando pro hotspot."
                activate_hotspot
                hotspot_uptime=0
            fi
        fi
    else
        # Sem internet e sem hotspot: tenta cliente antes de subir o AP
        if ! try_reconnect_client; then
            activate_hotspot
            hotspot_uptime=0
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
