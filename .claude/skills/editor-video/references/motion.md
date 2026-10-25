# Motion graphics: templates e animações sob medida

Toda animação é uma página HTML (CSS 3D, SVG ou Three.js) renderizada quadro a quadro no Chromium
(`scripts/motion_render.mjs`) e encaixada na timeline pelo `render.py`. Quando o usuário pede "anima X",
"coloca Y em 3D", "explica Z com animação", o Claude:

1. escolhe um template abaixo e preenche os params, **ou**
2. escreve uma composição nova (seção "Composição própria") quando nenhum template serve.

Pedido via `edit.py <projeto> --motion '<json>'` (ou `--motion @arquivo.json` com uma lista):
```json
{"template": "moldura", "at": "trecho falado onde começa", "until": "trecho onde termina", "dur": 5,
 "layer": "full", "params": {"title": "...", "items": [{"text": "...", "icon": "chef-hat", "at": "palavra"}]}}
```
- `at` / `until`: trechos falados (copie do `transcript.txt`); ou `dur` em segundos.
- Dentro de `params`, qualquer `"at"` ou `"*_at"` com texto vira o instante em que aquela palavra é dita.
- `layer`: `full` (substitui a imagem), `front` (por cima, fundo transparente), `behind` (atrás da pessoa).
- Animações de tela cheia têm prioridade: sobreposições são cortadas automaticamente.
- Ícones: nomes do Lucide em inglês (`assets/motion/vendor/lucide/icons/*.svg`, ~1.900).

## Templates

| Template | Layer padrão | O que faz | Params principais |
|---|---|---|---|
| `moldura` | full (usa vídeo) | Pessoa sai da tela cheia para moldura 3D inclinada num lado; explicação se monta item a item do outro; volta à tela cheia | `title`, `items[{text, icon, at}]`, `side` direita/esquerda, `accent`, `bg` escuro/claro |
| `camadas` | full (usa vídeo) | Cena gira e se separa em camadas de vidro (fundo, elementos, pessoa) com rótulos; depois junta | `graphic`, `icon`, `labels{fundo, elementos, voce}`, `accent` |
| `estudio3d` | full (usa vídeo, WebGL) | Troca o fundo por estúdio 3D iluminado (Three.js), câmera em parallax, letreiro na parede atrás da pessoa | `wall_text`, `accent`, `accent2`, `mood` noite/dia |
| `objeto3d` | front ou behind (WebGL) | Texto extrudado ou logo em placa 3D com reflexo; entra girando, flutua; **segue a mão** | `text` ou `image`, `color`, `follow: "hand"`, `offset`, `x`, `y`, `size` |
| `produto3d` | front (`atras`: `"layer": "behind"`; WebGL) | **Produto/ícone 3D de verdade**: a foto recortada (`scripts/recorte.py`) vira objeto extrudado pelo contorno do alfa, com chanfro arredondado, frente com a foto, laterais na cor da borda, luz key/rim/ambiente com verniz, sombra suave e brilho que passa. Entradas: `voa` (sobe em arco girando e pousa), `gira` (dá a volta e para de frente), `mao` (sai da palma e segue a mão; use `follow: "hand"`), `atras` (gira devagar atrás da pessoa). Sozinho, foge do rosto e da legenda | `image` (PNG recortado) ou `icone` (emoji, texto curto ou nome Lucide), `entrada`, `x`, `y`, `lado`, `size`, `espessura`, `cor`, `voltas`, `offset`, `brilho`, `sombra` |
| `mapa` | front (card) ou full | Mapa ilustrado com pino, ponto de interesse, rota desenhada e tempo de deslocamento | `place`, `poi`, `poi_icon`, `time_label`, `pin_at`, `route_at`, `mode` |
| `infografico` | front | Cartões de vidro com números que contam até o valor quando são ditos | `stats[{value, decimals, prefix, suffix, label, icon, at}]`, `y` |
| `documentario` | full | Foto/print com câmera Ken Burns até o ponto que importa + círculos/setas/rótulos no tempo da fala | `image`, `focus`, `zoom`, `title`, `marks[{x, y, label, at, kind}]` |
| `profundidade` | full (usa vídeo, WebGL) | 2.5D: câmera anda e o cenário se mexe em paralaxe pela profundidade (Depth Anything local ou heurístico), desfoque de lente ao longe, pessoa real nítida na frente; palavra gigante entre cenário e pessoa | `movimento` dolly/orbita/lateral, `intensidade` 0–1, `texto`, `cor`, `y`, `texto_at`, `desfoque`, `fundo` real/limpo |
| `icone` | front | Ícone que pula com rótulo (o plano já põe automático em palavras-chave no Viral/Anúncio) | `icon`, `label`, `color`, `y` |

