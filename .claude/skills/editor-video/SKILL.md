---
name: editor-video
description: "Editor automático de vídeo com IA em português (Reels/TikTok/Shorts 9:16, YouTube/aula/podcast 16:9, feed 1:1): recebe vídeos brutos, escolhe as melhores tomadas, remove pausas e erros, gera legendas animadas, faz zooms e cortes dinâmicos, põe palavras e objetos 3D atrás da pessoa, insere B-roll, ícones e motion graphics (moldura 3D com explicação, camadas de vidro, estúdio 3D no lugar do fundo, logo 3D que segue a mão, mapa, infográfico, documentário, ou qualquer animação escrita sob medida em HTML/Three.js), aplica estilos (Editorial Premium, Reels Viral, Anúncio de Alta Conversão), exporta MP4 e re-renderiza a partir de correções por texto. Use com /editor-video ou frases como 'edita esse vídeo', 'corta as pausas', 'anima isso na tela', 'coloca em 3D', 'me coloca numa moldura', 'troca meu fundo', 'faz um anúncio com esse vídeo', 'muda e renderiza de novo'."
---

# /editor-video

Vídeo bruto entra, MP4 editado sai. O usuário não abre editor: assiste, escreve o que quer mudar, e cada rodada
é uma nova versão (`renders/vN_<estilo>.mp4`) com histórico em `versions/`.

`SK` = pasta desta skill (onde está este SKILL.md). `PY` = `python3` (no Windows, `python` ou `py -3`).
Todos os scripts ficam em `SK/scripts/` e recebem a pasta do projeto como primeiro argumento.

## 0. Pré-requisitos (uma vez por máquina)

```bash
PY SK/scripts/setup.py              # STATUS de ffmpeg, Python, pacotes e modelos
PY -m pip install -r SK/requirements.txt
PY SK/scripts/setup.py --models     # ~690 MB: Parakeet (transcrição) + MediaPipe (rosto/recorte/mão)
npm install -g playwright && npx playwright install chromium   # motion graphics (HTML -> vídeo)
```
Só siga quando imprimir `READY`. Cada linha `MISSING` traz o comando de correção para o sistema do usuário.
Detalhes em `SK/references/dependencias.md`.

## 0b. Marca do cliente (leia antes de editar)

Se existir `SK/brands/<slug>/` para o cliente (ex.: `omarcelprado`), crie o projeto com `--brand <slug>` e **leia
`brand.md` antes de escrever qualquer gancho, texto de tela ou CTA**: tom de voz, CTAs, o que evitar, padrões de
edição aprovados, paleta e o vídeo de referência. O `brand.json` aplica sozinho cores, legenda em duas fontes, CTA
padrão, correções de palavras do ASR, velocidade (×1,15), pausas curtas e o mapa de gatilhos da marca
(`triggers.json`). Cliente novo: copie `brands/_modelo/` para `brands/<slug>/` e preencha com o material dele.
Consulte também `SK/references/catalogo.md` (tudo que o editor faz) em toda edição.

## 0c. Velocidade (siga sempre)

O que deixa a edição lenta na conversa é o Claude ler tudo, olhar quadro a quadro e renderizar a cada ajuste.
Regras:
1. **Uma rodada de decisão, um render.** Junte todas as correções da leitura de `qa/takes.md` num único
   `edit.py ... --no-render` e renderize uma vez (`run.py render`). Nunca renderize entre correções.
2. **Renders em segundo plano** (Bash com `run_in_background`) e responda ao usuário enquanto roda; não fique
   consultando o progresso.
3. **Não repita etapas**: transcrição, A-roll, máscara e animações ficam em cache. Mudou só texto, legenda,
   gancho ou CTA? O render reaproveita tudo (~1x a duração do vídeo).
4. **Leia pouco**: `transcript.txt` e `qa/takes.md` uma vez cada; não abra JSON grande nem o código dos scripts
   para editar normalmente. QA = a folha `qa/vN_*_cortes.jpg` + no máximo 3 quadros.
5. **Prévia**: para o usuário aprovar ritmo e cortes antes do acabamento, `render.py <projeto> --draft`.
   `--max` só quando ele pedir arquivo de máxima qualidade (YouTube/arquivo).
6. O render imprime `tempos:` por etapa; se algo estiver lento, diga qual etapa e por quê.

