
import json
import os
import random
import time
import threading
import subprocess
import spotipy
import requests
from configparser import ConfigParser
from datetime import datetime
from webapp.app import app as flask_app
from shared import bt_lock

# --- Caminhos e Configurações ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'settings.ini')
STATE_FILE = os.path.join(BASE_DIR, 'config', 'state.txt')
SPEAKERS_FILE = os.path.join(BASE_DIR, 'config', 'speakers.json')
PLAYLISTS_FILE = os.path.join(BASE_DIR, 'config', 'playlists.json')
ACTIVE_PLAYLIST_FILE = os.path.join(BASE_DIR, 'config', 'active_playlist.txt')
PLAY_EVENT_FILE       = os.path.join(BASE_DIR, 'config', 'play_event.txt')
BT_EVENT_FILE         = os.path.join(BASE_DIR, 'config', 'bt_event.txt')
BT_DISCONNECT_FILE    = os.path.join(BASE_DIR, 'config', 'bt_disconnect_event.txt')

# --- Interface Web ---

def run_webapp():
    """Inicia o servidor web Flask em uma thread daemon."""
    print("Iniciando interface web na porta 8080...")
    flask_app.run(host='0.0.0.0', port=8080, use_reloader=False, debug=False)

# --- Funções de Controle ---

def get_state():
    """Lê o estado atual (ENABLED ou DISABLED) do arquivo."""
    if not os.path.exists(STATE_FILE):
        return 'ENABLED'
    with open(STATE_FILE, 'r') as f:
        return f.read().strip()

def get_config():
    """Lê as configurações do arquivo settings.ini."""
    config = ConfigParser()
    config.read(CONFIG_FILE)
    return config

def load_speakers():
    """Carrega a lista de caixas de som salvas, ordenada por prioridade."""
    if not os.path.exists(SPEAKERS_FILE):
        return []
    with open(SPEAKERS_FILE, 'r') as f:
        speakers = json.load(f)
    return sorted(speakers, key=lambda s: s.get('priority', 99))

def is_bluetooth_connected(mac_address):
    """Verifica se o dispositivo Bluetooth está conectado."""
    try:
        with bt_lock:
            output = subprocess.check_output(
                ['bluetoothctl', 'info', mac_address], text=True
            )
        return "Connected: yes" in output
    except subprocess.CalledProcessError:
        return False

def _reprovision_bluetooth(mac_address):
    """Refaz pair+trust+connect para recuperar transporte de áudio (A2DP)."""
    try:
        with bt_lock:
            subprocess.run(['bluetoothctl', 'disconnect', mac_address],
                           capture_output=True, timeout=10)
        time.sleep(2)
        with bt_lock:
            for cmd in ['pair', 'trust']:
                subprocess.run(['bluetoothctl', cmd, mac_address],
                               capture_output=True, timeout=20)
                time.sleep(2)
        with bt_lock:
            result = subprocess.run(
                ['bluetoothctl', 'connect', mac_address],
                capture_output=True, text=True, timeout=20
            )
        output = result.stdout + result.stderr
        time.sleep(5)
        if 'Transport' in output and is_bluetooth_connected(mac_address):
            print("Re-pareamento bem-sucedido — transporte de áudio estabelecido.")
            return True
        print("Re-pareamento falhou — sem transporte de áudio.")
        return False
    except Exception as e:
        print(f"Erro no re-pareamento: {e}")
        return False

def connect_bluetooth(mac_address):
    """Tenta conectar ao dispositivo Bluetooth. Retorna True somente com A2DP estabelecido."""
    print(f"Tentando conectar ao dispositivo {mac_address}...")
    try:
        with bt_lock:
            result = subprocess.run(
                ['bluetoothctl', 'connect', mac_address],
                capture_output=True, text=True, timeout=20
            )
        output = result.stdout + result.stderr
        time.sleep(3)

        if not is_bluetooth_connected(mac_address):
            return False

        if 'Transport' in output:
            return True

        # Link BT estabelecido mas sem A2DP — ocorre quando caixinha está em modo pareamento
        print(f"Conexão BT sem áudio. Tentando re-parear {mac_address}...")
        if _reprovision_bluetooth(mac_address):
            return True

        # Re-pareamento falhou — desconecta para limpar estado e tentar fresh na próxima
        with bt_lock:
            subprocess.run(['bluetoothctl', 'disconnect', mac_address],
                           capture_output=True, timeout=10)
        return False
    except subprocess.TimeoutExpired:
        print("Timeout ao tentar conectar.")
        return False
    except Exception as e:
        print(f"Erro ao conectar Bluetooth: {e}")
        return False

