# Auditoria de arquitetura — Editor Viral IA™ (skill `editor-video`)

Data: 2026-10-23. Código auditado: commit `eb5f2e9` (branch `claude/video-editor-skill-y2ndvw`). O trabalho não
publicado de outros agentes (câmera/acabamento e 3D) foi parado e guardado em `git stash` (`WIP polish forks A+C`)
para que a auditoria olhasse só o código publicado. Nenhum arquivo do editor foi alterado durante a auditoria.

## 1. Arquitetura real

```
run.py new ──> project.json (clipes, estilo, overrides)            [fonte da verdade do usuário]
transcribe.py ──> transcript.json / transcript.txt                 [Parakeet, por clipe]
analyze.py ──> edl.json + qa/takes.md                              [tomadas, pausas, gaguejos; ou 1 segmento/clipe no modo sem cortes]
plan.py ──> timeline.json                                          [planos+zoom, palavras, legendas, palavras atrás,
                                                                    B-roll, gráficos, motion (pedidos + gatilhos), fx, SFX]
conectores.py ──> qa/pedidos-de-midia.md                           [só no run.py; o edit.py não chama]
render.py ──> renders/vN_<estilo>.mp4 + versions/vN/{timeline,project,qa}.json
    face_for_shots   (work/face_<clipe>.json)  → ajusta cx/cy/chin de cada plano EM MEMÓRIA
    render_shots     (work/shots/*.mkv → work/aroll.mkv, chave work/aroll.key)
    person_mask      (work/mask.mp4 + work/mask_stats.json)  — vídeo inteiro
    motion.render_clip (work/motion/clip_<sig>.mov; quadros em frames_<key>/) — Chromium/Playwright via Node
    recuo/place_behind/fit_behind (em memória)
    compose          → UM grafo ffmpeg para o vídeo inteiro: cor, palavras atrás (máscara), B-roll, recuo,
                       motion, gráficos, fx, legendas (ASS), mixagem de voz+SFX+trilha, loudnorm, H.264
    qa               → folha de contato + LUFS
edit.py ──> acrescenta pedidos em project.json["overrides"] e roda analyze → plan → render (sempre os três)
```

Fonte de verdade: `project.json → overrides` (lista de pedidos acumulados). `timeline.json` é **derivado e
descartável**: é recriado do zero a cada `plan.py`. Elementos da timeline não têm identidade (sem `id`).

## 2. Mecanismos de cache (o que existe hoje)

| Componente | Chave / onde | Invalida quando | Observação |
|---|---|---|---|
| Transcrição | nenhuma | `run.py all` sempre retranscreve | `edit.py` não retranscreve (ok) |
| Rosto por clipe | `work/face_<clipe>.json` (só o id) | nunca | trocar o arquivo do clipe com o mesmo id usa rastreio velho |
| A-roll | `work/aroll.key` = sha1(**todos** os planos) | qualquer mudança em qualquer plano | `rmtree(work/shots)`: **re-codifica todos os planos**; 1 slot só |
| Máscara | `work/mask.mp4` (sem chave) | apagada sempre que o A-roll muda | MediaPipe no **vídeo inteiro**; 1 slot só |
| Quadros de motion (needs_video) | `frames_<sha1(todos os planos, t0, t1…)>` | qualquer plano mudar, mesmo fora da janela | |
| Clipe de motion | `clip_<sha1(página, params, duração) + bytes de lib/*>` | params/HTML/lib mudam | bom: não depende de t0 absoluto; ruim: params enriquecidos com dados do vídeo inteiro |
| Composição final | nenhuma | sempre | ~27 s fixos em qualquer revisão |
| SFX sintetizados | `work/sfx/` | — | ok |

## 3. Evidência medida: o que cada revisão refaz

Projeto de referência `ref_pro2` (Mentos, 14,9 s, 7 planos, 4 animações), CPU de 4 núcleos, `--draft`.
Script: `docs/editor-video/auditoria/exp.py`; resultados brutos: `docs/editor-video/auditoria/exp_resultados.jsonl`.

| Revisão | Tempo | Refeito |
|---|---|---|
| R1 só legenda maior | 30,8 s | composição inteira (28,0 s) |
| R2 só CTA | 29,8 s | composição inteira (26,8 s) |
| R3 corta 1 frase no meio | 59,7 s | **todos** os planos, **máscara inteira** (10,5 s), quadros da animação de vídeo, composição |
| R4 desfaz o corte | 44,3 s | **tudo de novo** (o cache só guarda a última versão) |
| R5 velocidade 1,1 | 60,5 s | tudo |

## 4. Por que revisões provocam retrabalho (causas, com evidência no código)

1. **Composição monolítica** (`render.py: compose`) — um único `ffmpeg` re-codifica o vídeo inteiro a cada
   versão, mesmo quando só a legenda ou o texto do CTA mudou. É o custo fixo de ~27 s de toda revisão.