Referência (CPU de 4 núcleos, vídeo de 30 s com 4 animações): primeiro render ~85 s, re-render após correção ~30 s.

## 1. Intake

- Clipes: os arquivos que o usuário indicar (vários clipes = várias tomadas do mesmo roteiro, na ordem de gravação).
- B-roll: vídeos/imagens do próprio usuário (gravação de tela, produto, prints). Nunca baixe mídia de terceiros
  sem licença. Sem B-roll, o estilo usa só gráficos e zooms.
- Estilo: pergunte só se o usuário não disse. Sem resposta: `reels_viral` para orgânico, `anuncio_conversao` se
  ele falar em anúncio/tráfego/venda, `editorial_premium` para marca pessoal/autoridade, `pro_clean` para
  "máxima qualidade" / anúncio premium.
- **Já editado?** Se ele disser que já cortou (CapCut etc.) ou pedir para não cortar/acelerar, crie com
  `--sem-cortes`: o vídeo fica inteiro, no ritmo original, e você só embeleza.
- **Imagem de celular (luz, cor, pele, tremida).** Desligado por padrão. Ligue com
  `edit.py <projeto> --correcao auto --estabilizar auto` quando: estilo `pro_clean` / "máxima qualidade";
  vídeo escuro, granulado ou com cor puxada (luz de lâmpada); câmera na mão / selfie tremida; ou o pedido for
  "melhora a imagem", "tira a tremida", "deixa a pele bonita". `--pele 0..1` (padrão 0.35 com correção; 0 desliga).
  Tudo local e moderado (detalhes e custo em `SK/references/direcao.md`, seção 8c).
- Formato: `9:16` (padrão: Reels/TikTok/Shorts), `16:9` (YouTube, aula, podcast, vídeo longo), `1:1`/`4:5` (feed).
- Projeto: uma pasta nova por vídeo (ex.: `~/video-edits/<slug>`).

```bash
PY SK/scripts/run.py new <projeto> --clips <bruto1.mp4> [<bruto2.mp4> ...] --style <estilo> [--format 16:9] [--brand slug] \
   [--broll <arquivos ou pasta>] [--hook "texto do gancho"] [--cta "chamada final"]
PY SK/scripts/transcribe.py <projeto>     # transcript.txt + transcript.json (tempo por palavra)
```

**Vídeo longo / pelo Drive.** VSL de 30 min, aula ou live não passa no upload do chat (~30 MB) nem no WhatsApp
(16 MB). Peça para a pessoa subir no Google Drive e compartilhar como **"Qualquer pessoa com o link → Leitor"**;
`--clips` e `--broll` (e `edit.py --add-broll`) aceitam o link direto (Drive, Dropbox ou `.mp4`) e baixam em
`<projeto>/fontes/`. Link privado ou de pasta volta com a instrução de como liberar; repasse-a. Baixar sem
editar: `PY SK/scripts/drive.py <link> <pasta>`. Para vídeo longo use `--format 16:9` (ou 9:16 se for VSL para
celular) e `--draft` na primeira prévia.

## 2. Leia a transcrição e decida como editor (este é o seu trabalho, não do script)

**Antes de decidir qualquer coisa, leia `SK/references/direcao.md` (direção de edição profissional): o método,
a tabela de gatilhos fala → elemento, a densidade por tipo de vídeo, as receitas e os cuidados.** Monte o MAPA DE
EDIÇÃO (tempo | fala | função | elemento) e aplique tudo de uma vez com `--motion @motion.json`. Editar só com
legenda e zoom é o erro mais comum: siga a densidade do manual.

Leia `transcript.txt` inteiro. Depois (pule no modo sem cortes):
```bash
PY SK/scripts/analyze.py <projeto>        # escolhe tomadas e corta pausas -> qa/takes.md, edl.json
```
Leia `qa/takes.md` e corrija o que a regra automática não pega, com `edit.py --no-render`:
- **Começo fraco** ("É isso", "Então...", "Oi gente"): `--cut "É isso."`. O primeiro segundo tem que ser o gancho.
- **Tomada ruim que sobrou** ou trecho fora do assunto: `--cut "trecho exato falado"`.
- **Corte errado** (a regra tirou algo que importa): `--restore "trecho"`.
- **Palavras que o ASR errou** (nomes, marcas, gírias): `--fix "errado=certo"`.
- **Gancho** (faixa dos 3 primeiros segundos em Viral/Anúncio): escreva um, curto, TIRADO DO QUE A PESSOA DIZ.
  Nunca prometa resultado, número ou prova que não esteja no vídeo. `--hook "..."`.
