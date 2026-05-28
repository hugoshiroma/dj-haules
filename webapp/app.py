import json
import random
import re
import time
import threading
import subprocess
import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, jsonify
from shared import bt_lock

WIFI_CON_NAME = "djhaules-wifi"

app = Flask(__name__)

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
STATE_FILE = os.path.join(BASE_DIR, 'config', 'state.txt')
SPEAKERS_FILE = os.path.join(BASE_DIR, 'config', 'speakers.json')
PLAYLISTS_FILE = os.path.join(BASE_DIR, 'config', 'playlists.json')
ACTIVE_PLAYLIST_FILE = os.path.join(BASE_DIR, 'config', 'active_playlist.txt')
PLAY_EVENT_FILE       = os.path.join(BASE_DIR, 'config', 'play_event.txt')
BT_EVENT_FILE         = os.path.join(BASE_DIR, 'config', 'bt_event.txt')
BT_DISCONNECT_FILE    = os.path.join(BASE_DIR, 'config', 'bt_disconnect_event.txt')


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


# --- Captive portal detection ---
# iOS, Android, Windows e Firefox tentam essas URLs ao conectar numa rede nova.
# Respondendo com redirect para /wifi, o OS mostra o popup de "acessar rede".

@app.route('/hotspot-detect.html')
@app.route('/library/test/success.html')
@app.route('/success.html')
@app.route('/generate_204')
@app.route('/connecttest.txt')
@app.route('/ncsi.txt')
@app.route('/canonical.html')
@app.route('/redirect')
def captive_portal_redirect():
    from flask import redirect as flask_redirect
    return flask_redirect('/wifi', 302)


# --- Rotas principais ---

def compute_playback_status():
    """Estado consolidado do playback — usado pelo badge real."""
    state = get_state()
    if state != 'ENABLED':
        return {'tag': 'paused', 'emoji': '⏸', 'label': 'Pausado'}

    speakers = load_speakers()
    if not speakers:
        return {'tag': 'no-speaker', 'emoji': '🔇', 'label': 'Sem caixinha'}

    any_connected = any(is_bt_connected(s['mac']) for s in speakers)
    if not any_connected:
        return {'tag': 'waiting-bt', 'emoji': '📡', 'label': 'Aguardando caixinha'}

    # play_event.txt: gravado quando o Spotify confirma reprodução ativa
    play_ts = 0
    try:
        if os.path.exists(PLAY_EVENT_FILE):
            with open(PLAY_EVENT_FILE) as f:
                play_ts = int(f.read().strip())
    except Exception:
        pass
    if play_ts and (time.time() - play_ts) < 60:
        return {'tag': 'playing', 'emoji': '🎵', 'label': 'Tocando'}

    return {'tag': 'starting', 'emoji': '⏳', 'label': 'Iniciando música'}


@app.route('/')
def index():
    current_state = get_state()
    action_text = 'Desativar DJ Haules' if current_state == 'ENABLED' else 'Ativar DJ Haules'
    status = compute_playback_status()
    return render_template('index.html', status=status, action_text=action_text)


@app.route('/api/status/playback')
def api_status_playback():
    return jsonify({'ok': True, **compute_playback_status()})

@app.route('/toggle')
def toggle():
    current_state = get_state()
    set_state('DISABLED' if current_state == 'ENABLED' else 'ENABLED')
    return redirect(url_for('index'))


# --- Helpers de playlists ---

def load_playlists():
    if not os.path.exists(PLAYLISTS_FILE):
        return []
    with open(PLAYLISTS_FILE, encoding='utf-8') as f:
        return json.load(f)

def get_active_playlist_id():
    if not os.path.exists(ACTIVE_PLAYLIST_FILE):
        return 'automatico'
    with open(ACTIVE_PLAYLIST_FILE) as f:
        return f.read().strip() or 'automatico'


WEEKDAY_NAMES = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
WEEKDAY_PT    = ['segunda','terça','quarta','quinta','sexta','sábado','domingo']


