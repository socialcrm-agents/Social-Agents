# Base de conhecimento — Editor Viral (atendimento ao cliente)

Use só o que está aqui. Se a resposta não estiver nesta base, encaminhe para o suporte humano.

---

## 1. Os produtos

| Produto | O que é | Precisa instalar? |
|---|---|---|
| **Corte Viral** (produto de entrada) | Skill do Claude Code que edita o vídeo bruto: corta pausas, gaguejos e tomadas repetidas; legenda animada palavra por palavra (3 estilos); zoom dinâmico no rosto; palavra gigante atrás da cabeça; efeitos sonoros (whoosh, pop, boom, ding...); tremida, clarão e glitch; correção por texto ("legenda maior", "tira o começo"); vídeo de antes/depois. | Sim: Claude Code + Python + ffmpeg |
| **Pacote Motion 3D** (acelerador) | Soma-se ao Corte Viral. Traz 23 blocos de animação (moldura 3D com explicação, estúdio 3D no lugar do fundo, clones, chat de IA digitando, carrossel 3D, logo 3D seguindo a mão, card pegando fogo, notificações de venda, checklist, mapa, infográfico...). Também traz gatilhos automáticos pela fala, kit de marca (cores, fontes, CTAs), versões de 30 s e 15 s e uma versão por gancho. | Sim: o mesmo acima + Node.js 18+ + Playwright/Chromium |
| **Editor no WhatsApp** (SaaS) | A pessoa manda o vídeo pelo WhatsApp e recebe editado. Inclui tudo acima. Não precisa instalar nada. | Não |

Estilos de edição: **Reels Viral** (legenda grande com a palavra ativa amarela, cortes secos), **Anúncio de Alta
Conversão** (legenda em caixa, faixa de gancho, botão de CTA, barra de progresso) e **Editorial Premium**
(ritmo calmo, serifa itálica dourada, título discreto).

Formatos: 9:16 (Reels/TikTok/Shorts), 16:9 (YouTube, aula, podcast), 1:1 e 4:5 (feed).

---

## 2. O que NÃO funciona (dúvida mais comum)

- **Colar o zip no ChatGPT ou na conversa normal do Claude.ai não edita o vídeo.** O editor roda programas de
  verdade no computador (ffmpeg, modelos de IA e o navegador que gera as animações). A conversa comum roda código
  numa caixinha com limite de tempo e tamanho e sem esses programas. Por isso fica lenta, erra ou não termina.
- O lugar certo é o **Claude Code**: o app desktop, o terminal ou o claude.ai/code com o repositório.
- Quem não quer instalar nada deve usar o **Editor no WhatsApp**.

---

## 3. Requisitos

- **Claude Code** com um plano pago do Claude: o editor usa o Claude para decidir os cortes e escrever
  gancho e CTA.
- **Python 3.10 ou mais novo.**
- **ffmpeg** com libass (é ele que desenha as legendas).
- **Node.js 18+ e Playwright com Chromium**: só para o Pacote Motion 3D.
- Espaço em disco para os modelos: cerca de 690 MB, baixados uma vez.
- Computador de referência: 4 núcleos, sem placa de vídeo. Funciona em Mac, Windows e Linux.

---

## 4. Instalação passo a passo

### 4.1 Instalar os programas

| | Mac | Windows | Linux (Ubuntu) |
|---|---|---|---|
| ffmpeg | `brew install ffmpeg` | `winget install --id Gyan.FFmpeg -e` | `sudo apt install ffmpeg` |
| Python 3.12 | `brew install python@3.12` | `winget install --id Python.Python.3.12 -e` | `sudo apt install python3 python3-pip` |
| Node.js (só Motion) | site nodejs.org (versão LTS) | site nodejs.org (versão LTS) | site nodejs.org ou `sudo apt install nodejs npm` |

No Linux, para o recorte da pessoa (palavra atrás da cabeça), instale também:
`sudo apt install libegl1 libgles2 libgl1`

No Windows, use `python` em vez de `python3` nos comandos abaixo.

### 4.2 Instalar as skills (comando único)

Na pasta do produto (onde está a pasta `tools`):

```bash
python3 tools/instalar_skills.py --modelos
```

O instalador:
1. cria `~/.claude/skills/editor-video` (no Windows, `%USERPROFILE%\.claude\skills\editor-video`);
2. instala os pacotes Python que faltam;
3. baixa os modelos;
4. roda a verificação, que tem que terminar em `READY`.

Variações:
- `python3 tools/instalar_skills.py --copiar`: copia a pasta em vez de criar atalho. **Use no Windows** se der
  erro de permissão de atalho (symlink).
- Sem `--modelos`: só instala e verifica, sem baixar os modelos.

### 4.3 Instalação manual (se recebeu só o zip da skill)

1. Descompacte em `~/.claude/skills/editor-video` (Windows: `%USERPROFILE%\.claude\skills\editor-video`).
2. No terminal, dentro dessa pasta:
   ```bash
   python3 -m pip install -r requirements.txt
   python3 scripts/setup.py --models
   python3 scripts/setup.py
   ```