def connect_to_best_speaker(speakers):
    """
    Tenta conectar à melhor caixa disponível (pela ordem de prioridade).
    Retorna o MAC da caixa conectada ou None.
    """
    for speaker in speakers:
        mac = speaker['mac']
        name = speaker.get('name', mac)
        if is_bluetooth_connected(mac):
            print(f"Já conectado a '{name}'.")
            return mac
        print(f"Tentando conectar a '{name}' ({mac})...")
        if connect_bluetooth(mac):
            print(f"Conectado a '{name}' com sucesso.")
            return mac
    return None

def disconnect_all_speakers(speakers):
    """Desconecta todas as caixas conhecidas."""
    for speaker in speakers:
        mac = speaker['mac']
        if is_bluetooth_connected(mac):
            print(f"Desconectando {speaker.get('name', mac)}...")
            with bt_lock:
                subprocess.run(['bluetoothctl', 'disconnect', mac])

def reset_bluetooth_state(speakers):
    """Limpa estado cacheado do bluetoothd ao iniciar o serviço."""
    for speaker in speakers:
        mac = speaker['mac']
        name = speaker.get('name', mac)
        print(f"Resetando estado Bluetooth de '{name}'...")
        with bt_lock:
            subprocess.run(['bluetoothctl', 'disconnect', mac],
                           capture_output=True, timeout=10)

# --- Playlist ativa ---

WEEKDAY_NAMES = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']


def _resolve_auto_today(auto_entry, playlists):
    """Resolve qual playlist o modo 'automático' deve tocar hoje.

    Para dias mapeados a um id específico (segunda → reggae, etc), retorna direto.
    Para 'random' (fds), usa a data atual como seed — a escolha é determinística
    no mesmo dia (não fica trocando a cada 15s) mas muda ao virar o dia.
    """
    schedule = auto_entry.get('schedule', {})
    today_name = WEEKDAY_NAMES[datetime.now().weekday()]
    target_id = schedule.get(today_name)

    if target_id == 'random':
        candidates = sorted({
            v for v in schedule.values()
            if v and v != 'random'
        })
        if candidates:
            day_seed = int(datetime.now().strftime('%Y%m%d'))
            rng = random.Random(day_seed)
            target_id = rng.choice(candidates)

    return next((p for p in playlists if p['id'] == target_id), None)


def get_active_playlist_uri(config):
    """Retorna a URI da playlist selecionada no momento.

    Suporta o modo 'automático' (entrada com auto=true): escolhe o estilo
    do dia conforme o campo 'schedule'.
    """
    active_id = 'automatico'
    if os.path.exists(ACTIVE_PLAYLIST_FILE):
        with open(ACTIVE_PLAYLIST_FILE) as f:
            active_id = f.read().strip() or 'automatico'

    playlists = []
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE) as f:
            playlists = json.load(f)

    target = next((p for p in playlists if p['id'] == active_id), None)

    if target and target.get('auto'):
        target = _resolve_auto_today(target, playlists)

    if target and target.get('uri'):
        return target['uri']

    return config.get('APP', 'PLAYLIST_URI')


# --- Spotify ---

def get_spotify_token(config):
    """Busca o token de acesso do Spotify no Supabase."""
    print("Buscando token de acesso no Supabase...")
    try:
        url = f"{config.get('SUPABASE', 'URL')}/rest/v1/tokens?select=token"
        headers = {"apikey": config.get('SUPABASE', 'ANON_KEY')}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and 'token' in data[0]:
            print("Token obtido com sucesso.")
            return data[0]['token']
        print("Token não encontrado na resposta do Supabase.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar token no Supabase: {e}")
        return None

