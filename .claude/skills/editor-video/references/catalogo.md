# Catálogo de possibilidades (consulte em toda edição)

Base: o documento "Editor Viral IA — Catálogo de possibilidades" (46 itens, 22/10/2026) e o anúncio de referência
de 38 s. A coluna "Aqui" diz como fazer **nesta skill**. Os nomes do outro motor (Kit premium, ReelKit, Remotion,
rembg) aparecem só como origem: aqui tudo é ffmpeg + HTML/CSS 3D/Three.js no Chromium + MediaPipe.

Status: ✅ pronto e testado aqui · 🟡 pronto, falta testar com material real · ⛔ fora do alcance local.

| # | Família | Possibilidade | Aqui (como pedir) | Status |
|---|---|---|---|---|
| 1 | Corte | Tirar pausas (~50 ms entre frases) | automático; marca `cuts.max_gap` (omarcelprado: 0,08 s) | ✅ |
| 2 | Corte | Fica a última tomada boa | automático (`analyze.py`) | ✅ |
| 3 | Corte | Acelerar a fala ×1,15 sem mudar a voz | `speed` da marca ou `--velocidade 1.15` | ✅ |
| 4 | Corte | Versões de 30 s e 15 s terminando em fim de frase | `run.py curta <proj> --segundos 30 15` | ✅ |
| 5 | Câmera | Punch-in na palavra forte | automático (zoom por plano) | ✅ |
| 6 | Câmera | Whip (chicote) | automático na entrada de tela cheia; `--fx whip@palavra` | ✅ |
| 7 | Câmera | Tremida de impacto | gatilhos ("Minha aposta", "Para de") ou `--fx tremida@palavra` | ✅ |
| 8 | Câmera | Zoom lento contínuo | estilo (push) | ✅ |
| 9 | Texto | Legenda palavra a palavra com destaque | todos os estilos | ✅ |
| 10 | Texto | Legenda em duas fontes (pesada + serifada itálica) | marca omarcelprado: Anton + DM Serif Italic na palavra-chave | ✅ |
| 11 | Texto | Título com selo | `hook` (faixa) / `notificacao` | ✅ |
| 12 | Texto | Faixas de alerta cruzando | — (pedir composição própria) | 🟡 |
| 13 | Texto | Carimbo ("EDITOR DEMITIDO", "PRONTO PRA EDITAR") | `carimbo` | ✅ |
| 14 | Texto | Texto atrás da pessoa | automático (palavras-chave) + `--behind-add` | ✅ |
| 15 | Texto | Anotação à mão (setas, círculos, "só isso!") | `anotacao` (fonte Caveat) | ✅ |
| 16 | Cards | Card de vidro, arquivo enviado, selo | `tela_ia` (arquivo), `notificacao` (selo) | ✅ |
| 17 | Cards | Checklist item a item na palavra falada | `checklist` + gatilho "primeiro/segundo/terceiro" | ✅ |
| 18 | Cards | Chat digitando pedido e resposta | `tela_ia` | ✅ |
| 19 | Cards | Tela de IA em tela cheia com cursor, arquivo, digitação | `tela_ia` (interface genérica, sem marca de terceiros) | ✅ |
| 20 | Cards | Onda de áudio com cortes e duração caindo (2:03 → 0:40) | `onda_audio` (usa os cortes reais do projeto) | ✅ |
| 21 | Cards | Notificação no topo + selo "feito" | `notificacao` | ✅ |
| 22 | Cards | Botão "Saiba Mais" com cursor clicando | `botao_cta` + gatilho "clica no botão" | ✅ |
| 23 | Cards | Mockup de celular/notebook com tela dentro | `moldura` (quadro 3D) ou composição própria | 🟡 |
| 24 | Cards | Contador de número e relógio | `infografico` + gatilho de dinheiro (som de venda) | ✅ |
| 25 | Layout | Tela dividida (cena em cima, pessoa embaixo) | B-roll `split` (react) | ✅ |
| 26 | Layout | Pessoa em janela no canto, cena em tela cheia | `moldura` (lado) | 🟡 |
| 27 | Layout | Painel lateral deslizando | `moldura` com `items` | ✅ |
| 28 | 3D | Objetos 3D (texto, logo em placa) | `objeto3d` | ✅ |
| 29 | 3D | Card que gira (antes → depois) | `giro` | ✅ |
| 30 | 3D | Cards orbitando | `pedacos` / `carrossel3d` | ✅ |
| 31 | 3D | Carrossel 3D de prints e clipes (o da referência) | `carrossel3d` (imagem, vídeo, o próprio vídeo) | ✅ |
| 32 | 3D | Pedaços do vídeo girando sobre a cabeça | `pedacos` (posição da cabeça medida; passa atrás da cabeça) | ✅ |
| 33 | 3D | Modelo 3D do cliente (.glb) | composição própria com Three.js (GLTFLoader) | 🟡 |
| 34 | IA | Você em outro cenário por 1-1,5 s | `cenario` com fundo gerado (Canva/Moda) | ✅ |
| 35 | IA | Imagem de apoio do que é falado | `pedidos-de-midia.md` → Canva/Moda/Pinterest → `--add-broll` | 🟡 (download bloqueado na nuvem; ver conectores.md) |
| 36 | IA | Imagem gerada ganhando movimento | `cenario`/`documentario` (Ken Burns) | ✅ |
| 37 | IA | Troca de roupa/cenário no vídeo inteiro | Runway/Kling (pago, externo) | ⛔ |
| 38 | Efeitos | Clarão, vazamento de luz, grão, vinheta | `--fx clarao@…`, `luz`, estilos | ✅ |
| 39 | Efeitos | Fogo queimando um card | `card_fogo` | ✅ |
| 40 | Efeitos | Sombra de persiana no fundo das telas | `tela_ia`, `carrossel3d`, `checklist` (lib/scene.css) | ✅ |
| 41 | Efeitos | Glitch | `--fx glitch@…` + som glitch | ✅ |
| 42 | Efeitos | Card preso na mão acompanhando o movimento | `card_fogo` / `objeto3d` com `follow: "hand"` | 🟡 (mão em movimento real não testada) |
| 43 | Som | Whoosh, boom, ding, tick, clique, glitch, "plim" de venda | sintetizados (`assets.py`), sem licença de terceiros | ✅ |
| 44 | Som | −14 LUFS | automático | ✅ |
| 45 | Som | Trilha que abaixa quando você fala | `--music trilha.mp3:0.1` (música licenciada sua) | ✅ |
| 45b | Som | Trilha sem direitos gerada na hora (energia, inspirador, suspense, lofi, corporativo), na duração do vídeo e no ritmo da fala, já abaixando sob a voz | `--music auto:energia` (ou `--trilha lofi`, `--trilha-bpm 120`, `--trilha-semente 2`) | ✅ |
| 45c | Som | Biblioteca de efeitos sintetizados: whoosh (doppler), hit, riser (Shepard), swoosh, swipe, camera_shutter, notification, cash, plim, pop_bolha | `sfx.py <pasta>` gera todos | ✅ |
| 46 | Conectores | Descript, HeyGen, Canva, Moda, Pinterest, Instagram | `references/conectores.md` | 🟡 |
| + | Pessoa | Pessoa duplicada / várias versões (ontem, hoje, amanhã) | `clones` | ✅ |
| + | Cenário | Vários cenários trocando no tempo da fala | `cenario` com `scenes` | ✅ |
| + | Cena | Moldura 3D + explicação; camadas de vidro; estúdio 3D | `moldura`, `camadas`, `estudio3d` | ✅ |
| + | Cena | Mapa, infográfico, documentário | `mapa`, `infografico`, `documentario` | ✅ |

## Sensores (o que dispara efeito)
| Sensor | Aqui |
|---|---|
| Palavra (início/fim) | Parakeet (tempo por palavra) |
| Estrutura: número dito, lista, pergunta, frase de gancho | `triggers.py` (dinheiro, enumeração, frases da marca) |
| Pausa e ênfase | silêncios por energia + palavras de poder |
| Rosto e queixo | MediaPipe (legenda abaixo do queixo, zoom centrado, palavra atrás) |
| Mão | MediaPipe Hands (`follow: "hand"`) |
| Recorte da pessoa | MediaPipe selfie (palavras/objetos atrás, clones, cenário) |
| Expressão e gesto (sorriso, apontar) | ainda não; próximo passo do mapa de gatilhos |

## Mapa de gatilhos
`triggers/padrao.json` (todas as marcas) + `brands/<slug>/triggers.json`. Ex.: "Minha aposta" → carimbo + boom +
tremida; valor em reais → contador + som de venda; "primeiro/segundo/terceiro" → checklist; "comenta PRODUTO" →
notificação; "clica no botão" → botão com clique. `--gatilhos off` desliga.
