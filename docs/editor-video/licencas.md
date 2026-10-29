# Licenças: reaproveitamento e uso comercial

> Levantamento técnico de licenças, não é parecer jurídico. Para vender a solução como produto,
> valide com um advogado de propriedade intelectual.

## Repositórios de referência

| Repositório | Licença encontrada | Pode copiar código? | O que fizemos |
|---|---|---|---|
| tenfoldmarc/video-edit-skill | **Nenhuma** (sem LICENSE e sem concessão no README). Sem licença, vale o padrão "todos os direitos reservados". | **Não.** Ler e se inspirar em ideias gerais pode; copiar código, textos do SKILL.md, templates HTML ou presets, não. | Nenhuma linha copiada. Só ideias genéricas (zona segura, revisão por texto), que não são protegidas por copyright. |
| yerinsabraham/video-edit-skill | **Apache-2.0** + NOTICE (Copyright 2026 Yerins Abraham) | **Sim**, inclusive comercialmente, desde que: inclua a licença Apache-2.0, preserve o NOTICE, marque arquivos modificados. Sem uso das marcas do autor. | Nenhuma linha copiada (código 100% original). Como só usamos ideias de arquitetura, não há obrigação de atribuição. |

Se no futuro copiarmos arquivos do yerin (ex.: templates de motion), basta: copiar `LICENSE` + `NOTICE` dele para
`third_party/yerin-video-edit-skill/`, manter os cabeçalhos e anotar "modificado por ...".
Do tenfoldmarc, só com autorização por escrito do autor.

## O que a nossa skill usa e distribui

| Componente | Licença | Uso comercial | Obrigações |
|---|---|---|---|
| Código da skill (`.claude/skills/editor-video`) | Nosso (escrito do zero) | Livre | Definir a licença do produto (proprietária ou aberta) |
| Fontes Anton, Poppins, DM Serif Display | SIL OFL 1.1 | Sim, inclusive embutidas no produto e nos vídeos | Manter `OFL-*.txt`; não vender as fontes isoladas; não usar o nome reservado em versões modificadas |
| ffmpeg | LGPL 2.1+ (o build do apt inclui partes GPL, como x264) | Sim, chamado como programa externo | Se distribuirmos um binário do ffmpeg junto: entregar licença + fonte correspondente. Chamando o ffmpeg instalado pelo usuário, nada a fazer. |
| x264 (encoder H.264 dentro do ffmpeg) | GPL-2.0 | Sim (uso do programa) | As mesmas do ffmpeg. A **patente** do H.264 é licenciada pela Via LA: vídeos para internet gratuita não pagam royalty; venda de software com encoder embutido pode exigir licença. |
| sherpa-onnx | Apache-2.0 | Sim | Atribuição se redistribuído |
| Modelo NVIDIA Parakeet TDT 0.6B v3 | CC-BY-4.0 | Sim | **Atribuição** à NVIDIA na documentação/produto |
| MediaPipe + modelos blaze_face / selfie_segmenter | Apache-2.0 (model cards do Google) | Sim | Atribuição se redistribuído |
| numpy (BSD-3), Pillow (MIT-CMU/HPND) | permissivas | Sim | Atribuição se redistribuído |
| SFX (whoosh, pop, riser) | Sintetizados pelo nosso código | Livre | Nenhuma |
| faster-whisper (opcional) | MIT; modelos Whisper da OpenAI MIT | Sim | Atribuição |
| three.js 0.180 (+ addons TTFLoader, TextGeometry, RoomEnvironment) | MIT | Sim | Manter `vendor/three/LICENSE` |
| opentype.js 1.3.4 | MIT | Sim | Manter `vendor/LICENSE-opentype.txt` |
| Ícones Lucide 0.544 | ISC (partes de Feather, MIT) | Sim | Manter `vendor/lucide/LICENSE` |
| Playwright (Node) + Chromium | Apache-2.0 / BSD e outras | Sim, usados como ferramenta local (não embutidos) | Nenhuma enquanto o usuário instala; se embutir, incluir avisos |
| MediaPipe hand_landmarker | Apache-2.0 | Sim | Atribuição se redistribuído |

Motion graphics: não usamos GSAP (licença própria da Webflow, com restrições), Remotion (paga para empresas com
mais de 3 pessoas) nem HyperFrames localmente. As animações usam um runtime próprio (`assets/motion/lib/runtime.js`)
e um renderizador próprio (`scripts/motion_render.mjs`).

**Logos de marcas** (ChatGPT, Claude, Instagram...): marcas registradas. Os anúncios de referência usam logos de
terceiros; a skill não inclui nenhuma. Em anúncio pago, usar logo de outra empresa pode sugerir parceria e violar
as diretrizes da marca e as políticas da Meta. Use só com autorização, ou em contexto editorial/comparativo.

Não usamos: HyperFrames (Apache-2.0, ok, mas evitamos depender de Chrome/Node), GSAP, Remotion (licença paga
para empresas com mais de 3 pessoas), sons do Pixabay (a licença proíbe redistribuir o arquivo isolado) nem Apify.

## Conteúdo que entra nos vídeos

- **Música:** só faixas com licença comercial (biblioteca paga, ou gerada com plano comercial). Música em alta do
  Instagram/TikTok em anúncio = risco de bloqueio e de Content ID.
- **B-roll/imagens:** do próprio usuário, de banco com licença comercial, ou gerados por IA com termos que
  permitam uso comercial. A skill não baixa mídia da internet.
- **Pessoas e marcas:** depoimentos e rostos de terceiros exigem autorização de uso de imagem. Anúncio com
  depoimento precisa ser verdadeiro e representativo (CONAR e Código de Defesa do Consumidor).

## Checklist antes de vender ou distribuir

1. Escolher a licença do nosso código e colocar `LICENSE` na raiz do produto.
2. Criar `THIRD_PARTY_NOTICES.md` com: OFL das fontes, Apache-2.0 (sherpa-onnx, MediaPipe), CC-BY-4.0
   (Parakeet: "Contém o modelo Parakeet TDT 0.6B v3 da NVIDIA, licenciado sob CC-BY-4.0").
3. Não embutir binário de ffmpeg (pedir a instalação ao usuário, como hoje). Se embutir, cumprir LGPL/GPL.
4. Se virar SaaS que codifica H.264 em escala, avaliar licença de patente (Via LA) ou exportar também em VP9/AV1.
5. Termos de uso do produto: o cliente é responsável pela licença das mídias que envia.