### Blocos da referência e efeitos (rodada 3)

| Template | Layer padrão | O que faz | Params principais |
|---|---|---|---|
| `tela_ia` | full | Chat de IA genérico em fundo branco quente: saudação, cursor clica no +, arquivo entra, digita, envia, resposta digitando, carimbo, setas à mão | `greeting`, `steps[{do: attach/type/send/reply/stamp/mark, at, ...}]` |
| `carrossel3d` | full (usa vídeo) | Telas e clipes girando em arco 3D | `items[{image}/{video, start}/{self:true}]`, `title`, `speed` |
| `onda_audio` | front | Onda do bruto, cortes em vermelho somem, duração cai (dados reais) | `title`, `mode` |
| `checklist` | front | Itens marcados na palavra falada + barra | `title`, `items[{text, at}]` |
| `notificacao` | front | Notificação descendo do topo + selo "feito" | `app`, `title`, `text`, `icon`, `badge` |
| `botao_cta` | front | Botão "Saiba Mais" com cursor clicando | `text`, `sub`, `click_at`, `accent` |
| `anotacao` | front | Setas, círculos, sublinhados e texto à mão | `marks[{kind, from, to, text, at}]` (0..1) |
| `carimbo` | front | Carimbo com tremida | `text`, `color`, `x`, `y`, `size`, `rot` |
| `pedacos` | behind | Recortes do vídeo subindo e girando acima da cabeça | `count`, `items` (opcional) |
| `card_fogo` | front | Card preso na mão que queima de baixo para cima | `title`, `sub`, `follow: "hand"`, `burn_at` |
| `clones` | full (usa vídeo) | Pessoa duplicada em versões (P&B, neon, quente...), com atraso | `copies[{label, look, delay, mirror}]` |
| `cenario` | full (usa vídeo) | Vários cenários (imagens) atrás da pessoa, trocando com chicote | `scenes[{image, at, label}]` |
| `giro` | front | Card girando em 3D (antes → depois, sequência de imagens) | `images` ou `texts`, `labels`, `every` |
| `vendas` | front | Notificações de venda empilhando com "plim" (só números reais) | `items[{title, text}]`, `app` |
| `tabela` | front | Comparação em 2 colunas | `left`, `right`, `rows[{l, r, at}]` |
| `cronometro` | front | Relógio contando até o tempo dito | `seconds`, `label` |
| `luz` | front | Vazamento de luz / clarão | `kind`, `color` |
| `quadrinho` | full (usa vídeo) | Pessoa vai para um painel de história em quadrinhos; painéis com ilustrações animadas do que ela fala; balão, onomatopeia e botão de CTA no estilo quadrinho | `paineis[{ilustracao, rotulo, at}]` (até 3) ou `{imagem}` para foto realista, `balao`, `onomatopeia`, `cta`, `fundo`, `fundo2` |

| `pergunta` | front (zona topo) | Card claro no alto com etiqueta ("PERGUNTA") e o texto digitado no ritmo da fala; a legenda some enquanto ele aparece | `text`, `label`, `ate_at` (palavra em que a digitação termina), `accent`, `bg`, `esconde_legenda` |
| `palavra` | behind (cai para front se a cabeça encosta no topo) | Palavra gigante em degradê atrás da cabeça, entrando com desfoque ("SIM.") | `text`, `cores: [cima, baixo]`, `size`, `font`, `sombra` |
| `player` | front (zona topo) | Janela de player descendo do topo: título, selo, vídeo tocando, barra de progresso e tempo | `items: [{video, start}]` ou `[{image}]`, `titulo`, `selo`, `total` ("3:01"), `legenda`, `accent` |
| `dividida` | full (usa vídeo) | Tela dividida em fundo roxo: pessoa num painel com cantos de foco (embaixo ou em cima) e conteúdo animado na outra metade; entra e sai da tela cheia | `modo`: `grade` (`rotulo`, `titulo` com `**destaque**`, `itens[{texto, icone, image, at}]`), `pendencias` (`titulo`, `sub`, `itens[{texto, at}]` = post-its, `chips`, `chips_at`, `prazo`, `prazo_at`), `leque` (`images` ou quadros do vídeo, `titulo`), `palavra` (`texto`, `at`), `imagem` (`image`, `legenda`, `at`); `lado` baixo/cima, `accent`. Arquivos locais em `image`/`images`. Prefira `lado: baixo` (a legenda passa por cima da metade de baixo) |
| `editor_ia` | full (usa vídeo) | Interface de editor com IA: prévia do vídeo real, "VOCÊ PEDE" digitando, "A IA EDITA" marcando itens, linha do tempo com 4 faixas (miniaturas reais, legenda, edição, áudio) e cursor andando; termina acima da faixa da legenda | `titulo`, `arquivo`, `pedido`, `digitar_ate` (s), `itens[{text, at}]`, `accent`, `accent2`, `status` |

