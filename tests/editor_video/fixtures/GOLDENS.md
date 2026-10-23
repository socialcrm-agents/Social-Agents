# Histórico dos goldens

- `eb5f2e9`: baseline original (antes do Smart Revision Engine).
- QA do Creative Studio (2026-10-23): `semcortes` atualizado por duas correções intencionais em `plan.py`:
  1. animação adiada pela regra "dois textos no topo" mantém os tempos internos (itens do checklist) na palavra falada;
  2. âncoras `at`/`until` passam pela correção de palavras (pedido com a grafia do ASR, ex. "toutifrut", continua valendo).
  Diferenças: `motion[5]` (checklist) `t1` e `params.items[].at`, e os SFX derivados deles.