3. Só para o Pacote Motion 3D:
   ```bash
   npm install -g playwright && npx playwright install chromium
   ```
4. O último `setup.py` tem que mostrar `READY`.

### 4.4 Instalar o Pacote Motion 3D (por cima do Corte Viral)

1. Instale o Node.js 18+ (nodejs.org) e rode:
   ```bash
   npm install -g playwright && npx playwright install chromium
   ```
2. Descompacte o zip do Motion **por cima** da pasta da skill (`~/.claude/skills/editor-video`) e aceite
   substituir o `perfil.json`.
3. Rode `python3 ~/.claude/skills/editor-video/scripts/setup.py`. A linha "STATUS pacote completo" confirma
   que o Motion foi instalado.
4. No Claude Code, peça: "me coloca numa moldura 3D", "troca meu fundo por um estúdio 3D" ou "anima isso na tela".

### 4.5 Usar

Abra o Claude Code em qualquer pasta e digite `/editor-video`, ou só peça: "edita esse vídeo no estilo Reels
Viral". Diga onde está o arquivo, por exemplo `~/Downloads/gravacao.mp4`.

---

## 5. Lendo a verificação (`setup.py`)

Cada linha começa com `STATUS`. `OK` = tudo certo. `MISSING` = falta instalar (a linha diz o comando).

| Linha | Significa | O que fazer |
|---|---|---|
| `STATUS ffmpeg MISSING` | ffmpeg não instalado ou fora do PATH | instalar (tabela 4.1); no Windows, fechar e abrir o terminal e o Claude Code |
| `STATUS ffmpeg INCOMPLETE (sem ass, ...)` | ffmpeg sem libass (não desenha legenda) | reinstalar pelo comando da tabela 4.1 (essas versões vêm com libass) |
| `STATUS python TOO OLD (>=3.10)` | Python antigo | instalar Python 3.12 |
| `STATUS py:numpy MISSING` (ou pillow, sherpa-onnx, mediapipe) | pacote Python faltando | `python3 -m pip install -r requirements.txt` ou `python3 scripts/setup.py --install` |
| `STATUS py:mediapipe BROKEN (...)` | Linux sem bibliotecas gráficas | `sudo apt install libegl1 libgles2 libgl1` |
| `STATUS model:parakeet MISSING` | modelo de transcrição não baixado | `python3 scripts/setup.py --models` |
| `STATUS model:blaze_face_short_range.tflite MISSING` (ou selfie_segmenter, hand_landmarker) | modelos de rosto/recorte/mão não baixados | `python3 scripts/setup.py --models` |
| `STATUS node MISSING` | Node.js não instalado (só Motion) | instalar Node.js LTS (nodejs.org) |
| `STATUS playwright MISSING` | Playwright/Chromium faltando (só Motion) | `npm install -g playwright && npx playwright install chromium` |
| `STATUS motion (node + playwright) OK` | animações prontas | — |
| `READY` | tudo pronto | pode editar |
| `NOT READY` | alguma linha acima está MISSING | resolver as linhas MISSING e rodar de novo |

Quem comprou só o Corte Viral pode ignorar `node` e `playwright` MISSING.

---

## 6. Erros comuns e solução

1. **"ffmpeg não encontrado" depois de instalar (Windows)**: o PATH só atualiza em janelas novas. Feche e abra o
   terminal **e o Claude Code**. Teste com `ffmpeg -version`.
2. **Legenda não aparece / erro com "ass"**: ffmpeg sem libass. Reinstale pelo comando oficial da tabela 4.1.
3. **"Python too old" ou `python3` não existe (Windows)**: instale o Python 3.12 e use `python` ou `py -3`.
4. **Linux: erro com libEGL / mediapipe**: `sudo apt install libegl1 libgles2 libgl1`.
5. **"Playwright não encontrado" / animação falhou**: `npm install -g playwright && npx playwright install chromium`
   (só no Pacote Motion 3D).
6. **"Modelo ... ausente"**: `python3 scripts/setup.py --models`. Precisa de internet. São cerca de 690 MB, baixados
   uma vez.
7. **Disco cheio ("No space left on device")**: libere espaço. Os renders ficam em `renders/` e os arquivos
   temporários em `work/` dentro da pasta do projeto, e podem ser apagados depois de entregar.
8. **Vídeo muito grande ou demorado**: vídeos com mais de 3 minutos demoram mais (o Claude roda em segundo plano).
   Para revisar rápido, peça "me manda uma prévia". O Claude Code lê o arquivo direto da pasta, então não há limite
   de tamanho como nos anexos de conversa.
   **Vídeo longo (VSL, aula, até 30 min) ou que está em outro lugar:** suba no Google Drive, compartilhe como
   **"Qualquer pessoa com o link" → Leitor** e mande o link (no Claude Code: "edita esse vídeo: <link>"; no Editor
   no WhatsApp: cole o link na conversa). Link do Dropbox também serve. Se o link estiver privado, o editor responde
   como liberar. No WhatsApp, vídeo com mais de 3 minutos volta por link de download ou como documento.
