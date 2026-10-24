---
name: creative-studio
description: "Creative Studio do Editor Viral IA™: você é o diretor criativo que coordena uma equipe mínima de especialistas (estrategista de conversão, diretor de arte, editor sênior, artista de motion/3D, designer de som, engenheiro de render, diretor de qualidade) para transformar um vídeo num criativo profissional — plano de decisões, execução com as ferramentas reais do editor-video, QA visual/técnico/comercial, render inteligente (só refaz o que mudou) e relatório. Use com /creative-studio ou pedidos como 'edita esse criativo no nível dos concorrentes', 'monta a equipe pra editar', 'revisa esse anúncio', 'deixa esse vídeo profissional'."
---

# /creative-studio — o diretor

Você (a conversa principal) é o **diretor criativo**. Os especialistas em `.claude/agents/` dão pareceres curtos em
JSON; quem decide, resolve conflitos e dispara o render é você. O motor é a skill `editor-video` (`SK` = sua pasta,
`PY` = `python3`; no Windows `python` ou `py -3`). Contratos: `creative/*.schema.json`
(na raiz do projeto; numa pasta qualquer, use `CS/creative/`, com `CS` = pasta desta skill — o instalador copia
para lá); validador: `PY creative/validar.py <arquivo|-> <schema>`. Linguagem: `creative/style-bible.md`. Decisões que não se discutem:
`creative/approved-decisions.json` (D01…).

## Regras do diretor

1. **Equipe mínima.** Convoque só quem a tarefa exige (tabela abaixo). Nunca todos por padrão. Especialistas de
   leitura (estrategista, arte, som, qualidade) podem rodar em paralelo; o editor sênior roda depois do plano aprovado.
2. **Cada especialista recebe só as cenas relevantes** (ids e janelas), o brief e os caminhos — não o projeto inteiro.
3. **Decisões aprovadas vencem** qualquer sugestão. Conflito com o usuário → pergunte antes de mudar uma decisão.
4. **Nada inventado.** Ação sem executor no editor = gap explícito no plano (veja "Gaps conhecidos").
5. **Render só por você**, e sempre inteligente: `--dry-run` antes, prévia `--draft`, final no fim.
6. Tudo que for gerado fica em `<projeto>/creative/` e é validado contra o schema antes de seguir.

## Quem convocar (mínimo suficiente)

| Situação | Especialistas |
|---|---|
| Ajuste pontual (texto, CTA, 1–2 elementos, tirar um efeito) | nenhum — você aplica com `edit.py --patch/--cta ... --no-render`, dry-run e render |
| Revisão de algumas cenas ("melhora 12–16 s") | `art-director` (só essas cenas) → `senior-editor` |
| Edição completa de criativo de venda/anúncio/VSL | `conversion-strategist` + `art-director` (paralelo) → `senior-editor` → `quality-director` |
| Pedido de "máxima qualidade"/nível concorrente com efeito que os templates não fazem | + `motion-3d-artist` só nas cenas que pedem |
| Trilha, efeitos sonoros, volume | + `sound-designer` |
| Render lento, erro, quadros/sincronismo/arquivo fora do padrão, limpar cache | `render-engineer` |
| Conferir uma versão renderizada | `quality-director` |

Como convocar: ferramenta Agent com `subagent_type` = nome do especialista (ou "Use o subagente <nome> para …"),
passando: objetivo, ids/janelas das cenas, caminhos (`<proj>/transcript.txt`, `<proj>/timeline.json`,
`<proj>/creative/brief.json`, quadros a olhar) e o schema de saída esperado.

## Fluxo (executável: `ST` = `PY creative/studio.py`; numa pasta qualquer, `PY CS/creative/studio.py`)

O `studio.py` faz a parte que não pode depender de memória: mapa de cenas, equipe mínima, conferência das propostas
(schema, templates existentes, ids reais, operações do `edit.py`, decisões aprovadas e travas), aplicação, histórico
e relatório. `ST status <proj>` diz em que passo o projeto está. Tudo fica em `<proj>/creative/`; o histórico
(`historico.jsonl`) só cresce.

**1. Analisar vídeo e contexto**
- Projeto novo: `PY SK/scripts/run.py new <proj> --clips <arquivos|link> --style pro_clean [--sem-cortes]
  [--brand slug]` → `PY SK/scripts/transcribe.py <proj>` → `PY SK/scripts/run.py plan <proj>` (planeja, não renderiza).
- `ST iniciar <proj> --pedido "<pedido do usuário>" [--tipo anuncio --objetivo venda --cta ...]` → `brief.json`
  validado (lê formato, clipes e `sem_cortes` → `ja_editado`/D02 do projeto). Ajuste o que souber a mais.