- **CTA**: use o que o usuário pediu; se não pediu, deixe o padrão do estilo e mencione na entrega.
- **Título** (lower third do Editorial): `--title "..."`.

Mostre ao usuário uma tabela curta: o que foi cortado, o gancho, o CTA, onde entra B-roll. Não espere
aprovação para o primeiro render, a não ser que ele tenha pedido.

## 2b. Motion graphics (o "anima o que você quiser ver na tela")

> Se `SK/perfil.json` disser `"motion": false` (pacote Corte Viral), pule esta seção: as animações 3D fazem parte
> do **Pacote Motion 3D**. Se o usuário pedir uma, diga em uma linha que ela está nesse pacote e siga com o resto.

Leia `SK/references/motion.md`. Para cada momento do roteiro que pede visual (explicação de passos, números,
lugar, produto, comparação), proponha uma animação e peça com `edit.py --motion`:
- explicação em passos/itens -> `moldura` (pessoa na moldura 3D + itens surgindo no tempo da fala)
- revelar "como é feito" / bastidores -> `camadas`
- trocar o fundo por cenário -> `estudio3d`
- logo/palavra em 3D na mão, flutuando ou atrás da pessoa -> `objeto3d` (`follow: "hand"`, `layer: "behind"`)
- números (preço, metragem, resultado) -> `infografico`; endereço/distância -> `mapa`; foto/print com marcações -> `documentario`
- qualquer outra coisa (anatomia, receita animada, planeta abrindo, gráfico): escreva uma composição própria
  seguindo o contrato de `motion.md`, renderize um trecho e olhe os quadros antes de usar.
Blocos da referência do Marcel (fundo branco quente com sombra de persiana): `tela_ia` (chat de IA com cursor,
arquivo, digitação, carimbo), `carrossel3d` (telas e clipes em arco 3D), `onda_audio` (cortes reais, 2:03 → 0:40),
`checklist`, `notificacao`, `botao_cta`, `anotacao` (à mão), `carimbo`, `pedacos` (vídeo girando sobre a cabeça),
`card_fogo` (card na mão que queima). Mais: `clones` (pessoa duplicada/várias versões), `cenario` (vários
cenários), `giro` (imagens girando/antes-depois), `vendas` (notificações de venda com "plim", só números reais),
`tabela` (2 colunas), `cronometro`, `luz`, `quadrinho` (pessoa num painel de HQ + ilustrações do que ela fala).
Acabamento premium (referência de anúncios de infoproduto): estilo `pro_clean` + `pergunta` (card digitando),
`palavra` (palavra gigante em degradê atrás da cabeça) e `player` (janela de vídeo com título, selo e progresso).
O **mapa de gatilhos** já põe vários sozinhos (frase da marca, dinheiro, enumeração, "comenta PALAVRA",
"clica no botão"); confira em `timeline.json` (`motion[].trigger`) e ajuste.
Efeitos de impacto: `--fx tremida@palavra`, `clarao`, `glitch`, `whip` (chicote já entra sozinho em tela cheia).
Ritmo: no máximo uma animação de tela cheia a cada ~6-8 s num Reels; num vídeo longo, use nos pontos-chave.
Ícones em palavras-chave entram sozinhos no Viral/Anúncio (`--icons off` desliga).
Não invente números, endereços ou dados: só o que a pessoa disse ou o usuário forneceu.

## 2c. Direção premium (máxima qualidade / nível concorrente)

Leia `references/direcao.md` seção **4c**. Em resumo: `edit.py --direcao premium` (seletor por intenção, palavra-chave
com emoji e cor da emoção, transições no ritmo da fala, controle de densidade), composições de referência
(`--composicao revelacao@trecho | produto_heroi@trecho | impacto@trecho`), produto recortado
(`scripts/recorte.py foto.jpg produto.png` → `--produto produto.png`), trilha sem direitos (`--music auto:energia`),
prévia rápida (`run.py previa <proj> --de A --ate B`), ganchos para teste A/B (`run.py ganchos <proj>`) e estilo
copiado de um vídeo de referência (`scripts/referencia.py analisar video.mp4` → `aplicar perfil.json <proj>`).
O render protege o rosto sozinho e o QA reprova rosto tampado.

