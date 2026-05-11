
# Guia do DJ Haules — Para o Dono do Bar

> Este guia foi feito para você instalar e usar o DJ Haules do zero, sem precisar de ajuda técnica. Leia do começo ao fim na ordem e tudo vai funcionar.

---

## O que é o DJ Haules?

O DJ Haules é uma caixinha pequena (Raspberry Pi) que fica ligada na tomada no bar. Ele conecta automaticamente na caixa de som via Bluetooth e toca a playlist do bar no Spotify, sozinho — sem ninguém precisar conectar celular, abrir app nem apertar nada.

**Resumindo:** ligou tudo, a música toca. Simples assim.

---

## Parte 1 — Primeira Instalação (passo a passo)

Siga esta sequência na ordem. Ela só precisa ser feita uma vez.

### Passo 1 — Liga o DJ Haules na tomada

Conecta a caixinha pequena na tomada. A luz vai acender. Aguarda **1 minuto** para ela inicializar.

---

### Passo 2 — Conecta o DJ Haules ao Wi-Fi do Bar

O DJ Haules precisa de internet pra funcionar. Na primeira vez, ele cria uma rede Wi-Fi temporária pra você informar a senha do bar.

**1.** Pega qualquer celular e abre as configurações de Wi-Fi.

**2.** Procura uma rede chamada:

> **DJHaules-Config**

Conecta com a senha:

> **djhaules**

**3.** Assim que conectar, o celular vai **abrir uma página automaticamente** — é o DJ Haules pedindo os dados do Wi-Fi do bar. Se não abrir sozinho em uns 10 segundos, abre o navegador e acessa:

> **http://192.168.4.1/wifi**

> Não esquece o `http://` no começo, tá?

**4.** Na página que abrir, clica em **"Ver redes Wi-Fi disponíveis"** e escolhe a rede do bar. Insere a senha e clica em **"Salvar e Reconectar"**.

**5.** Aguarda até 30 segundos. Quando a rede **DJHaules-Config sumir** do Wi-Fi do seu celular, significa que deu certo — o DJ Haules se conectou na rede do bar.

**6.** Tira o DJ Haules da tomada, espera 10 segundos e liga de volta. Aguarda mais 1 minuto.

**7.** Reconecta seu celular na rede normal do bar.

---

### Passo 3 — Conecta a Caixa de Som Bluetooth

Agora que o DJ Haules está na internet, vamos conectar a caixa de som.

**1.** Liga a caixa de som e coloca ela em **modo de pareamento Bluetooth** — geralmente é segurar o botão de Bluetooth por alguns segundos até a luz piscar diferente (consulta o manual da sua caixinha se não souber).

**2.** Ainda com o celular no Wi-Fi do bar, abre o navegador e acessa:

> **http://dj-haules.local/speakers**

**3.** Clica em **"Procurar Caixas de Som por Bluetooth"** e aguarda ~15 segundos.

**4.** Apareceu sua caixa na lista? Clica em **"Salvar"** ao lado do nome dela.

**5.** O sistema vai tentar conectar — pode levar até 1 minuto. Aguarda aparecer a mensagem de confirmação.

> **Dica:** Se a caixa não aparecer na lista, verifica se ela está mesmo em modo de pareamento (luz piscando). Garante também que ela não está conectada em outro celular.

---

### Passo 4 — Pronto!

Após salvar a caixa, o DJ Haules vai começar a tocar em até 30 segundos. A partir de agora, basta ligar a caixa de som — a música vai começar sozinha.

---

## Parte 2 — Uso no Dia a Dia

### Como a música começa a tocar

1. **Liga a caixa de som Bluetooth** normalmente
2. **Aguarda uns 2 minutinhos** — o DJ Haules vai encontrar a caixinha, conectar e dar play sozinho
3. Pronto, a música começa em ordem aleatória

Não precisa mexer em nada, não precisa abrir nenhum app.

---

### Trocando o estilo musical

O DJ Haules tem playlists pré-configuradas. Para trocar o estilo que está tocando:

1. Conecta o celular no **Wi-Fi do bar**
2. Abre o navegador e acessa: **http://dj-haules.local**
3. Clica em **"🎵 Estilo Musical"**
4. Escolhe o estilo — a troca começa em até 30 segundos, sem precisar reiniciar nada

---

### Comportamento importante: o DJ Haules sempre volta a tocar

O DJ Haules é programado pra **sempre manter a música tocando**. Isso inclui:

- Se a música for **pausada pelo Spotify** (pelo celular, computador, ou qualquer outro app), o DJ Haules vai dar play de novo em até 30 segundos
- Se a caixa de som desconectar e reconectar, ele retoma automaticamente
- Se a internet cair brevemente e voltar, ele retoma automaticamente

**Pra parar a música de verdade, você tem duas opções:**

1. **Desativar pelo site** (recomendado): abre **http://dj-haules.local** e clica em "Desativar DJ Haules"
2. **Tirar da tomada**: desliga fisicamente o DJ Haules (a caixinha pequena)

Qualquer pausa feita diretamente no Spotify vai ser desfeita automaticamente pelo sistema.

---

### Quando tiver show, DJ ou banda (desativar o DJ Haules)

