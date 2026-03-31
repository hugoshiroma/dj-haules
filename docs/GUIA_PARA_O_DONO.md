
# Guia Completo do DJ Haules — Para o Dono do Bar

> Esse guia é pra você entender tudo sobre o DJ Haules: como usar no dia a dia, como conectar a caixinha de som, o que fazer quando der problema e como reconectar no Wi-Fi quando a internet mudar.

---

## O que é o DJ Haules?

O DJ Haules é uma caixinha pequena (um Raspberry Pi) que fica ligada na tomada no bar. Ele conecta automaticamente na caixa de som via Bluetooth e toca a playlist do bar no Spotify, sozinho, sem ninguém precisar conectar celular nem apertar nada.

Resumindo: ligou tudo, a música toca. Simples assim.

---

## Parte 1 — Uso no Dia a Dia

### Como a música começa a tocar

1. **Liga a caixa de som Bluetooth** do bar normalmente
2. **Aguarda uns 2 minutinhos** — o DJ Haules vai encontrar a caixinha, conectar e dar play sozinho
3. Pronto, a música começa em ordem aleatória

Não precisa mexer em nada, não precisa abrir nenhum app, não precisa conectar celular. É automático.

---

### Comportamento importante: o DJ Haules sempre volta a tocar

O DJ Haules é programado pra **sempre manter a música tocando**. Isso inclui:

- Se a música for **pausada pelo Spotify** (pelo celular, computador, ou qualquer outro app), o DJ Haules vai dar play de novo em até 30 segundos
- Se a caixa de som desconectar e reconectar, ele retoma automaticamente
- Se a internet cair brevemente e voltar, ele retoma automaticamente

**Pra parar a música de verdade, você tem duas opções:**

1. **Desativar pelo site** (recomendado): abre **http://dj-haules.local:8080** e clica em "Desativar DJ Haules"
2. **Tirar da tomada**: desliga fisicamente o DJ Haules (a caixinha pequena)

Qualquer pausa feita diretamente no Spotify vai ser desfeita automaticamente pelo sistema.

---

### Quando tiver show, DJ ou banda (desativar o DJ Haules)

Quando outra pessoa precisar usar a caixa de som, você precisa desligar o DJ Haules pra ele largar o controle.

1. Conecta o celular no **Wi-Fi do bar**
2. Abre o navegador (Chrome, Safari, qualquer um) e digita:
   > **http://dj-haules.local:8080**
3. Vai abrir uma página com um botão escrito **"Desativar DJ Haules"** — clica nele
4. A caixa de som fica livre pra quem for usar

Quando o evento acabar e quiser voltar ao normal:

1. Abre a mesma página: **http://dj-haules.local:8080**
2. Clica em **"Ativar DJ Haules"**
3. Aguarda uns 2 minutinhos e a música volta sozinha

---

## Parte 2 — Conectando a Caixa de Som Bluetooth

Precisa conectar uma caixa nova ou trocar a que tá sendo usada? Segue o passo a passo.

1. **Liga a caixa de som** e coloca ela em **modo de pareamento Bluetooth** — geralmente é segurar o botão de Bluetooth por uns segundos até a luz piscar diferente (consulta o manual da sua caixinha se não souber como fazer isso)

2. Conecta o celular no **Wi-Fi do bar**

3. Abre o navegador e digita:
   > **http://dj-haules.local:8080/speakers**

4. Clica em **"Escanear Bluetooth"** e aguarda uns 15 segundinhos

5. Vai aparecer uma lista com os dispositivos encontrados. Clica em **"Conectar e Salvar"** ao lado do nome da sua caixa

6. Pronto — a caixinha vai ser salva e o DJ Haules vai começar a usar ela automaticamente

> **Dica:** Se não aparecer a sua caixa na lista, verifica se ela tá mesmo em modo de pareamento. Às vezes precisa apertar o botão de Bluetooth por mais tempo. Também garante que ela não tá conectada em outro celular ou dispositivo antes.

---

### Se alguém conectar outro dispositivo na caixa de som

Se alguém conectar o celular na caixa de som enquanto o DJ Haules tá tocando, ele vai detectar a desconexão e tentar retomar. Alguns cenários:

- **Se o outro dispositivo desconectar**: a música volta em até 1 minuto, sem precisar fazer nada
- **Se a caixinha estiver ocupada com outro dispositivo**: o DJ Haules fica tentando a cada poucos segundos. Quando o outro dispositivo soltar, ele assume
- **Se você apertar o botão de pareamento na caixinha**: o DJ Haules vai detectar e tentar reparear automaticamente. Se não funcionar em alguns minutos, reinicia a caixinha de som (desliga e liga)

---

## Parte 3 — Quando a Internet do Bar Mudar

Se você trocar a senha do Wi-Fi ou mudar o nome da rede, o DJ Haules vai perder a conexão com a internet e parar de funcionar. Mas ele mesmo cria uma rede temporária pra você consertar isso sem precisar chamar ninguém.

### Passo 1 — Acha a rede "DJHaules-Config"

Pega qualquer celular, abre o Wi-Fi e procura uma rede chamada:

> **DJHaules-Config**

Conecta nessa rede com a senha:

> **djhaules**

⚠️ O celular pode falar que essa rede "não tem internet" — pode ignorar esse aviso e ficar conectado nela mesmo assim.

---

### Passo 2 — Abre a página de configuração

Com o celular conectado no **DJHaules-Config**, abre o navegador e digita:

> **http://192.168.4.1:8080/wifi**

> Não esquece o `http://` no começo, tá?

---

### Passo 3 — Coloca os dados do novo Wi-Fi

Na página que abrir, preenche:

- **Nome da Rede:** o nome do Wi-Fi do bar (exatamente como aparece na lista de redes, com maiúsculas, minúsculas e acentos certinhos)
- **Senha da Rede:** a nova senha do Wi-Fi

Clica em **"Salvar e Reconectar"**.

---

### Passo 4 — Aguarda uns 30 segundos

O DJ Haules vai tentar conectar na rede nova. Você vai saber que funcionou quando a rede **"DJHaules-Config"** sumir do Wi-Fi do seu celular.

---

### Passo 5 — Reinicia o DJ Haules (obrigatório)

Isso é importante pra garantir que tudo sobe certinho:

1. **Tira o DJ Haules da tomada** (a caixinha pequena)
2. **Espera 10 segundos**
3. **Liga de volta na tomada**
4. **Aguarda uns 2 minutinhos**

---

### Passo 6 — Reconecta seu celular no Wi-Fi do bar

Vai lá nas configurações de Wi-Fi do celular e conecta de volta na rede normal do bar. O DJ Haules já vai estar tocando.

---

## Parte 4 — Problemas Comuns e Soluções

| Problema | O que fazer |
|---|---|
| **A música não começou a tocar** | 1. Verifica se a caixa de som tá ligada<br>2. Aguarda mais uns 2 minutinhos<br>3. Desliga e liga a caixa de som de novo<br>4. Abre o Spotify no celular → vai em **Dispositivos** (ícone de caixinha no player) e verifica se **raspotify (dj-haules)** aparece e está selecionado. Se não aparecer, tira o DJ Haules da tomada, espera 10 segundos e liga de novo |
| **Pausei no Spotify e a música voltou sozinha** | Esse é o comportamento esperado — o DJ Haules retoma automaticamente. Pra parar de vez, usa o site **http://dj-haules.local:8080** e clica em "Desativar DJ Haules" |
| **A página de controle não abre** | 1. Verifica se o celular tá no Wi-Fi do bar<br>2. Tenta de novo: **http://dj-haules.local:8080**<br>3. Se a senha do Wi-Fi mudou, segue a Parte 3 desse guia |
| **A caixa de som não aparece no scan** | 1. Coloca a caixinha em modo de pareamento de novo<br>2. Garante que ela não tá conectada em outro dispositivo<br>3. Tenta escanear de novo |
| **A caixinha conectou em outro dispositivo e o DJ Haules não voltou** | 1. Aguarda até 1 minuto — ele tenta sozinho<br>2. Se não voltar, aperta o botão de Bluetooth na caixinha pra soltar a conexão<br>3. Se ainda não funcionar, desliga e liga a caixa de som |
| **A música tá travando ou picotando** | 1. Verifica se a caixinha do DJ Haules não tá muito longe da caixa de som<br>2. Evita objetos de metal ou muito líquido na frente da caixinha — atrapalha o sinal Bluetooth |
| **Nada funcionou** | Chama o responsável técnico |
