# O que funciona no Claude Code e limitações

## Funciona (testado em 21/10/2026 com vídeo real, Linux, 4 vCPU, sem GPU)

| Item pedido | Status | Como |
|---|---|---|
| 1. Receber vídeos brutos | ✅ | `run.py new --clips ...` (vários clipes = várias tomadas) |
| 2. Identificar melhores tomadas | ✅ regra + Claude | `analyze.py`: regravação (fica a última), gaguejo, frase final interrompida. O Claude revisa `qa/takes.md` e corta o que a regra não pega (ex.: abertura fraca). |
| 3. Remover pausas e erros | ✅ | Pausas medidas no áudio (limiar adaptativo) viram corte seco; muletas ("ãh", "hum") saem. |
| 4. Legendas animadas | ✅ | libass: palavra ativa colorida com "pop" (Viral), frase com destaque em serifa itálica (Editorial), caixa + slide com destaque verde (Anúncio). |
| 5. Zooms e cortes dinâmicos | ✅ | Tomadas longas viram planos de 2,6-5 s com troca de zoom (punch-in/push-in), centralizados no rosto quando há rosto. |
| 6. Palavras/gráficos atrás da pessoa | ✅ com condição | MediaPipe recorta a pessoa; a palavra fica atrás só com rosto detectado e cabeça estável. Sem pessoa no quadro, vira título animado na frente (o render informa). |
| 7. B-roll, imagens, animações | ✅ | B-roll do usuário em tela cheia (slide), cartão com moldura (fade + subida) ou tela dividida; gráficos gerados: gancho, CTA, lower third, número de capítulo, barra de progresso. |
| 8. Estilos diferentes | ✅ 3 estilos | `styles/*.json` (cor, ritmo de corte, zoom, legenda, gráficos, SFX, loudness). Estilo novo = novo JSON. |
| 9. Exportar MP4 | ✅ | 1080x1920, 30 fps, H.264 High + AAC 48 kHz, `+faststart`, loudness -14/-16 LUFS. |
| 10. Correções por texto e re-render | ✅ | `edit.py` (18 operações) + `--note`; overrides persistentes; `versions/` + `changelog.md`. |

## Limitações reais

**Ambiente / rede**
- Este ambiente de nuvem do Claude Code bloqueia `huggingface.co`, então o Whisper/faster-whisper não baixa modelos.
  Solução adotada: Parakeet via GitHub. No seu computador, os dois funcionam.
- O conector do Google Drive só entrega arquivos de até ~6 MB (resposta em base64). Vídeos maiores precisam ser
  enviados direto para a sessão, ou rodar a skill localmente no Claude Code apontando para a pasta do Drive
  sincronizada no computador. **Por isso o teste usou seu vídeo de 6 MB e não os clipes de câmera.**
- Não há GPU aqui: recorte da pessoa e render rodam em CPU (~2,2x a duração do vídeo).

**Edição**
- "Melhor tomada" é decidida por texto (repetição e similaridade), não por expressão facial, energia da voz ou
  foco. Para gravações com muitas tomadas, o Claude ainda deve ler `qa/takes.md` e decidir.
- O ASR erra nomes próprios e marcas (corrija com `--fix`). Parakeet v3 foi treinado com bastante português
  europeu; no teste o pt-BR saiu correto, mas gírias podem errar.
- Tempo por palavra vem dos tokens do modelo (precisão ~±80 ms); karaokê fica bom, mas não é alinhamento forçado.
- Palavra atrás da pessoa depende de rosto frontal, fundo separável e pouca movimentação da cabeça. Cabelo
  muito volumoso, fundo da mesma cor da roupa ou várias pessoas pioram o recorte (MediaPipe é rápido, não
  perfeito).
- B-roll é colocado por palavra-gatilho ("olha", "veja", "sistema"...) e espaçamento. Para casar uma imagem
  específica com uma frase específica, use `--broll-at`.
- Não gera B-roll, voz ou imagem por IA sozinho (pode ser plugado depois: Veo, Kling, Nano Banana, ElevenLabs).
- Música: não há biblioteca embutida (licença); o usuário fornece a trilha.
- Fonte de baixa resolução (o teste era 384x848) é ampliada para 1080x1920: fica mais suave; zoom forte
  amplia o defeito.
- Gráficos são PNG animados com fade/slide (sem motion design complexo tipo After Effects). Para animações de UI
  elaboradas, a evolução natural é um módulo HTML -> vídeo (HyperFrames, Apache-2.0).

**Claude Code**
- O Claude não "assiste" ao vídeo: ele lê transcrição, JSONs e olha quadros extraídos (contact sheet). A QA
  visual é por amostragem de quadros, não do vídeo inteiro.
- Renders longos (vídeos de mais de 3 minutos) devem rodar em segundo plano.
- No Windows, use `python` em vez de `python3`; o ffmpeg precisa estar no PATH (reinicie o Claude Code após instalar).