Quando outra pessoa precisar usar a caixa de som, você precisa desligar o DJ Haules pra ele largar o controle.

1. Conecta o celular no **Wi-Fi do bar**
2. Abre o navegador e acessa: **http://dj-haules.local**
3. Clica em **"Desativar DJ Haules"**
4. A caixa de som fica livre pra quem for usar

Quando o evento acabar:

1. Abre a mesma página: **http://dj-haules.local**
2. Clica em **"Ativar DJ Haules"**
3. Aguarda uns 2 minutinhos e a música volta sozinha

---

## Parte 3 — Quando a Internet do Bar Mudar

Se você trocar a senha do Wi-Fi ou mudar o nome da rede, o DJ Haules vai perder a conexão. Mas ele mesmo cria uma rede temporária pra você consertar isso, igual à instalação inicial.

### Passo 1 — Conecta no DJHaules-Config

Pega qualquer celular, abre o Wi-Fi e conecta na rede:

> **DJHaules-Config** (senha: **djhaules**)

Assim que conectar, o celular vai **abrir a página de configuração automaticamente**. Se não abrir sozinho, acessa no navegador:

> **http://192.168.4.1/wifi**

### Passo 2 — Coloca os dados do novo Wi-Fi

Clica em **"Ver redes Wi-Fi disponíveis"**, escolhe a rede do bar, insere a nova senha e clica em **"Salvar e Reconectar"**.

### Passo 3 — Aguarda uns 30 segundos

Quando a rede **"DJHaules-Config" sumir** do Wi-Fi do seu celular, significa que conectou.

### Passo 4 — Reinicia o DJ Haules

1. Tira o DJ Haules da tomada
2. Espera 10 segundos
3. Liga de volta na tomada
4. Aguarda uns 2 minutinhos

### Passo 5 — Reconecta seu celular no Wi-Fi do bar

O DJ Haules já vai estar tocando.

---

## Parte 4 — Trocando ou Adicionando uma Caixa de Som

Precisa conectar uma caixa nova ou trocar a que está sendo usada?

1. **Liga a nova caixa de som** e coloca em **modo de pareamento Bluetooth** (luz piscando)
2. Conecta o celular no **Wi-Fi do bar**
3. Abre o navegador: **http://dj-haules.local/speakers**
4. Clica em **"Procurar Caixas de Som por Bluetooth"** e aguarda ~15 segundos
5. Clica em **"Salvar"** ao lado do nome da sua caixa
6. Pronto — ela passa a ser a caixa principal automaticamente

### Se alguém conectar outro dispositivo na caixa de som

- **Se o outro dispositivo desconectar**: a música volta em até 1 minuto, sozinha
- **Se a caixinha estiver ocupada**: o DJ Haules fica tentando. Quando o outro dispositivo soltar, ele assume
- **Se apertar o botão de pareamento na caixinha**: o DJ Haules tenta reparear automático. Se não funcionar em alguns minutos, desliga e liga a caixa de som

---

## Parte 5 — Problemas Comuns e Soluções

| Problema | O que fazer |
|---|---|
| **A música não começou a tocar** | 1. Verifica se a caixa de som tá ligada e em alcance<br>2. Aguarda mais uns 2 minutinhos<br>3. Desliga e liga a caixa de som de novo<br>4. Abre o Spotify no celular → ícone de caixinha no player → verifica se **raspotify (dj-haules)** aparece. Se não aparecer, tira o DJ Haules da tomada, espera 10 segundos e liga de novo |
| **Pausei no Spotify e a música voltou sozinha** | É o comportamento esperado. Pra parar de vez, acessa **http://dj-haules.local** e clica em "Desativar DJ Haules" |
| **A página de controle não abre** | 1. Verifica se o celular tá no Wi-Fi do bar (não no 4G)<br>2. Tenta de novo: **http://dj-haules.local**<br>3. Se a senha do Wi-Fi mudou, segue a Parte 3 deste guia |
| **A página abriu mas está estranha / sem estilo** | Tenta acessar com `http://` na frente: **http://dj-haules.local** |
| **A caixa de som não aparece no scan** | 1. Coloca a caixinha em modo de pareamento de novo<br>2. Garante que ela não tá conectada em outro dispositivo<br>3. Tenta escanear de novo |
| **A caixinha conectou em outro dispositivo e o DJ Haules não voltou** | 1. Aguarda até 1 minuto — ele tenta sozinho<br>2. Se não voltar, aperta o botão de Bluetooth na caixinha<br>3. Se ainda não funcionar, desliga e liga a caixa de som |
| **A música tá travando ou picotando** | 1. Aproxima a caixinha do DJ Haules da caixa de som<br>2. Evita objetos de metal ou muito líquido entre as duas — atrapalha o sinal Bluetooth |
| **Nada funcionou** | Chama o responsável técnico |

---

## Links Rápidos

| O que fazer | Endereço |
|---|---|
| Ligar/desligar o DJ Haules | http://dj-haules.local |
| Trocar o estilo musical | http://dj-haules.local/playlist |
| Gerenciar caixas de som | http://dj-haules.local/speakers |
| Configurar Wi-Fi (via rede do bar) | http://dj-haules.local/wifi |
| Configurar Wi-Fi (via DJHaules-Config) | http://192.168.4.1/wifi |