2. **Cache de 1 slot** — `render_shots` apaga `work/shots` e o A-roll anterior; a máscara é apagada junto. Voltar
   a um estado anterior (R4) paga tudo de novo.
3. **Granularidade global** — a chave do A-roll e a dos quadros de motion usam a lista **inteira** de planos:
   um corte em 6 s invalida plano, máscara e quadros dos 14 s restantes.
4. **Zoom por índice** (`plan.py`: `n % punch_every`) — remover um plano desloca o padrão de zoom de **todos** os
   planos seguintes: mesmo com cache por plano, todos mudariam.
5. **Máscara do vídeo inteiro** (`vision.person_mask(aroll)`) — não há máscara por plano.

## 5. O replanejamento sobrescreve edições manuais? **Sim (confirmado).**

Teste reproduzível (`tests/editor_video` + script da seção 3): edita `timeline.json` à mão (param de um motion e
`zoom0` de um plano), roda `edit.py --caption-size +10%` → as duas edições somem.

- `plan.py` grava `timeline.json` do zero (`save_json(paths["timeline"], {...})`); não lê a timeline anterior.
- `edit.py` sempre roda `analyze → plan → render`; `run.py render` também. O `SKILL.md` (seções 3 e 5) manda
  editar `timeline.json` à mão "para casos que os comandos não cobrem" — essas edições morrem na próxima revisão.
- Mesmo sem replanejar, `render.py:face_for_shots` **sobrescreve `cx`/`cy`** de todos os planos com rosto:
  reenquadramento manual nunca é respeitado.

## 6. Riscos

| # | Risco | Evidência | Prioridade |
|---|---|---|---|
| R-1 | Edições manuais da timeline perdidas no replanejamento | seção 5 | **P0** |
| R-2 | Reaplicar o mesmo `--motion` (ou `@motion.json`) **duplica** animações | teste: 2 pedidos iguais → 2 cópias | **P0** |
| R-3 | Composição inteira refeita em toda revisão (~27 s fixos) | seção 3 | **P0** |
| R-4 | Corte/velocidade invalidam A-roll, máscara e quadros do vídeo inteiro | seção 3, R3/R5 | **P0** |
| R-5 | Windows: `prepare_fonts` usa `symlink_to` (exige modo desenvolvedor/admin no Windows) | `render.py: prepare_fonts` | **P0** |
| R-6 | `edit.py` grava `project.json` antes do render; se o render falha, o pedido fica aplicado sem versão (sem rollback) | `edit.py` fim do `main` | P1 |
| R-7 | Remoção de motion por **índice** (`--motion-remove N`): frágil após várias rodadas | `plan_motion` | P1 |
| R-8 | `run.py curta/variacoes` deixam `edl.json`/`timeline.json` no estado temporário e criam versões em `versions/` | `_temp_render` restaura só `project.json` | P1 |
| R-9 | Cache de 1 slot: desfazer uma mudança custa um render completo | R4 | P1 |
| R-10 | Zoom por índice: um corte muda o enquadramento de todo o resto do vídeo | `plan.py` passo 1 | P1 |
| R-11 | `find_word` usa a 1ª ocorrência: a mesma frase dita 2 vezes não pode ser alvo da 2ª | `plan.py: find_word` | P2 |
| R-12 | Mudanças em `lib/*.js` invalidam todos os clipes de motion de todos os projetos | `motion._page_bytes` | P2 (correto, mas caro) |
| R-13 | Rastreio de rosto em cache só pelo id do clipe | `face_for_shots` | P2 |
| R-14 | Motion pedido some sem aviso quando a sobreposição o deixa com menos de 1 s | `resolve_overlaps` | P2 |
| R-15 | `run.py all` sempre retranscreve | `cmd_all` | P2 |

## 7. Prioridades

- **P0** — timeline persistente com IDs estáveis + patches manuais que sobrevivem (R-1); pedidos idempotentes
  por id (R-2); cache por componente com composição por trechos (R-3, R-4); fallback de cópia para fontes no
  Windows (R-5).
- **P1** — transação/rollback (R-6, R-9), remoção por id (R-7), `_temp_render` restaurando tudo (R-8), zoom
  estável por id (R-10).
- **P2** — alvo da N-ésima ocorrência, aviso de motion descartado, cache de rosto com assinatura do arquivo,
  transcrição em cache.

## 8. Referência e baseline preservados

- Projetos de referência **somente leitura** com checksums: `scratchpad/referencia/` (`ref_semcortes`,
  `ref_pro2`, `mentos_bruto.MOV`, `MANIFEST.sha256`).
- Fixtures sem vídeo no repositório: `tests/editor_video/fixtures/{semcortes,pro2}`.
- Goldens gerados com `eb5f2e9`: `golden_edl.json` e `golden_timeline.json`.
- `tests/editor_video/test_baseline.py`: o planejamento tem que bater com o baseline e ser determinístico.
  Rodar: `python -m unittest discover -s tests/editor_video -v` (só biblioteca padrão).
