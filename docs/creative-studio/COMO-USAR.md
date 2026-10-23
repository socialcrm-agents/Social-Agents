# Creative Studio — como usar

Equipe de edição para o Editor Viral IA™: você conversa com o **diretor** (a skill `/creative-studio`) e ele chama
só os especialistas necessários. O motor continua sendo a skill `editor-video`.

## Instalar

- **Neste repositório:** já funciona (`.claude/skills/creative-studio`, `.claude/agents/`, `creative/`).
- **Em qualquer pasta (Mac/Linux):** `python3 tools/instalar_skills.py creative-studio editor-video` — copia a equipe
  para `~/.claude/agents/` e os contratos para dentro da skill.
- **Windows:** o `INSTALAR.bat` do zip `dist/Editor-Viral-Windows-*.zip` já leva a equipe e os contratos.
- **Reinicie o Claude Code depois de instalar.** Os agentes de `.claude/agents/` são carregados quando a sessão
  começa; numa sessão aberta antes, eles não aparecem para o `Agent` (confirme com `/agents`).

## Invocar

No Claude Code (modo **Code**, com a pasta dos vídeos aberta):

```
/creative-studio edita os 4 vídeos desta pasta no nível dos concorrentes. Já cortei no CapCut.
Pode trocar o fundo se fizer sentido. Objetivo: venda no TikTok Shop, CTA "TOQUE NO CARRINHO".
```

Outros exemplos:
- `/creative-studio revisa só o trecho de 12 a 16 s do criativo X, ficou fraco`
- `/creative-studio o gancho está fraco, melhora sem mudar o resto`
- `/creative-studio faz QA da última versão e corrige o que estiver errado`

Para falar direto com um especialista: `@agent-art-director olha a cena de 4 a 7 s do projeto X`.

## O que acontece (8 etapas)

1. Análise do vídeo e `creative/brief.json`.
2. O diretor monta o mapa de edição (`decision-plan`).
3. Só os especialistas necessários avaliam só as cenas relevantes (`shot-plan`, JSON validado).
4. O diretor resolve os conflitos e aprova o plano.
5. O `senior-editor` aplica com os comandos reais (`edit.py ... --no-render`) e mede o custo (`--dry-run`).
6. O diretor renderiza a prévia (`--draft`, só o que mudou) e o `quality-director` faz o QA.
7. Render final inteligente (planos, máscaras e animações vêm do cache).
8. Relatório: mapa, especialistas, conflitos, QA, custo (HIT/MISS) e gaps.

Arquivos do projeto ficam em `<projeto>/creative/`. Validar qualquer um:
`python creative/validar.py <arquivo.json> <brief|decision-plan|shot-plan|revision-plan|qa-report>`.

## Regras da equipe

- Ninguém faz render completo por conta própria — só o diretor, e sempre com dry-run antes.
- Só o `senior-editor` aplica mudanças no projeto. Só o `motion-3d-artist` (templates) e o `render-engineer`
  (scripts) alteram código, e sempre com testes.
- `creative/approved-decisions.json` vence qualquer sugestão (rosto livre, sem cortes em vídeo já editado, nada
  inventado, sem logos de terceiros, CTA único, som em cada animação…).
- Ação que o editor não sabe fazer vira **gap** no relatório, nunca promessa.

## Testes

```
python -m unittest tests/creative_studio/test_creative_studio.py -v
python -m unittest discover -s tests/editor_video -v
```

## Teste ao vivo (2026-10-23)

Fluxo completo no anúncio real do Mentos (`teste-ao-vivo/`): brief → 2 especialistas em paralelo (estratégia c1,
arte c2) → plano aprovado com 1 conflito resolvido → editor sênior com dry-run → prévia → QA reprovou com 5 falhas
→ rodada 2 → QA aprovado → render final (só trechos recodificados) → relatório. Todos os JSON validados.
O fluxo achou 4 defeitos do editor (corrigidos com teste; ver `teste-ao-vivo/relatorio-v18.md`).

Observação: nesta sessão os agentes foram criados com ela já aberta, então foram executados com as instruções de
cada arquivo `.claude/agents/<nome>.md` por um agente genérico (o `subagent_type` por nome só existe em sessão
aberta depois da instalação; aí as restrições de ferramentas do frontmatter passam a valer pelo próprio Claude Code).
