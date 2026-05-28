# Contexto do Projeto: DJ-Haules

Este arquivo serve como guia de contexto para o Claude sobre o projeto "DJ-Haules".

## 1. Resumo do Projeto

- **O que é:** Sistema de automação de playlist de música ambiente para o Bar do Haules. Roda em um **Raspberry Pi**, conecta a uma caixa de som Bluetooth e toca playlists via Spotify/Raspotify.
- **Objetivo:** Manter a música tocando de forma autônoma, sem intervenção manual. A playlist principal ("Brasilidades") é alimentada pelos clientes via `haules-landing-page`; outras playlists são selecionáveis pela interface.
- **Integração:** Consome a mesma conta Spotify e playlist comunitária gerenciadas pelas Edge Functions do Supabase usadas pelo `haules-landing-page`.
- **Controle:** Interface web em `http://dj-haules.local` para ativar/desativar o sistema, trocar playlist, gerenciar caixas e configurar Wi-Fi.

## 2. Tecnologias e Arquitetura

- **Hardware:** Raspberry Pi Zero 2 W (ou superior).
- **Sistema Operacional:** Raspberry Pi OS Desktop (64-bit, Bookworm). A versão Desktop é necessária para o PipeWire (áudio Bluetooth).
- **Linguagem Principal:** Python 3.
- **Gerenciador de Pacotes:** `pip` com `requirements.txt` (`flask`, `spotipy`, `requests`).
- **Ambiente:** Virtual environment Python (`.venv`).
- **Áudio/Música:**
  - **Raspotify (librespot):** Cliente Spotify Connect — faz o Pi aparecer como dispositivo de áudio no Spotify com o nome `raspotify (dj-haules)`.
  - **PipeWire:** Sistema de áudio que roteia o Raspotify para o Bluetooth. Roda como serviço de usuário.
  - **Bluetooth:** Conecta-se a caixas de som via MAC address com fallback automático por prioridade.
- **Framework Web:** Flask, porta 8080. Redireciona porta 80 → 8080 via iptables (setup_iptables.sh), permitindo acesso via `http://dj-haules.local` sem digitar porta.
- **Spotify SDK:** `spotipy` — wrapper Python para a Spotify Web API.

## 3. Arquitetura de Execução

O ponto de entrada é `main.py`, que orquestra **dois loops em paralelo**:

1. **Thread daemon (Flask web app):** Inicia `webapp/app.py` em background. Serve a interface na porta 8080. Não bloqueia o loop principal.
2. **Loop principal (controle de áudio):** Verifica a cada 15s o estado (ENABLED/DISABLED), mantém o Bluetooth conectado e garante que a playlist ativa está tocando no dispositivo correto.

**Comunicação entre webapp e loop principal — via arquivos em `config/`:**

| Arquivo | Quem escreve | Quem lê | Conteúdo |
|---|---|---|---|
| `state.txt` | webapp (`/toggle`) | loop principal | `ENABLED` ou `DISABLED` |
| `speakers.json` | webapp (scan/pair/remove) | loop principal (a cada iteração) | lista de caixas BT |
| `active_playlist.txt` | webapp (`/api/playlist/select`) | loop principal (`get_active_playlist_uri`) | ID da playlist ativa |
| `bt_event.txt` | loop principal (ao conectar BT) | webapp (`/api/status/banner`) | timestamp Unix da última conexão BT |
| `play_event.txt` | loop principal (após `next_track()`) | webapp (`/api/status/banner`) | timestamp Unix do último play confirmado |

**Lock compartilhado (`shared.bt_lock`):** `shared.py` expõe um `threading.Lock` que serializa todas as chamadas ao `bluetoothctl` — tanto do loop principal quanto das rotas de scan/pair da webapp.

## 4. Fluxo de Reprodução (`ensure_spotify_playing`)

A função aceita `force_restart=False`. Com `force_restart=True`, ignora o estado atual e sempre reinicia a playlist.

