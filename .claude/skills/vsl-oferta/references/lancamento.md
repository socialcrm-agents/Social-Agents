# Etapas 10 e 11 — Lançamento e otimização

## Calendário (14 dias, ~2 h por dia)

| Dia | Tarefa |
|-----|--------|
| 1 | Diagnóstico, público e oferta fechados |
| 2–3 | Roteiro da VSL escrito, lido em voz alta e ajustado |
| 4 | Página (rascunho), checkout criado, order bump, página de obrigado |
| 5 | Gravação por blocos + tomadas de apoio |
| 6 | Edição, hospedagem do vídeo, página final com o minuto da oferta certo |
| 7–8 | Gravar e editar 10 criativos |
| 9 | Pixel/eventos, teste de compra, campanhas no ar |
| 10–14 | Ler métricas todo dia às 10h, ajustar uma coisa por vez |

No Claude Code: `python3 scripts/calendario.py <slug> --inicio AAAA-MM-DD` gera `calendario.md` e `calendario.ics`
(importe no Google Agenda: Configurações → Importar). Fora dele, entregue a tabela com caixinhas e as datas reais.

## Antes de ligar o tráfego (checklist)

- Compra de teste feita (cupom 100% ou valor mínimo) e acesso chegou.
- Pixel da Meta / TikTok / tag do Google instalados na página e no checkout; eventos: PageView, ViewContent (play),
  InitiateCheckout, Purchase.
- Página abre em 3 s no 4G; vídeo toca no iPhone e no Android.
- Rodapé com dados da empresa, termos e privacidade.

## Os números que importam e as metas iniciais

| Métrica | Como medir | Meta de partida |
|---------|-----------|-----------------|
| CTR do anúncio (link) | gerenciador de anúncios | ≥ 1% |
| Custo por visita à página | gerenciador | depende do nicho; compare entre criativos |
| Play rate | player (Panda/VTurb) ou eventos | ≥ 60% de quem abre a página |
| Retenção em 1 min | player | ≥ 50% |
| Retenção no minuto da oferta | player | ≥ 15–25% |
| Cliques no botão / quem viu a oferta | eventos | ≥ 10% |
| Conversão do checkout | plataforma | ≥ 30–40% de quem inicia |
| Custo por venda (CPA) | gerenciador | ≤ margem por venda (meta: CPA ≤ 50% do preço no início) |

## Otimização — o que mexer primeiro (etapa 11)

Peça para a pessoa colar os números (print ou texto). Ache **o primeiro gargalo do funil** e mexa só nele:

| Sintoma | Onde está o problema | O que fazer |
|---------|---------------------|-------------|
| CTR baixo | criativo | novos ganchos; testar outro ângulo |
| CTR bom, play rate baixo | página/headline | headline igual ao gancho do criativo; aviso de som; página mais leve |
| Muita gente sai no 1º minuto | gancho da VSL | regravar só o gancho (2–3 versões) |
| Cai no meio, antes da oferta | identificação/mecanismo longo | cortar 20–30% do meio; mais ganchos de retenção |
| Chega na oferta, não clica | oferta/preço | stack e bônus mais fortes, ancoragem, garantia, parcela em destaque |
| Clica, não paga | checkout | menos campos, Pix e cartão, parcela visível, order bump não confuso |
| Vende, mas CPA alto | tudo junto | subir ticket (order bump/upsell) antes de baixar preço |

Uma mudança por vez, espere dados suficientes (≥ 1.000 visitas ou 3 dias) antes de concluir. Registre cada teste.

## Saída das etapas

Lançamento: calendário com datas + checklist técnico. Otimização: diagnóstico em 3 linhas (gargalo, por quê, o que
fazer esta semana) + o texto/roteiro novo já escrito.
