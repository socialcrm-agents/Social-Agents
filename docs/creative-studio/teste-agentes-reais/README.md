# Teste com os subagentes reais (2026-10-23)

Pedido: "melhora o visual de 12 a 16s, tá fraco perto dos concorrentes", no projeto de fixture do Mentos (sem cortes).
Os agentes foram chamados pelo nome (`subagent_type: art-director` e `senior-editor`), com as ferramentas
restritas pelo frontmatter. Não houve agente genérico.

1. `studio.py iniciar` + `rascunho`: equipe mínima = `art-director` (cenas c3, c4) + `senior-editor`.
2. O **art-director** propôs `objeto3d` "MENTOS" preso à mão (c3) e remover o card CTA duplicado `g_cta` (c4, D07).
3. `studio.py verificar` / `aprovar` → `aprovado.json`.
4. O **senior-editor** rodou `studio.py aplicar --so-previa` e **recusou-se a aplicar**: a âncora
   "dá uma olhadinha" é falada duas vezes (4,6 s e 12,1 s), e o editor usa a primeira, ou seja, outra cena.
   → regra nova no verificador (âncora ambígua) e devolução ao art-director, que corrigiu.
5. O senior-editor parou de novo na prévia: a animação ficaria com 0,76 s e o `plan.py` a descartava em silêncio,
   porque o `until` parava na **primeira** palavra do trecho (a documentação diz "onde termina").
   → correção no `plan.py` (última palavra + aviso ao descartar < 1 s) e verificação de duração no `studio.py`.
6. Aplicado: m8 `objeto3d` em 12,30–13,54 s, `g_cta` removido, sem avisos. Histórico em `historico.jsonl`.

Sem vídeo bruto nesta fixture, a prévia não foi renderizada. O render real dos 8 passos é coberto por
`EDITOR_TESTES_RENDER=1 python -m unittest tests/creative_studio/test_studio_integracao.py`.
