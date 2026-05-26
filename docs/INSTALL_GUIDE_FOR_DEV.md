
# Guia de Instalação do DJ Haules (Para Desenvolvedores)

Este guia contém o passo a passo técnico **completo e validado** para configurar o ambiente no Raspberry Pi.

> **Atenção:** Siga os passos na ordem. Vários deles dependem dos anteriores.

---

## Requisitos de Hardware

O requisito mínimo é o **Raspberry Pi Zero 2 W** (Wi-Fi + Bluetooth integrados, 64-bit).

Modelos mais potentes (Pi 3B+, Pi 4) também funcionam.

---

## 1. Preparando o Raspberry Pi

1. **Baixe o Raspberry Pi Imager:** [raspberrypi.com/software](https://www.raspberrypi.com/software/)

2. **Grave o Sistema Operacional:**
    - Use o Imager para gravar o **Raspberry Pi OS Desktop (64-bit)** em um cartão microSD.
    - > ⚠️ **Use a versão Desktop, não a Lite.** O sistema de áudio PipeWire (necessário para Bluetooth) só está disponível na versão Desktop.
    - Nas configurações avançadas (ícone da engrenagem), configure:
        - **Hostname:** `dj-haules` (o endereço ficará `dj-haules.local`)
        - **Usuário e senha:** defina um usuário (ex: `haules`) e **obrigatoriamente uma senha** — o SSH exige isso
        - **Habilite o SSH**
        - **Configure o Wi-Fi** com os dados da rede do bar

3. **Primeiro Boot e Acesso:**
    - Insira o cartão no Pi e ligue-o.
    - Após alguns minutos, acesse via SSH:
        ```bash
        ssh haules@dj-haules.local
        ```

---

## 2. Instalando Dependências

Execute os comandos abaixo no terminal do Pi:

```bash
# Atualizar o sistema
sudo apt update && sudo apt upgrade -y

# Pacotes essenciais
sudo apt install -y git python3-pip python3-venv bluez libasound2-dev

# Plugin ALSA do PipeWire — necessário para Bluetooth funcionar com librespot
sudo apt install -y pipewire-alsa

# Instalar o Raspotify (cliente Spotify Connect)
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh

# Reinicie para garantir que tudo foi carregado
sudo reboot
```

---

## 3. Configurando o Bluetooth

Após reiniciar:

```bash
# Adicionar o usuário ao grupo bluetooth (necessário para usar bluetoothctl sem sudo)
sudo usermod -aG bluetooth $USER

# Desbloquear o Bluetooth permanentemente
sudo rfkill unblock bluetooth

# Confirmar que está desbloqueado (deve mostrar "Soft blocked: no")
rfkill list
```

> ⚠️ **Desconecte e reconecte o SSH** após o `usermod` para o grupo fazer efeito.

---

## 4. Clonando o Projeto

```bash
git clone https://github.com/hugoshiroma/dj-haules.git /home/$USER/dj-haules
cd /home/$USER/dj-haules

# Criar e ativar o ambiente virtual Python
python3 -m venv .venv
source .venv/bin/activate

# Instalar bibliotecas
pip install -r requirements.txt
```

---

## 5. Configurando o Projeto

```bash
cp config/settings.ini.template config/settings.ini
nano config/settings.ini
```

Preencha os campos:

| Chave | Valor |
|---|---|
| `SUPABASE > URL` | URL do projeto Supabase |
| `SUPABASE > ANON_KEY` | Chave anônima do Supabase |
| `APP > DEVICE_NAME` | `raspotify (dj-haules)` — deve bater exatamente com o nome definido no Raspotify |
| `APP > PLAYLIST_URI` | URI da playlist comunitária (ex: `spotify:playlist:XXXX`) |

> **Como obter o `PLAYLIST_URI`:** abra a playlist no Spotify Desktop → botão direito → "Compartilhar" → "Copiar URI da playlist".

O arquivo `config/playlists.json` (versionado) define os estilos musicais disponíveis na interface. A entrada com `"uri": null` usa o `PLAYLIST_URI` do `settings.ini` — é o slot para a playlist comunitária principal. As outras entradas têm URI própria. Edite esse arquivo para adicionar ou remover estilos.

---

## 6. Configurando o Raspotify

O Raspotify é o cliente Spotify Connect que faz o Pi aparecer como dispositivo de áudio. Ele precisa ser configurado cuidadosamente.

### 6.1 Ajustando o arquivo de configuração

```bash
sudo chmod 644 /etc/raspotify/conf
sudo nano /etc/raspotify/conf
```

Faça estas alterações:

**a) Mude o backend para ALSA** (o PulseAudio não funciona com serviço de sistema):
```
LIBRESPOT_BACKEND=alsa
```