def create_spotify_client(config):
    """Cria um cliente Spotipy usando o token do Supabase."""
    access_token = get_spotify_token(config)
    if access_token:
        return spotipy.Spotify(auth=access_token)
    return None

def ensure_spotify_playing(sp, config, force_restart=False):
    """
    Garante que a playlist ativa está tocando no dispositivo correto.

    force_restart=True: ignora o estado atual e sempre reinicia a playlist numa
    posição aleatória. Usar na primeira conexão BT de cada sessão para evitar
    que o Spotify retome automaticamente da última posição salva.

    Retorna True se start_playback foi chamado, False caso contrário.
    """
    device_name = config.get('APP', 'DEVICE_NAME')
    playlist_uri = get_active_playlist_uri(config)

    try:
        playback = sp.current_playback()

        # Retorno antecipado somente se não for reinício forçado:
        # Spotify já está tocando a playlist certa no dispositivo certo.
        if not force_restart:
            if (playback
                    and playback.get('is_playing')
                    and playback.get('device', {}).get('name') == device_name
                    and playback.get('context') is not None
                    and playback.get('context', {}).get('uri') == playlist_uri):
                return False

        devices = sp.devices()
        target_device_id = None
        for device in devices['devices']:
            if device['name'] == device_name:
                target_device_id = device['id']
                break

        if not target_device_id:
            print(f"Dispositivo Spotify '{device_name}' não encontrado. Aguardando Raspotify registrar o dispositivo...")
            return False

        print(f"Iniciando playlist comunitária no dispositivo '{device_name}'...")

        # Spotify caches o shuffle seed por (dispositivo, playlist). Se a mesma
        # playlist for reiniciada no mesmo dispositivo (ex: após reboot), shuffle(True)
        # gera a mesma ordem e next_track() cai sempre na mesma música.
        # Solução: iniciar em um offset aleatório quebra o cache — mesmo que
        # shuffle(True) reutilize o seed, a posição inicial é diferente.
        # fallback=randint(0,19): não precisa do total, funciona para qualquer
        # playlist com 20+ faixas. Se a playlist for menor, o catch 400 usa offset=0.
        random_offset = random.randint(0, 19)
        try:
            result = sp.playlist_tracks(playlist_uri, limit=1)
            total = result.get('total', 0)
            if total > 1:
                random_offset = random.randint(0, total - 1)
            print(f"Playlist com {total} faixas. Offset inicial: {random_offset + 1}.")
        except Exception as e:
            print(f"Aviso: total de faixas indisponível ({type(e).__name__}). Usando offset {random_offset + 1}.")

        try:
            sp.start_playback(
                device_id=target_device_id,
                context_uri=playlist_uri,
                offset={'position': random_offset},
            )
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 400:
                print(f"Offset {random_offset + 1} fora do range. Iniciando do início.")
                sp.start_playback(device_id=target_device_id, context_uri=playlist_uri)
            else:
                raise
        print("Playlist iniciada. Aplicando shuffle...")

        try:
            time.sleep(2)
            sp.volume(50, device_id=target_device_id)
        except Exception as e:
            print(f"Aviso: não foi possível ajustar volume ({e}).")

        try:
            time.sleep(1)
            sp.shuffle(True, device_id=target_device_id)
        except Exception as e:
            print(f"Aviso: não foi possível ativar shuffle ({e}).")

        # Pula para a 1ª música da fila embaralhada — aqui está a aleatoriedade real.
        # O Spotify gera um novo seed a cada shuffle(True), então next_track()
        # sempre cai em uma música diferente.
        try:
            time.sleep(1)
            sp.next_track(device_id=target_device_id)
            print("Shuffle aplicado — música aleatória iniciada.")
            # Confirma com o Spotify que o áudio está de fato tocando no dispositivo
            # antes de sinalizar o banner — evita falsos positivos
            time.sleep(2)
            try:
                playback = sp.current_playback()
                if (playback
                        and playback.get('is_playing')
                        and playback.get('device', {}).get('id') == target_device_id):
                    with open(PLAY_EVENT_FILE, 'w') as _f:
                        _f.write(str(int(time.time())))
                    print("Play confirmado pelo Spotify — banner ativado.")
                else:
                    print("Aviso: next_track OK mas Spotify não confirmou playback ativo no dispositivo.")
            except Exception as e_chk:
                print(f"Aviso: não foi possível confirmar playback ({e_chk}).")
        except Exception as e:
            print(f"Aviso: não foi possível pular para música aleatória ({e}).")

        try:
            time.sleep(1)
            sp.repeat('context', device_id=target_device_id)
        except Exception as e:
            print(f"Aviso: não foi possível configurar repeat ({e}).")

        return True

    except Exception as e:
        print(f"Erro ao verificar/iniciar reprodução no Spotify: {e}")
        if isinstance(e, spotipy.exceptions.SpotifyException) and e.http_status == 401:
            raise e
        return False

