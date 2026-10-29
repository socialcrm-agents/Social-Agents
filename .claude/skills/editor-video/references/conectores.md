# Conectores: quando usar cada um e como o arquivo chega ao projeto

`run.py plan`/`render` gera `qa/pedidos-de-midia.md`: citações, profissões, cenários e ferramentas ditas na fala,
cada uma com o conector sugerido, a busca ou prompt e onde encaixar. O Claude atende os pedidos que valem a pena
(não todos), salva os arquivos em `<projeto>/midia/` e encaixa com `edit.py`. Os conectores são ferramentas do
Claude (MCP); os scripts não chamam conectores.

## Quando usar cada conector

| Situação na fala | Conector | Chamada | Encaixe |
|---|---|---|---|
| Citação de pessoa, marca ou post ("segundo Fulano…") | Pinterest (Scrape Creators) | `mcp__Scrape_Creators__v1_pinterest_search {query, trim:true}` → `pins[].images.orig.url` | `--motion documentario` (foto + marcação) ou `giro`, **com crédito @ na tela** |
| Referência de outro criador ou Reel | Instagram (Scrape Creators) | `v2_instagram_reels_search` / `v1_instagram_profile` / `v2_instagram_media_transcript` | React em `split` com crédito nos 3 primeiros s (só com o vídeo do usuário ou com autorização) |
| Profissão citada (nutricionista, personal…) | Canva ou Moda (gerar fundo) + Pinterest (referência) | `mcp__Canva__generate-image {prompt, aspectRatio:"PORTRAIT_9_16"}` / Moda `canvas_edit_image` | `--motion cenario` (pessoa recortada na frente do cenário da profissão) |
| "Fundo", "cenário", lugar citado | Canva / Moda | prompt "<lugar>, luz natural, sem pessoas, 9:16" | `--motion cenario` com várias cenas (troca com chicote) |
| Cena com avatar ("eu como médico…") | HeyGen | **Não há ferramenta de avatar conectada** (o conector HeyGen só tem HyperFrames, e o compose é recusado no CLI). Gerar no app HeyGen e anexar o MP4 | `--add-broll` + `--broll-at` ou `carrossel3d` |
| Ferramenta citada (ChatGPT, Canva, Hotmart…) | Gravação de tela do usuário (melhor) | — | `tela_ia`, `documentario`, `carrossel3d` |
| Capa / thumbnail / arte estática | Canva (design) ou Moda | `create-design` / `export-design` | Fora do vídeo (publicação) |
| Revisão colaborativa ou cortes de vícios de linguagem | Descript (Underlord) | `import_media` → `prompt_project_agent` → `publish_project` | Alternativa externa; o editor local já corta pausas e erros |
| Publicar/agendar | Metricool, Blog2Social, Meta | Sempre com aprovação do usuário | — |

## Como o arquivo chega ao disco

- **No Claude Code local (computador do usuário):** as URLs devolvidas pelos conectores (Pinterest `i.pinimg.com`,
  export do Canva, Moda, Instagram `fbcdn`) baixam normalmente com `curl -L -o midia/<nome> "<url>"`.
- **No Claude Code na nuvem**, a rede do ambiente bloqueia esses hosts. Há duas opções:
  1. Liberar no ambiente (Network access → Allowed domains): `i.pinimg.com`, `export-download.canva.com`,
     `assets-cdn.moda.app`, `*.fbcdn.net`, `huggingface.co`, `*.hf.space`. Passo a passo em
     https://code.claude.com/docs/en/cloud-environments#network-access
  2. Usar a ponte que funciona sem liberar nada: `Moda upload {url}` (o Moda baixa do lado dele) →
     `canvas_create 1080x1920` + `canvas_apply_markup <image src="file_…">` → `canvas_screenshot`. A imagem chega
     inline e o Claude Code grava em `tool-results/*.jpg` (máx. ~562x1000). Copie para `midia/` e use
     `ffmpeg -vf scale=1080:1920`. Serve para fundo e referência (fica um pouco macio), não para vídeo.
- **Hugging Face:** o conector está ligado, mas `dynamic_space invoke` está desativado (gradio=none) e `hf_jobs`
  exige conta paga (402). Não use até isso mudar.

## Regras
- Crédito visível (@ ou fonte) sempre que aparecer imagem ou post de outra pessoa.
- Logos de terceiros só com autorização do usuário. Fotos de pessoas reais só com direito de uso.
- Imagem gerada por IA que parece real e mostra resultado: rotule "ilustração" ou "exemplo".
- Custo: Pinterest/Instagram consomem créditos do Scrape Creators (1 por chamada); Canva e Moda usam a cota do plano.
  Atenda só os pedidos que melhoram o vídeo (2 a 4 por Reel).