**Flag `needs_restart` no loop principal:** define quando `force_restart=True` deve ser passado. É ativada em:
- Boot do serviço
- Nova conexão Bluetooth estabelecida
- Caixa Bluetooth desconectou
- Caixa removida via interface
- Transição DISABLED → ENABLED

**Sequência ao iniciar playlist:**
1. Busca o total de faixas da playlist (`sp.playlist_tracks(limit=1)`) para calcular um `random_offset` real (fallback: `randint(0, 19)`)
2. `sp.start_playback(context_uri=playlist_uri, offset={'position': random_offset})` — inicia em posição aleatória (quebra o cache de seed do Spotify por dispositivo+playlist)
3. `time.sleep(2)` → `sp.volume(50)` — define volume
4. `time.sleep(1)` → `sp.shuffle(True)` — ativa shuffle (deve ser APÓS `start_playback`, que reseta shuffle para OFF)
5. `time.sleep(1)` → `sp.next_track()` — pula para a 1ª música da fila embaralhada (garante música diferente a cada início)
6. Grava timestamp em `play_event.txt` para o banner da interface
7. `time.sleep(1)` → `sp.repeat('context')` — ativa repeat

**Retorno antecipado (sem `force_restart`):** se Spotify já está tocando a playlist certa no dispositivo certo, retorna `False` sem chamar a API — evita trocas desnecessárias.

**Erro 401:** invalida o cliente (`sp = None`); próxima iteração busca novo token no Supabase.

## 5. Token Spotify

O token de acesso é buscado via REST API do Supabase na tabela `tokens`:
- `GET /rest/v1/tokens?select=token` com header `apikey: ANON_KEY`
- O token é um **Spotify Access Token** (expira em ~1h)
- Em caso de erro 401, o loop invalida o cliente (`sp = None`) e busca um novo token na próxima iteração
- **Responsabilidade de renovação:** quem atualiza o token na tabela `tokens` é o backend (Edge Functions do Supabase). O `dj-haules` apenas consome.

## 6. Webapp — Rotas e API

### Páginas (HTML via Flask/Jinja2)

| Rota | Template | Descrição |
|---|---|---|
| `GET /` | `index.html` | Status do sistema (ATIVADO/DESATIVADO) + botão toggle |
| `GET /toggle` | — | Alterna ENABLED/DISABLED e redireciona para `/` |
| `GET /playlist` | `playlist.html` | Seleção de estilo musical |
| `GET /speakers` | `speakers.html` | Gerenciamento de caixas BT (scan, pair, remove) |
| `GET /wifi` | `wifi.html` | Configuração Wi-Fi (scan, salvar credenciais, esquecer rede) |

### Captive Portal (redirecionam para `/wifi`)

iOS, Android, Windows e Firefox detectam captive portals via estas URLs ao conectar numa rede nova. Redirecioná-las para `/wifi` faz o OS mostrar o popup de "acessar rede" automaticamente quando o celular conecta no hotspot.

`/hotspot-detect.html`, `/library/test/success.html`, `/success.html`, `/generate_204`, `/connecttest.txt`, `/ncsi.txt`, `/canonical.html`, `/redirect`

### API — Bluetooth / Caixas

| Rota | Método | Descrição |
|---|---|---|
| `POST /api/scan` | POST | Escaneia BT por 15s; retorna lista de dispositivos |
| `POST /api/pair` | POST | Pair+trust+connect (até 3 tentativas); salva em `speakers.json` |
| `GET /api/speakers/status` | GET | Status de conexão BT de cada caixa salva |
| `POST /api/speakers/remove` | POST | Remove caixa do JSON + desconecta via `bluetoothctl` |
| `GET /api/bt/status/<mac>` | GET | Verifica se MAC específico está conectado |

### API — Spotify / Banner

| Rota | Método | Descrição |
|---|---|---|
| `GET /api/status/banner` | GET | Retorna `bt_ts` e `play_ts` lidos dos arquivos de evento (sem chamada ao Spotify) |
| `GET /api/play/event` | GET | Retorna timestamp do último play confirmado |

