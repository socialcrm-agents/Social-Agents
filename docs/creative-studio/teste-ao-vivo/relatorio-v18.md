# Relatório — Creative Studio · Mentos UP2U (v18)

**Arquivo:** renders/v18_pro_clean.mp4 · 17,37 s · 521 quadros · −14,3 LUFS · render final 34,5 s (só trechos recodificados).

## Pedido do diretor
Gancho fraco (0–2,6 s) e bloco "mãos" vazio (4,5–6,6 s) num anúncio de TikTok Shop já cortado (sem cortes, D02).

## Especialistas convocados (mínimo)
| Especialista | Por quê | Cenas |
|---|---|---|
| conversion-strategist | gancho só nomeava o produto | c1 |
| art-director | mão aparece em 18/60 quadros | c2 |
| senior-editor | aplicar o plano (2 rodadas) com dry-run | c1, c2 + correções |
| quality-director | QA da prévia v16 | tudo que mudou + CTA |

Não convocados: motion-3d-artist (templates existentes bastaram), sound-designer (som automático por animação já
cobre), render-engineer (sem erro de render).

## Mapa final
| Tempo | Fala | Função | Elemento |
|---|---|---|---|
| 0,0–2,6 | "Gente, eu tô aqui com esse chiclete da Mentos" | gancho | m1 manchete "ACHADINHO / MENTOS UP2U / POR R$ 15 / NA PROMOÇÃO" |
| 4,5–5,9 | "dá uma olhadinha aqui como ele é" | produto | m2 seta à mão "OLHA AQUI" no pote |
| 8,9–12,0 | "por apenas 15 reais. Na promoção" | oferta | m3 infográfico R$ 15 + m4 carimbo PROMOÇÃO |
| 14,9–16,9 | "dois sabores, menta e tutti-frutti" | lista | m6 checklist marcando na fala |
| 15,9–17,4 | (fim) | CTA | m7 botão TOQUE NO CARRINHO (CTA único) |

## Conflitos resolvidos
- Preço no gancho e de novo em 8,9 s → mantidos (antecipação × confirmação).
- QA sugeriu botão em y=1520 (fora da zona segura) → diretor usou y=1400.

## QA
- v16 reprovada (5 falhas com evidência): texto cortado em m2, "VICIANTE." ilegível e não dito (D01/D05), legenda × CTA,
  botão sobre a boca, checklist fora da fala.
- v17 aprovada; alerta aceito: base do botão ~18 px abaixo do limite de 1470 px.

## Defeitos do editor encontrados pelo fluxo (corrigidos com teste)
1. `--motion` com id implícito (`m2`) duplicava em vez de substituir.
2. Animação adiada pela regra de topo perdia o sincronismo dos itens internos.
3. Âncora escrita com a grafia do ASR ("toutifrut") era ignorada em silêncio depois da correção de palavra.
4. `--patch-clear` junto com `--patch-remove` do mesmo id apagava o próprio remove.

## Custo (Smart Revision Engine)
v16 (prévia): 8 refeitos / 17 cache · v17 (correções): 7 / 18 · v18 (final): 5 trechos / 20 cache.

## Gaps
Nenhuma ação pedida ficou sem executor nesta rodada.