**b) Comente a linha que desabilita o cache de credenciais** (necessário para autenticação persistir):
```
#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=
```

**c) Remova a senha caso tenha adicionado** (autenticação por senha foi descontinuada pelo Spotify):
- Apague qualquer linha com `LIBRESPOT_PASSWORD=`

### 6.2 Autenticação OAuth (feita uma única vez)

O Spotify desativou login por senha. É necessário autenticar via OAuth uma vez para salvar as credenciais permanentemente.

```bash
# Corrige dono do diretório de cache para o usuário atual
sudo chown -R $USER:$USER /var/lib/raspotify /var/cache/raspotify

# Executa o OAuth interativo
librespot --enable-oauth --system-cache /var/lib/raspotify
```

Um link aparecerá no terminal. **Abra o browser no próprio Raspberry Pi** (Chromium), cole o link, faça login com a conta Spotify do bar e autorize. O callback voltará para o librespot automaticamente e as credenciais serão salvas.

Após concluir, pressione `Ctrl+C`.

### 6.3 Desabilitar o serviço de sistema e criar serviço de usuário

> **Por que serviço de usuário?** O Raspotify precisa acessar o PipeWire para rotear o áudio para o Bluetooth. O PipeWire roda na sessão do usuário — serviços de sistema (root) não conseguem acessá-lo, independente de configuração.

```bash
# Desabilitar o serviço de sistema do Raspotify
sudo systemctl stop raspotify
sudo systemctl disable raspotify

# Habilitar linger para que serviços do usuário iniciem no boot
sudo loginctl enable-linger $USER

# Criar o serviço de usuário
mkdir -p ~/.config/systemd/user/
cat > ~/.config/systemd/user/raspotify.service << 'EOF'
[Unit]
Description=Raspotify (Spotify Connect Client)
After=pipewire.service sound.target
Wants=pipewire.service

[Service]
ExecStart=/usr/bin/librespot \
  --name "raspotify (dj-haules)" \
  --backend alsa \
  --system-cache /var/lib/raspotify \
  --quiet
Restart=always
RestartSec=10
StartLimitIntervalSec=120s
StartLimitBurst=6

[Install]
WantedBy=default.target
EOF

# Ativar e iniciar
systemctl --user daemon-reload
systemctl --user enable raspotify
systemctl --user start raspotify

# Verificar
systemctl --user status raspotify
```

Deve aparecer `active (running)` e nos logs: `Using AlsaSink` e `Published zeroconf service` sem erros.

---

## 7. Instalando todos os serviços (setup.sh)

A partir daqui um único comando faz **todo** o resto: instala os 4 serviços systemd (`djhaules`, `djhaules-wifi`, `djhaules-update`, `djhaules-reconcile`), configura o captive portal DNS, ajusta permissões, grupos e linger:

```bash
cd /home/$USER/dj-haules
sudo ./scripts/setup.sh
```

O script é **idempotente** — pode rodar quantas vezes quiser. Detecta automaticamente o usuário-alvo (substitui o placeholder `seu_usuario` nos service files), compara cada arquivo com a versão instalada e só atualiza o que mudou.

**Pra sempre:** uma vez instalado, o `djhaules-reconcile.service` roda em todo boot logo após o `djhaules-update.service` (git pull), aplicando quaisquer mudanças que tenham chegado do repositório. Você nunca mais precisa entrar no Pi pra aplicar mudanças manualmente em service files ou configs.

