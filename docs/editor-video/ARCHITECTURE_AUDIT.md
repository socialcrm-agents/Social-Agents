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

## 9. Depois: Smart Revision Engine (implementado)

O que mudou (sem reescrever o editor e sem remover recursos; modo clássico disponível com
`EDITOR_COMPOSICAO=inteira`):

| Risco | Solução | Onde |
|---|---|---|
| R-1 edições manuais perdidas | IDs estáveis em todos os elementos; `timeline.json` editada à mão vira patch automaticamente (comparada com `work/timeline_gerada.json`); `edit.py --patch ID.campo=valor`, `--patch-remove`, `--patch-clear`; patch órfão avisa e fica guardado | `revisao.py`, `plan.py`, `edit.py` |
| R-2 motion duplicado | pedido idêntico é ignorado; pedido com `id` substitui; `--motion-remove` aceita id | `edit.py`, `plan.py` |
| R-3 composição inteira | composição por trechos de 4 s com cache por conteúdo; áudio separado; final por concatenação sem recodificar | `render.py`, `revisao.py` |
| R-4 invalidação global | cache por plano e por máscara; chave do motion depende só dos planos sob a janela | `render.py`, `motion.py` |
| R-5 Windows/symlink | fontes copiadas quando o link simbólico falha; listas de concat com caminho absoluto em barra normal; `os.replace` atômico | `render.py` |
| R-6 sem rollback | `edit.py` restaura `project.json`/`timeline.json` se algo falha; `run.py rollback --para N` | `edit.py`, `run.py` |
| R-8 `_temp_render` | restaura também `edl.json`, `timeline.json` e a timeline gerada | `run.py` |
| R-9 cache de 1 slot | cache guarda várias versões; `run.py limpar-cache --manter N` | `run.py` |
| R-10 zoom por índice | zoom de um plano persiste pelo id (um corte não muda o resto) | `plan.py` |
| (novo) atraso de áudio | **achado no teste de sincronismo**: `afftdn` (+25 ms) e `alimiter` (+5 ms) atrasavam o som em todas as versões, também no modo clássico. Agora a latência é medida no ffmpeg da máquina (cache em `~/.cache/editor-video/latencias.json`) e compensada | `render.py` |

Ferramentas: `edit.py ... --dry-run` / `run.py revisar` (HIT/MISS sem gravar), `run.py versoes`,
`run.py rollback`, `run.py limpar-cache`; cada versão grava `versions/vN/revisao.json` (HIT/MISS, chave, motivo,
segundos de cada componente).

### Prova: mesmo experimento da seção 3 (projeto `ref_pro2`, `--draft`, mesma máquina)

Script `auditoria/exp2.py`, resultados `auditoria/exp2_resultados.jsonl`.

| Revisão | Antes | Depois | O que ainda é refeito |
|---|---|---|---|
| Renderizar de novo sem mudança | ~30 s | **3,5 s** | nada (só a concatenação final) |
| Só legenda maior | 30,8 s | 21,4 s | os 4 trechos (a legenda está em todos) |
| Só CTA | 29,8 s | **11,7 s** | 2 trechos (onde o CTA aparece) |
| Corta 1 frase no meio | 59,7 s | **20,0 s** | 2 planos, 2 máscaras, 2 trechos, áudio |
| Desfaz o corte | 44,3 s | **3,7 s** | nada (tudo em cache) |
| Muda 1 animação (12,2–14,9 s) | ~45 s* | **16,7 s** | 1 animação + 1 trecho |
| Rollback para a 1ª versão | — | **3,2 s** | nada |
| Velocidade 1,1 | 60,5 s | 66,6 s | tudo (muda todos os planos: inerente) |

\* antes: refazia o clipe + a composição inteira (~27 s) + rosto/QA.

Operações que deixaram de ser repetidas: re-codificar planos não alterados, recalcular a máscara do vídeo
inteiro, extrair quadros/re-renderizar animações fora da janela alterada, recompor trechos sem mudança e
remixar o áudio quando só a imagem mudou.

### Testes

`python -m unittest discover -s tests/editor_video -v` (21 testes; 6 de render rodam com `EDITOR_TESTES_RENDER=1`):
baseline do planejamento (igual a `eb5f2e9`), IDs estáveis, patches que sobrevivem, captura de edição manual,
idempotência, grafo (mudar a animação de 12–16 s invalida só ela e o trecho), dry-run sem escrita, Windows
(fontes sem symlink, lista de concat), e com render: quadros/duração exatos, **sincronismo imagem×som em 5
eventos incluindo as emendas de 8 s e 12 s (≤ ½ quadro)**, render sem mudança = 0 MISS, revisão 12–16 s com
quadros fora da janela idênticos bit a bit, rollback 100 % cache e equivalência com o modo clássico (PSNR > 35 dB).

### Pendências conhecidas (P2)

- Máscara por plano reinicia o modelo do MediaPipe a cada plano: render a frio ~10 % mais lento.
- A montagem dos planos ainda deixa até ~10 ms de diferença entre som e imagem (início do plano no quadro do
  bruto vs. amostra de áudio); abaixo de meio quadro.
- Mudar a legenda refaz todos os trechos (a legenda aparece no vídeo todo), mas cada trecho é recomposto em paralelo.
