# Como usar os dois produtos na conversa

| Produto | Para quem | Comando | Entra | Sai |
|---|---|---|---|---|
| **Editor de vídeo** (`editor-video`) | Quem grava a si mesmo (Reels, aula, anúncio falado) | `/editor-video` | vídeo bruto | vídeo editado (cortes, legenda, zoom, motion 3D) |
| **Anúncio de produto** (`anuncio-produto`) | Quem vende produto (TikTok Shop, loja, e-commerce) | `/anuncio-produto` | fotos/vídeo do produto + preço | anúncio de 10-60 s com voz, cenas e CTA |

São produtos separados: cada um tem a própria pasta, as próprias dependências e o próprio pacote de venda
(`python3 tools/empacotar.py <produto>`). Quem compra um não recebe o outro.

## Onde funciona

O editor roda programas de verdade no computador (ffmpeg, modelos de IA, navegador para as animações). Por isso:

| Lugar | Funciona? | Observação |
|---|---|---|
| **Claude Code no computador** (app desktop ou terminal) | ✅ completo | Recomendado. Lê os vídeos direto das suas pastas, sem limite de tamanho. |
| **Claude Code na web** (claude.ai/code) com este repositório | ✅ completo | O vídeo precisa chegar à sessão: anexe na conversa ou use um link. O conector do Drive só traz arquivos de até ~6 MB. |
| **Conversa normal do Claude.ai ou ChatGPT** | ❌ não é este editor | A conversa comum roda código numa caixinha com limite de tempo e tamanho, sem navegador para as animações. Por isso fica lenta e erra. A skill "editor-de-video-ia" que aparece lá é outra, mais simples. Para vender pelo Claude.ai ou pelo ChatGPT, o caminho é colocar o motor num servidor e ligar um conector (ver "Vender" abaixo). |

## Instalar no seu computador (uma vez)

1. Instale o Claude Code (app desktop ou `npm install -g @anthropic-ai/claude-code`), o Python 3.10+, o ffmpeg e o
   Node.js 18+.
2. Baixe este repositório e rode:
   ```bash
   python3 tools/instalar_skills.py --modelos
   npm install -g playwright && npx playwright install chromium
   ```
   O instalador cria `~/.claude/skills/editor-video` e `~/.claude/skills/anuncio-produto`, baixa os modelos
   (cerca de 1,5 GB no total, uma vez) e termina mostrando `READY` para cada skill.
3. Pronto. Abra o Claude Code **em qualquer pasta** e as duas skills já aparecem.

## O que falar na conversa

**Editor de vídeo**
- `/editor-video edita ~/Downloads/gravacao.mp4 no estilo Reels Viral com a minha marca`
- "corta as pausas e põe legenda amarela", "me coloca numa moldura 3D quando eu falo dos 3 passos"
- "faz 3 versões, uma com cada gancho que eu gravei", "faz uma de 30 e uma de 15 segundos"
- correções: "tira o 'então' do começo", "legenda maior", "troca o CTA por COMENTA EU QUERO"

**Anúncio de produto**
- `/anuncio-produto` e arraste 2 a 5 fotos: "Sérum LUMA, R$ 129,90, antes R$ 199,90, TikTok Shop, 20 segundos,
  voz feminina"
- "faz versões de 15 e 30 segundos", "usa a minha voz" (ele te manda o roteiro, você grava no celular e anexa)
- correções: "voz masculina", "mais premium", "tira a música", "põe frete grátis"

Ele também entende sem o `/`: "faz um anúncio desse produto", "edita esse vídeo".

## Velocidade (por que antes demorava e agora não)

- **Render**:
  - um vídeo de 30 s com 4 animações levava 120 s; agora leva 84 s;
  - uma correção (texto, legenda, CTA) levava 42 s; agora leva 31 s.
  
  Ganhos: planos em paralelo, codificação mais rápida com a mesma qualidade, animações duas por vez.
- **Anúncio de produto**: cerca de 50 s para 20 s de anúncio. Se o roteiro não muda, a voz não é refeita; se a
  imagem não muda, as cenas não são refeitas.
- **Na conversa**: a skill manda o Claude juntar todas as correções num render só, rodar em segundo plano e
  não reler arquivos à toa. Isso costuma ser o que mais demora.
- Para aprovar rápido: peça "me manda uma prévia" (gera a 15 fps ou em qualidade de rascunho).
- Máquina mais forte = mais rápido. Os números acima são de 4 núcleos sem placa de vídeo.

## Vender

| Formato | Como | Prós | Contras |
|---|---|---|---|
| **Skill (arquivo)** | `python3 tools/empacotar.py anuncio-produto`, um zip com instalador | Pronto hoje, custo zero de servidor | O comprador precisa instalar Claude Code, ffmpeg e Node. O arquivo é fácil de copiar. |
| **Serviço (SaaS)** | O motor roda num servidor; o cliente manda fotos ou vídeo e recebe o MP4. As portas de entrada são um conector MCP no Claude, um app no ChatGPT, um site e o WhatsApp. | Funciona para qualquer pessoa, no Claude e no ChatGPT. Dá para cobrar por vídeo ou por assinatura, e o código fica protegido. | Exige servidor com fila de vídeos, armazenamento e cobrança. |

Os planos que você descreveu (10 e 20 s grátis, 30 s ou mais pagos) se configuram na camada de serviço, que libera
as durações conforme o plano. As skills já geram todas as durações.
