# Editor automático de vídeos (Claude Code Skill)

Skill: [`.claude/skills/editor-video`](../../.claude/skills/editor-video/SKILL.md). No Claude Code, abra este
repositório e peça "edita esse vídeo no estilo Reels Viral" ou use `/editor-video`.

```
bruto.mp4 ─► transcribe (Parakeet, pt-BR, tempo por palavra)
          ─► analyze   (tomadas, pausas, gaguejos, frase cortada) ─► qa/takes.md   ◄── Claude revisa
          ─► plan      (estilo + correções) ─► timeline.json                       ◄── Claude pode editar
          ─► motion    (HTML/CSS 3D/Three.js -> vídeo no Chromium: moldura, camadas, estúdio 3D, objeto 3D...)
          ─► render    (rosto, zoom, máscara, cor, B-roll, motion, gráficos, legendas, áudio) ─► renders/vN.mp4
          ─► edit.py   (correção por texto) ─► próxima versão, com changelog
```

| Documento | Conteúdo |
|---|---|
| [analise-referencias.md](analise-referencias.md) | Arquitetura, scripts, render, transcrição e efeitos das duas referências |
| [licencas.md](licencas.md) | Licenças das referências e de cada dependência, checklist para vender |
| [limitacoes.md](limitacoes.md) | O que funciona no Claude Code e o que não funciona |
| [teste-real.md](teste-real.md) | Teste com vídeo real: antes/depois, números, o que foi corrigido |
| [comparativo-me-ia.md](comparativo-me-ia.md) | O que os anúncios do ME.IA mostram vs. o que a Skill faz |
| [../../.claude/skills/editor-video/references/motion.md](../../.claude/skills/editor-video/references/motion.md) | Templates de motion e como criar animações sob medida |
| [../../.claude/skills/editor-video/references/dependencias.md](../../.claude/skills/editor-video/references/dependencias.md) | Instalação |
| [../../.claude/skills/editor-video/references/revisoes.md](../../.claude/skills/editor-video/references/revisoes.md) | Pedidos em português -> comandos |

## Início rápido

```bash
cd .claude/skills/editor-video
python3 -m pip install -r requirements.txt
python3 scripts/setup.py --models          # baixa ~680 MB de modelos, uma vez
python3 scripts/setup.py                   # deve terminar em READY

python3 scripts/run.py new ~/edits/meu-video --clips ~/Downloads/bruto.mp4 \
        --broll ~/Downloads/tela.mp4 --style reels_viral
python3 scripts/run.py all ~/edits/meu-video            # v1
python3 scripts/edit.py ~/edits/meu-video --note "legenda maior" --caption-size +15%   # v2
python3 scripts/compare.py ~/Downloads/bruto.mp4 ~/edits/meu-video/renders/v2_reels_viral.mp4 antes_depois.mp4
```

## Estilos

| | Editorial Premium | Reels Viral | Anúncio de Alta Conversão |
|---|---|---|---|
| Ritmo | respira (pausas até 0,32 s) | seco (pausas até 0,16 s) | rápido (0,2 s) |
| Zoom | push-in lento contínuo | punch-in alternado a cada plano | punch em palavra-chave |
| Cor | dessaturada, quente nos altos, vinheta | contraste e saturação altos | limpa, nítida |
| Legenda | frase curta, palavra-chave em serifa itálica dourada | 2-3 palavras gigantes, palavra ativa amarela com pop | caixa escura, 3-4 palavras, benefício em verde |
| Palavra atrás | serifa itálica translúcida | Anton branca gigante | Poppins verde |
| B-roll | cartão com moldura + número de capítulo | tela cheia entrando de lado | tela dividida (produto em cima) |
| Gráficos | lower third, CTA discreto | faixa de gancho, CTA pílula | faixa de gancho, barra de progresso, CTA botão |
| Som | riser antes do CTA | whoosh + pop | whoosh + pop |
| Loudness | -16 LUFS | -14 LUFS | -14 LUFS |