### API — Playlist

| Rota | Método | Descrição |
|---|---|---|
| `POST /api/playlist/select` | POST | Salva ID da playlist ativa em `active_playlist.txt` |

### API — Wi-Fi

| Rota | Método | Descrição |
|---|---|---|
| `GET /api/wifi/status` | GET | SSID atual (via `nmcli dev wifi`), hotspot ativo, internet |
| `GET /api/wifi/scan` | GET | Lista redes Wi-Fi disponíveis com sinal e segurança |
| `POST /api/wifi/save` | POST | Salva novo perfil Wi-Fi (`djhaules-wifi`) e tenta conectar |
| `POST /api/wifi/forget` | POST | Remove perfil `djhaules-wifi` e ativa o hotspot de recuperação |

## 7. Banner Global (`webapp/static/banner.js`)

Script auto-contido incluído em todos os templates. Injeta um banner fixo no topo da página (z-index 9999) e persiste estado entre navegações via `localStorage`.

**Estado da máquina:**
- `hidden` → nenhum banner visível
- `loading` (âmbar): `bt_ts > lastBtTs` e recente (< 180s) e play ainda não confirmado → "Dando play na fila..."
- `success` (verde): `play_ts > lastPlayTs` e recente (< 30s), ou `state=loading` e play chegou → "🎵 Tocando na caixinha!" → some após 5s

**Persistência entre páginas:** ao carregar uma nova página, restaura o estado a partir de `localStorage`:
- `_dj_bt`: último `bt_ts` visto
- `_dj_play`: último `play_ts` visto
- `_dj_success_at`: timestamp Unix de quando o sucesso foi exibido (restaura timer com tempo restante)

Polling: `GET /api/status/banner` a cada 4s. Sem chamadas ao Spotify.

## 8. Gerenciamento de Playlists

As playlists disponíveis são definidas em `config/playlists.json` (versionado). Cada entrada tem `id`, `name`, `emoji`, `uri` (Spotify URI ou `null`), e `descricao`.

A playlist com `uri: null` usa o `PLAYLIST_URI` do `settings.ini` como fallback — é o campo para a playlist comunitária principal.

A playlist ativa é salva em `config/active_playlist.txt` (não versionado, gerado em runtime). Padrão: `brasilidades`.

## 9. Wi-Fi — Hotspot de Recuperação

Gerenciado pelo serviço `djhaules-wifi.service` que roda `scripts/wifi_monitor.sh` (como root, via NetworkManager).

**Fluxo:**
1. Aguarda 10 min (`BOOT_WAIT=600`) no boot para o NM tentar conectar normalmente. Janela longa tolera cenários de blackout onde roteador/repetidor levam minutos pra subir depois do Pi.
2. A cada 30s (`CHECK_INTERVAL`): verifica internet via `nmcli -t -f CONNECTIVITY general status`
3. Sem internet **e sem hotspot** → `try_reconnect_client` tenta subir cada perfil Wi-Fi cliente salvo (lista perfis com `nmcli con show` filtrando por tipo `802-11-wireless` exceto o hotspot); só ativa o hotspot `DJHaules-Hotspot` (SSID: `DJHaules-Config`, senha: `djhaules`, IP: `192.168.4.1`) se nenhum conectar
4. Com internet → desativa hotspot se estava ativo
5. **Escape do hotspot:** após 5 min (`HOTSPOT_ESCAPE_INTERVAL=300`) em modo AP, derruba o hotspot e tenta reconectar nos perfis cliente; se falhar, sobe o hotspot de novo e reinicia o contador. Evita ficar preso no AP quando a rede do bar só voltou minutos depois.

**Captive portal:** `scripts/captive-portal-dns.conf` configura o dnsmasq do NetworkManager para redirecionar todo DNS para o Pi enquanto o hotspot está ativo. Combinado com as rotas de captive portal do Flask, o celular abre a página de configuração automaticamente ao conectar.