## 3. Renderize

```bash
PY SK/scripts/run.py render <projeto>     # analyze -> plan -> render: renders/v1_<estilo>.mp4
```
- `plan.py` gera `timeline.json` (planos, zoom, legendas, palavras atrás, B-roll, gráficos, SFX). Você pode
  editar esse arquivo à mão e rodar só `PY SK/scripts/render.py <projeto>` para casos que os comandos não cobrem.
- O render imprime quantas palavras ficaram ATRÁS da pessoa e quantas foram para a FRENTE: atrás só acontece com
  rosto detectado e cabeça estável; sem pessoa (tela, mão, produto), a palavra vira título animado na frente.
- Render final ~2-3x a duração do vídeo em CPU de 4 núcleos (motion incluso); re-render após correção ~1x.
  `--draft` (prévia) é mais rápido; `--max` comprime melhor (mais lento).

## 3b. Mídia dos conectores e versões

- `qa/pedidos-de-midia.md` (gerado no plan) lista citações, profissões, cenários e ferramentas ditas na fala, com o
  conector certo (Pinterest, Canva, Moda, Instagram...). Atenda só 2-4 que melhoram o vídeo, seguindo
  `SK/references/conectores.md` (inclui como baixar quando a rede da nuvem bloqueia), salve em `<projeto>/midia/`
  e encaixe (`--motion cenario`, `documentario`, `giro`, `--add-broll`).
- Variações de gancho (ele grava 3 ganchos seguidos e depois o corpo): `PY SK/scripts/run.py variacoes <projeto> --ganchos 3`
  → `renders/gancho1.mp4`, `gancho2.mp4`, `gancho3.mp4`.
- Versões curtas terminando em fim de frase: `PY SK/scripts/run.py curta <projeto> --segundos 30 15`.
- Gancho testado (3 aberturas do MESMO vídeo para teste no anúncio): `PY SK/scripts/run.py ganchos <projeto> [--n 3]`
  → `renders/gancho_A.mp4` (pergunta na tela), `_B` (manchete + zoom de impacto), `_C` (corte de gancho com a frase
  mais forte; em vídeo sem cortes, 2.5D com a palavra forte) + `qa/ganchos.md` com o que muda e o custo HIT/MISS.
  Só o começo é refeito; textos = palavras ditas; o projeto principal não muda. `--so-plano` só compara sem render.
- Referência do concorrente (copiar ritmo/densidade/estilo, nunca o conteúdo):
  `PY SK/scripts/referencia.py analisar <video_deles> --saida perfil.json` (cortes/min, plano médio, zoom, texto na
  tela, faixa e tamanho da legenda, paleta, flashes, loudness, trilha, ritmo da fala) e depois
  `PY SK/scripts/referencia.py aplicar perfil.json <projeto>` (estilo, zoom, legenda, cor de destaque, densidade,
  efeitos nas NOSSAS palavras fortes, via edit.py sem renderizar). Mostre ao usuário o que mudou e renderize.

## 4. Confira antes de entregar (obrigatório)

1. Abra `qa/vN_<estilo>_cortes.jpg` (um quadro por plano) e olhe: legenda legível, nada cortado nas bordas,
   gráfico não cobre rosto, B-roll certo.
2. Extraia 3-4 quadros nos momentos de gancho, B-roll e CTA (`ffmpeg -ss T -i render -frames:v 1 x.jpg`) e olhe.
3. `versions/vN/qa.json`: duração, loudness (alvo -14 LUFS no Viral/Anúncio, -16 no Editorial).
4. Achou problema? Corrija e renderize de novo antes de mostrar. Só entregue o que você viu.

Antes/depois para o usuário:
```bash
PY SK/scripts/compare.py <bruto.mp4> <projeto>/renders/vN_<estilo>.mp4 <projeto>/renders/antes_depois.mp4
```

## 5. Correções por texto (loop de revisão)

O usuário escreve em linguagem natural. Traduza para operações do `edit.py` (lista completa em
`SK/references/revisoes.md`) e passe o pedido original em `--note` (fica no `versions/changelog.md`):

