
import json
import os
import random
import time
import threading
import subprocess
import spotipy
import requests
from configparser import ConfigParser
from webapp.app import app as flask_app
from shared import bt_lock

# --- Caminhos e Configurações ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'config', 'settings.ini')
STATE_FILE = os.path.join(BASE_DIR, 'config', 'state.txt')
SPEAKERS_FILE = os.path.join(BASE_DIR, 'config', 'speakers.json')

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

def connect_bluetooth(mac_address):
    """Tenta conectar ao dispositivo Bluetooth."""
    print(f"Tentando conectar ao dispositivo {mac_address}...")
    try:
        with bt_lock:
            subprocess.run(['bluetoothctl', 'connect', mac_address], timeout=20)
        time.sleep(5)
        return is_bluetooth_connected(mac_address)
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

def ensure_spotify_playing(sp, config):
    """Garante que a playlist comunitária está tocando no dispositivo correto."""
    device_name = config.get('APP', 'DEVICE_NAME')
    playlist_uri = config.get('APP', 'PLAYLIST_URI')

    try:
        # 1. Verificar o estado atual de reprodução
        playback = sp.current_playback()

        # Se já estiver tocando a playlist certa no dispositivo certo, não faz nada
        if (playback
                and playback.get('is_playing')
                and playback.get('device', {}).get('name') == device_name
                and playback.get('context') is not None
                and playback.get('context', {}).get('uri') == playlist_uri):
            return

        # 2. Encontrar o dispositivo (o próprio Pi rodando raspotify)
        devices = sp.devices()
        target_device_id = None
        for device in devices['devices']:
            if device['name'] == device_name:
                target_device_id = device['id']
                break

        if not target_device_id:
            print(f"Dispositivo Spotify '{device_name}' não encontrado. Certifique-se que o raspotify está ativo.")
            return

        # 3. Iniciar a playlist comunitária em posição aleatória
        print(f"Iniciando playlist comunitária no dispositivo '{device_name}'...")
        try:
            playlist_id = playlist_uri.split(':')[-1]
            total = sp.playlist(playlist_id)['tracks']['total']
            offset = random.randint(0, max(0, total - 1))
            print(f"Posição aleatória escolhida: {offset}/{total}")
        except Exception as e:
            print(f"Aviso: não foi possível obter total de músicas ({e}). Iniciando do começo.")
            offset = 0
        sp.start_playback(device_id=target_device_id, context_uri=playlist_uri,
                          offset={'position': offset})
        print("Playlist iniciada com sucesso!")
        try:
            time.sleep(2)
            sp.volume(50, device_id=target_device_id)
        except Exception as e:
            print(f"Aviso: não foi possível ajustar volume ({e}).")
        try:
            time.sleep(3)
            sp.shuffle(True, device_id=target_device_id)
            sp.repeat('context', device_id=target_device_id)
        except Exception as e:
            print(f"Aviso: não foi possível configurar shuffle/repeat ({e}).")

    except Exception as e:
        print(f"Erro ao verificar/iniciar reprodução no Spotify: {e}")
        if isinstance(e, spotipy.exceptions.SpotifyException) and e.http_status == 401:
            raise e

# --- Loop Principal ---

def main():
    print("Iniciando serviço DJ Haules...")
    config = get_config()
    sp = None
    connected_mac = None

    # Inicia a interface web em uma thread separada
    webapp_thread = threading.Thread(target=run_webapp, daemon=True)
    webapp_thread.start()

    while True:
        current_state = get_state()
        speakers = load_speakers()

        if not speakers:
            print("Nenhuma caixa de som configurada. Acesse http://dj-haules.local:8080/speakers para adicionar.")
            time.sleep(30)
            continue

        if current_state == 'ENABLED':
            # 1. Bluetooth primeiro — independente do Spotify
            if connected_mac and not is_bluetooth_connected(connected_mac):
                print(f"Caixa {connected_mac} desconectou. Tentando reconectar ou buscar outra...")
                connected_mac = None

            if not connected_mac:
                connected_mac = connect_to_best_speaker(speakers)

            if not connected_mac:
                print("Não foi possível conectar a nenhuma caixa. Tentando novamente em 10 segundos...")
                time.sleep(10)
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
                ensure_spotify_playing(sp, config)
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 401:
                    print("Token do Spotify expirou. Obtendo um novo...")
                    sp = None
                    continue

        else:  # current_state == 'DISABLED'
            disconnect_all_speakers(speakers)
            connected_mac = None
            print("Serviço em modo de espera. Verificando novamente em 30 segundos.")

        time.sleep(30)

if __name__ == "__main__":
    main()