**Esquecer rede:** a rota `POST /api/wifi/forget` deleta o perfil `djhaules-wifi` via `nmcli` e sobe o hotspot via `subprocess.Popen` (não-bloqueante — resposta chega antes do Pi trocar de rede).

**SSID real:** para obter o SSID conectado, usa `nmcli -t -f ACTIVE,SSID dev wifi` com `split(':', 1)` (maxsplit=1 preserva SSIDs com `:` no nome). Não usa `nmcli con show`, que retorna o nome do perfil (`djhaules-wifi`), não o SSID.

## 10. Estrutura de Arquivos

```
main.py                          # Orquestrador: inicia webapp thread + loop principal
shared.py                        # bt_lock: threading.Lock compartilhado entre main e webapp
requirements.txt                 # flask, spotipy, requests

webapp/
  app.py                         # Flask: todas as rotas e endpoints API
  templates/
    index.html                   # Página principal (on/off + status)
    playlist.html                # Seleção de estilo musical
    speakers.html                # Gerenciamento de caixas BT (scan + pair + lista)
    wifi.html                    # Configuração Wi-Fi (scan + salvar + esquecer)
  static/
    logo.png                     # Logo Haules
    banner.js                    # Banner global loading/sucesso (incluído em todos os templates)

config/
  settings.ini.template          # Template de configuração (versionado)
  settings.ini                   # Configuração real (NÃO versionado — contém segredos)
  speakers.json.template         # Template vazio para o arquivo de caixas (versionado)
  speakers.json                  # Lista de caixas BT (gerado pela webapp, não versionado)
  playlists.json                 # Definição das playlists disponíveis (versionado)
  state.txt                      # ENABLED ou DISABLED (runtime, não versionado)
  active_playlist.txt            # ID da playlist ativa (runtime, não versionado)
  bt_event.txt                   # Timestamp da última conexão BT (runtime, não versionado)
  play_event.txt                 # Timestamp do último play confirmado (runtime, não versionado)

scripts/
  setup.sh                       # Setup/reconcile idempotente — rodado no install e em todo boot
  setup_iptables.sh              # Redireciona porta 80 → 8080 (roda no ExecStartPre do djhaules.service)
  wifi_monitor.sh                # Monitor Wi-Fi: detecta sem internet e ativa hotspot
  auto_update.sh                 # git pull no boot antes de iniciar o djhaules.service
  djhaules.service               # Serviço systemd principal — loop + webapp Flask
  djhaules-wifi.service          # Serviço systemd para wifi_monitor.sh (roda como root)
  djhaules-update.service        # Serviço systemd para auto_update.sh (Before=djhaules-reconcile)
  djhaules-reconcile.service     # Serviço systemd que roda setup.sh no boot (Before=djhaules*)
  raspotify.service              # Serviço de USUÁRIO (~/.config/systemd/user/) — librespot
  captive-portal-dns.conf        # Config dnsmasq para captive portal no hotspot

docs/
  INSTALL_GUIDE_FOR_DEV.md       # Guia completo de setup no Raspberry Pi
  GUIA_PARA_O_DONO.md            # Guia de uso para o dono do bar (sem termos técnicos)
  assets/                        # Imagens usadas nos docs

README.md                        # Guia rápido de uso para funcionários do bar
CLAUDE.md                        # Este arquivo — contexto do projeto para o Claude
```

## 11. Configurações

### `config/settings.ini`

| Seção | Chave | Descrição |
|---|---|---|
| `SUPABASE` | `URL` | URL base do projeto Supabase |
| `SUPABASE` | `ANON_KEY` | Chave anônima pública do Supabase |
| `APP` | `DEVICE_NAME` | Nome do dispositivo Raspotify no Spotify — deve bater exatamente com `--name` no serviço do Raspotify (ex: `raspotify (dj-haules)`) |
| `APP` | `PLAYLIST_URI` | URI da playlist comunitária principal (ex: `spotify:playlist:XXXX`) — usada pela playlist com `uri: null` no `playlists.json` |

### `config/speakers.json`

