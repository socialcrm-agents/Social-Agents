# Análise das referências

Analisadas em 21/10/2026, clonadas do GitHub:

| | tenfoldmarc/video-edit-skill | yerinsabraham/video-edit-skill |
|---|---|---|
| Commit analisado | `3f01f2e` (15/10/2026) | `fe3b198` (04/10/2026), versão 0.9.2 |
| Licença | **Nenhuma** (sem arquivo LICENSE) | **Apache-2.0** (+ NOTICE) |
| Tamanho | ~10 scripts Python + template HTML | ~40 scripts Python (~8.300 linhas) |

## tenfoldmarc/video-edit-skill

**Arquitetura.** É uma skill do Claude Code (`SKILL.md` + `scripts/` + `references/` + `assets/template`). O
SKILL.md conduz o agente passo a passo: setup -> ingest -> escolha de tomadas -> assemble -> transcrição do corte
-> recorte da pessoa -> inserts animados em subagentes paralelos -> build -> render -> QA de cortes.

**Transcrição.** faster-whisper (`small.en`/`medium.en`), com tempo por palavra e confirmação de pausas por
`silencedetect`. É pensada para inglês: os modelos `.en` não servem para português.

**Escolha de tomadas.** Feita pelo próprio Claude lendo a transcrição (regra: "fica a última tomada completa"),
escrevendo um `edl.json` à mão. Não há algoritmo de similaridade.

**Motor de render.** HyperFrames (HeyGen, HTML + GSAP renderizado em vídeo por navegador headless, versão
fixada `0.8.34`). Cada reel é um `build.py` que gera HTML; o render sai do Chrome. Dá muita liberdade visual
(qualquer CSS/animação), mas exige Node 22+, Chrome e tem armadilhas (documentadas em `gotchas.md`: máscara CSS não
sobrevive, `autoAlpha`, ids obrigatórios, quadros fora de sincronia).

**Palavras atrás da pessoa.** Recorte com o `remove-background` do HyperFrames (CoreML no Apple Silicon, CPU
no resto, lento) + `headpos.py` para achar o topo da cabeça e uma fórmula para a cabeça cobrir só a base das
letras.

**Efeitos.** Três "looks" (bold, cool girl, cool dude), punch-in a partir de 4K, inserts de UI animados
(perfil do Instagram, janela do Claude), órbita de reels, SFX do Pixabay baixados no setup, checagem de zona
segura com guia vermelho.

**Pontos fortes:** acabamento visual muito alto, loop de revisão por texto, regras de zona segura.
**Fracos:** sem licença; dependente de Instagram/Apify para alguns efeitos; inglês; render pesado (Chrome).

## yerinsabraham/video-edit-skill

**Arquitetura.** Plugin para Claude Code e Codex (`skills/video-edit/SKILL.md` + `shared/scripts`). Princípio
declarado: o agente planeja; scripts Python determinísticos fazem a mídia com ffmpeg, e cada etapa escreve um
arquivo legível (`transcript.json`, `takes.json`, `edl.json`, `recipe.json`, `qa/report.md`).

**Transcrição.** whisper.cpp `small.en` + `align.py`, que reajusta o tempo das palavras pela detecção de silêncio,
+ `fix_transcript.py` para limpeza. Também focado em inglês.

**Escolha de tomadas.** `takes.py` agrupa orações parecidas (similaridade de cláusula) e mantém a ordem de primeira
aparição: reconstrói o roteiro mesmo com clipes fora de ordem.

**Motor de render.** Um único grafo de filtros do ffmpeg por render: cor -> zooms (cortando o A-roll em resolução
nativa) -> layouts (split, phone frame) -> texto atrás da pessoa (máscara Apple Vision ou MediaPipe) -> overlays
-> legendas ASS (libass) -> áudio (limpeza, SFX sintetizados, música com ducking, loudness).
Motion graphics opcionais em HyperFrames.

**Efeitos.** 8 looks em JSON (bold, editorial-dark, creator-pro, course-promo...), 12 templates de motion
(callout, stat, lower-third, social-cta, phone-frame...), logos via Simple Icons, export para NLE (EDL/FCPXML),
`revise.py` com snapshots para correções.

**Pontos fortes:** determinístico, rápido, sem navegador, licença permissiva, QA por arquivo.
**Fracos:** visual mais "template"; inglês; muitas peças.

## O que aproveitamos (como ideia, não como código)

| Ideia | De onde | Como ficou na nossa skill |
|---|---|---|
| Agente decide, script executa, tudo em arquivo legível | as duas | `transcript.json -> edl.json -> timeline.json -> render` |
| Render em um grafo ffmpeg + legendas libass | yerin | `render.py` + `assets.py`, sem Chrome/Node |
| Texto atrás da pessoa com máscara MediaPipe | as duas | `vision.py`, com regra de rosto + cabeça estável |
| Zona segura do Reels como regra dura | tenfold | `common.py` (220 / 1470) e posições fixas |
| Revisão por texto com versões | as duas | `edit.py` com overrides persistentes + `changelog.md` |
| SFX sintetizados (sem licença) | yerin | `assets.py` (whoosh, pop, riser) |

## O que fizemos diferente

- **Português primeiro:** transcrição com Parakeet TDT v3 (multilíngue, pontuação e maiúsculas nativas, tempo
  por token), rodando offline via sherpa-onnx. Não depende do HuggingFace (que pode estar bloqueado).
- **Pausas por energia adaptativa:** o limiar de silêncio é medido no próprio clipe (piso de ruído + 7 dB). Os
  -35/-40 dB fixos das referências falharam no nosso teste com celular em ambiente ruidoso.
- **Correções persistentes:** cada correção vira um override em `project.json`, então sobrevive a troca de
  estilo e a re-renders (nas referências, a revisão edita o build daquela versão).
- **Palavra atrás com fallback honesto:** se não há rosto/cabeça estável, a palavra vai para a frente como
  título animado, e o render diz isso.
- **Três estilos novos** pensados para o mercado BR: Editorial Premium, Reels Viral e Anúncio de Alta Conversão
  (com barra de progresso, legenda em caixa, tela dividida e CTA de botão).