9. **Windows: erro ao criar atalho (symlink)**: `python3 tools/instalar_skills.py --copiar`.
10. **A skill não aparece no Claude Code**: confira se existe `~/.claude/skills/editor-video/SKILL.md` (Windows:
    `%USERPROFILE%\.claude\skills\editor-video\SKILL.md`). Se não existir, rode o instalador de novo. Depois
    reinicie o Claude Code.
11. **Palavra não ficou atrás da cabeça**: só funciona com rosto de frente, cabeça estável e fundo que se separe
    da pessoa. Sem isso, a palavra vai para a frente como título (é proposital).
12. **Legenda escreveu errado um nome ou marca**: peça "a legenda escreveu cloud, é Claude". Ele corrige e
    renderiza de novo.

---

## 7. Como pedir edições na conversa

Exemplos que funcionam:
- "edita ~/Downloads/gravacao.mp4 no estilo Reels Viral"
- "corta as pausas e põe legenda amarela"
- "faz no estilo anúncio com o CTA 'COMENTA EU QUERO'"
- "faz uma versão de 30 e uma de 15 segundos" (Motion 3D)
- "faz 3 versões, uma com cada gancho que eu gravei" (Motion 3D)
- "me coloca numa moldura 3D quando eu falo dos 3 passos" (Motion 3D)

Correções depois da primeira versão (cada pedido gera uma versão nova, com histórico):

| Você diz | O editor faz |
|---|---|
| "tira o 'é isso' do começo" | corta o trecho |
| "volta a frase X que você cortou" | restaura o trecho |
| "a legenda escreveu cloud, é Claude" | corrige a palavra |
| "muda pro estilo anúncio / editorial / viral" | troca o estilo |
| "troca o gancho para ..." / "o CTA tem que ser ..." | troca o texto |
| "destaca a palavra dinheiro" | destaca a palavra na legenda |
| "coloca LUCRO atrás de mim quando eu falo faturamento" | palavra atrás da cabeça |
| "não quero palavra atrás de mim" | desliga |
| "legenda maior / menor" / "sobe a legenda" | ajusta tamanho e posição |
| "menos zoom" / "sem zoom" / "zoom mais forte" | ajusta o zoom |
| "coloca essa música baixinha" | música do cliente, que abaixa sozinha quando a pessoa fala |
| "põe a gravação de tela quando eu falo 'sistema'" | B-roll no momento certo |
| "faz a versão horizontal pro YouTube" | formato 16:9 |
| "tira a segunda animação" / "sem ícones" | remove (Motion 3D) |
| "quero ver rápido" | prévia em qualidade menor |

Dica de velocidade: mande **todas as correções numa mensagem só**. O editor junta tudo num render só.

---

## 8. Tempos de render

Referência: computador de 4 núcleos, sem placa de vídeo, vídeo de 30 s com 4 animações.
- **Primeiro render: cerca de 84 s.**
- **Depois de uma correção (texto, legenda, CTA): cerca de 31 s.** O editor reaproveita o que não mudou.
- A transcrição leva cerca de 15% da duração do vídeo.
- Computador mais forte = mais rápido. Vídeo mais longo = proporcionalmente mais tempo.

---

## 9. Limites honestos (não prometa além disto)

- **Melhor tomada**: é escolhida pelo texto (repetição da frase), não por expressão ou emoção. Em gravações com
  muitas tomadas, vale revisar.
- **Transcrição**: pode errar nomes próprios e marcas; corrige-se por texto.
- **Palavra atrás da pessoa**: precisa de rosto de frente, fundo separável e pouco movimento. Cabelo volumoso,
  roupa da cor do fundo ou várias pessoas pioram o recorte.
- **Não gera** voz, música, imagens nem cenas por IA sozinho. Música e B-roll são do cliente ou licenciados.
- **Vídeo em baixa resolução** fica mais suave quando ampliado.
- **Animações 3D** rodam no processador: CSS 10-25 quadros/s, 3D 2-7 quadros/s.
- **Logo 3D na mão**: com mão rápida pode atrasar ou perder a mão.
- **Mapa**: é ilustrativo (não é cartografia real).
- **Como o Claude confere o resultado**: ele não assiste ao vídeo; confere por quadros extraídos.
- **Resultado**: o editor não garante visualizações nem vendas. Ele entrega a edição.

---

## 10. Quando encaminhar para o suporte humano

- Pagamento, reembolso, acesso ou licença.
- Erro que não está nesta base, ou que continua depois dos passos sugeridos.
- Pedido de recurso que não existe nos produtos.
- Qualquer dúvida sobre o Editor no WhatsApp além do básico (como enviar o vídeo e receber de volta).