Gerenciado automaticamente pela webapp (rotas `/api/pair` e `/api/speakers/remove`). Formato:

```json
[
  {"name": "JBL Charge 5", "mac": "AA:BB:CC:DD:EE:FF", "priority": 1},
  {"name": "Sony XB43",    "mac": "11:22:33:44:55:66", "priority": 2}
]
```

A caixa `priority: 1` é a principal. O loop tenta sempre em ordem crescente. Ao parear nova caixa pela webapp, ela vira prioridade 1 automaticamente.

### `config/playlists.json`

Define as playlists disponíveis na interface. Versionado no repositório — editar aqui para adicionar/remover estilos musicais.

```json
[
  {"id": "brasilidades", "name": "Brasilidades", "emoji": "🇧🇷", "uri": null,    "descricao": "A playlist oficial do bar"},
  {"id": "rap",          "name": "Rap BR",        "emoji": "🎤", "uri": "spotify:playlist:...", "descricao": "Os melhores do rap nacional"}
]
```

`uri: null` → usa `PLAYLIST_URI` do `settings.ini` (playlist comunitária).

## 12. Serviços systemd em Produção

São **quatro serviços de sistema** + um de usuário no Pi. Todos versionados em `scripts/` e instalados/atualizados pelo `scripts/setup.sh`:

| Serviço | Arquivo | Descrição |
|---|---|---|
| `djhaules.service` | `scripts/djhaules.service` | Serviço principal — roda `main.py` (loop + webapp Flask) |
| `djhaules-wifi.service` | `scripts/djhaules-wifi.service` | Monitor Wi-Fi + hotspot de recuperação (roda como root) |
| `djhaules-update.service` | `scripts/djhaules-update.service` | `git pull` no boot, antes dos serviços principais |
| `djhaules-reconcile.service` | `scripts/djhaules-reconcile.service` | Roda `setup.sh` no boot após o update — aplica idempotentemente configs/services novos sem precisar SSH no Pi |
| `raspotify.service` | `scripts/raspotify.service` (versionado) → `~/.config/systemd/user/raspotify.service` | Raspotify como serviço de usuário (via PipeWire). Flags: `--initial-volume 50 --volume-ctrl linear` |

**Ordem no boot:** `update → reconcile → djhaules + djhaules-wifi`. Isso garante que mudanças puxadas pelo `git pull` (incluindo nos próprios service files) entram em vigor antes dos serviços principais subirem.

**`scripts/setup.sh`:** script idempotente que detecta o usuário-alvo (substitui placeholder `seu_usuario`), copia service files / `captive-portal-dns.conf` se mudaram, atualiza venv se `requirements.txt` mudou, **reinicia o `djhaules.service` se qualquer `.py` (main, shared, webapp) mudou** (hash em `.venv/.code.sha256`), garante grupo bluetooth + linger + rfkill, e reinicia apenas as units alteradas. Rodado uma vez no setup inicial (`sudo ./scripts/setup.sh`) e automaticamente em todo boot via `djhaules-reconcile.service`.

**Workflow do dia a dia:** `git push` localmente → religa o Pi → tudo atualizado. O update puxa o código, o reconcile detecta o que mudou (service files, code, deps) e reinicia somente o necessário. Mudanças em templates/JS são picked up automaticamente pelo Flask (sem restart).

```bash
sudo systemctl status djhaules.service
sudo systemctl status djhaules-wifi.service
sudo systemctl status djhaules-update.service
sudo systemctl status djhaules-reconcile.service
systemctl --user status raspotify
```

## 13. Relação com Outros Projetos

| Projeto | Relação |
|---|---|
| `haules-landing-page` | Gerencia a playlist comunitária que o DJ Haules toca. Clientes adicionam músicas via site. O `dj-haules` consome a mesma playlist Spotify. |
| `service-haules-v2` (Supabase) | Hospeda a tabela `tokens` com o Spotify Access Token e as Edge Functions que renovam o token. |
| `haules-pos-app` | Sem relação direta. |