def resolve_auto_today(playlists):
    """Espelha _resolve_auto_today do main.py para o webapp exibir o estilo do dia.

    Retorna a entrada da playlist que o modo automático escolheu hoje, ou None
    se não há entrada 'auto' ou o schedule não resolve.
    """
    auto = next((p for p in playlists if p.get('auto')), None)
    if not auto:
        return None
    schedule = auto.get('schedule', {})
    today_name = WEEKDAY_NAMES[datetime.now().weekday()]
    target_id = schedule.get(today_name)

    if target_id == 'random':
        candidates = sorted({v for v in schedule.values() if v and v != 'random'})
        if candidates:
            day_seed = int(datetime.now().strftime('%Y%m%d'))
            rng = random.Random(day_seed)
            target_id = rng.choice(candidates)

    return next((p for p in playlists if p['id'] == target_id), None)


# --- Rotas de playlist ---

@app.route('/playlist')
def playlist_page():
    playlists = load_playlists()
    active_id = get_active_playlist_id()
    auto_today = resolve_auto_today(playlists)
    today_label = WEEKDAY_PT[datetime.now().weekday()].capitalize()
    return render_template(
        'playlist.html',
        playlists=playlists,
        active_id=active_id,
        auto_today=auto_today,
        today_label=today_label,
    )

@app.route('/api/playlist/select', methods=['POST'])
def api_playlist_select():
    data = request.get_json() or {}
    playlist_id = (data.get('id') or '').strip()
    if not playlist_id:
        return jsonify({'ok': False, 'error': 'ID não informado.'})
    playlists = load_playlists()
    if not any(p['id'] == playlist_id for p in playlists):
        return jsonify({'ok': False, 'error': 'Playlist não encontrada.'})
    with open(ACTIVE_PLAYLIST_FILE, 'w') as f:
        f.write(playlist_id)

    # Reporta condições que impedem o efeito imediato — o id já está salvo
    # e vai ser aplicado quando o estado convergir.
    if get_state() != 'ENABLED':
        return jsonify({
            'ok': True,
            'warning': 'Salvo! Mas o DJ Haules está desativado — ative na tela inicial para começar a tocar.'
        })

    speakers = load_speakers()
    if not speakers:
        return jsonify({
            'ok': True,
            'warning': 'Salvo! Mas ainda não tem nenhuma caixinha pareada — só vai tocar depois de adicionar uma em "Caixas de Som".'
        })

    if not any(is_bt_connected(s['mac']) for s in speakers):
        return jsonify({
            'ok': True,
            'warning': 'Salvo! A música muda assim que a caixinha conectar.'
        })

    return jsonify({'ok': True})


# --- Rotas de gerenciamento de caixas ---

@app.route('/speakers')
def speakers_page():
    speakers = load_speakers()
    return render_template('speakers.html', speakers=speakers, disabled=get_state() == 'DISABLED')

@app.route('/speakers/remove', methods=['POST'])
def remove_speaker():
    mac = request.form.get('mac', '').upper()
    speakers = [s for s in load_speakers() if s['mac'].upper() != mac]
    save_speakers(speakers)
    return redirect(url_for('speakers_page'))