# --- Loop Principal ---

def main():
    print("Iniciando serviço DJ Haules...")
    config = get_config()
    sp = None
    connected_mac = None
    # Força reinício da playlist na primeira conexão BT de cada sessão,
    # evitando que o Spotify retome automaticamente da última posição salva.
    needs_restart = True

    # Inicia a interface web em uma thread separada
    webapp_thread = threading.Thread(target=run_webapp, daemon=True)
    webapp_thread.start()

    # Limpa estado Bluetooth cacheado do bluetoothd antes de começar
    initial_speakers = load_speakers()
    if initial_speakers:
        reset_bluetooth_state(initial_speakers)

    while True:
        current_state = get_state()
        speakers = load_speakers()

        if not speakers:
            print("Nenhuma caixa de som configurada. Acesse http://dj-haules.local:8080/speakers para adicionar.")
            time.sleep(30)
            continue

        if current_state == 'ENABLED':
            # 1. Bluetooth primeiro — independente do Spotify

            # Verifica se a caixa conectada foi removida pelo usuário via interface web
            if connected_mac and not any(s['mac'].upper() == connected_mac.upper() for s in speakers):
                print(f"Caixa {connected_mac} removida da lista. Desconectando...")
                with bt_lock:
                    subprocess.run(['bluetoothctl', 'disconnect', connected_mac],
                                   capture_output=True, timeout=10)
                connected_mac = None
                needs_restart = True

            if connected_mac and not is_bluetooth_connected(connected_mac):
                print(f"Caixa {connected_mac} desconectou. Tentando reconectar ou buscar outra...")
                try:
                    with open(BT_DISCONNECT_FILE, 'w') as _f:
                        _f.write(str(int(time.time())))
                except Exception:
                    pass
                connected_mac = None
                needs_restart = True  # Nova conexão BT = reinício da playlist

            if not connected_mac:
                connected_mac = connect_to_best_speaker(speakers)
                if connected_mac:
                    needs_restart = True  # Nova conexão BT = reinício da playlist
                    # Grava evento de BT conectado para o banner de loading da interface
                    try:
                        with open(BT_EVENT_FILE, 'w') as _f:
                            _f.write(str(int(time.time())))
                    except Exception:
                        pass
                    # Aguarda o Raspotify registrar o dispositivo no Spotify após nova conexão BT
                    print("Bluetooth conectado. Aguardando Raspotify ficar disponível...")
                    time.sleep(20)

            if not connected_mac:
                print("Não foi possível conectar a nenhuma caixa. Tentando novamente em 5 segundos...")
                time.sleep(5)
                continue

            # 2. Spotify — só tenta se Bluetooth estiver conectado
            if not sp:
                print("Cliente Spotify não inicializado. Tentando criar...")
                sp = create_spotify_client(config)
                if not sp:
                    print("Falha ao criar cliente Spotify. Tentando novamente em 30s.")
                    time.sleep(30)
                    continue

            try:
                started = ensure_spotify_playing(sp, config, force_restart=needs_restart)
                if started:
                    needs_restart = False
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 401:
                    print("Token do Spotify expirou. Obtendo um novo...")
                    sp = None
                    continue

        else:  # current_state == 'DISABLED'
            disconnect_all_speakers(speakers)
            connected_mac = None
            needs_restart = True  # Ao reativar, reinicia playlist do zero
            print("Serviço em modo de espera. Verificando novamente em 15 segundos.")

        time.sleep(15)

if __name__ == "__main__":
    main()