Zona topo (`pergunta`, `player`): o rosto desce no enquadramento (quando há zoom para isso), o CTA vai para baixo
e a legenda sobe para logo acima dele. Estilo `pro_clean` = acabamento de anúncio premium (legenda limpa em
caixa baixa montando palavra a palavra, zoom sutil, sons discretos): combine com esses três blocos.

Ilustrações prontas (`lib/ilustracoes.js`, desenhadas no código, sem custo e sem direitos de terceiros):
`menta`, `frutas` (tutti-frutti), `dente` (escova e brilho), `casa` (casa 3D se montando), `brilho`. Para um
assunto sem ilustração, use `{imagem: "arquivo.png"}` no painel: uma foto do cliente ou uma imagem gerada
(realista) a partir dos conectores. Ilustração nova = mais uma função em `lib/ilustracoes.js`.
Durante animações de tela cheia, as faixas de gancho/CTA/título somem; se o CTA ficaria todo coberto, ele
entra como botão dentro do `quadrinho` (`params.cta`).

Exemplos (os mesmos dos anúncios de referência):
- "Me coloca numa moldura do lado direito e do lado esquerdo explica a receita": `moldura` com `items`.
- "Separa tudo em camadas de vidro: o fundo, as logos e eu": `camadas`.
- "Coloca a logo em 3D na minha mão e faz acompanhar o movimento": `objeto3d` com `image` = logo do usuário,
  `follow: "hand"`. "Joga pra trás de mim": `layer: "behind"`.
- "Remove meu fundo e coloca um cenário 3D": `estudio3d`.
- "Tira o fundo da foto do produto e faz ele voar e girar até a tela": `python scripts/recorte.py foto.jpg produto.png`
  (100% local: rembg se instalado, senão o IS-Net do anuncio-produto, senão OpenCV para foto de estúdio; de um
  quadro do vídeo: `recorte.py video.mov produto.png --tempo 4.2 --caixa x0,y0,x1,y1`) e depois `produto3d` com
  `image` = produto.png e `entrada: "voa"` (ou `"gira"`; `follow: "hand"` para sair da mão; `"atras"` + `"layer":
  "behind"` para girar atrás da pessoa). Ícone 3D com o mesmo motor: `{"icone": "🔥"}`, `{"icone": "star", "preencher": true}`.
- Corretor ("a 4 minutos a pé do metrô"): `mapa`; ("18 andares, 72 m², a partir de 1,1 milhão"): `infografico`.
- Documentário / aula sobre uma foto: `documentario`.

## Composição própria (quando nenhum template serve)

Crie `<projeto>/work/motion/custom/<nome>.html` e peça com `{"page": "/work/motion/custom/<nome>.html", ...}`.
Contrato:
```html
<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/lib/base.css">
<!-- Three.js: <script type="importmap">{"imports":{"three":"/vendor/three/three.module.min.js"}}</script> -->
</head><body>
<script type="module">
import motion from '/lib/runtime.js';
const p = motion.params, W = motion.w, H = motion.h, D = motion.duration;
// monte o DOM/cena aqui; carregamentos assíncronos: motion.waitFor(promise)
motion.onFrame(async (t) => {
  // desenhe o estado no tempo t (0..D). Use motion.prog(t, inicio, duracao, 'outBack'), motion.inOut(...)
  // quadros reais: await motion.setFrame(imgEl, 'plate' | 'cut' | 'bg', t)   (precisa "needs_video": true)
});
</script></body></html>
```
Regras:
- Tudo em função de `t` (nada de `setTimeout`, `requestAnimationFrame` ou animação CSS automática): o render
  é determinístico e roda em paralelo em várias abas.
- Fundo transparente por padrão (`layer: front/behind`); em `full` desenhe o quadro inteiro.
- Recursos: `/fonts/*.ttf`, `/vendor/three/...`, `/vendor/three/addons/{TTFLoader,FontLoader,TextGeometry,RoomEnvironment}.js`,
  `/vendor/lucide/icons/<nome>.svg`, arquivos do usuário em `params` (`image`, `logo`, `src`, `photo` são copiados
  automaticamente para o servidor).
