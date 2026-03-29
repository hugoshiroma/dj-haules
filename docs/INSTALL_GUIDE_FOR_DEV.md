
# Guia de Instalação do DJ Haules (Para Desenvolvedores)

Este guia contém o passo a passo técnico para configurar o ambiente no Raspberry Pi.

---

## Requisitos de Hardware

Para este projeto, o requisito mínimo e de melhor custo-benefício é o **Raspberry Pi Zero 2 W**.

Ele já possui Wi-Fi, Bluetooth e o processador de 64-bit necessários para rodar o sistema de forma estável.

Modelos mais potentes como o **Raspberry Pi 3 Model B+** ou o **Raspberry Pi 4** também funcionam perfeitamente, mas não são estritamente necessários.

---

## 1. Preparando o Raspberry Pi

1.  **Baixe o Raspberry Pi Imager:** Faça o download no [site oficial](https://www.raspberrypi.com/software/).
2.  **Grave o Sistema Operacional:**
    *   Use o Imager para gravar o **Raspberry Pi OS Lite (64-bit)** em um cartão microSD.
    *   Nas configurações avançadas (ícone da engrenagem), já configure:
        *   **Hostname:** `dj-haules.local` (para o endereço amigável).
        *   **Habilite o SSH**.
        *   **Configure o Wi-Fi** com os dados da rede do bar.

3.  **Primeiro Boot e Acesso:**
    *   Insira o cartão no Pi e ligue-o.
    *   Após alguns minutos, acesse-o via SSH pelo terminal: `ssh seu_usuario@dj-haules.local`.

---

## 2. Instalando Dependências

Execute os seguintes comandos no terminal do Pi para instalar tudo que o projeto precisa.

```bash
# Atualizar o sistema
sudo apt update && sudo apt upgrade -y

# Instalar pacotes essenciais e de áudio
sudo apt install -y python3-pip python3-venv bluez libasound2-dev

# Instalar o Raspotify (cliente Spotify Connect)
curl -sL https://dtcooper.github.io/raspotify/install.sh | sh

# Reinicie para garantir que tudo foi carregado
sudo reboot
```

---

## 3. Configurando o Projeto

1.  **Instale o Git e clone o repositório:**
    ```bash
    sudo apt install -y git
    git clone https://github.com/hugoshiroma/dj-haules.git /home/$USER/dj-haules
    cd /home/$USER/dj-haules
    ```

2.  **Crie o Ambiente Virtual Python:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Instale as bibliotecas Python:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as Variáveis:**
    *   Copie os templates de configuração:
        ```bash
        cp config/settings.ini.template config/settings.ini
        cp config/speakers.json.template config/speakers.json
        ```
    *   Edite o `config/settings.ini` com a URL e Chave Anônima (ANON_KEY) do Supabase e o URI da playlist Spotify (`PLAYLIST_URI`):
        ```bash
        nano config/settings.ini
        ```
    *   **As caixas de som são configuradas pela interface web** — não é necessário editar o `speakers.json` manualmente. Veja a seção 4.1 abaixo.

---

## 4.1 Pareando a Caixa de Som (via Interface Web)

Após iniciar o serviço (seção 5), o pareamento de caixas é feito pela própria interface web — sem necessidade de terminal.

1.  No celular conectado ao Wi-Fi do bar, acesse **http://dj-haules.local:8080/speakers**.
2.  Ligue a caixa de som e coloque-a em **modo de pareamento** (geralmente segurando o botão Bluetooth).
3.  Clique em **"Escanear Bluetooth"** e aguarde ~8 segundos.
4.  Na lista de dispositivos encontrados, clique em **"Conectar e Salvar"** ao lado da sua caixa.
5.  Pronto. A caixa é salva como principal e o DJ Haules começará a usá-la na próxima iteração.

Para **trocar de caixa** no futuro, basta repetir os passos acima com a nova caixa — ela assumirá automaticamente a prioridade 1.

---

## 4.2 Testando a Recuperação de Wi-Fi

Para verificar se o hotspot de recuperação funciona antes de precisar dele:

```bash
# Simule perda de conexão desativando temporariamente o Wi-Fi normal
sudo nmcli con down "$(nmcli -t -f NAME,TYPE con show --active | grep '802-11-wireless' | cut -d: -f1)"
# Aguarde ~30s. O monitor deve ativar o hotspot "DJHaules-Config"
sudo systemctl status djhaules-wifi.service
# Para restaurar manualmente:
sudo nmcli con down "DJHaules-Hotspot"
sudo nmcli con up djhaules-wifi
```

---

## 4. Configurando o Bluetooth (Método Manual — Opcional)

1.  **Abra a ferramenta de Bluetooth:**
    ```bash
    bluetoothctl
    ```
2.  **Ligue o modo de escaneamento para encontrar sua caixa de som:**
    ```bash
    scan on
    ```
3.  **Identifique o MAC Address** da sua caixa (ex: `AA:BB:CC:11:22:33`).
4.  **Pareie, confie e conecte:**
    ```bash
    pair AA:BB:CC:11:22:33
    trust AA:BB:CC:11:22:33
    connect AA:BB:CC:11:22:33
    ```
5.  **Anote o MAC Address** e coloque-o no arquivo `config/settings.ini`.

---

## 5. Configurando a Resiliência Wi-Fi (Hotspot de Recuperação)

Este passo instala o monitor de Wi-Fi, que cria automaticamente um hotspot de recuperação caso a senha ou o nome da rede do bar seja alterado.

> **Requisito:** Raspberry Pi OS **Bookworm** (2023+), que usa o NetworkManager por padrão.

### Como funciona

1. O script `wifi_monitor.sh` roda como serviço systemd em background.
2. Após o boot, ele aguarda 60 segundos para o Pi tentar conectar normalmente.
3. Se não houver internet, ativa o hotspot **"DJHaules-Config"** (senha: `djhaules`) no IP `192.168.4.1`.
4. O dono conecta o celular nesse hotspot e acessa **http://192.168.4.1:8080/wifi**.
5. Após salvar as novas credenciais, o Pi reconecta e o hotspot é desativado automaticamente.

### Instalação

1.  **Torne o script executável:**
    ```bash
    chmod +x /home/seu_usuario/dj-haules/scripts/wifi_monitor.sh
    ```

2.  **Copie e instale o serviço systemd:**
    ```bash
    # Edite o arquivo para substituir "seu_usuario" antes de copiar
    sed -i "s/seu_usuario/$USER/g" /home/$USER/dj-haules/scripts/djhaules-wifi.service
    sudo cp /home/$USER/dj-haules/scripts/djhaules-wifi.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable djhaules-wifi.service
    sudo systemctl start djhaules-wifi.service
    ```

3.  **Verifique se o serviço está rodando:**
    ```bash
    sudo systemctl status djhaules-wifi.service
    ```

---

## 6. Rodando como um Serviço (Automático)

Para que o DJ Haules inicie com o Pi, vamos criar um serviço systemd.

1.  **Crie o arquivo de serviço** (substitua `seu_usuario` pelo seu usuário real):
    ```bash
    sudo bash -c "cat > /etc/systemd/system/djhaules.service" << EOF
    [Unit]
    Description=DJ Haules Service
    After=network.target sound.target bluetooth.target

    [Service]
    User=$USER
    Group=$USER
    WorkingDirectory=/home/$USER/dj-haules
    ExecStart=/home/$USER/dj-haules/.venv/bin/python /home/$USER/dj-haules/main.py
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    EOF
    ```

2.  **Habilite e inicie o serviço:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable djhaules.service
    sudo systemctl start djhaules.service
    ```

3.  **Verifique o status** para ver se está tudo rodando:
    ```bash
    sudo systemctl status djhaules.service
    ```

Pronto! O DJ Haules agora está configurado para iniciar e rodar automaticamente.

---

## 7. Atualizando o Projeto

Para puxar uma nova versão do código sem precisar reconfigurar nada:

```bash
cd /home/$USER/dj-haules

# Para o serviço, atualize e reinicie
sudo systemctl stop djhaules.service
git pull
source .venv/bin/activate && pip install -r requirements.txt
sudo systemctl start djhaules.service
```

> O `config/settings.ini` **não é sobrescrito** pelo `git pull` — suas credenciais ficam preservadas.
