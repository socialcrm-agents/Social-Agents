# Auditoria: o potencial máximo de cada conector e de cada parte do editor (2026-10-28)

**A pergunta:** o que cada ferramenta que já temos consegue fazer no máximo, e quanto disso usamos hoje.
**Resposta curta:** usamos bem o corte, a legenda, o som e os blocos 2D. Do 3D, da IA generativa e dos conectores
usamos uma fração pequena, e é aí que os concorrentes estão na frente.

Legenda da coluna "hoje": 🟢 perto do máximo · 🟡 usamos uma parte · 🔴 quase nada · ⚫ não usamos

---

## Parte A — os motores do editor

### A1. Three.js (3D no navegador): **hoje 🔴, uns 15% do potencial**

| O que dá para fazer | Hoje | Exemplo no vídeo |
|---|---|---|
| Texto 3D extrudado, logo em placa 3D | 🟢 `objeto3d` | título com espessura e brilho |
| Foto do produto virando objeto 3D (extrusão do recorte) | 🟢 `produto3d` | produto voando para a mão |
| Modelo 3D completo (.glb) com animação, câmera de cinema e vista explodida | 🟢 `cena3d` (novo) | a casa de Tóquio, o produto desmontando em blocos |
| **Fotos e prints em 3D**: galeria flutuando em profundidade, câmera voando por dentro dela | ⚫ | "olha os resultados dos meus alunos" com 12 prints passando em 3D |
| **Foto 3D (parallax de verdade)**: a foto vira uma malha com relevo pelo mapa de profundidade e a câmera mexe | 🟡 (só no vídeo, `profundidade`) | foto do cliente ou do imóvel ganhando volume |
| **Partículas**: poeira de luz, faíscas, dinheiro caindo, a palavra se desfazendo em pó | ⚫ | "explodiu de vendas" com partículas douradas |
| **Pós-processamento**: brilho (bloom), profundidade de campo, aberração cromática, grão de filme | ⚫ | o 3D com cara de comercial e não de jogo |
| **Shaders de transição**: dissolver, líquido, vidro quebrando, página virando entre cenas | ⚫ | troca de cena "premium" |
| **Ambientes 3D (HDRI)**: produto num cenário de estúdio, praia ou cozinha com reflexo real | 🟡 (só a sala neutra) | perfume num pedestal com reflexo |
| **O vídeo da pessoa dentro do 3D**: o vídeo vira uma tela num ambiente 3D (celular, TV, outdoor) | 🟡 (moldura, carrossel em CSS) | você aparecendo dentro de um celular 3D girando |
| **Texto 3D em volta da pessoa**: anel de palavras girando atrás e na frente da cabeça | ⚫ | a palavra "VENDAS" orbitando você |
| **Gráficos 3D**: barras e pizza subindo em 3D com os números ditos | ⚫ | "faturei 3x mais" em barras 3D |
| **Mapa e globo 3D**: rota, países, "atendemos 12 estados" | ⚫ | |

### A2. Motion 2D (HTML, Anime.js, Lottie): **hoje 🟡**
- 51 blocos prontos, tipografia cinética, Lottie.
- Falta usar **Lottie de verdade**: hoje não temos nenhum arquivo. Uma biblioteca de 30-50 Lotties gratuitos curados (setas, checks, likes, carrinho, fogo, confete) vira enfeite automático nos gatilhos da fala.
- Falta **morph de formas e traço desenhado** (Anime.js faz, ainda não usamos): ícone virando outro, assinatura e setas "desenhando".

### A3. FFmpeg / corte / legenda / som: **hoje 🟢**
Corte por fala, legenda viva, zoom, correção de imagem, estabilização, voz de estúdio, trilha, SFX. Faltam:
- **speed ramp** (acelera e desacelera no beat);
- **cortes no ritmo da música** (beat sync).

---

## Parte B — os conectores