- WebGL (Three.js) é ~3x mais lento: marque `"webgl": true` no pedido (os templates 3D já marcam).
- `params.video = {plate, cut, bg, count}` quando `needs_video: true`: `plate` = imagem inteira com a cor do
  estilo, `cut` = só a pessoa (PNG transparente), `bg` = cenário sem a pessoa (área dela desfocada).
- `params.hand` = `[[x, y] | null]` por quadro (0..1) quando `"hand": true` ou `params.follow == "hand"`.
- Teste rápido de um clipe sem renderizar o vídeo todo:
  `PY -c "import sys; sys.path.insert(0,'SK/scripts'); ..."` com `motion.render_clip(...)` (ver `render.py`), ou
  rode `run.py render` com `--draft`.

## Desempenho (CPU de 4 núcleos, sem GPU)

| Tipo | Velocidade |
|---|---|
| CSS/SVG (moldura, camadas, mapa, infográfico, documentário, ícone) | 10-25 quadros/s |
| Three.js (estúdio 3D, objeto 3D) | 2-7 quadros/s |
Clipes ficam em cache (`work/motion/clip_<hash>.mov`): só renderizam de novo se o HTML ou os params mudarem.


## Recursos do concorrente (rodada 5)

| `manchete` | front (zona topo; também serve como `behind`, sem caixa opaca) | Manchete de 1-3 linhas no alto, palavras entrando com desfoque no tempo da fala; última linha (ou palavras marcadas) em degradê; riscar com traço vermelho + glitch; rótulo pequeno acima, sub abaixo e ícone em círculo | `linhas` (texto ou `{text, at}`), `text`, `destaque[]`, `cores`, `riscar` (true ou lista), `riscar_at`, `cor_risco`, `rotulo`, `sub`, `icone`, `size`, `y` |
| `proibido` | front | Fileira de ícones genéricos de programa (Lucide; nunca logos de marcas) que levam um X vermelho desenhado + tremida, ficando cinza | `icones[]` (3-5), `x_at`, `rotulo`, `y`, `accent`, `cor_x` |
| `comentario` | front | Caixa de comentário estilo Instagram com a palavra-chave sendo digitada e botão de enviar pulsando; opcional notificação de direct deslizando depois | `texto`, `chamada` (palavra-chave em destaque), `placeholder`, `digitar_ate`, `dm: {nome, texto, app, selo, at}`, `accent`, `y` |
| `final` | full | Tela final: rótulo ("COMENTA"), palavra-chave gigante em degradê, chevrons descendo e cartão de perfil (foto ou iniciais, nome, site) que sobe por cima da palavra | `rotulo`, `palavra`, `nome`, `site`, `foto`, `cores`, `perfil_at`, `fundo` |

# Templates de visão computacional (fork B)

Linhas para a tabela de templates em motion.md. Coordenadas por quadro vêm de `scripts/motion_dados_visao.py`
(MediaPipe local, cache em `work/motion/visao_<hash>.json`); o template recebe tudo pronto em `params`.

| template | camada | o que faz | params |
|---|---|---|---|
| `hud` | front | Colchetes e caixa que seguem o rosto quadro a quadro, chip "EDITOR NOME", "ROSTO 0,94", etiquetas OLHOS/BOCA ligadas aos pontos, varredura, faixa "VISÃO COMPUTACIONAL · QUADRO nnnn". `modo:"zoom"`: colchetes lilás + chip "ZOOM · ÂNCORA: ROSTO" com 1,00× → 1,38× | `rosto` (auto), `modo` (rosto\|zoom), `nome`, `rotulo`, `titulo`, `contador`, `numero`, `zoom_de`, `zoom_para`, `confianca`, `olhos`, `boca`, `topo`, `accent` |
| `pontos` | full, needs_video | A pessoa vira nuvem de pontos lilás (amostrada do recorte, revelada de cima para baixo, leve parallax), fundo escurece, varredura e contador real de pontos ("31.567 pontos"). Foto → pontos → foto | `titulo`, `passo` (7), `cor`, `giro` (10) |
| `recorte` | full, needs_video | 1ª parte: pessoa tingida com contorno brilhante, escala LONGE/FUNDO/VOCÊ/PERTO e rótulos. 2ª parte: as camadas VOCÊ e FUNDO se separam em 3D (placas de vidro) com "01 LIMITE DE VOCÊ", "02 LIMITE DO FUNDO", "DISTÂNCIA VOCÊ ⟷ FUNDO" | `separar` (true), `corte` (0.5), `cor`, `rotulos {voce, fundo}` |
| `maos` | front | Esqueleto das mãos (21 pontos + ossos, brilho), etiqueta presa à ponta do indicador, chip "MÃO · 21 PONTOS · X Y", cubo 3D wireframe girando sobre a palma, faixa "EDITANDO AO VIVO" | `maos` (auto), `etiqueta` ("TEXTO"), `cubo`, `info`, `accent`, `accent2`, `topo` |