### O que cada serviço faz

| Serviço | Função |
|---|---|
| `djhaules-update.service` | `git pull origin main` no boot — pega código novo |
| `djhaules-reconcile.service` | Roda `setup.sh` no boot — aplica configs/services novos |
| `djhaules.service` | Loop principal Python + webapp Flask |
| `djhaules-wifi.service` | Monitor Wi-Fi: ativa hotspot de recuperação se cair internet |

### Hotspot de Recuperação

Se a senha do Wi-Fi do bar for alterada, o Pi ativa automaticamente o hotspot **"DJHaules-Config"** (senha: `djhaules`). Ao conectar pelo celular, o captive portal **abre a página de configuração automaticamente**. Caso não abra, acesse `http://192.168.4.1/wifi`.

Pela interface (`http://dj-haules.local/wifi`), use **"Esquecer rede"** pra remover as credenciais salvas e retornar ao hotspot voluntariamente.

> **Requisito:** Raspberry Pi OS **Bookworm** (2023+) com NetworkManager.

---

## 8. Pareando a Caixa de Som (via Interface Web)

Com todos os serviços rodando:

1. No celular conectado ao Wi-Fi do bar, acesse **http://dj-haules.local/speakers**
2. Ligue a caixa de som e coloque-a em **modo de pareamento**
3. Clique em **"Procurar Caixas de Som por Bluetooth"** e aguarde ~15 segundos
4. Clique em **"Conectar"** ao lado da sua caixa

A caixa é salva como prioridade 1 e o DJ Haules começará a tocar automaticamente em até 30s.

> **Se o scan não encontrar nada:** abra um terminal no Pi, rode `bluetoothctl` e depois `scan on`. Mantenha aberto por 20s com a caixinha em modo pareamento. Depois feche e tente novamente pela interface web — o scan da webapp funciona melhor após uma sessão manual prévia.

---

## 9. Atualização Automática no Boot

Já configurada pelo `setup.sh` na seção 7. O `djhaules-update.service` roda `git pull origin main --ff-only` antes do `djhaules.service` iniciar, e o `djhaules-reconcile.service` aplica em seguida quaisquer mudanças que tenham chegado em service files, scripts ou configs.

Workflow do dia a dia: `git push` localmente → religar o Pi (ou `sudo reboot` via SSH) → tudo atualizado automaticamente.

```bash
# Ver logs do update e do reconcile
sudo journalctl -t djhaules-update
sudo journalctl -u djhaules-reconcile.service
```

> O `config/settings.ini` e `config/speakers.json` **não são sobrescritos** pelo `git pull` — suas configurações e caixas salvas ficam preservadas.

---

## 10. Verificando o Sistema Completo

```bash
# Status de todos os serviços
sudo systemctl status djhaules.service
sudo systemctl status djhaules-wifi.service
sudo systemctl status djhaules-update.service
sudo systemctl status djhaules-reconcile.service
systemctl --user status raspotify

# Logs em tempo real do DJ Haules
sudo journalctl -u djhaules.service -f

# Logs do Raspotify
journalctl --user -u raspotify -f

# Logs do monitor Wi-Fi
sudo journalctl -u djhaules-wifi.service -f
```

O sistema está funcionando quando os logs do DJ Haules mostrarem:
```
Já conectado a 'Nome da Caixinha'.
Iniciando playlist comunitária no dispositivo 'raspotify (dj-haules)'...
Shuffle aplicado — música aleatória iniciada.
```

---

## 11. Atualizando o Projeto Manualmente

Em geral não é necessário — basta `git push` e religar o Pi. Mas se quiser forçar agora:

```bash
cd /home/$USER/dj-haules
git pull
sudo ./scripts/setup.sh        # aplica configs novas, reinicia serviços alterados
```

O `setup.sh` detecta sozinho o que mudou (service files, captive portal, `requirements.txt`) e reinicia apenas o necessário.