| Conector | O máximo que ele faz para vídeo | Hoje | O que fazer |
|---|---|---|---|
| **Hugging Face** | Roda IA com placa de vídeo na nuvem: **foto → modelo 3D** (TRELLIS, Hunyuan3D), **imagem → vídeo** (Wan 2.2: B-roll e produto ganhando movimento), **imagem do início e do fim → vídeo**, **voz clonada** (Chatterbox), **recorte de objetos** (SAM 3), **ampliar a imagem para 9:16** (outpaint), **girar a câmera numa foto** (Qwen Image Edit Angles), **restaurar foto ruim** (InstantIR), **tirar objeto/marca d'água**, imagens (FLUX, Qwen-Image) | 🔴 (só busca) | **1º da lista.** Precisa liberar (ver Parte D). Com isso: foto do produto → 3D → `cena3d`; foto → B-roll animado; fundo 16:9 → 9:16 |
| **Canva** | Gerar imagem (fundos, cenários), remover fundo, **separar arte em camadas** (vira parallax), criar e redimensionar designs (capa, thumbnail, carrossel do mesmo vídeo), exportar, kit de marca, **importar "Claude Motion"** | 🟡 (cenário e fundo) | Capa e thumbnail automáticas de cada vídeo; camadas → parallax; kit de marca → cores e fontes do vídeo |
| **Moda** | Design editável, imagem gerada e editada dentro do design, remover fundo, **ver quadros de vídeo**, motion com exportação mp4/gif | 🟡 (fundo) | Cards e telas animadas exportadas como clipes; capa |
| **Descript** | **Agente Underlord**: Studio Sound, tirar vícios de linguagem, **Eye Contact** (olhar na câmera), tela verde, **tradução e dublagem**, exportar timeline para Premiere e DaVinci, publicar | ⚫ | **Correção de olhar e dublagem pelo Descript** (já está conectado; usa o plano Descript que você tiver). Exportar timeline para o seu editor humano |
| **HyperFrames (HeyGen)** | Render na nuvem de composições HTML; projeto compartilhável no HeyGen | ⚫ | Render pesado (3D) na nuvem quando o PC estiver lento |
| **Scrape Creators** | Anúncios, Reels, TikTok e YouTube de qualquer perfil, **transcrições**, **músicas em alta** (TikTok/Instagram audio), tendências, comentários | 🟡 (vencedores) | Banco de ganchos por nicho a partir das transcrições; trilhas em alta (como referência de clima); comentários → objeções para o roteiro |
| **Meta Ads** | Biblioteca de anúncios, métricas por anúncio, testes A/B, **criar o anúncio com o vídeo** | 🟡 (aprender, vencedores) | Subir a fábrica de variações direto como anúncios em rascunho |
| **Vturb** | Métricas, curva de retenção, teste A/B, upload | 🟡 (aprender) | Subir as versões e montar o A/B (com o seu "sim") |
| **Metricool / Blog2Social** | Melhor horário, análise, **agendar e publicar** nas redes | ⚫ | Editou → agenda no melhor horário com legenda pronta |
| **Google Drive** | Buscar vídeos brutos e entregar os prontos | 🟡 | Pasta "brutos" → edição automática → pasta "prontos" |
| **Notion / Claude Docs** | Relatórios, roteiros, calendário | ⚫ | Calendário de conteúdo com os ganchos aprovados |
| **Make** | Automação entre tudo | ⚫ | Gatilho "vídeo novo no Drive" → edita → avisa no WhatsApp |
| **Lovable / Netlify** | Páginas | — | Página de acesso do Editor Viral |
| **Gmail / Calendar / Hubla** | E-mail, agenda, vendas | — | Pós-venda do Editor Viral |

---

## Parte C — o plano em ordem de impacto no vídeo

1. **Three.js no máximo**, sem custo e testável aqui:
   - fotos em 3D;
   - foto 3D com profundidade;
   - partículas;
   - brilho e profundidade de campo;
   - transições com shader;
   - o vídeo da pessoa dentro de objetos 3D;
   - texto orbitando;
   - gráficos 3D.
   - *Resolve "os outros estão muito mais incríveis".*
2. **Hugging Face ligado:**
   - foto do produto → 3D;
   - foto → B-roll em vídeo;
   - 16:9 → 9:16;
   - restaurar foto.
   - *Precisa da sua liberação.*
3. **Biblioteca de Lottie** gratuita e curada, entrando sozinha nos gatilhos da fala.
4. **Descript:** olhar na câmera e dublagem, como alternativa ao HeyGen, no seu plano Descript.
5. **Publicação:**
   - capa e thumbnail no Canva;
   - agenda no Metricool;
   - variações como anúncios em rascunho no Meta.
6. **Speed ramp e corte no ritmo da música.**

---

## Parte D — o que só você pode liberar

- **Hugging Face (Spaces):** no site do Hugging Face, em Settings → MCP, ative o uso de Spaces. Hoje o conector
  está com "gradio=none", que bloqueia rodar os modelos. Para render pesado, a conta PRO (US$ 9/mês) dá cerca de
  25 min de placa de vídeo por dia.
- **Rede desta sessão** (só para eu testar aqui): liberar `huggingface.co`, `*.hf.space`,
  `export-download.canva.com`, `assets-cdn.moda.app` e `*.fbcdn.net`. No seu computador já funciona.
- **Descript:** conferir se o seu plano tem Eye Contact e dublagem.
