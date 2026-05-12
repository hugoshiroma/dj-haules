#!/bin/bash
# Redireciona porta 80 → 8080 para que http://dj-haules.local funcione sem precisar
# digitar a porta. Roda como ExecStartPre no djhaules.service a cada inicialização.

# Localiza o iptables (caminho varia entre distros e versões do Pi OS)
IPT=$(command -v iptables || command -v iptables-legacy || echo "")
if [ -z "$IPT" ]; then
    echo "setup_iptables: iptables não encontrado, pulando redirect de porta." >&2
    exit 0
fi

add_rule() {
    local chain="$1"; shift
    "$IPT" -t nat -C "$chain" "$@" 2>/dev/null || "$IPT" -t nat -A "$chain" "$@"
}

# Requisições vindas da rede (outros dispositivos acessando o Pi)
add_rule PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080

# Requisições locais (o próprio Pi acessando localhost:80)
add_rule OUTPUT -p tcp -d 127.0.0.1 --dport 80 -j REDIRECT --to-port 8080