# --- API para scan e pair (chamadas AJAX) ---

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Escaneia dispositivos Bluetooth próximos por 15 segundos.

    Captura o stdout do bluetoothctl para identificar MACs que emitiram
    eventos durante o scan ([NEW] ou [CHG]) — esses estão fisicamente em
    alcance. Dispositivos já salvos como caixas são omitidos.
    """
    with bt_lock:
        raw_output = ''
        try:
            proc = subprocess.Popen(
                ['bluetoothctl'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            proc.stdin.write('scan on\n')
            proc.stdin.flush()
            time.sleep(15)
            proc.stdin.write('scan off\n')
            proc.stdin.write('quit\n')
            proc.stdin.flush()
            try:
                raw_output, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                raw_output, _ = proc.communicate()
        except Exception:
            pass

        # MACs com atividade durante o scan via eventos do stdout
        clean = re.sub(r'\x1b\[[0-9;]*[mK]', '', raw_output)
        active_macs = set()
        for line in clean.split('\n'):
            m = re.match(r'\[(NEW|CHG)\]\s+Device\s+([0-9A-Fa-f:]{17})', line)
            if m:
                active_macs.add(m.group(2).upper())

        try:
            output = subprocess.check_output(
                ['bluetoothctl', 'devices'], text=True, timeout=5
            )
            saved_macs = {s['mac'].upper() for s in load_speakers()}
            mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$')

            devices = []
            for line in output.strip().split('\n'):
                match = re.match(r'Device\s+([0-9A-Fa-f:]{17})\s+(.+)', line)
                if not match:
                    continue
                mac  = match.group(1).upper()
                name = match.group(2).strip()
                if mac_pattern.match(name) or mac in saved_macs:
                    continue

                if mac in active_macs:
                    # Emitiu eventos durante o scan → estava em alcance
                    devices.append({'mac': mac, 'name': name})
                else:
                    # Não emitiu eventos (connectable mas não discoverable).
                    # Dispositivos pareados: o BlueZ guarda RSSI de tudo que viu
                    # durante o scan — se tem RSSI é porque estava em alcance.
                    try:
                        info = subprocess.check_output(
                            ['bluetoothctl', 'info', mac], text=True, timeout=3
                        )
                        if 'RSSI:' in info:
                            devices.append({'mac': mac, 'name': name})
                    except Exception:
                        pass

            return jsonify({'ok': True, 'devices': devices})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e), 'devices': []})


def is_bt_connected(mac):
    """Verifica se o dispositivo está conectado via Bluetooth."""
    try:
        output = subprocess.check_output(['bluetoothctl', 'info', mac], text=True, timeout=5)
        return 'Connected: yes' in output
    except Exception:
        return False


def is_already_paired(mac):
    """Verifica se o dispositivo já está pareado no Pi."""
    try:
        output = subprocess.check_output(['bluetoothctl', 'info', mac], text=True, timeout=5)
        return 'Paired: yes' in output
    except Exception:
        return False


# Padrões de erro do bluetoothctl que indicam pareamento velho corrompido —
# a caixa recusa por incompatibilidade de chave de auth. Solução: 'remove' +
# pair fresco. Cobre tanto caixas com PIN quanto caixas "abertas" cuja link
# key ficou inconsistente entre Pi e dispositivo.
PAIRING_CORRUPT_PATTERNS = (
    'br-connection-refused',
    'connection refused',
    'authentication failed',
    'authentication canceled',
    'host is down',
)


def _output_indicates_corrupt_pairing(output):
    if not output:
        return False
    low = output.lower()
    return any(p in low for p in PAIRING_CORRUPT_PATTERNS)


def _do_pair_attempt(mac, attempt_num=None):
    """
    Executa uma tentativa completa de pair+trust+connect.
    Retorna (conectado: bool, tem_audio: bool, corrupted_pairing: bool).
    corrupted_pairing=True sinaliza que a próxima tentativa deve fazer 'remove'.
    """
    tag = f"[pair {mac} #{attempt_num}]" if attempt_num else f"[pair {mac}]"

    already_paired = is_already_paired(mac)
    cmds = ['trust', 'connect'] if already_paired else ['pair', 'trust', 'connect']
    print(f"{tag} already_paired={already_paired}, sequência: {' → '.join(cmds)}", flush=True)
    connect_output = ''
    # Timeout por comando — connect é o mais demorado (caixinha pode levar
    # mais de meio minuto pra negociar A2DP em alguns modelos)
    cmd_timeout = {'pair': 60, 'trust': 15, 'connect': 120}
    for cmd in cmds:
        timeout = cmd_timeout.get(cmd, 30)
        print(f"{tag} executando '{cmd}' (timeout {timeout}s)...", flush=True)
        t0 = time.time()
        try:
            result = subprocess.run(
                ['bluetoothctl', cmd, mac],
                capture_output=True, text=True, timeout=timeout
            )
            elapsed = time.time() - t0
            out = (result.stdout or '').strip().replace('\n', ' | ')
            err = (result.stderr or '').strip().replace('\n', ' | ')
            print(f"{tag} '{cmd}' levou {elapsed:.1f}s → stdout: {out[:200]}", flush=True)
            if err:
                print(f"{tag} '{cmd}' stderr: {err[:200]}", flush=True)
            if cmd == 'connect':
                connect_output = result.stdout + result.stderr
            time.sleep(4)
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            print(f"{tag} TIMEOUT em '{cmd}' após {elapsed:.1f}s", flush=True)
            return False, False, False

    # Tempo extra pra A2DP estabilizar antes de verificar
    print(f"{tag} aguardando 6s para A2DP estabilizar...", flush=True)
    time.sleep(6)
    if not is_bt_connected(mac):
        corrupted = already_paired and _output_indicates_corrupt_pairing(connect_output)
        if corrupted:
            print(f"{tag} pareamento velho corrompido detectado (br-connection-refused com already_paired). "
                  f"Próxima tentativa vai fazer 'remove' antes.", flush=True)
        else:
            print(f"{tag} bluetoothctl info NÃO reporta 'Connected: yes' — falha", flush=True)
        return False, False, corrupted

    has_audio = 'Transport' in connect_output
    print(f"{tag} SUCESSO — conectado, has_audio={has_audio}", flush=True)
    return True, has_audio, False


@app.route('/api/pair', methods=['POST'])
def api_pair():
    """Faz pair+trust+connect com várias tentativas e verifica se o áudio foi estabelecido."""
    data = request.get_json()
    mac = (data.get('mac') or '').upper()
    name = data.get('name') or mac

    if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac):
        return jsonify({'ok': False, 'error': 'Endereço do dispositivo inválido.'})

    connected = False
    has_audio = False
    MAX_ATTEMPTS = 6
    should_remove_next = False  # Sinalizado quando detectamos pareamento corrompido

    print(f"[pair {mac}] Iniciando pareamento (até {MAX_ATTEMPTS} tentativas) — nome='{name}'", flush=True)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        # Auto-recovery: pareamento velho recusou conexão na tentativa anterior.
        # Remove o registro local antes de tentar de novo — força pair fresco,
        # gerando nova link key compatível.
        if should_remove_next:
            print(f"[pair {mac}] limpando pareamento corrompido: bluetoothctl remove", flush=True)
            with bt_lock:
                subprocess.run(['bluetoothctl', 'remove', mac],
                               capture_output=True, timeout=10)
            should_remove_next = False
            time.sleep(2)

        with bt_lock:
            connected, has_audio, corrupted = _do_pair_attempt(mac, attempt_num=attempt)

        if connected:
            print(f"[pair {mac}] tentativa #{attempt} conectou. has_audio={has_audio}", flush=True)
            break

        if corrupted:
            should_remove_next = True

        if attempt < MAX_ATTEMPTS:
            # Descarta estado ruim antes de tentar de novo
            backoff = 2 + attempt * 2
            print(f"[pair {mac}] tentativa #{attempt} falhou. Disconnect + backoff {backoff}s...", flush=True)
            with bt_lock:
                subprocess.run(['bluetoothctl', 'disconnect', mac],
                               capture_output=True, timeout=10)
            time.sleep(backoff)
        else:
            print(f"[pair {mac}] todas as {MAX_ATTEMPTS} tentativas falharam", flush=True)

    if not connected:
        return jsonify({
            'ok': False,
            'error': (
                f'Não foi possível conectar após {MAX_ATTEMPTS} tentativas. '
                'Verifique se a caixa está ligada, próxima do Pi, e em modo de pareamento '
                '(botão Bluetooth piscando). Garanta também que ela não está conectada em outro dispositivo (celular/PC). '
                'Tente novamente.'
            )
        })

    # Salva como prioridade 1 (principal), incrementa as demais
    speakers = [s for s in load_speakers() if s['mac'].upper() != mac]
    for s in speakers:
        s['priority'] = s.get('priority', 1) + 1
    speakers.insert(0, {'name': name, 'mac': mac, 'priority': 1})
    save_speakers(speakers)

    # Dispara o banner de loading imediatamente — só faz sentido se o serviço estiver ativo.
    # Se DISABLED, o loop principal vai desconectar em seguida e o banner ficaria preso.
    if get_state() == 'ENABLED':
        try:
            with open(BT_EVENT_FILE, 'w') as _f:
                _f.write(str(int(time.time())))
        except Exception:
            pass

    if not has_audio:
        return jsonify({
            'ok': True,
            'warning': (
                'A caixa foi salva, mas pode demorar alguns segundos até o som aparecer. '
                'Se não tocar, desligue e ligue a caixa novamente.'
            )
        })

    return jsonify({'ok': True})


# --- API de status das caixas ---

@app.route('/api/speakers/status')
def api_speakers_status():
    """Retorna o status de conexão Bluetooth de cada caixa salva."""
    speakers = load_speakers()
    statuses = []
    for s in speakers:
        mac = s['mac']
        connected = is_bt_connected(mac)
        statuses.append({'mac': mac, 'connected': connected})
    return jsonify({'ok': True, 'statuses': statuses})


@app.route('/api/speakers/remove', methods=['POST'])
def api_speakers_remove():
    """Remove uma caixa salva e inicia a desconexão Bluetooth."""
    data = request.get_json() or {}
    mac = (data.get('mac') or '').upper()
    if not mac:
        return jsonify({'ok': False, 'error': 'MAC não informado.'})
    speakers = [s for s in load_speakers() if s['mac'].upper() != mac]
    save_speakers(speakers)
    # Dispara desconexão BT em background — o loop principal também vai detectar
    with bt_lock:
        try:
            subprocess.run(['bluetoothctl', 'disconnect', mac], capture_output=True, timeout=10)
        except Exception:
            pass
    return jsonify({'ok': True})


@app.route('/api/status/banner')
def api_status_banner():
    """Retorna timestamps dos eventos de BT conectado e play confirmado para o banner."""
    def read_ts(path):
        try:
            if os.path.exists(path):
                with open(path) as f:
                    return int(f.read().strip())
        except Exception:
            pass
        return 0
    return jsonify({'ok': True,
                    'bt_ts':          read_ts(BT_EVENT_FILE),
                    'play_ts':        read_ts(PLAY_EVENT_FILE),
                    'disconnect_ts':  read_ts(BT_DISCONNECT_FILE)})


@app.route('/api/play/event')
def api_play_event():
    """Retorna o timestamp do último evento de play confirmado no speaker."""
    try:
        if os.path.exists(PLAY_EVENT_FILE):
            with open(PLAY_EVENT_FILE) as f:
                ts = f.read().strip()
            return jsonify({'ok': True, 'ts': int(ts)})
    except Exception:
        pass
    return jsonify({'ok': True, 'ts': 0})


@app.route('/api/bt/status/<mac>')
def api_bt_status(mac):
    """Verifica se um MAC específico ainda está conectado via Bluetooth."""
    connected = is_bt_connected(mac.upper())
    return jsonify({'connected': connected})


# --- Rotas de configuração Wi-Fi ---

@app.route('/wifi')
def wifi_page():
    return render_template('wifi.html')


@app.route('/api/wifi/scan')
def api_wifi_scan():
    """Lista as redes Wi-Fi disponíveis com nome, força de sinal e se está em uso."""
    try:
        # Dispara rescan para garantir cache fresco. O rádio fica off-channel
        # por ~2-3s, mas a conexão TCP sobrevive (timeout >> tempo de scan).
        # Ignoramos erros — se falhar, usa o cache disponível.
        subprocess.run(
            ['sudo', 'nmcli', 'dev', 'wifi', 'rescan'],
            capture_output=True, timeout=15
        )
        time.sleep(3)

        output = subprocess.check_output(
            ['nmcli', '-t', '-f', 'IN-USE,SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list'],
            text=True, timeout=10
        )
        seen = set()
        networks = []
        for line in output.strip().split('\n'):
            parts = line.split(':')
            if len(parts) < 4:
                continue
            in_use   = parts[0].strip() == '*'
            ssid     = ':'.join(parts[1:-2]).strip()  # SSID pode conter ':'
            signal   = parts[-2].strip()
            security = parts[-1].strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal_pct = int(signal)
            except ValueError:
                signal_pct = 0
            networks.append({
                'ssid': ssid,
                'signal': signal_pct,
                'security': security not in ('', '--'),
                'in_use': in_use,
            })
        networks.sort(key=lambda x: (-int(x['in_use']), -x['signal']))
        return jsonify({'ok': True, 'networks': networks})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'networks': []})


@app.route('/api/wifi/status')
def api_wifi_status():
    """Retorna o estado atual da conectividade Wi-Fi."""
    try:
        # Detecta hotspot ativo pelo nome da conexão
        active = subprocess.check_output(
            ['nmcli', '-t', '-f', 'NAME,TYPE,STATE', 'con', 'show', '--active'],
            text=True, timeout=5
        )
        hotspot = any(
            line.split(':')[0] == 'DJHaules-Hotspot'
            for line in active.strip().split('\n')
            if line
        )

        # Obtém o SSID real da interface Wi-Fi (somente em modo estação)
        ssid = None
        if not hotspot:
            try:
                wifi_out = subprocess.check_output(
                    ['nmcli', '-t', '-f', 'ACTIVE,SSID', 'dev', 'wifi'],
                    text=True, timeout=5
                )
                for wline in wifi_out.strip().split('\n'):
                    # split com maxsplit=1 preserva SSIDs que contenham ':'
                    wparts = wline.split(':', 1)
                    if len(wparts) == 2 and wparts[0] == 'yes':
                        candidate = wparts[1].strip()
                        if candidate:
                            ssid = candidate
                            break
            except Exception:
                pass

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
            ['sudo', 'nmcli', 'con', 'delete', WIFI_CON_NAME],
            capture_output=True, timeout=10
        )

        # Cria novo perfil (sem ifname para não conflitar com hotspot ativo)
        cmd = [
            'sudo', 'nmcli', 'con', 'add',
            'type', 'wifi',
            'con-name', WIFI_CON_NAME,
            'ssid', ssid,
            'connection.autoconnect', 'yes',
        ]
        if password:
            cmd += ['wifi-sec.key-mgmt', 'wpa-psk', 'wifi-sec.psk', password]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return jsonify({'ok': False, 'error': result.stderr.strip() or 'Erro ao salvar configuração de rede.'})

        # Tenta conectar em background (o wifi_monitor vai confirmar em até 30s)
        subprocess.Popen(['sudo', 'nmcli', 'con', 'up', WIFI_CON_NAME])

        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/wifi/forget', methods=['POST'])
def api_wifi_forget():
    """Remove a rede Wi-Fi salva e ativa o hotspot de recuperação.

    Executa em background com delay para garantir que a resposta HTTP chega ao
    cliente antes do Pi derrubar a conexão Wi-Fi ao deletar o perfil.
    """
    def _do_forget():
        time.sleep(1)
        subprocess.run(['sudo', 'nmcli', 'con', 'delete', WIFI_CON_NAME],
                       capture_output=True, timeout=10)
        subprocess.run(['sudo', 'nmcli', 'con', 'up', 'DJHaules-Hotspot'],
                       capture_output=True, timeout=15)

    threading.Thread(target=_do_forget, daemon=True).start()
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