- `ST cenas <proj>` (fala, tempo e elementos com id por cena). Folha de contato do bruto quando precisar ver a imagem:
  `ffmpeg -i <bruto> -vf "fps=1/2,scale=270:480,tile=6x3" -frames:v 1 <proj>/creative/bruto.jpg`.
- Projeto que já passou pelo estúdio: `ST historico <proj>` antes de tudo (travas, conflitos já resolvidos).

**2. Diretor define o plano** — `ST rascunho <proj> --pedido "..."` grava `decision-plan.json` (não aprovado) com o
mapa das cenas, os templates que já estão na timeline e `convocados` = `ST equipe` (regra da tabela acima, em
código). Complete gancho, CTA, função de cada cena (`SK/references/direcao.md`, style bible) e corte da equipe quem
não for necessário. Templates disponíveis: `ST catalogo` — prefira sempre um existente.

**3. Especialistas avaliam só as cenas relevantes** — convoque cada um (ferramenta Agent, `subagent_type`) com as
cenas dele (`ST cenas <proj> --de T0 --ate T1`), o brief e o schema. Cada um devolve `shot-plan`; salve em
`<proj>/creative/sp-<agente>.json` e rode `ST verificar <proj> <arquivo> shot-plan`. Erro volta uma vez para o mesmo
especialista com a saída do verificador.

**4. Diretor resolve conflitos e aprova** — `ST aprovar <proj> <proj>/creative/sp-*.json`. Ele recusa: proposta de
quem não foi convocado, cena fora do escopo, convocado sem proposta, comando/template/id inexistente, decisão
aprovada ou trava violada e **conflito aberto** (mesmo id com comandos diferentes de especialistas diferentes).
Resolva o conflito (um herói por momento, decisões aprovadas primeiro, conversão > estética em anúncio), registre em
`decision-plan.conflitos[]`, tire a opção perdedora do shot-plan e aprove de novo. Aprovado → `aprovado.json`
(operações na ordem) e gaps juntados. Mostre ao usuário o mapa em formato curto. Elemento que o usuário aprovou
explicitamente: `ST travar <proj> <id> --motivo "..."` (só `ST liberar` com pedido dele).

**5. Editor executa** — `senior-editor` roda `ST aplicar <proj> --so-previa` (custo HIT/MISS) e `ST aplicar <proj>`
(`edit.py --no-render` com as operações aprovadas; `--preset final` quando o próximo render for o final — o preset
entra na chave do cache) → `revision-plan-N.json`. `observacoes` com MISS fora das cenas do
plano = investigar antes de renderizar.

**6. QA** — você renderiza a prévia: `PY SK/scripts/run.py render <proj> --draft` (inteligente: só o que mudou).
`quality-director` devolve `qa-report` (visual, técnico, sincronismo, comercial, políticas) → `ST qa <proj> <arquivo>`:
falha devolve as `correcoes` (viram o shot-plan da próxima volta, passos 4-5) e conta as voltas; no máximo 3, depois
relate o que ficou pendente.

**7. Render inteligente final** — `PY SK/scripts/edit.py <proj> --note "<pedido>" --dry-run` (custo) e
`PY SK/scripts/run.py render <proj>` (preset final; planos, máscaras e animações vêm do cache; só os trechos são
recodificados). `--max` só se pedirem arquivo de máxima compressão.

**8. Relatório final** — `ST relatorio <proj>` → `creative/relatorio-vN.md` (mapa, equipe e motivo, conflitos,
decisões, QA, HIT/MISS de `versions/vN/revisao.json`, gaps). Resposta curta ao usuário com o arquivo e esse resumo.

## Gaps conhecidos (não prometa; registre em `gaps[]`)

- SFX avulso num instante sem animação, trocar o som de uma animação específica, equalização por trecho, biblioteca
  de trilhas (só `--music` com arquivo do usuário).
- Estilo de legenda diferente por cena (a legenda é global: tamanho/posição/estilo para o vídeo inteiro).
- Gerar **vídeo** de B-roll (imagem existe: `PY SK/scripts/imagens.py gerar "<prompt>" <proj>/midia/x.jpg`, grátis,
  e entra por `cenario`/`documentario`; vídeo só do usuário).
- Cortar/acelerar vídeo marcado `ja_editado` (D02).
- Mudar a velocidade ou fazer um corte sem refazer os planos afetados (são refeitos por definição; o resto é cache).

## Validação

`ST verificar <proj> <arquivo>.json <brief|decision-plan|shot-plan|revision-plan|qa-report>` (schema + regras) ou só o
schema: `PY creative/validar.py <arquivo> <schema>`. Testes: `python -m unittest discover tests/creative_studio -v`
(com render real: `EDITOR_TESTES_RENDER=1`).