Dados (`enriquecer`):
- `hud` → `params.rosto`: por quadro `[x0,y0,x1,y1, olhoE_x,olhoE_y, olhoD_x,olhoD_y, boca_x,boca_y]` (0..1, suavizado, segura 6 quadros sem detecção).
- `maos` → `params.maos`: por quadro lista de mãos, cada uma 21 `[x,y]` (HandLandmarker VIDEO, 540x960, confiança 0.3). Remove `params.hand`.

Dicas de uso:
- `maos` só funciona em trecho em que a mão aparece de verdade (mostrando produto); sem mão, nada é desenhado.
- `hud` e `maos` têm faixa no alto (y≈230): use `topo:false` quando houver CTA subindo para o topo no mesmo trecho.
- `pontos`/`recorte` dependem da qualidade da máscara selfie; 2–3 s é o ideal.

# Novos motions (lote C): edição visual "ao vivo"

Linhas para a tabela de templates de `motion.md`. Os dados reais vêm de `scripts/motion_dados_edicao.py` (gancho `motion_dados_*`, chamado por `motion.render_clip`).

| template | camada | o que faz | params | dados automáticos |
|---|---|---|---|---|
| `transcricao` | full (needs_video) | Tela "EDITANDO AO VIVO": o vídeo num painel com cantoneiras. Um card conta "N erros e pausas" e em `virar_at` vira "N cortes" (−X s · duração Y s). Abaixo correm chips de palavras com mini onda; a palavra falada fica lilás com timecode, sob uma agulha fixa. Embaixo fica a onda do BRUTO com os cortes em vermelho (rótulos PAUSA x s / REPETIDO), que depois somem, e a duração vai do bruto à final. | `etapa` ("01 Transcrição"), `virar_at` (s; padrão 55%), `erros`, `cortes`, `selo`, `accent` (#A78BFA), `alerta` (#F43F5E) | `palavras` [{w,a,b}], `total_palavras`, `primeira`, `onda` (220 picos do A-roll), `bruto` {peaks, cuts[{a,b,m,s}], raw, final}, `erros` = descartadas + pausas, `cortes` = trechos removidos (vêm de edl.json) |
| `tomadas` | front | De 2 a 3 cards de tomada (miniatura, "TOMADA n · 00:00:ss", frase entre aspas, mini onda). Um brilho compara os cards; em `escolha_at` a melhor cresce com borda verde e o selo "MELHOR TOMADA ✓", e as outras ficam cinza e são riscadas. | `itens` [{rotulo, frase, melhor, tempo, image}], `escolha_at` (s; padrão 55%), `selo`, `y` (padrão 370), `accent` | `image` = miniatura do bruto em `tempo` (ou do A-roll), `onda` = 40 picos do mesmo trecho |

Uso típico (overrides.motion):

```json
{"template":"transcricao","at":"Esse chiclete está","dur":4.8,"params":{"etapa":"01 Transcrição"}}
{"template":"tomadas","at":"Na promoção","dur":3.6,"params":{"itens":[{"rotulo":"Tomada 1","frase":"15 reais.","tempo":8.92},{"rotulo":"Tomada 2","frase":"Na promoção, 15 reais","tempo":10.44,"melhor":true}]}}
```

Notas:
- `transcricao` reserva a faixa y≈1150, onde fica a legenda do editor. Os chips ficam em 1168+ e o bruto em 1362+.
- `tomadas` fica no alto do quadro. Se o estilo tiver CTA no topo, convém marcá-lo com `"zona": "topo"` em plan.py para o planejador não sobrepor os dois.

Regras de espaço: elementos de zona `topo` (pergunta, player, etiqueta, manchete, proibido, tomadas, palavra sem espaço) fazem a cena recuar quando a cabeça está alta; `barra` (hud, maos) só manda o CTA para baixo. Texto grande pedido tira as palavras automáticas atrás da pessoa do mesmo instante.
