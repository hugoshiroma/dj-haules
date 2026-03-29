# Contexto do Projeto: DJ-Haules

Este arquivo serve como guia de contexto para o Claude sobre o projeto "DJ-Haules".

## 1. Resumo do Projeto

- **O que é:** Sistema de automação de playlist de música ambiente para o Bar do Haules. Roda em um **Raspberry Pi**, conecta a uma caixa de som Bluetooth e toca a **playlist comunitária do bar** (gerenciada pelo `haules-landing-page`) via Spotify/Raspotify.
- **Objetivo:** Manter a música tocando de forma autônoma, sem intervenção manual, a partir da playlist que os clientes constroem pelo site do bar.
- **Integração:** Consome a mesma conta Spotify e playlist comunitária gerenciadas pelas Edge Functions do Supabase usadas pelo `haules-landing-page`.
- **Controle:** Interface web em `http://dj-haules.local:8080` para ativar/desativar o sistema (ex: para shows ao vivo).

## 2. Tecnologias e Arquitetura

- **Hardware:** Raspberry Pi Zero 2 W (ou superior).
- **Sistema Operacional:** Raspberry Pi OS Lite (64-bit).
- **Linguagem Principal:** Python 3.
- **Gerenciador de Pacotes:** `pip` com `requirements.txt`.
- **Ambiente:** Virtual environment Python (`.venv`).
- **Áudio/Música:**
  - **Raspotify:** Cliente Spotify Connect — faz o Pi aparecer como dispositivo de áudio no Spotify.
  - **Bluetooth:** Conecta-se a caixas de som via MAC address. Suporta múltiplas caixas com fallback automático por prioridade.
- **Framework Web:** Flask (serve a interface de controle em `http://dj-haules.local:8080`).
- **Spotify SDK:** `spotipy` — wrapper Python para a Spotify Web API.
- **Configuração:** `config/settings.ini` (credenciais Supabase e configurações do app) + `config/speakers.json` (lista de caixas Bluetooth, gerenciada pela webapp).

## 3. Arquitetura de Execução

O ponto de entrada é `main.py`, que orquestra **dois loops em paralelo**:

1. **Thread daemon (Flask web app):** Inicia `webapp/app.py` em background. Serve a página de controle na porta 8080. Não bloqueia o loop principal.
2. **Loop principal (controle de áudio):** Verifica a cada 30s o estado (ENABLED/DISABLED), mantém o Bluetooth conectado e garante que a playlist comunitária está tocando no dispositivo correto.

**Comunicação entre webapp e loop principal:** via arquivos em `config/`:
- `state.txt` — ENABLED ou DISABLED. A webapp escreve; o loop lê.
- `speakers.json` — lista de caixas Bluetooth. A webapp escreve (scan/pair/remove); o loop lê a cada iteração.

**Lock compartilhado (`shared.bt_lock`):** `shared.py` expõe um `threading.Lock` que serializa todas as chamadas ao `bluetoothctl` — tanto do loop principal quanto das rotas de scan/pair da webapp.

## 4. Fluxo de Reprodução (`ensure_spotify_playing`)

A cada iteração do loop (quando ENABLED e Bluetooth conectado), a função:

1. Chama `sp.current_playback()` para verificar o estado atual.
2. Se já estiver tocando **a playlist certa** (`PLAYLIST_URI`) **no dispositivo certo** (`DEVICE_NAME`), não faz nada (evita chamadas desnecessárias à API).
3. Caso contrário: localiza o dispositivo Raspotify, habilita shuffle, habilita repeat e inicia a playlist.

Isso garante que a playlist **reinicia automaticamente** se parar por qualquer motivo (expiração de sessão, fim da fila, etc).

## 5. Token Spotify

O token de acesso é buscado via REST API do Supabase na tabela `tokens`:
- `GET /rest/v1/tokens?select=token` com header `apikey: ANON_KEY`
- O token é um **Spotify Access Token** (expira em ~1h)
- Em caso de erro 401, o loop invalida o cliente (`sp = None`) e busca um novo token na próxima iteração
- **Responsabilidade de renovação:** quem atualiza o token na tabela `tokens` é o backend (Edge Functions do Supabase). O `dj-haules` apenas consome.

