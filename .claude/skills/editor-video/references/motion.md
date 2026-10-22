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
| `mapa` | front (card) ou full | Mapa ilustrado com pino, ponto de interesse, rota desenhada e tempo de deslocamento | `place`, `poi`, `poi_icon`, `time_label`, `pin_at`, `route_at`, `mode` |
| `infografico` | front | Cartões de vidro com números que contam até o valor quando são ditos | `stats[{value, decimals, prefix, suffix, label, icon, at}]`, `y` |
| `documentario` | full | Foto/print com câmera Ken Burns até o ponto que importa + círculos/setas/rótulos no tempo da fala | `image`, `focus`, `zoom`, `title`, `marks[{x, y, label, at, kind}]` |
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
