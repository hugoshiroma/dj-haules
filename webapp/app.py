import json
import re
import time
import subprocess
import os
from flask import Flask, render_template, redirect, url_for, request, jsonify
from shared import bt_lock

WIFI_CON_NAME = "djhaules-wifi"

app = Flask(__name__)

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
STATE_FILE = os.path.join(BASE_DIR, 'config', 'state.txt')
SPEAKERS_FILE = os.path.join(BASE_DIR, 'config', 'speakers.json')


# --- Helpers de estado ---

def get_state():
    if not os.path.exists(STATE_FILE):
        set_state('ENABLED')
    with open(STATE_FILE, 'r') as f:
        return f.read().strip()

def set_state(state):
    with open(STATE_FILE, 'w') as f:
        f.write(state)


# --- Helpers de speakers ---

def load_speakers():
    if not os.path.exists(SPEAKERS_FILE):
        return []
    with open(SPEAKERS_FILE, 'r') as f:
        return json.load(f)

def save_speakers(speakers):
    with open(SPEAKERS_FILE, 'w') as f:
        json.dump(speakers, f, indent=2, ensure_ascii=False)


# --- Rotas principais ---

@app.route('/')
def index():
    current_state = get_state()
    status_text = 'ATIVADO' if current_state == 'ENABLED' else 'DESATIVADO'
    action_text = 'Desativar DJ Haules' if current_state == 'ENABLED' else 'Ativar DJ Haules'
    return render_template('index.html', status=status_text, action_text=action_text)

@app.route('/toggle')
def toggle():
    current_state = get_state()
    set_state('DISABLED' if current_state == 'ENABLED' else 'ENABLED')
    return redirect(url_for('index'))


# --- Rotas de gerenciamento de caixas ---

@app.route('/speakers')
def speakers_page():
    speakers = load_speakers()
    return render_template('speakers.html', speakers=speakers)

@app.route('/speakers/remove', methods=['POST'])
def remove_speaker():
    mac = request.form.get('mac', '').upper()
    speakers = [s for s in load_speakers() if s['mac'].upper() != mac]
    save_speakers(speakers)
    return redirect(url_for('speakers_page'))


# --- API para scan e pair (chamadas AJAX) ---

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Escaneia dispositivos Bluetooth próximos por 15 segundos."""
    with bt_lock:
        try:
            # Modo interativo via stdin — mantém o scan ativo igual ao terminal manual
            scan_proc = subprocess.Popen(
                ['bluetoothctl'],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True
            )
            scan_proc.stdin.write('scan on\n')
            scan_proc.stdin.flush()
            time.sleep(15)
            scan_proc.stdin.write('scan off\n')
            scan_proc.stdin.write('exit\n')
            scan_proc.stdin.flush()
            scan_proc.wait(timeout=5)
        except Exception:
            pass

        try:
            output = subprocess.check_output(
                ['bluetoothctl', 'devices'], text=True, timeout=5
            )
            mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$')
            devices = []
            for line in output.strip().split('\n'):
                match = re.match(r'Device\s+([0-9A-Fa-f:]{17})\s+(.+)', line)
                if match:
                    mac = match.group(1).upper()
                    name = match.group(2).strip()
                    # Ignora entradas sem nome resolvido (nome é apenas o MAC)
                    if mac_pattern.match(name):
                        continue
                    devices.append({'mac': mac, 'name': name})
            return jsonify({'ok': True, 'devices': devices})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e), 'devices': []})


@app.route('/api/pair', methods=['POST'])
def api_pair():
    """Faz pair + trust + connect num dispositivo e salva como caixa principal."""
    data = request.get_json()
    mac = (data.get('mac') or '').upper()
    name = data.get('name') or mac

    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac):
        return jsonify({'ok': False, 'error': 'MAC address inválido'})

    with bt_lock:
        for cmd in ['pair', 'trust', 'connect']:
            try:
                subprocess.run(
                    ['bluetoothctl', cmd, mac],
                    capture_output=True, text=True, timeout=20
                )
                time.sleep(2)
            except subprocess.TimeoutExpired:
                return jsonify({'ok': False, 'error': f'Timeout ao executar "{cmd}"'})

    # Salva como prioridade 1 (principal), incrementa as demais
    speakers = [s for s in load_speakers() if s['mac'].upper() != mac]
    for s in speakers:
        s['priority'] = s.get('priority', 1) + 1
    speakers.insert(0, {'name': name, 'mac': mac, 'priority': 1})
    save_speakers(speakers)

    return jsonify({'ok': True})


# --- Rotas de configuração Wi-Fi ---

@app.route('/wifi')
def wifi_page():
    return render_template('wifi.html')


@app.route('/api/wifi/status')
def api_wifi_status():
    """Retorna o estado atual da conectividade Wi-Fi."""
    try:
        active = subprocess.check_output(
            ['nmcli', '-t', '-f', 'NAME,TYPE,STATE', 'con', 'show', '--active'],
            text=True, timeout=5
        )
        ssid = None
        hotspot = False
        for line in active.strip().split('\n'):
            parts = line.split(':')
            if len(parts) >= 3 and parts[1] == '802-11-wireless':
                if parts[0] == 'DJHaules-Hotspot':
                    hotspot = True
                else:
                    ssid = parts[0]

        connectivity = subprocess.check_output(
            ['nmcli', '-t', '-f', 'CONNECTIVITY', 'general', 'status'],
            text=True, timeout=5
        )
        internet = 'full' in connectivity

        return jsonify({'ok': True, 'ssid': ssid, 'hotspot': hotspot, 'internet': internet})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'ssid': None, 'hotspot': False, 'internet': False})


@app.route('/api/wifi/save', methods=['POST'])
def api_wifi_save():
    """Salva novas credenciais Wi-Fi e tenta reconectar."""
    data = request.get_json() or {}
    ssid = (data.get('ssid') or '').strip()
    password = (data.get('password') or '').strip()

    if not ssid or len(ssid) > 32:
        return jsonify({'ok': False, 'error': 'SSID inválido (máximo 32 caracteres)'})
    if password and (len(password) < 8 or len(password) > 63):
        return jsonify({'ok': False, 'error': 'Senha deve ter entre 8 e 63 caracteres'})

    try:
        # Remove perfil anterior para evitar conflito
        subprocess.run(
            ['nmcli', 'con', 'delete', WIFI_CON_NAME],
            capture_output=True, timeout=10
        )

        # Cria novo perfil
        cmd = [
            'nmcli', 'con', 'add',
            'type', 'wifi',
            'ifname', 'wlan0',
            'con-name', WIFI_CON_NAME,
            'ssid', ssid,
            'connection.autoconnect', 'yes',
        ]
        if password:
            cmd += ['wifi-sec.key-mgmt', 'wpa-psk', 'wifi-sec.psk', password]

        subprocess.run(cmd, capture_output=True, timeout=10, check=True)

        # Tenta conectar em background (o wifi_monitor vai confirmar em até 30s)
        subprocess.Popen(['nmcli', 'con', 'up', WIFI_CON_NAME])

        return jsonify({'ok': True})
    except subprocess.CalledProcessError:
        return jsonify({'ok': False, 'error': 'Erro ao salvar configuração de rede. Verifique o SSID e a senha.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