## 6. Estrutura de Arquivos

```
main.py                         # Orquestrador: inicia webapp thread + loop principal
shared.py                       # bt_lock: threading.Lock compartilhado entre main e webapp
webapp/
  app.py                        # Flask: /, /toggle, /speakers, /api/scan, /api/pair
  templates/
    index.html                  # Página principal (on/off)
    speakers.html               # Gerenciamento de caixas (scan + pair + lista)
  static/
    logo.png                    # Logo Haules (copiado de haules-landing-page/public/)
config/
  settings.ini.template         # Template de configuração (versionado)
  settings.ini                  # Configuração real (NÃO versionado — contém segredos)
  speakers.json.template        # Template vazio para o arquivo de caixas
  speakers.json                 # Lista de caixas Bluetooth (gerado pela webapp, não versionado)
  state.txt                     # Estado atual: ENABLED ou DISABLED (gerado em runtime)
requirements.txt                # flask, spotipy, requests
docs/
  INSTALL_GUIDE_FOR_DEV.md      # Guia completo de setup no Raspberry Pi
README.md                       # Guia de uso para funcionários do bar
```

## 7. Configurações

### `config/settings.ini`

| Seção | Chave | Descrição |
|---|---|---|
| `SUPABASE` | `URL` | URL base do projeto Supabase |
| `SUPABASE` | `ANON_KEY` | Chave anônima pública do Supabase |
| `APP` | `DEVICE_NAME` | Nome do dispositivo Raspotify no Spotify (ex: `DJHaules`) |
| `APP` | `PLAYLIST_URI` | URI da playlist comunitária (ex: `spotify:playlist:XXXX`) |

**`PLAYLIST_URI`:** URI da playlist Spotify comunitária — a mesma que clientes alimentam pelo `haules-landing-page`. Para obter: abrir a playlist no Spotify Desktop → botão direito → "Compartilhar" → "Copiar URI da playlist".

### `config/speakers.json`

Gerenciado automaticamente pela webapp (rotas `/api/pair` e `/speakers/remove`). Não precisa ser editado manualmente. Formato:

```json
[
  {"name": "JBL Charge 5", "mac": "AA:BB:CC:DD:EE:FF", "priority": 1},
  {"name": "Sony XB43",    "mac": "11:22:33:44:55:66", "priority": 2}
]
```

A caixa de `priority: 1` é a principal. O loop tenta sempre em ordem crescente de prioridade. Ao parear uma nova caixa pela webapp, ela vira prioridade 1 automaticamente.

## 8. Setup e Execução

Ver `docs/INSTALL_GUIDE_FOR_DEV.md` para o guia completo. Resumo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config/settings.ini.template config/settings.ini
cp config/speakers.json.template config/speakers.json
# Editar settings.ini com PLAYLIST_URI e chaves Supabase
python main.py
# Acessar http://dj-haules.local:8080/speakers para parear a primeira caixa
```

## 9. Operação em Produção (Serviço systemd)

O serviço `djhaules.service` roda `main.py`, que já sobe a webapp Flask internamente na porta 8080. **Não é necessário um serviço separado para a webapp.**

```bash
sudo systemctl start djhaules.service
sudo systemctl stop djhaules.service
sudo systemctl status djhaules.service
sudo systemctl enable djhaules.service   # Iniciar no boot
```

## 10. Relação com Outros Projetos

| Projeto | Relação |
|---|---|
| `haules-landing-page` | Gerencia a playlist comunitária que o DJ Haules toca. Clientes adicionam músicas via site. O `dj-haules` consome a mesma playlist Spotify. |
| `service-haules-v2` (Supabase) | Hospeda a tabela `tokens` com o Spotify Access Token e as Edge Functions que renovam o token. |
| `haules-pos-app` | Sem relação direta. |
