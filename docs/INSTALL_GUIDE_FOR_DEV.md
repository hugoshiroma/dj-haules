
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
        - **Hostname:** `djhaules` (o endereço ficará `djhaules.local`)
        - **Usuário e senha:** defina um usuário (ex: `haules`) e **obrigatoriamente uma senha** — o SSH exige isso
        - **Habilite o SSH**
        - **Configure o Wi-Fi** com os dados da rede do bar

3. **Primeiro Boot e Acesso:**
    - Insira o cartão no Pi e ligue-o.
    - Após alguns minutos, acesse via SSH:
        ```bash
        ssh haules@djhaules.local
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
| `APP > DEVICE_NAME` | `raspotify (djhaules)` — deve bater exatamente com o nome definido no Raspotify |
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
  --name "raspotify (djhaules)" \
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

## 7. Instalando o Serviço Principal (DJ Haules)

```bash
# Tornar o script de iptables executável
chmod +x /home/$USER/dj-haules/scripts/setup_iptables.sh

sudo bash -c "cat > /etc/systemd/system/djhaules.service << EOF
[Unit]
Description=DJ Haules Service
After=network.target sound.target bluetooth.target

[Service]
User=$USER
Group=$USER
WorkingDirectory=/home/$USER/dj-haules
ExecStartPre=/usr/sbin/rfkill unblock bluetooth
ExecStartPre=+/home/$USER/dj-haules/scripts/setup_iptables.sh
ExecStart=/home/$USER/dj-haules/.venv/bin/python /home/$USER/dj-haules/main.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable djhaules.service
sudo systemctl start djhaules.service
sudo systemctl status djhaules.service
```

> O `ExecStartPre` com `rfkill` garante que o Bluetooth nunca fique bloqueado após um reboot.
> O `ExecStartPre` com `setup_iptables.sh` redireciona porta 80 → 8080, permitindo acessar a interface via `http://djhaules.local` sem precisar digitar a porta.

---

## 8. Configurando a Resiliência Wi-Fi (Hotspot de Recuperação + Captive Portal)

Se a senha do Wi-Fi do bar for alterada, o Pi ativa automaticamente um hotspot para reconfiguração. O captive portal faz o celular **abrir a página de configuração automaticamente** ao conectar no hotspot.

> **Requisito:** Raspberry Pi OS **Bookworm** (2023+) com NetworkManager.

```bash
# Instalar a configuração de DNS para captive portal
sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d
sudo cp /home/$USER/dj-haules/scripts/captive-portal-dns.conf \
    /etc/NetworkManager/dnsmasq-shared.d/djhaules-captive.conf

# Tornar o script executável
chmod +x /home/$USER/dj-haules/scripts/wifi_monitor.sh

# Instalar o serviço systemd
sed -i "s/seu_usuario/$USER/g" /home/$USER/dj-haules/scripts/djhaules-wifi.service
sudo cp /home/$USER/dj-haules/scripts/djhaules-wifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable djhaules-wifi.service
sudo systemctl start djhaules-wifi.service
```

Quando o Pi perder a internet, ele cria a rede **"DJHaules-Config"** (senha: `djhaules`). Ao conectar, o celular detecta o captive portal e **abre a página de configuração automaticamente**. Caso não abra, acesse manualmente `http://192.168.4.1/wifi`.

Pela interface (`http://djhaules.local/wifi`), também é possível usar **"Esquecer rede"** para remover as credenciais salvas e retornar ao modo hotspot voluntariamente — útil para trocar de rede sem esperar a internet cair.

---

## 9. Pareando a Caixa de Som (via Interface Web)

Com todos os serviços rodando:

1. No celular conectado ao Wi-Fi do bar, acesse **http://djhaules.local/speakers**
2. Ligue a caixa de som e coloque-a em **modo de pareamento**
3. Clique em **"Procurar Caixas de Som por Bluetooth"** e aguarde ~15 segundos
4. Clique em **"Conectar"** ao lado da sua caixa

A caixa é salva como prioridade 1 e o DJ Haules começará a tocar automaticamente em até 30s.

> **Se o scan não encontrar nada:** abra um terminal no Pi, rode `bluetoothctl` e depois `scan on`. Mantenha aberto por 20s com a caixinha em modo pareamento. Depois feche e tente novamente pela interface web — o scan da webapp funciona melhor após uma sessão manual prévia.

---

## 10. Atualização Automática no Boot

O Pi atualiza o código automaticamente ao ligar (inclusive após corte de energia), desde que tenha internet. Basta fazer `git push` do desenvolvimento e religar o Pi para ele pegar as novidades.

```bash
# Tornar o script executável
chmod +x /home/$USER/dj-haules/scripts/auto_update.sh

# Substituir "seu_usuario" pelo seu usuário real no arquivo do serviço
sed -i "s/seu_usuario/$USER/g" /home/$USER/dj-haules/scripts/djhaules-update.service

# Instalar o serviço
sudo cp /home/$USER/dj-haules/scripts/djhaules-update.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable djhaules-update.service
```

O serviço roda `git pull origin main --ff-only` antes do `djhaules.service` iniciar. Se não houver internet, ignora e sobe normalmente. Logs em:

```bash
sudo journalctl -t djhaules-update
```

> O `config/settings.ini` e `config/speakers.json` **não são sobrescritos** pelo `git pull` — suas configurações e caixas salvas ficam preservadas.

---

## 11. Verificando o Sistema Completo

```bash
# Status de todos os serviços
sudo systemctl status djhaules.service
sudo systemctl status djhaules-wifi.service
sudo systemctl status djhaules-update.service
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
Iniciando playlist comunitária no dispositivo 'raspotify (djhaules)'...
Shuffle aplicado — música aleatória iniciada.
```

---

## 12. Atualizando o Projeto Manualmente

```bash
cd /home/$USER/dj-haules
sudo systemctl stop djhaules.service
git pull
source .venv/bin/activate && pip install -r requirements.txt
sudo systemctl start djhaules.service
```