```bash
PY SK/scripts/edit.py <projeto> --note "tira o oi do começo e deixa a legenda maior" \
   --cut "Oi gente" --caption-size +15%
```
Cada `edit.py` grava a mudança em `project.json` (vale para todas as versões seguintes, inclusive se trocar de
estilo) e renderiza a próxima versão. Pedido ambíguo: faça a leitura mais provável e diga qual foi.

**Revisão inteligente (só refaz o que mudou).** Todo elemento da `timeline.json` tem `id` estável (planos
`sc1_8920`, animações `m1..` na ordem pedida, automáticas `a_<template>_<n>`, ícones `i<n>`, palavras atrás `b<n>`,
gráficos `g_cta`, B-roll `r<n>`, legendas `p<n>`).
- Ajuste fino que os comandos não cobrem: `--patch "ID.campo=valor"` (ex.: `m5.params.text=VICIANTE.`,
  `m5.t1=15.2`, `sc1_8920.zoom0=1.2`, `g_cta.text="COMPRE"`), `--patch-remove ID`, `--patch-clear ID`. O patch
  sobrevive a cortes, troca de estilo e replanejamento. Editar `timeline.json` à mão também funciona: no próximo
  `plan.py` a diferença vira patch sozinha.
- Antes de uma mudança grande, mostre o custo: `edit.py <projeto> <operações> --dry-run` (ou `run.py revisar`)
  lista HIT/MISS por componente sem gravar nada. Ex.: mudar uma animação em 12–16 s refaz só ela e o trecho 12–16.
- `motion.json` reaplicado não duplica: pedido idêntico é ignorado; pedido com `"id"` substitui o anterior.
- O render imprime `HIT`/`MISS` de planos, máscaras, animações, trechos (4 s) e áudio, e grava
  `versions/vN/revisao.json`. `run.py versoes <projeto>` mostra o histórico; `run.py rollback <projeto> --para N
  [--render]` volta a uma versão (100 % cache); `run.py limpar-cache <projeto> --manter 5` libera disco.
- Se o render falhar, o projeto volta sozinho ao estado anterior (nada fica pela metade).

## 6. Entrega

Envie o MP4 final (e o antes/depois). Diga em poucas linhas: duração bruto -> editado, o que foi cortado,
estilo, gancho/CTA usados, o que ficou atrás da pessoa, e qualquer decisão que precise do usuário.

## Outras ferramentas (quando ajudam)

Local primeiro (gratuito, privado, sem limite). Use conectores/skills quando o pedido exigir o que o local não faz:
- **Imagens para B-roll** (produto, cenário, ilustração): skills `nano-banana`, `flux`, `ideogram`, `image-prompt`;
  depois `edit.py --add-broll` ou `documentario`.
- **Vídeo gerado por IA** para B-roll: skills `veo-3`, `kling`, `runway`, `luma`.
- **Voz/narração e música licenciada**: skills `ai-voiceover` (ElevenLabs), `ai-music-and-sound`, `suno`; música entra com `--music`.
- **Descript** (conector): se o usuário já edita lá, exporte o MP4 final para um projeto Descript, ou use o
  Underlord para revisão colaborativa.
- **HyperFrames by HeyGen** (conector): render na nuvem de composições HTML quando o usuário quiser um projeto
  compartilhável no HeyGen (do Claude Code local, a skill local é o caminho).
- **Canva** (conector): capas, thumbnails e artes estáticas do mesmo vídeo.
- Publicação/agendamento: Metricool / Blog2Social / Meta (conectores), sempre com aprovação do usuário.

## Regras fixas

1. Zona segura 9:16: nada importante acima de y=220 nem abaixo de y=1470 (interface do Reels/TikTok).
2. Texto nunca cobre o rosto. Palavra atrás da pessoa só com rosto detectado e cabeça estável.
3. Legenda diz exatamente o que foi falado (corrija o ASR com `--fix`). Gancho e CTA não inventam promessa.
4. Originais nunca são alterados: o projeto só lê os clipes.
5. Música e B-roll só do usuário ou com licença comercial clara. Os efeitos sonoros da skill são sintetizados
   (sem licença de terceiros). Logos de marcas de terceiros (ChatGPT, Claude etc.) só com o arquivo e o direito
   de uso fornecidos pelo usuário; a skill não inclui logos de marcas.
6. Mostre só o que você verificou nos quadros do render final.
